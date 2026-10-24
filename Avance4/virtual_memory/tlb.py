from collections import OrderedDict
from typing import Optional

class TLB:
    def __init__(self, size: int):
        """Crea una TLB con un tamaño máximo especificado.

        Args
            size: Número máximo de entradas que la TLB puede contener. Debe ser mayor que cero.
        
        Raises
            ValueError: Si size es menor o igual a cero.
        """
        if size <= 0:
            raise ValueError("El tamaño de la TLB debe ser mayor que cero.")
        self.size: int = size
        self.entries: OrderedDict[int, int] = OrderedDict()

    def look_up(self, virtual_page_number: int) -> Optional[int]:
        """Traduce un número de página virtual a un número de marco físico usando la TLB.

        Args
            virtual_page_number: Número de página virtual a traducir.

        Returns
            Número de marco físico correspondiente si está en la TLB, o None si no está.
        """
        if not virtual_page_number in self.entries:
            return None
        self.entries.move_to_end(virtual_page_number)
        return self.entries[virtual_page_number]

    def insert(self, virtual_page_number: int, physical_frame_number: int) -> None:
        """Inserta una nueva entrada en la TLB.

        Si la TLB está llena, se elimina la entrada menos recientemente usada (LRU).

        Args
            virtual_page_number: Número de página virtual.
            physical_frame_number: Número de marco físico correspondiente.
        """
        if virtual_page_number not in self.entries and len(self.entries) >= self.size:
            self.entries.popitem(last=False)
        self.entries[virtual_page_number] = physical_frame_number
        self.entries.move_to_end(virtual_page_number)