import random
import socket
import threading
import time

ROUTER_PORT_TCP = 9000
ROUTER_IP = "192.168.100.153" #CAMBIAR por la IP del router al que se quiere conectar

ROUTER_ANNOUNCE_PREFIX = "HELLO|"
ROUTER_RESPONSE_PREFIX = "HELLO_OK|"
ROUTER_COMMAND_RESPONSE_PREFIX = "OK|"
VERSION_PREFIX = "VERSION|"
LIST_PREFIX = "LIST"
GET_PREFIX = "GET|"
CERT_PREFIX = "CERT|"
ROA_PREFIX = "ROA|"

LOCAL_ROAS = []
LOCAL_ROAS_BUFFER = []
ROA_VERSION = 0
ROAS_UPDATED = False
ROAS_MUTEX = threading.Lock()

#TODO: Añadir la verificación criptografica.

def connect_to_router():
    # Global variables to be used outside
    global ROA_VERSION, LOCAL_ROAS, ROAS_MUTEX
    time.sleep(random.randrange(0, 75))  # Random wait to prevent concurrency
    while True:
      s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
      s.settimeout(10)
      try:
          s.connect((ROUTER_IP, ROUTER_PORT_TCP))
          print(f"Conectado al router en {ROUTER_IP}:{ROUTER_PORT_TCP}")
          # Send router announce message
          s.sendall(f"{ROUTER_ANNOUNCE_PREFIX}ENRUTADOR|1".encode())
          response = s.recv(1024).decode()
          if response.startswith(ROUTER_RESPONSE_PREFIX):
              print(f"Respuesta del router: {response}")
              s.sendall(f"{LIST_PREFIX}".encode())
              # Recieve 4096 bytes to fit roas
              response = s.recv(4096).decode()
              if response.startswith(ROUTER_COMMAND_RESPONSE_PREFIX):
                  message_parts = response.split("|")
                  if int(message_parts[1]) == ROA_VERSION:
                      print(f"ROAs ya están actualizadas (versión {ROA_VERSION})")
                  else:
                    ROAS_UPDATED = True
                    print(f"Lista de ROAs recibida: {response}")
                    # Process the list of ROAs and update LOCAL_ROAS and ROA_VERSION
                    roas = response[len(ROUTER_COMMAND_RESPONSE_PREFIX):].strip().splitlines()
                    LOCAL_ROAS_BUFFER.clear()
                    for roa in roas:
                        if roa.startswith(ROA_PREFIX):
                            LOCAL_ROAS_BUFFER.append(roa)
                    ROA_VERSION = int(message_parts[1])
                    print(f"ROAs actualizadas (versión {ROA_VERSION}): {LOCAL_ROAS_BUFFER}")
          else:
              print(f"Respuesta inesperada del router: {response}")
      except OSError as e:
          print(f"No se pudo conectar al router: {e}")
      finally:
          s.close()


      if ROAS_UPDATED:
          # Create a mutex to update ROAS 
          ROAS_MUTEX.acquire()
          LOCAL_ROAS.clear()
          LOCAL_ROAS.extend(LOCAL_ROAS_BUFFER)
          print("ROAS LOCAL ACTUALIZADAS")
          ROAS_MUTEX.release()

      time.sleep(75);