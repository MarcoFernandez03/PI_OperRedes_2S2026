// ejemplo_receptor_syscall.cpp
//
// Igual que ejemplo_receptor.cpp, con un solo cambio importante: el ACK
// no se contesta al puerto de origen que reporta receiveFrom() (ese es el
// puerto efímero que la syscall del kernel usó y ya cerró), sino a un
// puerto FIJO del Raspberry Pi, acordado de antemano (el mismo
// PUERTO_ACK_LOCAL con el que el emisor bindeó su socketAck en
// ejemplo_emisor_syscall.cpp).
//
// La IP sí se toma del datagrama recibido (ipOrigen), porque esa sigue
// siendo la IP real del Raspberry Pi; lo único que no sirve es el puerto.
//
// Uso: ./ejemplo_receptor_syscall <puerto_escucha> <archivo_salida> <puerto_ack_pi>

#include "UDPSocket.h"
#include "Trama.h"

#include <iostream>
#include <fstream>
#include <vector>
#include <cstdint>
#include <cstdlib>
#include <thread>
#include <chrono>
#include <time.h>

int main(int argc, char* argv[])
{
    srand(time(NULL));
    if (argc < 4)
    {
        std::cerr << "Uso: " << argv[0] << " <puerto_escucha> <archivo_salida> <puerto_ack_pi>\n";
        return 1;
    }

    unsigned short puerto = static_cast<unsigned short>(std::stoi(argv[1]));
    std::string archivoSalida = argv[2];
    unsigned short puertoAckPi = static_cast<unsigned short>(std::stoi(argv[3]));
    while (true){
        
        try
        {
            UDPSocket socket;
            socket.bind(puerto);

            std::ofstream salida(archivoSalida, std::ios::binary | std::ios::app);
            if (!salida)
            {
                std::cerr << "No se pudo abrir el archivo de salida: " << archivoSalida << "\n";
                return 1;
            }

            std::cout << "Receptor escuchando en el puerto " << puerto
                    << " (los ACK se contestarán al puerto fijo " << puertoAckPi << " del Pi)...\n";

            uint32_t seqEsperado = 0;
            uint32_t ultimoSeqConfirmado = 0;
            bool huboAlMenosUnFragmento = false;

            std::vector<uint8_t> buffer(protocolo::TAM_HEADER_DATOS + protocolo::MAX_PAYLOAD);
            std::vector<uint8_t> bufferAck;

            while (true)
            {
                std::string ipOrigen;
                unsigned short puertoOrigenIgnorado; // no se usa: ver comentario arriba

                int recibidos = socket.receiveFrom(buffer.data(), buffer.size(), &ipOrigen, &puertoOrigenIgnorado);
                
                // Simulación de perdida de paquetes
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
                    if (encabezado.longitud > 0)
                    {
                        salida.write(reinterpret_cast<const char*>(payload), encabezado.longitud);
                    }
                    ultimoSeqConfirmado = encabezado.seq;
                    huboAlMenosUnFragmento = true;

                    protocolo::construirTramaAck(encabezado.seq, bufferAck);
                    // Clave: se contesta a (ipOrigen, puertoAckPi), NO a
                    // (ipOrigen, puertoOrigenIgnorado).
                    socket.sendTo(bufferAck.data(), bufferAck.size(), ipOrigen, puertoAckPi);

                    std::cout << "Fragmento seq=" << encabezado.seq
                            << " (" << encabezado.longitud << " bytes) recibido y confirmado.\n";

                    seqEsperado++;
                }
                else
                {
                    std::cout << "Fragmento duplicado/fuera de orden seq=" << encabezado.seq
                            << " (esperado=" << seqEsperado << "), se reenvía ACK.\n";

                    if (huboAlMenosUnFragmento)
                    {
                        protocolo::construirTramaAck(ultimoSeqConfirmado, bufferAck);
                        socket.sendTo(bufferAck.data(), bufferAck.size(), ipOrigen, puertoAckPi);
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
    }
    return 0;
}
