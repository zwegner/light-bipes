import logging
import select
import socket

import util

SOCKET_DEST = {}
SOCKET_ADDRESS = {}

KQUEUE = select.kqueue()

READ_FLAGS = select.KQ_FILTER_READ# | select.KQ_FILTER_EXCEPT

def listen(host, port):
    global LISTEN_SOCK
    LISTEN_SOCK = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    LISTEN_SOCK.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
    LISTEN_SOCK.bind((host, port))
    LISTEN_SOCK.listen()
    event = select.kevent(LISTEN_SOCK, READ_FLAGS, select.KQ_EV_ADD)
    KQUEUE.control([event], 0)

def connect_one(src, dest):
    SOCKET_DEST[src.fileno()] = (src, dest)
    # XXX oneshot
    event = select.kevent(src, READ_FLAGS, select.KQ_EV_ADD)
    KQUEUE.control([event], 0)

def disconnect_one(src, dest):
    del SOCKET_DEST[src.fileno()]
    event = select.kevent(src, READ_FLAGS, select.KQ_EV_DELETE)
    KQUEUE.control([event], 0)

def connect(src, src_address, dest, dest_address):
    logging.info('Connecting %s to %s', src_address, dest_address)
    SOCKET_ADDRESS[src] = src_address
    SOCKET_ADDRESS[dest] = dest_address
    connect_one(src, dest)
    connect_one(dest, src)

def disconnect(src, dest):
    logging.info('Disconnecting %s from %s', SOCKET_ADDRESS[src], SOCKET_ADDRESS[dest])
    del SOCKET_ADDRESS[src]
    del SOCKET_ADDRESS[dest]
    disconnect_one(src, dest)
    disconnect_one(dest, src)
    src.close()
    dest.close()

def accept():
    (src, src_address) = LISTEN_SOCK.accept()

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
    connect(src, src_address, dest, dest_address)

def run_event_loop():
    while True:
        events = KQUEUE.control(None, 1)
        if not events:
            logging.error('No events, exiting.')
            break
        assert len(events) == 1
        event = events[0]

        src_fd = event.ident

        # New connection available, accept it
        if src_fd == LISTEN_SOCK.fileno():
            accept()
        else:
            # Otherwise, we got an event on a tunneled socket
            assert src_fd in SOCKET_DEST
            src, dest = SOCKET_DEST[src_fd]

            # Error, disconnect
            if event.flags & (select.KQ_EV_ERROR | select.KQ_EV_EOF):
                disconnect(src, dest)
            else:
                buf = util.recv(src, 1024)
                # Error, disconnect
                if not buf:
                    disconnect(src, dest)
                util.send(dest, buf)

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    listen('127.0.0.1', 5050)
    run_event_loop()
