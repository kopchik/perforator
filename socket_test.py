from socket import socketpair, SOL_SOCKET, SO_SNDBUF
MAXSIZE = 1000000
s1, s2 = socketpair()
s1.setsockopt(SOL_SOCKET, SO_SNDBUF, MAXSIZE*3)
print(s1.getsockopt(SOL_SOCKET, SO_SNDBUF))
data = b" " * MAXSIZE
print(len(data))
size = s1.send(data)
assert len(data) == size
data2 = s2.recv()
assert data2 == data
