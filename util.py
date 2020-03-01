import os
import select
import struct

def recv(conn, fmt):
    try:
        if isinstance(fmt, int):
            return conn.recv(fmt)
        size = struct.calcsize(fmt)
        result = struct.unpack(fmt, conn.recv(size))
        if len(result) == 1:
            return result[0]
        return result
    except Exception:
        return None

def recv_str(conn):
    length = conn.recv(1)
    if length is None:
        return None
    return conn.recv(length[0])

def send(conn, fmt, *args):
    if args:
        buf = struct.pack(fmt, *args)
    else:
        buf = fmt
    try:
        conn.sendall(buf)
        return True
    except Exception:
        return False

def send_str(conn, buf):
    assert len(buf) < 256
    return send(conn, 'B', len(buf)) and send(conn, buf)

def get_read_write_fds(src):
    if not isinstance(src, tuple):
        src = (src, src)
    src_in, src_out = src
    return (src_in.fileno(), src_out.fileno())

# This function kinda sucks. For all that UNIXy stuff about "everything is a file", it's not always
# that simple. Sockets have one fd for both directions, but stdin/stdout are distinct file descriptors.
# Plus the genius Python os.read/os.write APIs only support integer file descriptors, and the socket
# API doesn't have read()/write(). And to top it all off, this function is named "bipe". That's pretty dumb.
def bipe(src, dest):
    src_in, src_out = get_read_write_fds(src)
    dest_in, dest_out = get_read_write_fds(dest)

    while True:
        (rready, _, _) = select.select([src_in, dest_in], [], [])
        if src_in in rready:
            buf = os.read(src_in, 1024)
            if not buf or os.write(dest_out, buf) <= 0:
                return False
        if dest_in in rready:
            buf = os.read(dest_in, 1024)
            if not buf or os.write(src_out, buf) <= 0:
                return False
