"""
logica_rutas.py

Decide qué hacer con cada mensaje ANNOUNCE / ADVERTISE / DATA, usando la
tabla de rutas. Deliberadamente NO toca sockets: cada función recibe los
datos ya extraídos (mensaje, IP de quien lo mandó) y devuelve qué acción
tomar, para poder probar la lógica de enrutamiento con asserts comunes,
sin tener que levantar servidores. escuchar_nodo_router.py es quien
conecta esto con sockets reales.
"""

from typing import Optional, Tuple
from tabla_rutas import TablaRutas


def procesar_announce(ip_vecino: str, ip_propia: str, tabla: TablaRutas) -> Optional[str]:
    """
    Se llama cuando llega un ANNOUNCE por UDP broadcast. ip_vecino es
    remitente[0] (la IP real de quien lo mandó, no un campo del mensaje).

    Un ANNOUNCE siempre describe a un vecino directo: el siguiente salto
    hacia esa IP es la IP misma.

    Devuelve la IP a propagar por ADVERTISE si la ruta era nueva, o None
    si ya se conocía (no hay que propagar de nuevo).
    """
    if ip_vecino == ip_propia:
        return None
    if tabla.agregar_ruta(ip_vecino, ip_vecino):
        return ip_vecino
    return None


def procesar_advertise(msg: str, ip_remitente: str, ip_propia: str,
                        tabla: TablaRutas) -> Optional[str]:
    """
    Se llama cuando llega un ADVERTISE|IP_A_PROPAGAR por TCP unicast.
    ip_remitente es quien nos lo mandó (el vecino TCP directo), y por lo
    tanto es el siguiente salto hacia ip_a_propagar.

    Devuelve la IP a repropagar si la ruta era nueva, o None si no.
    """
    try:
        _, ip_a_propagar = msg.split("|", 1)
    except ValueError:
        return None

    if ip_a_propagar == ip_propia:
        return None
    if tabla.agregar_ruta(ip_a_propagar, ip_remitente):
        return ip_a_propagar
    return None


# Resultado de procesar_data(): (accion, ...)
#   ("local", contenido)                          -> el destino somos nosotros
#   ("reenviar", ip_siguiente_salto, ip_destino, contenido) -> reenviar
#   ("sin_ruta", ip_destino)                       -> no hay ruta conocida
#   ("formato_invalido", None)                     -> mensaje mal formado
def procesar_data(msg: str, ips_locales: list, tabla: TablaRutas) -> Tuple:
    try:
        _, ip_destino, contenido = msg.split("|", 2)
    except ValueError:
        return ("formato_invalido", None)

    if ip_destino in ips_locales:
        return ("local", ip_destino, contenido)

    # TODO: Esto es lo que hay que cambiar por interfaz
    # también podemos simplificar y enviar interfaz + ip router vecino
    # para quitar esa parte de escuchar_nodo_router.py
    siguiente_salto = tabla.buscar_siguiente_salto(ip_destino)
    if siguiente_salto is not None:
        return ("reenviar", siguiente_salto, ip_destino, contenido)

    return ("sin_ruta", ip_destino)