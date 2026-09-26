# Broadcast de mi existencia

import socket
import time

PUERTO = 5005
GRUPO = "10.1.35.21"        # <-- pongan el suyo

DESTINO = "192.168.100.255" # Esto hay que cambiarlo por la dirección de broadcast de la pi

s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

while True:
  msg = f"ANNOUNCE|{GRUPO}"

  s.sendto(msg.encode(), (DESTINO, PUERTO))

  print("enviado:", msg)
  time.sleep(30)
