#ifndef SYSCALL_TRANSPORT_H
#define SYSCALL_TRANSPORT_H

#include <cstddef>
#include <string>

// ---------------------------------------------------------------------------
// SyscallTransport
// ---------------------------------------------------------------------------
// Wrapper for the custom send_sensor_data kernel syscall.
//
// It only sends DATA/FIN frames; ACKs still use a regular UDPSocket.
//
// It requires the custom kernel to be running on the Raspberry Pi.
// ---------------------------------------------------------------------------

// Must match the number assigned in the custom kernel syscall table.
constexpr long NUMERO_SYSCALL_SEND_SENSOR_DATA = 470;

// Sends len bytes through send_sensor_data. Throws SocketException on failure.
void enviarPorSyscall(const void* datos, std::size_t len,
                       const std::string& host, unsigned short puerto);

#endif // SYSCALL_TRANSPORT_H
