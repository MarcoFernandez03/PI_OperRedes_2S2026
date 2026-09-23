#ifndef MEMORIA_FISICA_H
#define MEMORIA_FISICA_H

#include <stdint.h>
#include <stdbool.h>
#include <stddef.h>

/**
 * Inicializa la memoria física asignando dinámicamente un bloque contiguo de RAM.
 * @param tamano_bytes Tamaño total en bytes de la memoria física.
 * @return true si la asignación fue exitosa, false en caso contrario.
 */
bool mf_init(size_t tamano_bytes);

/**
 * Libera el bloque de memoria física asignado y reinicia su estado.
 */
void mf_destroy(void);

/**
 * Lee un byte de la memoria física en la dirección especificada.
 * @param direccion_fisica Offset absoluto dentro de la RAM.
 * @return El byte leído, o 0x00 si hay error de acceso.
 */
uint8_t mf_read_byte(uint32_t direccion_fisica);

/**
 * Escribe un byte en la memoria física en la dirección especificada.
 * @param direccion_fisica Offset absoluto dentro de la RAM.
 * @param valor Byte a escribir.
 */
void mf_write_byte(uint32_t direccion_fisica, uint8_t valor);

#endif // MEMORIA_FISICA_H