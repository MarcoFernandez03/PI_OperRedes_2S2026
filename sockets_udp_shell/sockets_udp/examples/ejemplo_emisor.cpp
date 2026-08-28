// ejemplo_emisor.cpp
//
// Corre en el Raspberry Pi (cliente). Lee un archivo, lo divide en
// fragmentos de hasta MAX_PAYLOAD bytes y los envía uno por uno,
// esperando el ACK correspondiente antes de continuar, con timeout
// y reintentos, siguiendo el flujo del emisor descrito en el protocolo.
//
// En el proyecto real, en vez de leer un archivo, este mismo patrón de
// envío se usaría con los datos que entrega el sensor a través de la
// syscall que están implementando; la parte de sockets es idéntica.
//
// Uso: ./ejemplo_emisor <ip_destino> <puerto_destino> <archivo_entrada>

#include "UDPSocket.h"
#include "Trama.h"

#include <iostream>
#include <fstream>
#include <vector>
#include <cstdint>

namespace
{
    constexpr int TIMEOUT_SEG = 2;      // según el protocolo: 2 a 3 segundos
    constexpr int MAX_REINTENTOS = 5;   // ajustar según lo acordado por el equipo
}

// Envía un fragmento (DATA o FIN) y espera su ACK, reintentando ante
// timeout. Devuelve true si se confirmó, false si se agotaron los
// reintentos (fallo de conexión).
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
                return true; // ACK esperado recibido
            }
            // ACK con seq distinto al esperado: se ignora y se sigue
            // esperando (o se agota el intento actual por timeout).
        }
        catch (const SocketTimeoutException&)
        {
            std::cout << "Timeout esperando ACK de seq=" << seq
                      << " (intento " << (intento + 1) << "/" << MAX_REINTENTOS << "), retransmitiendo...\n";
        }
    }

    return false; // se agotaron los reintentos -> fallo de conexión
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
