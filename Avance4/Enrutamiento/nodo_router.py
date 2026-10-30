"""
nodo_router.py - El enrutador (intermediario) de una isla. Junta las tres piezas:

    vector_distancia.Nodo   -> decide las rutas (algoritmo, sin sockets)
    tabla_rutas.TablaRutas  -> guarda el resumen en la memoria virtual
    este archivo            -> sockets, hilos, ANNOUNCE periodico, DATA

Uso:   python3 nodo_router.py config_isla3.json

Lo que pasa en cada parte (los numeros son los pasos de la explicacion):
  [3.1] Llega un ANNOUNCE   -> nodo.recibir(); si la tabla cambio -> al_cambiar()
  [3.2] al_cambiar()        -> guarda el resumen en memoria, imprime la tabla con hora,
                               y anuncia YA a los vecinos (sin esperar los 30 s)
  [3.3] Cada 30 s           -> ANNOUNCE a todos (keepalive + publicar rutas)
  [3.4] Cada 1 s            -> nodo.revisar_silencio(tolerancia)
  [3.5] Falla un envio      -> ese vecino se da por caido (no esperamos al silencio)
  [3.6] Llega un DATA       -> entregar / descartar / reenviar al siguiente salto (con TTL)
  [3.7] SIGINT / SIGTERM    -> aviso de muerte a los vecinos y cierre
"""
import json
import signal
import socket
import socketserver
import sys
import threading
import time

# nodo_router.py
from vector_distancia import Nodo
from tabla_rutas import TablaRutas

# ---------------------------------------------------------------------------
# Formato del ANNOUNCE.  [ACORDAR] con los otros grupos: todo el formato vive en estas
# dos funciones; si el acuerdo cambia (una ruta por mensaje, IP en vez de isla...) solo
# se tocan estas dos.     Ejemplo:  ANNOUNCE|3|1:3,2:3,4:-1     (de la isla 3: destino:costo)
# Aviso de muerte:  ANNOUNCE|3|3:-1                (la isla se anuncia -1 a si misma)
# ---------------------------------------------------------------------------
def armar_announce(isla, vector):
    return f"ANNOUNCE|{isla}|" + ",".join(f"{d}:{c}" for d, c in sorted(vector.items()))


def leer_announce(msg):
    """'ANNOUNCE|3|1:3,2:-1' -> (3, {1: 3, 2: -1}).  None si esta mal formado."""
    try:
        _, isla, cuerpo = msg.split("|", 2)
        vector = {}
        for par in filter(None, cuerpo.split(",")):
            destino, costo = par.split(":")
            vector[int(destino)] = int(costo)      # con texto las claves llegan como str: se pasan a int
        return int(isla), vector
    except ValueError:
        return None


