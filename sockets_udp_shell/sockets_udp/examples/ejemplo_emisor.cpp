// ejemplo_emisor.cpp
//
// Sends a file from the Raspberry Pi in acknowledged UDP fragments.
//
// The same flow can be used with sensor data instead of a file.
//
// Usage: ./ejemplo_emisor <destination_ip> <destination_port> <input_file>

#include "UDPSocket.h"
#include "Trama.h"

#include <iostream>
#include <fstream>
#include <vector>
#include <cstdint>

namespace
{
    constexpr int TIMEOUT_SEG = 2;
    constexpr int MAX_REINTENTOS = 5;
}

// Sends one DATA/FIN frame and retries until its ACK arrives.
bool enviarFragmentoConfirmado(UDPSocket& socket, protocolo::TipoTrama tipo,
                                uint32_t seq, const uint8_t* datos, uint16_t longitud)
{
    std::vector<uint8_t> tramaSalida;
    protocolo::construirTramaDatos(tipo, seq, datos, longitud, tramaSalida);

    std::vector<uint8_t> bufferRespuesta(protocolo::TAM_HEADER_ACK);

    for (int intento = 0; intento < MAX_REINTENTOS; ++intento)
    {
        socket.send(tramaSalida.data(), tramaSalida.size());

        try
        {
            int recibidos = socket.receiveFrom(bufferRespuesta.data(), bufferRespuesta.size());

            protocolo::EncabezadoAck ack;
            if (protocolo::parsearTramaAck(bufferRespuesta.data(), recibidos, ack) && ack.seq == seq)
            {
                return true; // Expected ACK received.
            }
            // Ignore ACKs for a different sequence number.
        }
        catch (const SocketTimeoutException&)
        {
            std::cout << "Timeout esperando ACK de seq=" << seq
                      << " (intento " << (intento + 1) << "/" << MAX_REINTENTOS << "), retransmitiendo...\n";
        }
    }

    return false; // Retry limit reached.
}

int main(int argc, char* argv[])
{
    if (argc < 4)
    {
        std::cerr << "Uso: " << argv[0] << " <ip_destino> <puerto_destino> <archivo_entrada>\n";
        return 1;
    }

    std::string ipDestino = argv[1];
    unsigned short puertoDestino = static_cast<unsigned short>(std::stoi(argv[2]));
    std::string archivoEntrada = argv[3];

    try
    {
        UDPSocket socket;
        socket.setDestino(ipDestino, puertoDestino);
        socket.setTimeout(TIMEOUT_SEG);

        std::ifstream entrada(archivoEntrada, std::ios::binary);
        if (!entrada)
        {
            std::cerr << "No se pudo abrir el archivo de entrada: " << archivoEntrada << "\n";
            return 1;
        }

        std::vector<uint8_t> bufferLectura(protocolo::MAX_PAYLOAD);
        uint32_t seq = 0;

        while (true)
        {
            entrada.read(reinterpret_cast<char*>(bufferLectura.data()), bufferLectura.size());
            std::streamsize leidos = entrada.gcount();

            bool esUltimoFragmento = entrada.eof();
            protocolo::TipoTrama tipo = esUltimoFragmento ? protocolo::FIN : protocolo::DATA;

            bool confirmado = enviarFragmentoConfirmado(
                socket, tipo, seq, bufferLectura.data(), static_cast<uint16_t>(leidos));

            if (!confirmado)
            {
                std::cerr << "Fallo de conexión: no se confirmó el fragmento seq=" << seq << "\n";
                return 1;
            }

            std::cout << "Fragmento seq=" << seq << " confirmado (" << leidos << " bytes).\n";
            seq++;

            if (esUltimoFragmento)
            {
                std::cout << "Archivo transmitido por completo.\n";
                break;
            }
        }
    }
    catch (const SocketException& e)
    {
        std::cerr << "Error de socket: " << e.description() << "\n";
        return 1;
    }

    return 0;
}
