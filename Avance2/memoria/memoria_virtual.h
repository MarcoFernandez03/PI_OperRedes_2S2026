#ifndef MEMORIA_VIRTUAL_H
#define MEMORIA_VIRTUAL_H

#include <stdint.h>

typedef struct MemoriaVirtual MemoriaVirtual;

MemoriaVirtual* mv_crear(uint32_t tam_pagina, uint32_t num_paginas);
void            mv_destruir(MemoriaVirtual *mv);

uint8_t mv_read_byte(MemoriaVirtual *mv, uint32_t direccion_virtual);
void    mv_write_byte(MemoriaVirtual *mv, uint32_t direccion_virtual, uint8_t valor);

// Conveniencia para leer/escribir varios bytes de una vez (ej. una IP de 4 bytes)
void mv_read_bytes(MemoriaVirtual *mv, uint32_t direccion_virtual, uint8_t *buffer, uint32_t cantidad);
void mv_write_bytes(MemoriaVirtual *mv, uint32_t direccion_virtual, const uint8_t *buffer, uint32_t cantidad);

#endif