
# DEPENDS ON CRYPTOGRAPHY (pip install cryptography)

import base64
import ipaddress
import random
import socket
import threading
import time
from datetime import datetime, timezone

from cryptography import x509
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.x509.oid import NameOID

REPOSITORY_PORT_TCP = 9000
REPOSITORY_IP = "10.1.35.21" #CAMBIAR por la IP del repositorio al que se quiere conectar

REPOSITORY_ANNOUNCE_PREFIX = "HELLO|"
REPOSITORY_RESPONSE_PREFIX = "HELLO_OK|"
REPOSITORY_COMMAND_RESPONSE_PREFIX = "OK|"
VERSION_PREFIX = "VERSION|"
LIST_PREFIX = "LIST"
GET_PREFIX = "GET|"
CERT_PREFIX = "CERT|"
ROA_PREFIX = "ROA|"

LOCAL_ROAS = {}          # ip -> (isla, vence)
LOCAL_ROAS_BUFFER = {}
ROA_VERSION = -1
ROAS_UPDATED = False
ROAS_MUTEX = threading.Lock()

TRUSTSTORE_PATH = "../etc/rpki/truststore/trusted-roots.pem"  # Trusted roots
ROOTS = []

def load_roots():
    with open(TRUSTSTORE_PATH, "rb") as f:
        return x509.load_pem_x509_certificates(f.read())

def _not_after(c):
    return getattr(c, "not_valid_after_utc", None) or c.not_valid_after.replace(tzinfo=timezone.utc)

def _not_before(c):
    return getattr(c, "not_valid_before_utc", None) or c.not_valid_before.replace(tzinfo=timezone.utc)

def ask_cert(num_emisor):
    # Respuesta del repositorio (punto C): OK|<certificado DER en base64, una sola linea>
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(10)
    try:
        s.connect((REPOSITORY_IP, REPOSITORY_PORT_TCP))
        f = s.makefile("r")
        s.sendall(f"{REPOSITORY_ANNOUNCE_PREFIX}ENRUTADOR|1\n".encode())
        if not f.readline().startswith(REPOSITORY_RESPONSE_PREFIX):
            raise OSError("HELLO rechazado al pedir CERT")
        s.sendall(f"{CERT_PREFIX}{num_emisor}\n".encode())
        respuesta = f.readline().strip()
    finally:
        s.close()
    if respuesta == "":
        raise OSError("Conexión cerrada al pedir CERT")
    if not respuesta.startswith(REPOSITORY_COMMAND_RESPONSE_PREFIX):
        return None  # ERR_NO_EXISTE u otro error
    try:
        der = base64.b64decode(respuesta[len(REPOSITORY_COMMAND_RESPONSE_PREFIX):], validate=True)
        return x509.load_der_x509_certificate(der)
    except ValueError:
        return None

def validate_cert(cert):
    now = datetime.now(timezone.utc)
    if not (_not_before(cert) <= now <= _not_after(cert)):
        return False
    bc = cert.extensions.get_extension_for_class(x509.BasicConstraints).value
    ku = cert.extensions.get_extension_for_class(x509.KeyUsage).value
    if bc.ca or not ku.digital_signature:
        return False
    for root in ROOTS:
        if root.subject != cert.issuer:
            continue
        if not (_not_before(root) <= now <= _not_after(root)):
            continue
        rbc = root.extensions.get_extension_for_class(x509.BasicConstraints).value
        rku = root.extensions.get_extension_for_class(x509.KeyUsage).value
        if not (rbc.ca and rku.key_cert_sign):
            continue
        try:
            root.public_key().verify(cert.signature, cert.tbs_certificate_bytes,
                                     padding.PKCS1v15(), cert.signature_hash_algorithm)
            return True
        except Exception:
            continue
    return False

