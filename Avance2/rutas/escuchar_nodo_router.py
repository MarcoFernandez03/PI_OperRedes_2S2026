# Escuchar como nodo enrutador

import socket
import psutil
import select
import sys

from tabla_rutas import TablaRutas
from logica_rutas import procesar_announce, procesar_advertise, procesar_data


PUERTO_UDP = 5005
PUERTO_TCP = 5005
PUERTO_TCP_LOCAL = 5006

PREFIJO_ANUNCIO = "ANNOUNCE|"
PREFIJO_PROPAGAR = "ADVERTISE|"
PREFIJO_DATOS = "DATA|"

if len(sys.argv) < 2:
    print("Uso: python escuchar_nodo_router.py <IP_PROPIA> [IPS_LOCALES...]")
    sys.exit(1)

IP_PROPIA = sys.argv[1] # La IP propia es para no apuntarnos a nosotros mismo con broadcast
IPS_LOCALES = sys.argv[2:]
IP_VECINOS = {} # Tenemos que popular esta tabla con que interfaz le pertenece a cada vecino, para poder reenviar por la interfaz que toca

# Tabla de rutas respaldada por la memoria virtual (TLB + tabla de páginas + memoria física)
tabla = TablaRutas()


# Socket UDP
s_udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
s_udp.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
s_udp.bind(("", PUERTO_UDP))

# Socket TCP
s_tcp = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s_tcp.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
s_tcp.bind(("", PUERTO_TCP))
s_tcp.listen(30) # Cola de conexiones entrantes

# Socket TCP local
s_tcp_local = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s_tcp_local.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
s_tcp_local.bind(("", PUERTO_TCP_LOCAL))
s_tcp_local.listen(5) # Cola de conexiones entrantes

# Esto se usa para conseguir al router al que 
# hay que darle el paquete enviar al ser dueño de la interfaz
def get_ip_vecino(interfaz: str) -> str:
    for ip, interfaces in IP_VECINOS.items():
        if interfaces == interfaz:
            return ip
    return None

def reenviar_datos(ip_destino: str, contenido: str):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.connect((ip_destino, PUERTO_TCP_LOCAL))
        msg = f"{PREFIJO_DATOS}{ip_destino}|{contenido}"
        s.sendall(msg.encode())
        print(f"Reenviado a {ip_destino}: {msg}")
    except OSError as e:
        print(f"No se pudo reenviar a {ip_destino}: {e}")
    finally:
        s.close()

def propagar_advertise(ip_a_propagar: str, ip_excluir: str):
    """Envía ADVERTISE|ip_a_propagar por TCP unicast a todos los vecinos
    conocidos, excepto a quien nos la mandó (para no devolvérsela)."""
    mensaje = f"{PREFIJO_PROPAGAR}{ip_a_propagar}"
    for ip_vecino in IP_VECINOS:
        if ip_vecino == ip_excluir:
            continue
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            s.connect((ip_vecino, PUERTO_TCP))
            s.sendall(mensaje.encode())
            print(f"Propagado a {ip_vecino}: {mensaje}")
        except OSError as e:
            print(f"No se pudo propagar a {ip_vecino}: {e}")
        finally:
            s.close()

def enviar_tabla(ip_vecino: str):
    """Envía por TCP unicast un ADVERTISE por cada ruta conocida a un
    vecino recién descubierto, para que aprenda toda la tabla."""
    # Anunciar todas las IP locales
    for ip_local in IPS_LOCALES:
        mensaje = f"{PREFIJO_PROPAGAR}{ip_local}"
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            s.connect((ip_vecino, PUERTO_TCP))
            s.sendall(mensaje.encode())
            print(f"IP local enviada a {ip_vecino}: {mensaje}")
        finally:
            s.close()



