// ejemplo_receptor.cpp
//
// Corre en la computadora Linux/Mac que actúa como servidor.
// Escucha en un puerto UDP, recibe fragmentos DATA/FIN en orden
// (usando seq_esperado), los escribe a un archivo de salida y
// confirma cada uno con un ACK, siguiendo el flujo del receptor
// descrito en el protocolo del equipo.
//
// Uso: ./ejemplo_receptor <puerto> <archivo_salida>

#include "UDPSocket.h"
#include "Trama.h"

#include <iostream>
#include <fstream>
#include <vector>
#include <cstdint>

int main(int argc, char* argv[])
{
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
        uint32_t ultimoSeqConfirmado = 0; // para reenviar el ACK si llega una retransmisión
        bool huboAlMenosUnFragmento = false;

        std::vector<uint8_t> buffer(protocolo::TAM_HEADER_DATOS + protocolo::MAX_PAYLOAD);
        std::vector<uint8_t> bufferAck;

        while (true)
        {
            std::string ipOrigen;
            unsigned short puertoOrigen;

            // Nota: aquí NO se usa setTimeout() -> receiveFrom() bloquea
            // indefinidamente hasta que llega algo. El timeout/retransmisión
            // es responsabilidad del EMISOR, no del receptor.
            int recibidos = socket.receiveFrom(buffer.data(), buffer.size(), &ipOrigen, &puertoOrigen);

            protocolo::EncabezadoDatos encabezado;
            const uint8_t* payload = nullptr;

            if (!protocolo::parsearTramaDatos(buffer.data(), recibidos, encabezado, payload))
            {
                std::cerr << "Trama inválida recibida, se ignora.\n";
                continue;
            }

            if (encabezado.seq == seqEsperado)
            {
                // Fragmento nuevo y en orden: se escribe y se confirma.
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
                // No coincide con lo esperado: se asume una retransmisión de
                // un fragmento ya procesado. No se vuelve a escribir; solo
                // se reenvía el último ACK confirmado.
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