def validate_crypto(parts):
    # parts = [ROA, IP, ISLA, NUM_EMISOR, EMISION, VENCE, FIRMA]
    _, ip, isla, emisor, emision, vence, firma = parts
    cert = ask_cert(emisor)
    if cert is None:
        print(f"ROA {ip}: certificado no disponible para el emisor {emisor}")
        return False
    try:
        if not validate_cert(cert):
            print(f"ROA {ip}: certificado no válido contra las raíces")
            return False
        cn = cert.subject.get_attributes_for_oid(NameOID.COMMON_NAME)[0].value
        if cn != f"AS{isla}-{emisor}":
            print(f"ROA {ip}: CN {cn} no coincide con AS{isla}-{emisor}")
            return False
        if int(vence) > _not_after(cert).timestamp():
            print(f"ROA {ip}: VENCE posterior al notAfter del certificado")
            return False
        msg = "|".join(parts[:6]).encode()
        cert.public_key().verify(base64.b64decode(firma), msg,
                                 padding.PKCS1v15(), hashes.SHA256())
        return True
    except Exception as e:
        print(f"ROA {ip}: verificación fallida ({type(e).__name__})")
        return False

def parse_roa(line):
    # ROA|IP|ISLA|NUM_EMISOR|EMISION|VENCE|FIRMA
    parts = line.split("|")
    if len(parts) != 7 or parts[0] + "|" != ROA_PREFIX:
        return None
    _, ip, isla, emisor, emision, vence, firma = parts
    try:
        ipaddress.ip_address(ip)
        emision, vence = int(emision), int(vence)
    except ValueError:
        return None
    if not (emision <= time.time() <= vence):
        return None
    if not validate_crypto(parts):
        return None
    return ip, (isla, vence)

def connect_to_repo():
    # Global variables to be used outside
    global ROA_VERSION, LOCAL_ROAS, ROAS_MUTEX, ROAS_UPDATED
    time.sleep(random.randrange(0, 75))  # Random wait to prevent concurrency
    while True:
      ROAS_UPDATED = False
      s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
      s.settimeout(10)
      try:
          s.connect((REPOSITORY_IP, REPOSITORY_PORT_TCP))
          f = s.makefile("r")  # permite leer linea por linea
          print(f"Conectado al repositorio en {REPOSITORY_IP}:{REPOSITORY_PORT_TCP}")
          # Send REPOSITORY announce message
          s.sendall(f"{REPOSITORY_ANNOUNCE_PREFIX}ENRUTADOR|1\n".encode())
          response = f.readline().strip()
          if response.startswith(REPOSITORY_RESPONSE_PREFIX):
              print(f"Respuesta del repositorio: {response}")
              s.sendall(f"{LIST_PREFIX}\n".encode())
              # Header: OK|<version>|<n>, followed by n lines of ROA
              header = f.readline().strip()
              if header.startswith(REPOSITORY_COMMAND_RESPONSE_PREFIX):
                  message_parts = header.split("|")
                  version = int(message_parts[1])
                  n = int(message_parts[2])
                  if version == ROA_VERSION:
                      print(f"ROAs ya están actualizadas (versión {ROA_VERSION})")
                  else:
                    roas = [f.readline().strip() for _ in range(n)]
                    s.close()
                    if "" in roas:
                        print("Lista de ROAs incompleta, se conserva la tabla anterior")
                    else:
                        ROOTS[:] = load_roots()
                        LOCAL_ROAS_BUFFER.clear()
                        for roa in roas:
                            parsed = parse_roa(roa)
                            if parsed:
                                LOCAL_ROAS_BUFFER[parsed[0]] = parsed[1]
                            else:
                                print(f"ROA inválido descartado: {roa}")
                        ROA_VERSION = version
                        ROAS_UPDATED = True
                        print(f"ROAs actualizadas (versión {ROA_VERSION}): {LOCAL_ROAS_BUFFER}")
              else:
                  print(f"Respuesta inesperada al LIST: {header}")
          else:
              print(f"Respuesta inesperada del repositorio: {response}")
      except Exception as e:
          # If something fails, leave previous ROA table
          print(f"Error al consultar el repositorio: {e}")
      finally:
          s.close()


      if ROAS_UPDATED:
          # Create a mutex to update ROAS 
          ROAS_MUTEX.acquire()
          LOCAL_ROAS.clear()
          LOCAL_ROAS.update(LOCAL_ROAS_BUFFER)
          print("ROAS LOCAL ACTUALIZADAS")
          ROAS_MUTEX.release()

      time.sleep(75)