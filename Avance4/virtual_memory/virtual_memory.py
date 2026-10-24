from collections.abc import Iterator
from typing import Optional

from frame_allocator import FrameAllocator
from page_table import PageTable
from physical_memory import PhysicalMemory
from tlb import TLB

class VirtualMemory:
    def __init__(self, page_size: int, num_pages: int, num_frames: int, tlb_size: int):
        """Inicializa la memoria virtual con los parámetros especificados.

        Args
            page_size: Tamaño de cada página en bytes.
            num_pages: Número de páginas en la memoria virtual.
            num_frames: Número de marcos en la memoria física.
            tlb_size: Tamaño de la tabla de traducción de direcciones.
        
        Raises
            ValueError: Si alguno de los parámetros es menor o igual a cero.
        """
        if page_size <= 0 or num_pages <= 0 or num_frames <= 0 or tlb_size <= 0:
            raise ValueError("Todos los parámetros deben ser mayores que cero.")
        self.page_size = page_size
        self.num_pages = num_pages
        self.allocator = FrameAllocator(num_frames)
        self.physical_memory = PhysicalMemory(size=page_size * num_frames)
        self.page_table = PageTable(num_pages=num_pages)
        self.tlb = TLB(size=tlb_size)

    def read_bytes(self, virtual_address: int, length: int) -> bytes:
        """Lee bytes de la memoria virtual.
        
        Args
            virtual_address: Dirección virtual absoluta.
            length: Número de bytes a leer.

        Returns
            Los valores de los bytes leídos, como un objeto bytes.

        Raises
            ValueError: Si la dirección virtual o la longitud están fuera de los límites.
            MemoryError: Si no hay marcos de página disponibles para asignar.
        """
        self._validate_range(virtual_address, length)
        data = bytearray()
        for physical_address, size in self._translate(virtual_address, length):
            data += self.physical_memory.read_bytes(physical_address, size)
        return bytes(data)

    def write_bytes(self, virtual_address: int, data: bytes) -> None:
        """Escribe bytes en la memoria virtual.

        Args
            virtual_address: Dirección virtual absoluta.
            data: Bytes a escribir en la memoria virtual.

        Raises
            ValueError: Si la dirección virtual o la longitud de los datos están fuera de los límites.
            MemoryError: Si no hay marcos de página disponibles para asignar.
        """
        self._validate_range(virtual_address, len(data))
        position = 0
        for physical_address, size in self._translate(virtual_address, len(data)):
            self.physical_memory.write_bytes(physical_address, data[position:position + size])
            position += size

    def _validate_range(self, virtual_address: int, length: int) -> None:
        if virtual_address < 0 or length < 0 or virtual_address + length > self.page_size * self.num_pages:
            raise ValueError("Rango de direcciones virtuales fuera de los límites.")

    def _translate(self, virtual_address: int, length: int) -> Iterator[tuple[int, int]]:
        end = virtual_address + length
        while virtual_address < end:
            virtual_page_number, offset = divmod(virtual_address, self.page_size)
            size = min(end - virtual_address, self.page_size - offset)
            physical_frame_number = self._look_up(virtual_page_number)
            yield physical_frame_number * self.page_size + offset, size
            virtual_address += size

    def _look_up(self, virtual_page_number: int) -> int:
        physical_frame_number: Optional[int] = self.tlb.look_up(virtual_page_number)
        if physical_frame_number is not None:
            return physical_frame_number

        physical_frame_number = self.page_table.look_up(virtual_page_number)
        if physical_frame_number is None:
            physical_frame_number = self._handle_fault(virtual_page_number)

        self.tlb.insert(virtual_page_number, physical_frame_number)
        return physical_frame_number

    def _handle_fault(self, virtual_page_number: int) -> int:
        physical_frame_number: Optional[int] = self.allocator.allocate()
        if physical_frame_number is None:
            raise MemoryError("No hay marcos de página disponibles para asignar.")
        self.page_table.map(virtual_page_number, physical_frame_number)
        return physical_frame_number
