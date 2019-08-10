import os
import select
import struct

def recv(conn, fmt):
    if isinstance(fmt, int):
        return conn.recv(fmt)
    size = struct.calcsize(fmt)
    result = struct.unpack(fmt, conn.recv(size))
    if len(result) == 1:
        return result[0]
    return result

def recv_str(conn):
    length = conn.recv(1)[0]
    return conn.recv(length)

def send(conn, fmt, *args):
    if not args:
        conn.sendall(fmt)
        return
    buf = struct.pack(fmt, *args)
    conn.sendall(buf)

def send_str(conn, buf):
    assert len(buf) < 256
    send(conn, 'B', len(buf))
    conn.sendall(buf)

def bipe(src, dest):
    if isinstance(src, tuple):
        src_in, src_out = src
    else:
        src_in = src_out = src

    if isinstance(dest, tuple):
        dest_in, dest_out = dest
    else:
        dest_in = dest_out = dest

    # Meh
    (src_in, src_out, dest_in, dest_out) = [f.fileno() for f in
            (src_in, src_out, dest_in, dest_out)]

    while True:
        (rready, _, _) = select.select([src_in, dest_in], [], [])
        if src_in in rready:
            buf = os.read(src_in, 1024)
            if buf and os.write(dest_out, buf) <= 0:
                return False
        if dest_in in rready:
            buf = os.read(dest_in, 1024)
            if buf and os.write(src_out, buf) <= 0:
                return False
