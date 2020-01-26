import socket
import threading
import time
import queue

server_ip = ...
server_port = 50001
server_addr = (server_ip, server_port)

local_port = 1234

room = b"A"

with socket.socket() as s:
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    print(f"Requesting room {room} on {server_addr} with local port {local_port}...")
    s.bind(('', local_port))
    s.connect(server_addr)
    s.send(room)

    resp = s.recv(1024)
    resp = resp.decode().split(":")
    remote_addr = (resp[0], int(resp[1]))
    print(f"Received forward to {remote_addr}")


running = [True]


def connect():
    with socket.socket() as connecting:
        connecting.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        connecting.bind(('', local_port))
        connecting.settimeout(5)

        while running[0]:
            try:
                print("Attempting to connect...")
                connecting.connect(remote_addr)
                break
            except (socket.timeout, ConnectionRefusedError) as ex:
                print("Failed to connect")
                time.sleep(1)

        q.put(connecting)


def listen():
    with socket.socket() as listening:
        listening.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        listening.bind(('', local_port))
        listening.settimeout(5)
        listening.listen(1)

        while running[0]:
            try:
                print("Listening for incoming connections...")
                connection = listening.accept()
                q.put(connection)
                break
            except socket.timeout as ex:
                print("Found no incoming connections")


thread_listen = threading.Thread(target=listen)
thread_connect = threading.Thread(target=connect)

q = queue.Queue()
print("Starting connecting and listening threads...")
thread_listen.start()
thread_connect.start()

conn = q.get()
print("Established connection")
running[0] = False
print("Waiting for threads to exit...")
thread_listen.join()
thread_connect.join()
