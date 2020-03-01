import contextlib
import select
import socket
import sys

import util

PROXY = ('localhost', 5050)

@contextlib.contextmanager
def open_proxy(dest_host, dest_port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as proxy:
        proxy.connect(PROXY)
        util.send(proxy, b'zlbs')
        util.send_str(proxy, dest_host.encode('ascii'))
        util.send(proxy, '!H', dest_port)

        yield proxy

if __name__ == '__main__':
    dest_host = sys.argv[1]
    dest_port = int(sys.argv[2])
    with open_proxy(dest_host, dest_port) as proxy:
        src = (sys.stdin, sys.stdout)
        util.bipe(src, proxy)
