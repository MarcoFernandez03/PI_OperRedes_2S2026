# Broadcast de mi existencia

import socket
import time

PUERTO = 5005
GRUPO = "10.1.35.23"        # <-- pongan el suyo

# TODO 1: averiguar su dirección de broadcast.
#   Corran el script de interfaces, tomen su IP
#   y su mascara. cuál es la dirección de broadcast
#   de SU subred. Escriban en un comentario cómo la obtuvieron.
#   Con ayuda del script interfaces.py se miró la ip privada correspondiente
#   a la maquina y se tomó su dirección broadcast
DESTINO = "192.168.100.255" # Esto hay que cambiarlo por la dirección de broadcast de la pi

# TODO 2: crear el socket (igual que en el listener).
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

# TODO 3: el programa va a fallar con PermissionError: [Errno 13].
#   Corran primero SIN esta línea para verlo.
#   Luego averigüen qué opción de socket hay que activar y agréguenla.
#   ¿por qué el sistema operativo lo prohíbe
#   por defecto? ¿Qué pasaría si cualquier proceso pudiera hacerlo?
#   Por seguridad y protección de la red haciendo al desarrollador responsable
#   de lo que implica el envio, si no se controla es posible que la red se abusar de los envios.
s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

for i in range(3):
  # TODO 4: armar el mensaje.
  #   Mínimo debe permitir que quien lo reciba sepa QUIÉN lo envió.
  msg = f"ANNOUNCE|{GRUPO}"

  # TODO 5: enviarlo.
  #   El método de envío para datagramas necesita DOS argumentos.
  #   Ojo: uno de ellos no es un string.
  s.sendto(msg.encode(), (DESTINO, PUERTO))

  print("enviado:", msg)
  time.sleep(3)
