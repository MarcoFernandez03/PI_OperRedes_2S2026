"""
Donde se GUARDA en la memoria virtual (Etapa 2) el resumen que calcula
vector_distancia.Nodo: la mejor ruta a cada isla. Ya no se guardan IPs sino
numeros de isla, y ahora cada ruta lleva su costo.

Formato de cada entrada (8 bytes = 1 pagina, acordado en clase):
    byte 0     -> isla destino        (1..5; 0 = slot vacio)
    byte 1     -> isla del siguiente salto
    bytes 2..3 -> costo total          (2 bytes, big endian)
    bytes 4..7 -> sin usar

24 paginas -> hasta 24 destinos. Con 5 islas se usan 4.

La memoria es cualquier objeto con read_bytes(direccion, cantidad) y
write_bytes(direccion, datos). Por defecto se usa la de C (Avance2/memoria,
via memoria_bridge), igual que el enrutador de Avance 2. Para usar la version en
Python de Avance4/virtual_memory, se pasa memoria=VirtualMemory(8, 24, 24, 8).
"""

import os
import sys
import threading
from typing import Dict, Optional, Tuple

TAM_PAGINA = 8      # bytes por entrada/pagina (acordado en clase)
NUM_PAGINAS = 24    # destinos maximos (acordado en clase)


def _memoria_en_c():
    """La memoria de la Etapa 2 (C por ctypes). Hay que compilarla: cd Avance2/memoria && make lib"""
    rutas = os.path.join(os.path.dirname(__file__), "..", "..", "Avance2", "rutas")
    sys.path.insert(0, os.path.abspath(rutas))
    from memoria_bridge import MemoriaVirtual
    return MemoriaVirtual(TAM_PAGINA, NUM_PAGINAS)


class TablaRutas:
    def __init__(self, memoria=None):
        self._mem = memoria if memoria is not None else _memoria_en_c()
        # Un hilo escribe el resumen (cuando cambia) mientras otros lo leen para reenviar DATA.
        # La memoria no es segura entre hilos, asi que todo acceso pasa por este candado.
        self._candado = threading.Lock()

    def _leer_slot(self, i: int) -> Tuple[int, int, int]:
        d = self._mem.read_bytes(i * TAM_PAGINA, TAM_PAGINA)
        return d[0], d[1], int.from_bytes(d[2:4], "big")

    def _escribir_slot(self, i: int, destino: int, via: int, costo: int) -> None:
        datos = bytes([destino, via]) + costo.to_bytes(2, "big") + bytes(4)
        self._mem.write_bytes(i * TAM_PAGINA, datos)

    def guardar_resumen(self, resumen: Dict[int, Tuple[int, Optional[int]]]) -> None:
        """Escribe en memoria lo que devuelve Nodo.resumen(): {destino: (costo, via)}.
        Solo se guardan los alcanzables; el resto de los slots se deja vacio."""
        alcanzables = [(d, c, v) for d, (c, v) in sorted(resumen.items()) if v is not None]
        with self._candado:
            for i in range(NUM_PAGINAS):
                if i < len(alcanzables):
                    d, c, v = alcanzables[i]
                    self._escribir_slot(i, d, v, c)
                else:
                    self._escribir_slot(i, 0, 0, 0)

    def buscar_siguiente_salto(self, destino: int) -> Optional[int]:
        """Lo que consulta el reenvio de DATA. None = sin ruta."""
        with self._candado:
            for i in range(NUM_PAGINAS):
                d, via, _ = self._leer_slot(i)
                if d == destino:
                    return via
        return None

    def cerrar(self) -> None:
        if hasattr(self._mem, "cerrar"):
            self._mem.cerrar()