class Router:
    def __init__(self, cfg, memoria=None):
        self.id = cfg["isla"]
        self.cfg = cfg
        # Solo se conocen los vecinos del archivo de configuracion (regla del enunciado).
        self.vecino = {v["isla"]: v for v in cfg["vecinos"]}
        self.nodo = Nodo(self.id, {i: v["costo"] for i, v in self.vecino.items()})
        self.tabla = TablaRutas(memoria)
        self.intervalo = cfg.get("intervalo_announce", 30)       # [ACORDAR]
        self.tolerancia = cfg.get("tolerancia_silencio", 40)     # [ACORDAR] mayor que el intervalo
        self._detenido = threading.Event()
        self._servidores = []
        self._candado_log = threading.Lock()
        self._candado_registro = threading.Lock()

    # ---------------------------------------------------------------- bitacora
    def log(self, texto):
        with self._candado_log:
            print(f"[{time.strftime('%H:%M:%S')}] [isla {self.id}] {texto}", flush=True)

    # ---------------------------------------------------------------- red
    def _enviar(self, ip, puerto, msg):
        """Una conexion TCP por mensaje (como en Avance 2). True si se pudo entregar.
        Se intenta dos veces: un fallo pasajero no debe dar por caido a un vecino sano
        (se recuperaria hasta 30 s despues, cuando vuelva a anunciar)."""
        for intento in range(2):
            try:
                with socket.create_connection((ip, puerto), timeout=2) as s:
                    s.sendall(msg.encode())
                return True
            except OSError:
                time.sleep(0.2)
        return False

    def _enviar_a_vecino(self, isla, msg):
        v = self.vecino[isla]
        return self._enviar(v["ip"], v["puerto"], msg)

    # ---------------------------------------------------------------- [3.2] cambio de tabla
    def _registrar(self):
        """Guarda el resumen en la memoria virtual e imprime la tabla con hora (bitacora)."""
        with self._candado_registro:     # calcular + guardar + imprimir juntos: que un hilo no pise con un resumen mas viejo
            self.tabla.guardar_resumen(self.nodo.resumen())
            self.log("la tabla cambio:")
            self.nodo.imprimir()

    def anunciar(self):
        """ANNOUNCE a todos los vecinos. Si un envio falla [3.5], ese vecino se da por caido,
        y si eso cambia la tabla se vuelve a anunciar con la tabla nueva."""
        while True:
            mensajes = {v: armar_announce(self.id, self.nodo.vector_para(v)) for v in self.vecino}
            entregado = {}
            # Se manda a todos a la vez: un vecino caido tarda varios segundos en dar error y no debe
            # retrasar el aviso a los vecinos que si estan vivos.
            hilos = [threading.Thread(target=lambda v=v: entregado.update({v: self._enviar_a_vecino(v, mensajes[v])}))
                     for v in self.vecino]
            [h.start() for h in hilos]
            [h.join() for h in hilos]
            cambio = False
            for v, ok in entregado.items():
                if not ok:
                    cambio |= self.nodo.vecino_caido(v)
            if not cambio:
                return
            self._registrar()

    def al_cambiar(self):
        self._registrar()
        self.anunciar()

    # ---------------------------------------------------------------- [3.1] ANNOUNCE
    def recibir_announce(self, msg):
        r = leer_announce(msg)
        if r is None:
            self.log(f"ANNOUNCE mal formado, se ignora: {msg!r}")
            return
        vecino, vector = r
        if self.nodo.recibir(vecino, vector):      # True = mi tabla cambio
            self.al_cambiar()

    # ---------------------------------------------------------------- [3.6] DATA
    def recibir_data(self, msg):
        """DATA|ISLA_ORIGEN|ISLA_DESTINO|TTL|DATOS   (las 4 reglas del documento)."""
        try:
            _, origen, destino, ttl, datos = msg.split("|", 4)
            origen, destino, ttl = int(origen), int(destino), int(ttl)
        except ValueError:
            self.log(f"DATA mal formado, se descarta: {msg!r}")
            return
        if destino == self.id:                                           # regla 1: es para mi
            srv = self.cfg["servidor_local"]
            ok = self._enviar(srv["ip"], srv["puerto"], msg)
            self.log(f"DATA entregado al servidor local (origen isla {origen}): {datos!r}" if ok
                     else f"DATA para mi isla, pero el servidor local no responde: {datos!r}")
            return
        ttl -= 1                                                         # regla 2: gasta un salto
        if ttl <= 0:
            self.log(f"DATA descartado: TTL llego a 0 (origen {origen}, destino {destino})")
            return
        via = self.tabla.buscar_siguiente_salto(destino)                 # lo lee de la memoria virtual
        if via is None:                                                  # regla 3: sin ruta
            self.log(f"DATA descartado: sin ruta a la isla {destino} (origen {origen})")
            return
        if self._enviar_a_vecino(via, f"DATA|{origen}|{destino}|{ttl}|{datos}"):   # regla 4
            self.log(f"DATA reenviado: origen={origen} destino={destino} siguiente_salto={via} ttl={ttl}")
        else:
            self.log(f"DATA perdido: no se pudo enviar a la isla {via}")
            if self.nodo.vecino_caido(via):
                self.al_cambiar()

    # ---------------------------------------------------------------- arranque
    def _manejador(self):
        router = self

        class Manejador(socketserver.StreamRequestHandler):
            timeout = 5

            def handle(self):                      # un hilo por conexion (ThreadingTCPServer)
                try:
                    msg = self.rfile.read(65536).decode(errors="replace").strip()
                except OSError:
                    return
                if msg.startswith("ANNOUNCE|"):
                    router.recibir_announce(msg)
                elif msg.startswith("DATA|"):
                    router.recibir_data(msg)
                else:
                    router.log(f"mensaje desconocido, se ignora: {msg[:40]!r}")
        return Manejador

    def arrancar(self):
        class Servidor(socketserver.ThreadingTCPServer):
            allow_reuse_address = True
            daemon_threads = True
            request_queue_size = 128     # cola de conexiones pendientes; el valor por defecto (5) pierde mensajes en rafagas

        bind = self.cfg.get("escuchar_en", "")
        # 5005: los vecinos (ANNOUNCE y DATA).   5006: los clientes de mi propia isla (DATA).
        for puerto in (self.cfg.get("puerto", 5005), self.cfg.get("puerto_local", 5006)):
            srv = Servidor((bind, puerto), self._manejador())
            self._servidores.append(srv)
            threading.Thread(target=srv.serve_forever, daemon=True).start()
        threading.Thread(target=self._ciclo, daemon=True).start()
        self.log(f"enrutador arriba; vecinos: {sorted(self.vecino)}")

    def _ciclo(self):
        self.anunciar()                                      # [3.3] ANNOUNCE al iniciar
        proximo = time.monotonic() + self.intervalo
        while not self._detenido.wait(1.0):
            if self.nodo.revisar_silencio(self.tolerancia):  # [3.4] cada segundo
                self.al_cambiar()
            if time.monotonic() >= proximo:                  # [3.3] cada 30 s
                self.anunciar()
                proximo += self.intervalo

    # ---------------------------------------------------------------- [3.7] cierre
    def cerrar(self, avisar=True):
        self._detenido.set()
        if avisar:                                           # aviso de muerte antes de terminar
            msg = armar_announce(self.id, self.nodo.aviso_de_muerte())
            for v in self.vecino:
                self._enviar_a_vecino(v, msg)
        for srv in self._servidores:
            srv.shutdown()
            srv.server_close()
        # [PENDIENTE] imprimir aciertos/fallos de TLB y fallos de pagina (hoy la memoria no los cuenta)
        self.tabla.cerrar()


def main():
    if len(sys.argv) != 2:
        print("Uso: python3 nodo_router.py <config.json>")
        sys.exit(1)
    with open(sys.argv[1]) as f:
        router = Router(json.load(f))
    router.arrancar()

    def salir(*_):
        router.cerrar(avisar=True)
        sys.exit(0)
    signal.signal(signal.SIGINT, salir)
    signal.signal(signal.SIGTERM, salir)
    while True:
        time.sleep(1)


if __name__ == "__main__":
    main()