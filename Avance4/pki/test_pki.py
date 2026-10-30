import time
from cryptography import x509
import pki
from roa import crear_roa, verificar_roa

def cargar(ruta):
    with open(ruta, "rb") as f:
        return x509.load_pem_x509_certificate(f.read())

pki.generar_ca("OTRO", "out")
pki.generar_nodo("OTRO", 65009, 1, "out")

raices = pki.cargar_truststore("out/trusted-roots.pem")
cert = cargar("out/AS65003-17.crt")
llave = "out/AS65003-17.key"
ahora = time.time()

def caso(nombre, esperado, resultado):
    ok, motivo = resultado
    print(("PASA " if ok == esperado else "FALLA"), nombre, "->", ok, motivo)

caso("ROA válido", True, verificar_roa(crear_roa("10.1.0.5", 65003, 17, llave, 3600), cert, raices))
caso("ROA vencido", False, verificar_roa(crear_roa("10.1.0.5", 65003, 17, llave, 3600), cert, raices, ahora + 7200))
caso("isla falsa", False, verificar_roa(crear_roa("10.1.0.5", 65004, 17, llave, 3600), cert, raices))
caso("VENCE > notAfter", False, verificar_roa(crear_roa("10.1.0.5", 65003, 17, llave, 400*86400), cert, raices))
caso("campo alterado", False, verificar_roa(crear_roa("10.1.0.5", 65003, 17, llave, 3600).replace("10.1.0.5", "10.1.0.6"), cert, raices))
caso("CA no confiable", False, verificar_roa(crear_roa("10.9.0.1", 65009, 1, "out/AS65009-1.key", 3600), cargar("out/AS65009-1.crt"), raices))