def transportar_datos(ip_siguiente_salto: str, ip_destino_final: str, contenido: str):
    """
    Envía un fragmento DATA al siguiente salto (no necesariamente al
    destino final; puede ser un router intermedio). El mensaje conserva
    el destino final para que, si el siguiente salto no es el destino,
    lo siga reenviando.
 
    NOTA: por ahora usa TCP simple, igual que ADVERTISE, para poder
    probar el enrutamiento primero. Cuando se migre al transporte
    confiable de la Etapa 1 (UDP + syscall del kernel), solo hay que
    cambiar el cuerpo de esta función — la firma y quién la llama no
    cambian.
    """
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.connect((ip_siguiente_salto, PUERTO_TCP))
        msg = f"{PREFIJO_DATOS}{ip_destino_final}|{contenido}"
        s.sendall(msg.encode())
        print(f"Reenviado a {ip_siguiente_salto} (destino final {ip_destino_final}): {msg}")
    except OSError as e:
        print(f"No se pudo reenviar a {ip_siguiente_salto}: {e}")
        IP_VECINOS[ip_siguiente_salto] = 0 # Marcar que el nodo calló
    finally:
        s.close()
 
 
print(f"Escuchando en UDP {PUERTO_UDP} y TCP {PUERTO_TCP}...\n")
 
while True:
    # Esperar actividad en cualquiera de los sockets
    readable, _, _ = select.select([s_udp, s_tcp, s_tcp_local], [], [])
 
    for sock in readable:
        if sock is s_udp:
            data, remitente = s_udp.recvfrom(1024)
            msg = data.decode(errors="replace")
 
            if msg.startswith(PREFIJO_ANUNCIO) and remitente[0] != IP_PROPIA:
                print(f"{remitente[0]:16} -> {msg}")
                if remitente[0] not in IP_VECINOS:
                    # Vecino nuevo: se le responde el ANNOUNCE (descubrimiento mutuo)
                    s_udp.sendto(f"{PREFIJO_ANUNCIO}{IP_PROPIA}".encode(), (remitente[0], PUERTO_UDP))
                    enviar_tabla(remitente[0])
                    IP_VECINOS[remitente[0]] = 1 # Guardar el vecino y marcar que enviamos su ANNOUNCE
                elif remitente[0] in IP_VECINOS:
                    if IP_VECINOS[remitente[0]] == 0:
                        enviar_tabla(remitente[0])
                        IP_VECINOS[remitente[0]] = 1 # Guardar el vecino y marcar que enviamos su ANNOUNCE
                    
                # La IP real del vecino es remitente[0] (el campo del mensaje
                # no hace falta para esto: lo da el socket, no el payload).
                # POSIBLE BORRAR
                ip_a_propagar = procesar_announce(remitente[0], IP_PROPIA, tabla)
                #if ip_a_propagar is not None:
                    #print(f"Nueva ruta directa: {ip_a_propagar} (vecino)")
                    #propagar_advertise(ip_a_propagar, ip_excluir=ip_a_propagar)
                # POSIBLE BORRAR
 
        elif sock is s_tcp or sock is s_tcp_local:
            conn, remitente = sock.accept()
            data = conn.recv(1024)
            msg = data.decode(errors="replace")
 
            if msg.startswith(PREFIJO_PROPAGAR):
                print(f"{remitente[0]:16} -> {msg}")
                #ip_a_repropagar = procesar_advertise(msg, remitente[0], IP_PROPIA, tabla)
                #if ip_a_repropagar is not None:
                   # print(f"Nueva ruta vía {remitente[0]}: {ip_a_repropagar}")
                procesar_advertise(msg, remitente[0], IP_PROPIA, tabla)
 
            elif msg.startswith(PREFIJO_DATOS):
                print(f"{remitente[0]:16} -> {msg}")
 
                resultado = procesar_data(msg, IPS_LOCALES, tabla)
 
                if resultado[0] == "local":
                    _, ip_destino, contenido = resultado
                    reenviar_datos(ip_destino, contenido)
                    print(f"Datos entregados localmente: {contenido}")
 
                elif resultado[0] == "reenviar":
                    _, ip_siguiente_salto, ip_destino, contenido = resultado
                    transportar_datos(ip_siguiente_salto, ip_destino, contenido)
 
                elif resultado[0] == "sin_ruta":
                    _, ip_destino = resultado
                    print(f"Sin ruta conocida hacia {ip_destino}, se descarta")
 
                elif resultado[0] == "formato_invalido":
                    print("Formato inválido en DATA")
 
            conn.close()
