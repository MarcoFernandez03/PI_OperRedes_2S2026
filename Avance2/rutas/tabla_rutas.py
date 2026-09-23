"""
tabla_rutas.py

Tabla de enrutamiento respaldada por la memoria virtual del equipo
(memoria_bridge.MemoriaVirtual), no por una estructura de datos común de
Python. Cada consulta o inserción de ruta pasa por mv_read_bytes/
mv_write_bytes, que en C resuelven TLB -> tabla de páginas -> memoria
física, tal como pide el enunciado de la Etapa 2 (punto d.b).

Formato de cada entrada (acordado en clase: 8 bytes por página):
    offset 0..3 -> IP destino        (4 bytes, un octeto por byte)
    offset 4..7 -> IP siguiente salto (4 bytes)

24 páginas -> máximo 24 rutas simultáneas. La IP 0.0.0.0 se usa como
marca de slot vacío (no debería usarse como destino real).

No hay campo de métrica/hop-count: el diseño acordado es que cada
router solo propaga una IP la primera vez que la aprende (ver
agregar_ruta). Con eso el flooding termina solo, sin necesitar contar
saltos, dado el tipo de topología con el que se va a probar en clase.
"""

from typing import Optional, List, Tuple

from memoria_bridge import MemoriaVirtual

TAM_PAGINA = 8      # bytes por entrada/página (acordado en clase)
NUM_PAGINAS = 24    # cantidad de rutas máximas (acordado en clase)
IP_VACIA = "0.0.0.0" #Se asume que esta IP no se usará como destino real, solo como marca de slot vacío


def _ip_a_bytes(ip: str) -> bytes:
    partes = ip.split(".")
    if len(partes) != 4:
        raise ValueError(f"IP inválida: {ip!r}")
    return bytes(int(p) for p in partes)


def _bytes_a_ip(datos: bytes) -> str:
    return ".".join(str(b) for b in datos)


class TablaRutas:
    def __init__(self, ruta_lib: str = None):
        if ruta_lib is None:
            self._mv = MemoriaVirtual(TAM_PAGINA, NUM_PAGINAS)
        else:
            self._mv = MemoriaVirtual(TAM_PAGINA, NUM_PAGINAS, ruta_lib=ruta_lib)

    def _direccion_slot(self, indice: int) -> int:
        return indice * TAM_PAGINA

    def _leer_slot(self, indice: int) -> Tuple[str, str]:
        datos = self._mv.read_bytes(self._direccion_slot(indice), TAM_PAGINA)
        destino = _bytes_a_ip(datos[0:4])
        siguiente_salto = _bytes_a_ip(datos[4:8])
        return destino, siguiente_salto

    def _escribir_slot(self, indice: int, ip_destino: str, ip_siguiente_salto: str) -> None:
        datos = _ip_a_bytes(ip_destino) + _ip_a_bytes(ip_siguiente_salto)
        self._mv.write_bytes(self._direccion_slot(indice), datos)

    def buscar_siguiente_salto(self, ip_destino: str) -> Optional[str]:
        """Devuelve la IP del siguiente salto para llegar a ip_destino,
        o None si no hay ruta conocida todavía."""
        for i in range(NUM_PAGINAS):
            destino, siguiente_salto = self._leer_slot(i)
            if destino == ip_destino:
                return siguiente_salto
        return None

    def conoce_ruta(self, ip_destino: str) -> bool:
        return self.buscar_siguiente_salto(ip_destino) is not None

    def agregar_ruta(self, ip_destino: str, ip_siguiente_salto: str) -> bool:
        """
        Guarda una ruta nueva. Devuelve True si la ruta era nueva (y por lo
        tanto hay que propagarla a los demás vecinos), False si ya se
        conocía (no hay que volver a propagar; así se corta el flooding).
        """
        if ip_destino == IP_VACIA:
            return False  # no permitir usar la IP centinela como destino real

        if self.conoce_ruta(ip_destino):
            return False

        for i in range(NUM_PAGINAS):
            destino, _ = self._leer_slot(i)
            if destino == IP_VACIA:
                self._escribir_slot(i, ip_destino, ip_siguiente_salto)
                return True

        # Tabla llena: con 24 rutas máximo, esto solo pasaría con una red
        # más grande de lo acordado en clase.
        print(f"[tabla_rutas] ADVERTENCIA: tabla llena, no se pudo agregar {ip_destino}")
        return False

    def todas_las_rutas(self) -> List[Tuple[str, str]]:
        rutas = []
        for i in range(NUM_PAGINAS):
            destino, siguiente_salto = self._leer_slot(i)
            if destino != IP_VACIA:
                rutas.append((destino, siguiente_salto))
        return rutas

    def cerrar(self) -> None:
        self._mv.cerrar()