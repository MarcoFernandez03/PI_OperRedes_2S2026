import threading
from contextlib import contextmanager


class LectoresEscritores:
    def __init__(self):
        self._lectores = 0
        self._escritores = 0              # escritores activos o esperando
        self._mutex_lectores = threading.Semaphore(1)
        self._mutex_escritores = threading.Semaphore(1)
        self._entrada_lectores = threading.Semaphore(1)  # serializa la entrada de lectores
        self._puerta_lectores = threading.Semaphore(1)   # los escritores la cierran
        self._recurso = threading.Semaphore(1)           # acceso exclusivo al dato

    def adquirir_lectura(self) -> None:
        self._entrada_lectores.acquire()
        self._puerta_lectores.acquire()
        self._mutex_lectores.acquire()
        self._lectores += 1
        if self._lectores == 1:
            self._recurso.acquire()
        self._mutex_lectores.release()
        self._puerta_lectores.release()
        self._entrada_lectores.release()

    def liberar_lectura(self) -> None:
        self._mutex_lectores.acquire()
        self._lectores -= 1
        if self._lectores == 0:
            self._recurso.release()
        self._mutex_lectores.release()

    def adquirir_escritura(self) -> None:
        self._mutex_escritores.acquire()
        self._escritores += 1
        if self._escritores == 1:
            self._puerta_lectores.acquire()
        self._mutex_escritores.release()
        self._recurso.acquire()

    def liberar_escritura(self) -> None:
        self._recurso.release()
        self._mutex_escritores.acquire()
        self._escritores -= 1
        if self._escritores == 0:
            self._puerta_lectores.release()
        self._mutex_escritores.release()

    @contextmanager
    def lectura(self):
        self.adquirir_lectura()
        try:
            yield
        finally:
            self.liberar_lectura()

    @contextmanager
    def escritura(self):
        self.adquirir_escritura()
        try:
            yield
        finally:
            self.liberar_escritura()


class RegistroCandados:
    """Entrega un LectoresEscritores por clave (número de inodo o de directorio)."""

    def __init__(self):
        self._candados: dict[int, LectoresEscritores] = {}
        self._mutex = threading.Lock()

    def obtener(self, clave: int) -> LectoresEscritores:
        with self._mutex:
            if clave not in self._candados:
                self._candados[clave] = LectoresEscritores()
            return self._candados[clave]