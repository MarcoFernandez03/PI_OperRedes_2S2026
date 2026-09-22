// ejemplo_receptor.cpp
//
// Receives acknowledged DATA/FIN fragments and reconstructs a file.
//
// Usage: ./ejemplo_receptor <listen_port> <output_file>

#include "UDPSocket.h"
#include "Trama.h"

#include <iostream>
#include <fstream>
#include <vector>
#include <cstdint>
#include <cstdlib>

int main(int argc, char* argv[])
{
    srand(time(NULL));
    if (argc < 3)
    {
        std::cerr << "Uso: " << argv[0] << " <puerto> <archivo_salida>\n";
        return 1;
    }

    unsigned short puerto = static_cast<unsigned short>(std::stoi(argv[1]));
    std::string archivoSalida = argv[2];

    try
    {
        UDPSocket socket;
        socket.bind(puerto);

        std::ofstream salida(archivoSalida, std::ios::binary | std::ios::trunc);
        if (!salida)
        {
            std::cerr << "No se pudo abrir el archivo de salida: " << archivoSalida << "\n";
            return 1;
        }

        std::cout << "Receptor escuchando en el puerto " << puerto << "...\n";

        uint32_t seqEsperado = 0;
        uint32_t ultimoSeqConfirmado = 0; // Resend this ACK for duplicates.
        bool huboAlMenosUnFragmento = false;

        std::vector<uint8_t> buffer(protocolo::TAM_HEADER_DATOS + protocolo::MAX_PAYLOAD);
        std::vector<uint8_t> bufferAck;

        while (true)
        {
            std::string ipOrigen;
            unsigned short puertoOrigen;

            // The receiver blocks; timeout and retransmission are sender tasks.
            int recibidos = socket.receiveFrom(buffer.data(), buffer.size(), &ipOrigen, &puertoOrigen);

            // Simulate packet loss.
            int probabilidadPerdida = (std::rand() % 100) + 1;
            if (probabilidadPerdida <= 30){
                std::cout << "Paquete perdido por simulación \n";
                continue;
            }

            protocolo::EncabezadoDatos encabezado;
            const uint8_t* payload = nullptr;

            if (!protocolo::parsearTramaDatos(buffer.data(), recibidos, encabezado, payload))
            {
                std::cerr << "Trama inválida recibida, se ignora.\n";
                continue;
            }

            if (encabezado.seq == seqEsperado)
            {
                // New in-order fragment: write and acknowledge it.
                if (encabezado.longitud > 0)
                {
                    salida.write(reinterpret_cast<const char*>(payload), encabezado.longitud);
                }
                ultimoSeqConfirmado = encabezado.seq;
                huboAlMenosUnFragmento = true;

                protocolo::construirTramaAck(encabezado.seq, bufferAck);
                socket.sendTo(bufferAck.data(), bufferAck.size(), ipOrigen, puertoOrigen);

                std::cout << "Fragmento seq=" << encabezado.seq
                          << " (" << encabezado.longitud << " bytes) recibido y confirmado.\n";

                seqEsperado++;
            }
            else
            {
                // Duplicate or out-of-order fragment: do not write it again.
                std::cout << "Fragmento duplicado/fuera de orden seq=" << encabezado.seq
                          << " (esperado=" << seqEsperado << "), se reenvía ACK.\n";

                if (huboAlMenosUnFragmento)
                {
                    protocolo::construirTramaAck(ultimoSeqConfirmado, bufferAck);
                    socket.sendTo(bufferAck.data(), bufferAck.size(), ipOrigen, puertoOrigen);
                }
            }

            if (encabezado.tipo == protocolo::FIN && encabezado.seq == ultimoSeqConfirmado)
            {
                std::cout << "Trama FIN procesada. Cerrando archivo y terminando recepción.\n";
                break;
            }
        }

        salida.close();
    }
    catch (const SocketException& e)
    {
        std::cerr << "Error de socket: " << e.description() << "\n";
        return 1;
    }

    return 0;
}
