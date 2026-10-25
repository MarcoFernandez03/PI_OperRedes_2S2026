import os
import tempfile

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization

from pki import _ext_raiz_ok


def huella(cert):
    return cert.fingerprint(hashes.SHA256()).hex()


def _normalizar(texto):
    return texto.replace(":", "").strip().lower()