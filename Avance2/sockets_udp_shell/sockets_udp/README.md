# UDP Sockets

This module provides the UDP transport and frame serialization used by the
SHELL protocol. It sends sensor data from a Raspberry Pi to a Linux or macOS
server.

## Components

- `UDPSocket`: sends and receives UDP datagrams with an optional timeout.
- `protocolo::Trama`: builds and parses DATA, ACK, and FIN frames.
- `SyscallTransport`: sends DATA/FIN frames through the custom
  `send_sensor_data` kernel syscall. ACKs still use `UDPSocket`.
- `examples/`: file-transfer examples with and without the syscall.

Protocol framing is independent from the socket layer. Frames are serialized
manually to avoid struct padding and to use network byte order.

## Build

```bash
make
```

The build produces four example programs:

```text
ejemplo_emisor
ejemplo_receptor
ejemplo_emisor_syscall
ejemplo_receptor_syscall
```

## Basic example

Start the receiver:

```bash
./ejemplo_receptor 30000 output.txt
```

Send a file from the Raspberry Pi or another host:

```bash
./ejemplo_emisor <server_ip> 30000 input.txt
```

The sender fragments the file, waits for the matching ACK, and retransmits on
timeout. The receiver ignores duplicates and writes each fragment once.

## Frame format

```text
DATA / FIN                         ACK
+--------+--------+----------+     +--------+--------+
| type   | seq    | length   |     | type   | seq    |
| 1 byte | 4 bytes| 2 bytes  |     | 1 byte | 4 bytes|
+--------+--------+----------+     +--------+--------+
| payload (length bytes)     |
+----------------------------+
```

`type` is `0 = DATA`, `1 = ACK`, or `2 = FIN`. Multi-byte fields use network
byte order. The default payload limit is `1024` bytes.

## Syscall variant

The custom syscall creates, uses, and closes a kernel UDP socket for each
datagram, so it cannot receive ACKs on the same socket. The sender therefore
binds a regular UDP socket to a fixed local ACK port, and the receiver sends
ACKs to that port.

On the Raspberry Pi with the custom kernel running:

```bash
./ejemplo_emisor_syscall <server_ip> 30000 input.txt 41000
```

On the server:

```bash
./ejemplo_receptor_syscall 30000 output.txt 41000
```

`NUMERO_SYSCALL_SEND_SENSOR_DATA` in `include/SyscallTransport.h` must match
the number assigned in the kernel syscall table. The syscall variant can only
be validated on the Raspberry Pi running that custom kernel.
