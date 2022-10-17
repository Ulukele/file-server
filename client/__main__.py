import socket
import os
import sys
import hashlib
from argparse import ArgumentParser

MAX_FILENAME_SIZE = 4096


def send_file(file_path: str, sock: socket.socket):

    file_size = os.path.getsize(file_path)
    filename = os.path.basename(file_path)

    if len(filename) > MAX_FILENAME_SIZE:
        print('Specified file has too long name')
        return

    size_bytes = file_size.to_bytes(8, sys.byteorder)
    filename_size_bytes = len(filename).to_bytes(4, sys.byteorder)
    filename_bytes = bytes(filename, 'utf-8') + bytes(MAX_FILENAME_SIZE - len(filename))

    # Send file info (MAX_FILENAME_SIZE + 12 bytes)
    sock.send(size_bytes + filename_size_bytes + filename_bytes)

    md5 = hashlib.md5()
    with open(file_path, 'rb') as f:
        while True:
            batch = f.read(1024)
            if len(batch) <= 0:
                break
            md5.update(batch)
            sock.send(batch)

    checksum = bytes(md5.hexdigest(), 'utf-8')
    sock.send(checksum)


def main():
    parser = ArgumentParser()
    parser.add_argument("-p", "--port", type=int, default=8081, help="port send to")
    parser.add_argument("--host", default='', help="hostname send to")
    parser.add_argument("-f", "--file", dest="filename", help="FILE send to", metavar="FILE")

    args_values = parser.parse_args()
    port = args_values.port
    host = args_values.host
    filename = args_values.filename

    print(f'Sending file: {filename} to: {host}:{port}')

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.connect((host, port))
    except ConnectionRefusedError as e:
        print("Unable to connect: " + e.strerror)
        return

    try:
        send_file(filename, sock)
    except KeyboardInterrupt:
        print('Sending interrupted')
    finally:
        sock.close()
        print('Program finished')


if __name__ == '__main__':
    main()
