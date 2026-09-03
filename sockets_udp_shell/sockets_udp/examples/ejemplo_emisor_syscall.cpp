// ejemplo_emisor_syscall.cpp
//
// Versión del emisor que corre en el Raspberry Pi usando el kernel
// personalizado (Kernel/Image). A diferencia de ejemplo_emisor.cpp:
//
//   - El envío de DATA/FIN se hace con la syscall send_sensor_data
//     (enviarPorSyscall), NO con UDPSocket::send().
//   - La recepción de ACK sigue usando UDPSocket normal, pero bindeado
//     a un puerto FIJO conocido de antemano (PUERTO_ACK_LOCAL), porque
//     la syscall no deja ningún socket abierto para recibir respuestas
//     (crea uno, envía, y lo cierra en cada llamada -> puerto efímero
//     distinto cada vez, inútil para recibir).
//
// El servidor debe correr ejemplo_receptor_syscall (no ejemplo_receptor),
// que sabe contestar el ACK a PUERTO_ACK_LOCAL en vez de al puerto de
// origen que reporta recvfrom().
//
// Uso: ./ejemplo_emisor_syscall <ip_servidor> <puerto_servidor> <archivo_entrada> <puerto_ack_local>

#include "SyscallTransport.h"
#include "UDPSocket.h"
#include "Trama.h"

#include <iostream>
#include <fstream>
#include <vector>
#include <cstdint>
#include <cstdio>
#include <thread>
#include <chrono>

const int delayMinutes = 1;

namespace
{
    constexpr int TIMEOUT_SEG = 2;
    constexpr int MAX_REINTENTOS = 5;
}

bool enviarFragmentoConfirmado(UDPSocket& socketAck,
                                const std::string& ipServidor, unsigned short puertoServidor,
                                protocolo::TipoTrama tipo, uint32_t seq,
                                const uint8_t* datos, uint16_t longitud)
{
    std::vector<uint8_t> tramaSalida;
    protocolo::construirTramaDatos(tipo, seq, datos, longitud, tramaSalida);

    std::vector<uint8_t> bufferRespuesta(protocolo::TAM_HEADER_ACK);

    for (int intento = 0; intento < MAX_REINTENTOS; ++intento)
    {
        // --- Único cambio real respecto a ejemplo_emisor.cpp: ---
        // en vez de socket.send(...), se usa la syscall del kernel.
        enviarPorSyscall(tramaSalida.data(), tramaSalida.size(), ipServidor, puertoServidor);

        try
        {
            int recibidos = socketAck.receiveFrom(bufferRespuesta.data(), bufferRespuesta.size());

            protocolo::EncabezadoAck ack;
            if (protocolo::parsearTramaAck(bufferRespuesta.data(), recibidos, ack) && ack.seq == seq)
            {
                return true;
            }
        }
        catch (const SocketTimeoutException&)
        {
            std::cout << "Timeout esperando ACK de seq=" << seq
                      << " (intento " << (intento + 1) << "/" << MAX_REINTENTOS << "), retransmitiendo...\n";
        }
    }

    return false;
}

int main(int argc, char* argv[])
{
    if (argc < 5)
    {
        std::cerr << "Uso: " << argv[0]
                  << " <ip_servidor> <puerto_servidor> <archivo_entrada> <puerto_ack_local>\n";
        return 1;
    }

    std::string ipServidor = argv[1];
    unsigned short puertoServidor = static_cast<unsigned short>(std::stoi(argv[2]));
    std::string archivoEntrada = argv[3];
    unsigned short puertoAckLocal = static_cast<unsigned short>(std::stoi(argv[4]));
    while (true){
        std::this_thread::sleep_for(std::chrono::minutes(delayMinutes));
        try
        {
            // Este UDPSocket NO se usa para enviar: solo escucha los ACK que
            // devuelve el servidor, en un puerto fijo conocido de antemano.
            UDPSocket socketAck;
            socketAck.bind(puertoAckLocal);
            socketAck.setTimeout(TIMEOUT_SEG);

            std::ifstream entrada(archivoEntrada, std::ios::binary);
            if (!entrada)
            {
                std::cerr << "No se pudo abrir el archivo de entrada: " << archivoEntrada << "\n";
                
            } else {

                std::vector<uint8_t> bufferLectura(protocolo::MAX_PAYLOAD);
                uint32_t seq = 0;

                std::cout << "Enviando por syscall a " << ipServidor << ":" << puertoServidor
                        << ", escuchando ACK en el puerto local " << puertoAckLocal << "...\n";

                while (true)
                {
                    entrada.read(reinterpret_cast<char*>(bufferLectura.data()), bufferLectura.size());
                    std::streamsize leidos = entrada.gcount();

                    bool esUltimoFragmento = entrada.eof();
                    protocolo::TipoTrama tipo = esUltimoFragmento ? protocolo::FIN : protocolo::DATA;

                    bool confirmado = enviarFragmentoConfirmado(
                        socketAck, ipServidor, puertoServidor,
                        tipo, seq, bufferLectura.data(), static_cast<uint16_t>(leidos));

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
                        // Borrar archivo de entrada tras enviarlo
                        if (std::remove(archivoEntrada.c_str()) == 0) {
                            std::cout << "Archivo borrado: " << archivoEntrada << "\n";
                        } else {
                            std::cerr << "No se pudo borrar el archivo: " << archivoEntrada << "\n";
                        }
                        break;
                    }
                }
            }
        }
        catch (const SocketException& e)
        {
            std::cerr << "Error: " << e.description() << "\n";
            return 1;
        }
    }
    return 0;
}
