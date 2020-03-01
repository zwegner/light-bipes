import logging
import socket

import event_queue
import util

# Do we use the OS APIs to remove fds from the watched set when they receive an event?
ONESHOT = False

# This server is not thread safe! I tried to make it so, but it seems it's not worth the
# effort and complexity right now. The problem is seen while relaying traffic between two sockets:
# either socket can get an error/EOF at any time, and we want to quickly shut down the other
# socket.
#
# We can't just call close() on the socket, because a different thread could be operating
# on it. And even if we caught errors that resulted from using stale fds, we couldn't deal with
# the case of a new socket being opened with the same fd, which would cause some serious
# correctness issues (data being read from/written to the wrong socket).
#
# The next potential solution would be calling shutdown() instead of close() on the other
# socket whenever a socket gets an error. That would solve correctness issues, and would
# ensure that both sockets are flushed out of the kqueue/epoll watched set. But we still need
# to close the sockets eventually, preferrably as soon as possible. Implementing this efficiently
# would involve a per-socket-pair reference count, that starts at two for each tunnel. When a
# thread gets an error/EOF on a socket, it atomically decrements the count. If the count goes to
# one, the other socket might still be active, so call shutdown on it. If the count goes to zero,
# the other socket is already shut down (or is about to be shut down), so we can close both
# sockets safely.
#
# This whole problem could be avoided if the kqueue/epoll APIs were designed a little better,
# and provided a way to atomically remove a file descriptor from the set being watched, and
# let the calling thread know whether the fd was in the set or not. When combined with one-shot
# events, we could use this to reliably detect whether another thread might be operating on
# a socket. If the fd was in the watched set, we can call close() on it and be fine, otherwise,
# we call shutdown() on it, and the other thread will deal with its closure (potentially needing
# to run through another iteration of the add-to-watch-set and poll loop).
#
# In fact, there was a Linux kernel change to provide exactly this API, but it seems it never
# made it to the mainline: https://lwn.net/Articles/520012/
#
# More references for people hitting this same problem:
# https://stackoverflow.com/questions/28764101/epoll-kqueue-user-specified-pointer-how-to-safely-deallocate-it-in-a-multithr
# https://stackoverflow.com/questions/13808346/safe-way-to-handle-closure-of-sockets-managed-by-epoll
#
# So anyways, in the end this is a Python program, hence pretty much limited to a single thread
# anyways, and should be I/O bound rather than CPU bound. So for now I'm just punting on the
# issue and staying single threaded.

class LightBipes:
    BUF_SIZE = 4096

    def __init__(self):
        self.event_queue = event_queue.EventQueue()
        self.socket_src = {}
        self.socket_dest = {}
        self.socket_address = {}

    def listen(self, host, port):
        self.listen_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.listen_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
        self.listen_sock.bind((host, port))
        self.listen_sock.listen()

        self.event_queue.register(self.listen_sock)

    def connect_one(self, src, dest):
        connection = (src, dest)
        self.socket_src[dest.fileno()] = connection
        self.socket_dest[src.fileno()] = connection
        self.event_queue.register(src, oneshot=ONESHOT)

    def connect(self, src, src_address, dest, dest_address):
        logging.info('Connecting %s:%s to %s:%s', src.fileno(), src_address, dest.fileno(), dest_address)
        self.socket_address[src] = src_address
        self.socket_address[dest] = dest_address
        self.connect_one(src, dest)
        self.connect_one(dest, src)

    def disconnect_one(self, src, dest):
        del self.socket_dest[src.fileno()]
        if not ONESHOT:
            try:
                self.event_queue.unregister(src)
            except OSError:
                pass

    def disconnect(self, src, dest):
        logging.info('Disconnecting %s:%s from %s:%s', src.fileno(), self.socket_address[src], dest.fileno(), self.socket_address[dest])
        del self.socket_address[src]
        del self.socket_address[dest]
        self.disconnect_one(src, dest)
        self.disconnect_one(dest, src)
        src.close()
        dest.close()

    def accept(self):
        (src, src_address) = self.listen_sock.accept()

        # Confirm protocol
        version = util.recv(src, 4)
        assert version == b'zlbs', version

        # Receive destination address
        domain = util.recv_str(src).decode('ascii')
        port = util.recv(src, '!H')
        dest_address = (domain, port)

        # Connect to the desired domain/port
        dest = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        dest.connect(dest_address)

        # Bi-directionally connect the client socket and the destination socket
        # so we can mirror traffic back and forth
        self.connect(src, src_address, dest, dest_address)

    def run_event_loop(self):
        # File descriptor to re-register when waiting
        register_fd = None
        while True:
            event = self.event_queue.wait(register_fd=register_fd, oneshot=ONESHOT)
            register_fd = None
            if not event:
                logging.error('No events, exiting.')
                break
            src_fd, event_type = event

            # New connection available, accept it
            if src_fd == self.listen_sock.fileno():
                self.accept()
            else:
                # Otherwise, we got an event on a tunneled socket
                assert src_fd in self.socket_dest
                src, dest = self.socket_dest[src_fd]

                # Error, disconnect
                if event_type == event_queue.ERROR:
                    self.disconnect(src, dest)
                else:
                    buf = util.recv(src, self.BUF_SIZE)
                    # Error, disconnect
                    if not buf:
                        self.disconnect(src, dest)
                    # XXX buffer if not writeable? take read fd out of poll set?
                    elif not util.send(dest, buf):
                        self.disconnect(src, dest)
                    # Re-register this file descriptor
                    elif ONESHOT:
                        register_fd = src_fd

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    server = LightBipes()
    server.listen('127.0.0.1', 5050)
    server.run_event_loop()
