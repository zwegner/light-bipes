import logging
import select
import socket
from socketserver import ThreadingMixIn, TCPServer, StreamRequestHandler

import util

class LightBipes(StreamRequestHandler):
    def recv(self, fmt):
        return util.recv(self.connection, fmt)

    def recv_str(self):
        return util.recv_str(self.connection)

    def send(self, fmt, *args):
        return util.send(self.connection, fmt, *args)

    def send_str(self, buf):
        return util.send(self.connection, buf)

    def handle(self):
        logging.info('New connection: %s' % (self.client_address,))

        version = self.recv(4)
        assert version == b'zlbs', version

        domain = self.recv_str().decode('ascii')
        port = self.recv('!H')

        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as dest:
            dest.connect((domain, port))
            util.bipe(self.connection, dest)

class ThreadingTCPServer(ThreadingMixIn, TCPServer):
    allow_reuse_address = True

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    with ThreadingTCPServer(('127.0.0.1', 5050), LightBipes) as server:
        server.serve_forever()
