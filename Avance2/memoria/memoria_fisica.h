#ifndef MEMORIA_FISICA_H
#define MEMORIA_FISICA_H

#include <stdint.h>

uint8_t mf_read_byte(uint32_t direccion_fisica);
void    mf_write_byte(uint32_t direccion_fisica, uint8_t valor);

#endif