import os
import sys
import json
from datetime import datetime, timezone
AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(AQUI, "..", "pki"))     # pki.py y roa.py viven en Avance4/pki

from cryptography import x509
import pki


def _vigente(base):
  """True si existen base.key y base.crt y el certificado está dentro de su vigencia."""
  if not (os.path.exists(base + ".key") and os.path.exists(base + ".crt")):
    return False
  with open(base + ".crt", "rb") as f:
    cert = x509.load_pem_x509_certificate(f.read())
  return pki.valido_desde(cert) <= datetime.now(timezone.utc) <= pki.valido_hasta(cert)


def _borrar(base, extensiones):
  for ext in extensiones:
    if os.path.exists(f"{base}.{ext}"):
      os.remove(f"{base}.{ext}")


def generarLlaves():
  cfg = json.load(open(os.path.join(AQUI, "config_emisor.json")))
  carpeta = os.path.join(AQUI, cfg.get("carpeta_llaves", "llaves"))
  equipo = cfg["equipo"]
  cn = f"AS{cfg['isla']}-{cfg['num_emisor']}"
  ca_base = os.path.join(carpeta, f"ca-{equipo}")
  nodo_base = os.path.join(carpeta, cn)

  ca_ok = _vigente(ca_base)
  nodo_ok = ca_ok and _vigente(nodo_base)    # si la CA se renueva, el certificado del nodo también (lo firmó la CA vieja)
  if ca_ok and nodo_ok:
    print("La CA y las llaves del emisor siguen vigentes: no se genera nada.")
    return

  if not ca_ok:
    print("CA ausente o vencida: se renueva.")
    _borrar(ca_base, ["key", "crt", "srl"])
    pki.generar_ca(equipo, carpeta, cnf=os.path.join(AQUI, "ca-ext.cnf"))
  print("Llaves del emisor ausentes o vencidas: se renuevan.")
  _borrar(nodo_base, ["key", "csr", "crt"])
  pki.generar_nodo(equipo, cfg["isla"], cfg["num_emisor"], carpeta, cnf=os.path.join(AQUI, "nodo-ext.cnf"))


if __name__ == "__main__":
  while True:
    input("Presiona Enter para generar llaves y certificados de emisor...")
    generarLlaves()