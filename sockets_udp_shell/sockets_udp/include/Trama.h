#ifndef TRAMA_H
#define TRAMA_H

#include <cstdint>
#include <cstddef>
#include <vector>

// ---------------------------------------------------------------------------
// Serialización de las tramas definidas en el protocolo del equipo SHELL.
//
// IMPORTANTE: por qué esto NO se hace simplemente enviando un struct
// "tal cual" por el socket (algo como sendto(&trama, sizeof(trama), ...)):
//
//   1) Padding: el compilador puede insertar bytes de relleno entre campos
//      de un struct para alinearlos en memoria (por ejemplo entre el
//      uint8_t y el uint32_t). sizeof(struct) puede no ser 7 bytes aunque
//      los campos sumen 1+4+2. Esto además puede variar entre plataformas
//      (Raspberry Pi ARM vs. servidor x86_64/Mac).
//   2) Orden de bytes (endianness): ARM (Raspberry Pi) suele ser
//      little-endian, y hosts x86_64 también, pero no hay que asumirlo;
//      la convención de red es big-endian ("network byte order"). Por eso
//      se usan htonl/ntohl y htons/ntohs.
//
// Para evitar ambos problemas, se arma el datagrama a mano en un buffer de
// bytes, campo por campo, en vez de confiar en la representación en
// memoria del struct.
// ---------------------------------------------------------------------------

namespace protocolo
{
    enum TipoTrama : uint8_t
    {
        DATA = 0,
        ACK  = 1,
        FIN  = 2
    };

    // Tamaño máximo de payload por fragmento. Ajustar según lo que
    // acuerde el equipo (debe quedar por debajo del límite práctico de
    // un datagrama UDP, considerando cabeceras IP/UDP, para evitar
    // fragmentación a nivel de IP).
    constexpr std::size_t MAX_PAYLOAD = 1024;

    // Tamaño del encabezado en el cable (wire format), NO sizeof(struct):
    constexpr std::size_t TAM_HEADER_DATOS = 1 + 4 + 2; // tipo + seq + longitud
    constexpr std::size_t TAM_HEADER_ACK   = 1 + 4;     // tipo + seq

    // Representación "cómoda" en memoria de una trama DATA/FIN ya
    // deserializada (para usar en el código, no para enviar tal cual).
    struct EncabezadoDatos
    {
        uint8_t  tipo;      // DATA o FIN
        uint32_t seq;
        uint16_t longitud;  // bytes de payload
    };

    struct EncabezadoAck
    {
        uint8_t  tipo;      // siempre ACK
        uint32_t seq;
    };

    // --- Construcción (emisor) --------------------------------------------

    // Arma en 'salida' una trama DATA o FIN lista para enviar por el
    // socket. 'salida' se redimensiona automáticamente.
    // tipo debe ser DATA o FIN.
    void construirTramaDatos(TipoTrama tipo, uint32_t seq,
                              const uint8_t* payload, uint16_t longitud,
                              std::vector<uint8_t>& salida);

    // Arma en 'salida' una trama ACK lista para enviar por el socket.
    void construirTramaAck(uint32_t seq, std::vector<uint8_t>& salida);

    // --- Interpretación (receptor) ------------------------------------------

    // Lee solo el primer byte para saber qué tipo de trama llegó, sin
    // asumir todavía cuál de las dos formas de encabezado aplica.
    // Lanza std::runtime_error si el buffer viene vacío.
    TipoTrama leerTipo(const uint8_t* buffer, std::size_t len);

    // Interpreta 'buffer' (de tamaño 'len', tal como lo devolvió
    // UDPSocket::receiveFrom) como un encabezado DATA/FIN.
    // 'payload' queda apuntando dentro de 'buffer' (no se copia).
    // Devuelve false si 'len' es menor al tamaño mínimo esperado o si
    // 'longitud' no concuerda con los bytes realmente recibidos.
    bool parsearTramaDatos(const uint8_t* buffer, std::size_t len,
                            EncabezadoDatos& out, const uint8_t*& payload);

    // Interpreta 'buffer' como un encabezado ACK.
    bool parsearTramaAck(const uint8_t* buffer, std::size_t len, EncabezadoAck& out);

} // namespace protocolo

#endif // TRAMA_H
