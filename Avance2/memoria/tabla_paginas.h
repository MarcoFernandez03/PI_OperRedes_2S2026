#ifndef TABLA_PAGINAS_H
#define TABLA_PAGINAS_H

#include <stdint.h>
#include <stdbool.h>

typedef struct {
    uint32_t pagina_fisica;
    bool valida;
} EntradaTabla;

typedef struct {
    EntradaTabla *entradas;
    uint32_t num_paginas;
} TablaPaginas;

TablaPaginas* tp_crear(uint32_t num_paginas);
void          tp_destruir(TablaPaginas *tp);
bool          tp_traducir(TablaPaginas *tp, uint32_t pagina_virtual, uint32_t *pagina_fisica_out);
void          tp_mapear(TablaPaginas *tp, uint32_t pagina_virtual, uint32_t pagina_fisica);

#endif