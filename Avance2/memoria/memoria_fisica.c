#include "memoria_fisica.h"
#define TAM_MEMORIA_FISICA (1024 * 4)  // ES UN STUB, Jose, a vos te toca esto ;3

static uint8_t ram[TAM_MEMORIA_FISICA];

uint8_t mf_read_byte(uint32_t direccion_fisica) {
    return ram[direccion_fisica % TAM_MEMORIA_FISICA];
}

void mf_write_byte(uint32_t direccion_fisica, uint8_t valor) {
    ram[direccion_fisica % TAM_MEMORIA_FISICA] = valor;
}