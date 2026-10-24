from collections import deque
from typing import Optional

class FrameAllocator:
    def __init__(self, num_frames: int):
        """Inicializa el FrameAllocator con un número específico de marcos de página.
        
        Args
            num_frames: Número total de marcos de página disponibles.
        
        Raises
            ValueError: Si num_frames es menor o igual a cero.
        """
        if num_frames <= 0:
            raise ValueError("El número de marcos de página debe ser mayor que cero.")
        self._free = deque(range(num_frames))

    def allocate(self) -> Optional[int]:
        """Asigna un marco de página libre y lo marca como ocupado.

        Returns
            El número del marco de página asignado, o None si no hay marcos disponibles.
        """
        if not self._free:
            return None
        return self._free.popleft()