
import os
import sys
import json
AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(AQUI, "..", "pki"))     # pki.py y roa.py viven en Avance4/pki

import pki


def generarLlaves():
  cfg = json.load(open(os.path.join(AQUI, "config_emisor.json")))
  pki.generar_ca(cfg["equipo"], cfg.get("carpeta_llaves", "llaves"))
  pki.generar_nodo(cfg["equipo"], cfg["isla"], cfg["num_emisor"], cfg.get("carpeta_llaves", "llaves"))

