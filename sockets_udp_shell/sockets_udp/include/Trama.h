#ifndef TRAMA_H
#define TRAMA_H

#include <cstdint>
#include <cstddef>
#include <vector>

// ---------------------------------------------------------------------------
// Serialization of protocol frames.
//
// Frames are built manually instead of sending a struct directly.
//
// Padding and endianness can vary across platforms.
//
// This avoids compiler padding and ensures network byte order.
// ---------------------------------------------------------------------------

namespace protocolo
{
    enum TipoTrama : uint8_t
    {
        DATA = 0,
        ACK  = 1,
        FIN  = 2
    };

    // Maximum payload size per fragment.
    constexpr std::size_t MAX_PAYLOAD = 1024;

    // Header sizes on the wire, not sizeof(struct).
    constexpr std::size_t TAM_HEADER_DATOS = 1 + 4 + 2; // type + seq + length
    constexpr std::size_t TAM_HEADER_ACK   = 1 + 4;     // type + seq

    // In-memory representations of decoded frames.
    struct EncabezadoDatos
    {
        uint8_t  tipo;      // DATA or FIN
        uint32_t seq;
        uint16_t longitud;  // Payload bytes.
    };

    struct EncabezadoAck
    {
        uint8_t  tipo;      // Always ACK.
        uint32_t seq;
    };

    // --- Frame construction -----------------------------------------------

    // Builds a DATA or FIN frame in salida.
    void construirTramaDatos(TipoTrama tipo, uint32_t seq,
                              const uint8_t* payload, uint16_t longitud,
                              std::vector<uint8_t>& salida);

    // Builds an ACK frame in salida.
    void construirTramaAck(uint32_t seq, std::vector<uint8_t>& salida);

    // --- Frame parsing -----------------------------------------------------

    // Reads the frame type. Throws std::runtime_error for an empty buffer.
    TipoTrama leerTipo(const uint8_t* buffer, std::size_t len);

    // Parses a DATA/FIN frame. payload points into buffer and is not copied.
    // Returns false when the frame length is invalid.
    bool parsearTramaDatos(const uint8_t* buffer, std::size_t len,
                            EncabezadoDatos& out, const uint8_t*& payload);

    // Parses an ACK frame.
    bool parsearTramaAck(const uint8_t* buffer, std::size_t len, EncabezadoAck& out);

} // namespace protocolo

#endif // TRAMA_H
