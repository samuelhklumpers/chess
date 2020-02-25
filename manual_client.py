import socket

local_port = 1234
server_port = 50001
server_ip = "94.210.203.129"

server_addr = (server_ip, server_port)

print("Opening socket...")
s = socket.socket()
s.bind(('', local_port))

print("Connecting to server...")
s.connect(server_addr)
print("Connected")

s.setblocking(False)

while True:
    resp = None
    msg = input()

    s.send(msg.encode())

    try:
        resp = s.recv(1024)
    except:
        ...

    if resp:
        print("Response", resp.decode())

    if msg == "exit":
        break
