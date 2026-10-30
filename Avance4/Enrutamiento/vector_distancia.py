"""
vector_distancia.py - Vector de distancia para el intermediario de cada isla.

  [GRUPO]    = lo que cada equipo debe conectar/modificar en su propio código.
  [ACORDAR]  = decisión que debe ser IGUAL en los 5 grupos (documento compartido).

Este archivo es solo el ALGORITMO (sin sockets ni memoria). En nuestro repo lo conecta
nodo_router.py (sockets, hilos) y tabla_rutas.py (memoria virtual). Lo que cada grupo conecta:
  1. La configuración: de su archivo salen mi_id y {vecino: costo} (solo vecinos).
  2. Recibir: cuando llega un ANNOUNCE de un vecino -> nodo.recibir(vecino, vector).
  3. Enviar: si recibir() devolvió True (la tabla cambió) -> mandar nodo.vector_para(v)
     a cada vecino v YA, sin esperar los 30 s. Además, cada 30 s -> lo mismo (keepalive).
  4. Silencio: cada pocos segundos -> nodo.revisar_silencio(tolerancia); si devuelve True,
     anunciar igual que en el punto 3.
  5. Al cerrar (SIGINT/SIGTERM): mandar nodo.aviso_de_muerte() a los vecinos.
  6. Memoria virtual (Etapa 2): tras cada cambio, guardar el resumen() en su memoria.
  7. Reenviar DATA: nodo.siguiente_salto(isla_destino); restar 1 al TTL en cada salto.
"""
import functools
import threading
import time


def _con_candado(f):
    """El servidor atiende cada conexion en un hilo distinto: sin esto, dos hilos
    tocando la tabla a la vez dan RuntimeError y pueden perder un cambio."""
    @functools.wraps(f)
    def envuelta(self, *args, **kwargs):
        with self._candado:
            return f(self, *args, **kwargs)
    return envuelta


INF = 100              # [ACORDAR] costo >= INF = inalcanzable (valor del documento de diseño)
POISON_REVERSE = True  # [ACORDAR] a un vecino se le anuncia -1 por lo que llego a traves de el


class Nodo:
    def __init__(self, mi_id, vecinos):
        self.id = mi_id           # [GRUPO] numero de isla (1..5) - [ACORDAR] ids = numero de isla
        self.vecinos = vecinos    # [GRUPO] {id_vecino: costo_enlace}, SOLO de su archivo de configuracion
        self.tabla = {}           # tabla[destino][via] = costo total de llegar a destino pasando por via
        self.ultimo_oido = {}     # vecino -> ultima vez que se oyo (para detectar silencio)
        self._candado = threading.RLock()   # no tocar: protege la tabla entre hilos

    # ---------------- consulta ----------------
    @_con_candado
    def mejor(self, destino):
        """(costo, siguiente_salto). Empate: gana el menor id. [ACORDAR]"""
        opciones = [(c, via) for via, c in self.tabla.get(destino, {}).items() if c < INF]
        return min(opciones) if opciones else (INF, None)

    @_con_candado
    def resumen(self):
        """{destino: (costo, siguiente_salto)}.  [GRUPO] esto es lo que se guarda en la memoria virtual."""
        return {d: self.mejor(d) for d in self.tabla}

    @_con_candado
    def siguiente_salto(self, destino):
        """[GRUPO] lo que consulta el reenvio de DATA. None = sin ruta (descartar y registrar)."""
        return self.mejor(destino)[1]

    # ---------------- entrada ----------------
    @_con_candado
    def recibir(self, vecino, vector, ahora=None):
        """Llego el vector de un vecino: {destino: costo}.  Devuelve True si MI tabla cambio.
        [GRUPO] 'vector' ya debe venir como diccionario {int: int}. OJO: con JSON las claves llegan
        como TEXTO ('2' en vez de 2); conviertanlas: {int(k): v for k, v in vector.items()}.
        Valores del protocolo: costo > 0 = distancia, -1 = inalcanzable, 0 = sin ruta (se ignora)."""
        if vecino not in self.vecinos:
            return False                                   # no es un vecino configurado
        if vector.get(vecino) == -1:                       # [ACORDAR] aviso de muerte: el vecino
            return self.vecino_caido(vecino)               # se anuncia -1 a si mismo al cerrar
        antes = self.resumen()
        for d, fila in self.tabla.items():                 # el vector nuevo REEMPLAZA al anterior
            if d != vecino:
                fila[vecino] = INF
        self.ultimo_oido[vecino] = time.monotonic() if ahora is None else ahora
        self.tabla.setdefault(vecino, {})[vecino] = self.vecinos[vecino]    # enlace directo
        for destino, costo in vector.items():
            if destino in (self.id, vecino) or costo == 0:  # ni hacia mi, ni hacia el que lo manda, ni 0
                continue
            self.tabla.setdefault(destino, {})[vecino] = \
                INF if costo < 0 else min(INF, self.vecinos[vecino] + costo)
        return self.resumen() != antes

    @_con_candado
    def vecino_caido(self, v):
        """El vecino murio (aviso de muerte, o silencio). Devuelve True si MI tabla cambio."""
        antes = self.resumen()
        self.ultimo_oido.pop(v, None)
        for fila in self.tabla.values():
            fila[v] = INF
        return self.resumen() != antes

    @_con_candado
    def revisar_silencio(self, tolerancia, ahora=None):
        """[GRUPO] llamarlo cada pocos segundos. tolerancia = N intervalos de anuncio
        (en segundos). [ACORDAR] N (propuesta: al menos 2-3 intervalos de 30 s).
        Devuelve True si algun vecino se dio por caido y MI tabla cambio."""
        ahora = time.monotonic() if ahora is None else ahora
        cambio = False
        for v, t in list(self.ultimo_oido.items()):
            if ahora - t > tolerancia:
                cambio |= self.vecino_caido(v)
        return cambio

    # ---------------- salida ----------------
    @_con_candado
    def vector_para(self, vecino):
        """Lo que se le anuncia a ese vecino: {destino: costo}, con -1 = inalcanzable.
        Nunca incluye mi propio costo (0 significaria 'sin ruta').
        [GRUPO] aqui se arma el contenido del ANNOUNCE (una ruta por mensaje o toda la tabla)."""
        out = {}
        for d, (costo, via) in self.resumen().items():
            if d == vecino:
                continue
            out[d] = -1 if costo >= INF or (POISON_REVERSE and via == vecino) else costo
        return out

    def aviso_de_muerte(self):
        """[ACORDAR] Que mandar al cerrar con SIGINT/SIGTERM: yo mismo = -1."""
        return {self.id: -1}

    @_con_candado
    def imprimir(self):
        """[GRUPO] la bitacora pide la tabla completa con hora cada vez que cambia."""
        print(f"Tabla de isla {self.id}:")
        for d, (costo, via) in sorted(self.resumen().items()):
            print(f"  -> isla {d}: " + (f"costo {costo}, por isla {via}" if via else "INALCANZABLE"))

