# Escuchar como nodo enrutador

import socket
import psutil
import select
import sys

PUERTO_UDP = 5005
PUERTO_TCP = 5006

PREFIJO_ANUNCIO = "ANNOUNCE|"
PREFIJO_PROPAGAR = "ADVERTISE|"
PREFIJO_DATOS = "DATA|"

if len(sys.argv) < 2:
    print("Uso: python escuchar.py <IP_PROPIA> [IP_CONOCIDAS...]")
    sys.exit(1)

IP_PROPIA = sys.argv[1] # La IP propia es para no apuntarnos a nosotros mismo con broadcast
IP_CONOCIDAS = sys.argv[2:] # Esto es pruebas, estas ip hay que pasarlas a la tabla

# Socket UDP
s_udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
s_udp.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
s_udp.bind(("", PUERTO_UDP))

# Socket TCP
s_tcp = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s_tcp.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
s_tcp.bind(("", PUERTO_TCP))
s_tcp.listen(5) # Cola de conexiones entrantes

def reenviar_datos(ip_destino: str, contenido: str):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.connect((ip_destino, PUERTO_TCP))
        msg = f"{PREFIJO_DATOS}{ip_destino}|{contenido}"
        s.sendall(msg.encode())
        print(f"Reenviado a {ip_destino}: {msg}")
    finally:
        s.close()


print(f"Escuchando en UDP {PUERTO_UDP} y TCP {PUERTO_TCP}...\n")

while True:
    # Esperar actividad en cualquiera de los sockets
    readable, _, _ = select.select([s_udp, s_tcp], [], [])

    for sock in readable:
        if sock is s_udp:
            data, remitente = s_udp.recvfrom(1024)
            msg = data.decode(errors="replace")

            if msg.startswith(PREFIJO_ANUNCIO):
                print(f"{remitente[0]:16} -> {msg}")
                # Separar los campos: prefijo, ip_vecino
                _, ip_vecino = msg.split("|", 1) # Esto se podría quitar ya que la ip viene en remitente[0]
                # Aquí hace falta añadir la ip guardada en el campo
                # remitente a la tabla de direccionamiento y programar la propagación 

        elif sock is s_tcp:
            conn, remitente = s_tcp.accept()
            data = conn.recv(1024)
            msg = data.decode(errors="replace")

            if msg.startswith(PREFIJO_PROPAGAR):
                print(f"{remitente[0]:16} -> {msg}")
            elif msg.startswith(PREFIJO_DATOS):
                print(f"{remitente[0]:16} -> {msg}")
                try:
                    # Separar los campos: prefijo, ip_destino, contenido
                    _, ip_destino, contenido = msg.split("|", 2)
                    
                    if ip_destino in IP_CONOCIDAS: # Esto es solo el check de prueba, cambiar por la ip traída de la tabla
                        reenviar_datos(ip_destino, contenido)

                except ValueError:
                    print("Formato inválido en DATA")

            conn.close()
