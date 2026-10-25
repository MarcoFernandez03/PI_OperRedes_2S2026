import base64
import ipaddress
import time

from cryptography import x509
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

def cargar_llave(ruta):
    with open(ruta, "rb") as f:
        return serialization.load_pem_private_key(f.read(), password=None)