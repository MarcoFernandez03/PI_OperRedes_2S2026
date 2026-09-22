#ifndef TLB_H
#define TLB_H

#include <stdint.h>
#include <stdbool.h>

#define TLB_TAMANO 8

typedef struct {
    uint32_t pagina_virtual;
    uint32_t pagina_fisica;
    bool valida;
    uint32_t ultimo_uso;  // para LRU
} EntradaTLB;

typedef struct {
    EntradaTLB entradas[TLB_TAMANO];
    uint32_t contador_uso;
} TLB;

void tlb_inicializar(TLB *tlb);
bool tlb_buscar(TLB *tlb, uint32_t pagina_virtual, uint32_t *pagina_fisica_out);
void tlb_insertar(TLB *tlb, uint32_t pagina_virtual, uint32_t pagina_fisica);

#endif