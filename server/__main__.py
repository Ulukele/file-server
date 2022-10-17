import asyncio
import socket
import sys
import time
from pathlib import Path
import hashlib
from typing import Any, List
from argparse import ArgumentParser

LOG_TIME = 3
TIMEOUT = 5  # in seconds

MAX_FILENAME_SIZE = 4096
UPLOADS_FOLDER_PATH = Path(__file__).parent.joinpath('uploads')


class Client:
    __idx: int
    __sock: socket.socket = None
    __task: Any = None

    __recv_count: int = 0
    __start: float

    __last_seen: float
    __instant_speed: float = 0
    __average_speed: float = 0

    __finished: bool = False

    def __init__(self, idx: int, sock: socket.socket):
        self.__idx = idx
        self.__start = time.time()
        self.__last_seen = time.time()
        self.__sock = sock

    def get_idx(self) -> int:
        return self.__idx

    def update_last_seen(self):
        self.__last_seen = time.time()

    def increase_recv_count(self, value):

        now = time.time()

        # Calculate instant speed
        self.__instant_speed = (value / (now - self.__last_seen))
        self.__last_seen = now

        # Calculate average speed
        self.__recv_count += value
        self.__average_speed = (self.__recv_count / (now - self.__start))

    def get_last_seen(self) -> float:
        return self.__last_seen

    def check_finished(self) -> bool:
        return self.__finished

    def finish(self):
        print(f'Client {self.__idx} finished')
        self.__finished = True
        self.print_speed()

    def print_speed(self):
        client_idx = self.get_idx()
        print(f'Client {client_idx} Average speed: {int(self.__average_speed)} bytes per sec')
        print(f'Client {client_idx} Instant speed: {int(self.__instant_speed)} bytes per sec')

    async def receive_async(self, size, loop):
        try:
            data = await asyncio.wait_for(loop.sock_recv(self.__sock, size), TIMEOUT)
        except asyncio.TimeoutError:
            self.kill_connection()
            return None

        if len(data) == 0:
            self.kill_connection()
            return None

        return data

    async def handle_client_connection(self):
        loop = asyncio.get_event_loop()

        # Receive info about file
        file_info = await self.receive_async(MAX_FILENAME_SIZE + 12, loop)
        if file_info is None:
            return

        # Parse info about file
        file_size = int.from_bytes(file_info[:8], sys.byteorder)
        filename_size = int.from_bytes(file_info[8:12], sys.byteorder)
        filename = file_info[12:12 + filename_size].decode('utf-8')

        # Start receiving file
        received = 0
        md5 = hashlib.md5()
        with open(UPLOADS_FOLDER_PATH.joinpath(filename), 'wb') as f:
            while received < file_size:
                self.update_last_seen()

                # Receive data from socket with timeout
                batch = await self.receive_async(1024, loop)
                if batch is None:
                    return
                batch_len = len(batch)

                received += batch_len
                self.increase_recv_count(batch_len)

                md5.update(batch)
                f.write(batch)

        # Check that file transferred correct
        checksum = bytes(md5.hexdigest(), 'utf-8')
        client_checksum = await self.receive_async(32, loop)
        if client_checksum is None:
            return

        if checksum != client_checksum:
            print(f'Client {self.__idx} checksum invalid!')
        else:
            print(f'Client {self.__idx} checksum correct')

        self.kill_connection()

    def kill_connection(self):
        self.__sock.close()
        self.finish()


async def client_watcher_loop(clients: List[Client]):

    while True:
        await asyncio.sleep(LOG_TIME)

        clients_to_remove = []
        for client in clients:
            if client.check_finished():
                clients_to_remove.append(client)
                continue
            client.print_speed()

        for client in clients_to_remove:
            clients.remove(client)


def print_canceled_clients(canceled_clients):
    print('\nCanceled clients:')
    for client in canceled_clients:
        print(f'- Client {client.get_idx()}')
    print(f'Total: {len(canceled_clients)} clients canceled\n')


async def start_server(host: str, port: int, clients: List[Client]):
    print(f'Start listening on {host}:{port}')

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind((host, port))
    sock.listen()
    sock.setblocking(False)

    last_client_idx = 0

    loop = asyncio.get_event_loop()
    loop.create_task(client_watcher_loop(clients))
    while True:
        client_sock, _ = await loop.sock_accept(sock)

        client = Client(last_client_idx, client_sock)
        clients.append(client)
        last_client_idx += 1

        loop.create_task(client.handle_client_connection())


def main():
    parser = ArgumentParser()
    parser.add_argument("-p", "--port", type=int, default=8081, help="port listen to")
    parser.add_argument("--host", default='', help="hostname listen to")

    args_values = parser.parse_args()
    port = args_values.port
    host = args_values.host

    clients = []

    try:
        asyncio.run(start_server(host, port, clients))
    except KeyboardInterrupt:
        print_canceled_clients(clients)
    finally:
        print('Server closed')


if __name__ == '__main__':
    main()
