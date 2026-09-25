# Recibir mensajes de la pi

import socket
import psutil

PUERTO_TCP = 5005

PREFIJO_DATOS = "DATA|"

# Socket TCP
s_tcp = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s_tcp.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
s_tcp.bind(("", PUERTO_TCP))
s_tcp.listen(5) # Cola de conexiones entrantes

print(f"Escuchando en TCP {PUERTO_TCP}...\n")

while True:

  conn, addr = s_tcp.accept()
  data = conn.recv(1024)
  msg = data.decode(errors="replace")

  if msg.startswith(PREFIJO_DATOS):
      print(f"{addr[0]:16} -> {msg}")

  conn.close()
