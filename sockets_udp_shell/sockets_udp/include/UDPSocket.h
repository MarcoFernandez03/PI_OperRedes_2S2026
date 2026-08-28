#ifndef UDP_SOCKET_H
#define UDP_SOCKET_H

#include <string>
#include <cstddef>
#include <cstdint>
#include <netinet/in.h>
#include "SocketException.h"

// ---------------------------------------------------------------------------
// UDPSocket
// ---------------------------------------------------------------------------
// Envoltorio (wrapper) en C++ sobre un socket UDP crudo (SOCK_DGRAM).
//
// A diferencia de ClientSocket/ServerSocket del ejemplo TCP, aquí NO existe
// el concepto de "conexión" ni de accept(): un único objeto UDPSocket puede
// tanto enviar como recibir datagramas hacia/desde cualquier dirección.
//
// Esta clase es intencionalmente "tonta": no sabe nada del protocolo de
// tramas (DATA/ACK/FIN, números de secuencia, retransmisión, etc). Eso se
// implementa en una capa aparte (ver Trama.h y la lógica de emisor/receptor
// del equipo), que usa este socket únicamente para:
//   - enviar bytes a una IP:puerto destino
//   - recibir bytes desde cualquier IP:puerto, con un timeout configurable
//
// Esa separación es justamente la que comentaban en el chat: el socket no
// depende del protocolo, el protocolo se apoya en el socket.
// ---------------------------------------------------------------------------
class UDPSocket
{
public:
    // Crea el socket UDP (llama a socket(AF_INET, SOCK_DGRAM, 0)).
    // Lanza SocketException si falla.
    UDPSocket();

    // Cierra el descriptor si sigue abierto.
    ~UDPSocket();

    // No tiene sentido copiar un socket (el descriptor es un recurso único).
    UDPSocket(const UDPSocket&) = delete;
    UDPSocket& operator=(const UDPSocket&) = delete;

    // Permite moverlo (útil si se quiere devolver por valor, meterlo en un
    // vector, etc.)
    UDPSocket(UDPSocket&& otro) noexcept;
    UDPSocket& operator=(UDPSocket&& otro) noexcept;

    // ---- Configuración -----------------------------------------------

    // Asocia el socket a un puerto local para poder RECIBIR datagramas
    // en ese puerto (típico en el receptor / servidor).
    // ip_local: "0.0.0.0" para escuchar en todas las interfaces.
    void bind(unsigned short puerto, const std::string& ip_local = "0.0.0.0");

    // Define un timeout para las llamadas a receiveFrom()/receive().
    // Es la base para implementar el timeout de espera de ACK que pide
    // el protocolo (TIMEOUT_SEG). Si expira, receiveFrom() lanza
    // SocketTimeoutException (ver más abajo) para que la capa superior
    // decida retransmitir.
    void setTimeout(int segundos, int microsegundos = 0);

    // Fija un "destino por defecto" para poder usar send() sin repetir
    // host/puerto en cada llamada (típico en el emisor, que siempre le
    // habla al mismo receptor).
    void setDestino(const std::string& host, unsigned short puerto);

    // ---- Envío ----------------------------------------------------------

    // Envía 'len' bytes al destino fijado previamente con setDestino().
    // Devuelve la cantidad de bytes enviados.
    int send(const void* datos, std::size_t len) const;

    // Envía 'len' bytes a un host:puerto específico (sin necesidad de
    // haber llamado setDestino()).
    int sendTo(const void* datos, std::size_t len,
               const std::string& host, unsigned short puerto) const;

    // ---- Recepción --------------------------------------------------------

    // Recibe hasta 'maxLen' bytes en 'buffer'. Si se configuró un timeout
    // con setTimeout() y no llega nada a tiempo, lanza SocketTimeoutException.
    // Devuelve la cantidad de bytes efectivamente recibidos.
    // Si se pasan 'ipOrigen'/'puertoOrigen' (no nulos), se llenan con la
    // dirección de quien envió el datagrama (imprescindible en el receptor,
    // para poder contestar el ACK al remitente correcto).
    int receiveFrom(void* buffer, std::size_t maxLen,
                     std::string* ipOrigen = nullptr,
                     unsigned short* puertoOrigen = nullptr) const;

    // Cierra el socket explícitamente (el destructor también lo hace).
    void close();

    int descriptor() const { return m_fd; }

private:
    int m_fd;
    sockaddr_in m_destino{};
    bool m_tieneDestino;
};

// Excepción específica para cuando expira el timeout de recepción.
// Hereda de SocketException para poder capturarla junto con las demás
// si no interesa distinguir el caso, o por separado para implementar
// la lógica de reintentos (MAX_REINTENTOS) del protocolo.
class SocketTimeoutException : public SocketException
{
public:
    SocketTimeoutException() : SocketException("Timeout esperando datos") {}
};

#endif // UDP_SOCKET_H
