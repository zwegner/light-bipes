import select
import socket
import sys

import util

PROXY = ('localhost', 5050)

dest_host = sys.argv[1]
dest_port = int(sys.argv[2])

with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as proxy:
    proxy.connect(PROXY)
    util.send(proxy, b'zlbs')
    util.send_str(proxy, dest_host.encode('ascii'))
    util.send(proxy, '!H', dest_port)

    src = (sys.stdin, sys.stdout)
    util.bipe(src, proxy)
