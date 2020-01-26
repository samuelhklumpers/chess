import socket
import select
import threading

server_port = 50002

print(f"Opening server on {server_port}...")
s = socket.socket()
s.bind(('', server_port))  # port forward this
s.listen(128)

print("Opened server")

rooms = {"proxy": {}, "punch": {}}


def mainloop():
    while True:
        print("Waiting for requests...")
        c1, a1 = s.accept()
        print(f"Incoming connection from {a1}")

        prot, room = c1.recv(1024).decode().split(",")

        print("Received subscription")
        process((c1, a1), prot, room)


def punch(addr1, addr2):
    c1, a1 = addr1
    c2, a2 = addr2

    c2.send(f"{a1[0]}:{a1[1]}".encode())
    c1.send(f"{a2[0]}:{a2[1]}".encode())

    c1.close()
    c2.close()


def proxy(addr1, addr2):
    c1, a1 = addr1
    c2, a2 = addr2

    with c1, c2:
        while True:
            r, _, _ = select.select([c1, c2], [], [])
            r = r[0]

            msg = c1.recv(1024) if r == c1 else c2.recv(1024)

            if not msg:
                break

            if r == c1:
                c2.send(msg)
            else:
                c1.send(msg)


def process(addr1, prot, room):
    c1, a1 = addr1

    if prot not in rooms:
        print(f"Invalid protocol {prot}, ignoring")
        c1.close()
        return

    print(f"Client wants to connect to room {room} with protocol {prot}")

    prot_room = rooms[prot]
    if room in prot_room:
        print("Room was open")
        addr2 = prot_room[room]

        if prot == "proxy":
            proxy_thread = threading.Thread(target=lambda: proxy(addr1, addr2))
            proxy_thread.start()

            print("Starting proxy thread. Closed room")
            del prot_room[room]
        else:
            punch(addr1, addr2)
            print("Forwarded clients. Closed room")
            del prot_room[room]
    else:
        prot_room[room] = addr1
        print("Opened room")


mainloop()
