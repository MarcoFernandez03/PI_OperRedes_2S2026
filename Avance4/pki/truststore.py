import os
import tempfile

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization

from pki import _ext_raiz_ok

def huella(cert):
    return cert.fingerprint(hashes.SHA256()).hex()

def _normalizar(texto):
    return texto.replace(":", "").strip().lower()

def cargar_huellas(ruta):
    tabla = {}
    with open(ruta) as f:
        for linea in f:
            linea = linea.strip()
            if not linea or linea.startswith("#"):
                continue
            nombre, valor = linea.split(None, 1)
            tabla[nombre] = _normalizar(valor)
    return tabla

def actualizar_truststore(carpeta, ruta_huellas, destino):
    esperadas = cargar_huellas(ruta_huellas)
    aceptadas, rechazadas, pems = [], [], []

    for archivo in sorted(os.listdir(carpeta)):
        if not archivo.endswith(".crt"):
            continue
        nombre = archivo[:-4]
        try:
            with open(os.path.join(carpeta, archivo), "rb") as f:
                cert = x509.load_pem_x509_certificate(f.read())
        except ValueError:
            rechazadas.append((nombre, "no es un certificado PEM válido"))
            continue

        if nombre not in esperadas:
            rechazadas.append((nombre, "no tiene huella registrada"))
        elif huella(cert) != esperadas[nombre]:
            rechazadas.append((nombre, "la huella no coincide"))
        elif not _ext_raiz_ok(cert):
            rechazadas.append((nombre, "extensiones de CA incorrectas"))
        else:
            aceptadas.append(nombre)
            pems.append(cert.public_bytes(serialization.Encoding.PEM))