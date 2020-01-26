import socket
import time
import threading
import queue

local_port = 1234


def transit(mode, server, port, room):
    if mode not in ["punch", "proxy"]:
        return None

    s = socket.socket()
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    print(f"Requesting room {room} on {server}:{port} with local port {local_port}...")

    s.bind(('', local_port))
    s.connect((server, port))
    s.send((mode + room).encode())

    if mode == "punch":
        ip, port = s.recv(1024).decode().split(":")
        port = int(port)

        addr = (ip, port)
        print(f"Received forward to {addr}")

        c = punch(addr)
        s.close()

        return c
    else:
        return s


def punch(addr):
    q = queue.Queue()
    running = [True]

    thread_listen = threading.Thread(target=lambda: listen(running, q))
    thread_connect = threading.Thread(target=lambda: connect(addr, running, q))

    print("Starting connecting and listening threads...")
    thread_listen.start()
    thread_connect.start()

    conn = q.get()
    print("Established connection")
    running[0] = False
    print("Waiting for threads to exit...")
    thread_listen.join()
    thread_connect.join()

    return conn


def connect(addr, running, q):
    with socket.socket() as connecting:
        connecting.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        connecting.bind(('', local_port))
        connecting.settimeout(5)

        while running[0]:
            try:
                print("Attempting to connect...")
                connecting.connect(addr)
                q.put(connecting)
                break
            except (socket.timeout, ConnectionRefusedError) as ex:
                print("Failed to connect")
                time.sleep(1)


def listen(running, q):
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
