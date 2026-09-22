#include "Trama.h"

#include <arpa/inet.h>
#include <stdexcept>
#include <cstring>

namespace protocolo
{

void construirTramaDatos(TipoTrama tipo, uint32_t seq,
                          const uint8_t* payload, uint16_t longitud,
                          std::vector<uint8_t>& salida)
{
    salida.resize(TAM_HEADER_DATOS + longitud);

    uint8_t* p = salida.data();

    p[0] = static_cast<uint8_t>(tipo);

    uint32_t seqRed = htonl(seq);
    std::memcpy(p + 1, &seqRed, sizeof(seqRed));

    uint16_t longitudRed = htons(longitud);
    std::memcpy(p + 5, &longitudRed, sizeof(longitudRed));

    if (longitud > 0)
    {
        std::memcpy(p + TAM_HEADER_DATOS, payload, longitud);
    }
}

// Builds an ACK frame in salida.
void construirTramaAck(uint32_t seq, std::vector<uint8_t>& salida)
{
    salida.resize(TAM_HEADER_ACK);

    uint8_t* p = salida.data();
    p[0] = static_cast<uint8_t>(ACK);

    uint32_t seqRed = htonl(seq);
    std::memcpy(p + 1, &seqRed, sizeof(seqRed));
}

TipoTrama leerTipo(const uint8_t* buffer, std::size_t len)
{
    if (len < 1)
    {
        throw std::runtime_error("Trama vacía: no se puede leer el tipo");
    }
    return static_cast<TipoTrama>(buffer[0]);
}

bool parsearTramaDatos(const uint8_t* buffer, std::size_t len,
                        EncabezadoDatos& out, const uint8_t*& payload)
{
    if (len < TAM_HEADER_DATOS)
    {
        return false;
    }

    out.tipo = buffer[0];

    uint32_t seqRed;
    std::memcpy(&seqRed, buffer + 1, sizeof(seqRed));
    out.seq = ntohl(seqRed);

    uint16_t longitudRed;
    std::memcpy(&longitudRed, buffer + 5, sizeof(longitudRed));
    out.longitud = ntohs(longitudRed);

    // The declared payload length must match the received datagram.
    if (len != TAM_HEADER_DATOS + out.longitud)
    {
        return false;
    }

    payload = (out.longitud > 0) ? (buffer + TAM_HEADER_DATOS) : nullptr;
    return true;
}

bool parsearTramaAck(const uint8_t* buffer, std::size_t len, EncabezadoAck& out)
{
    if (len != TAM_HEADER_ACK)
    {
        return false;
    }

    out.tipo = buffer[0];

    uint32_t seqRed;
    std::memcpy(&seqRed, buffer + 1, sizeof(seqRed));
    out.seq = ntohl(seqRed);

    return true;
}

} // namespace protocolo
