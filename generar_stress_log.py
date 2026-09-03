#!/usr/bin/env python3
"""
Genera un motion_log.txt gigante, con el mismo formato que produce
sensor.py, para hacer stress test del syscall / transporte UDP.

Formato de cada línea (idéntico al de sensor.py):
    Motion detected! dd.Mmm YYYY HH:MM:SS

Uso:
    python3 generar_stress_log.py --lines 5000000
    python3 generar_stress_log.py --mb 500
    python3 generar_stress_log.py --lines 1000000 --out mi_log.txt --start-jump 2

Notas de diseño:
- Escribe en bloques (buffer) en vez de línea por línea para que generar
  el archivo no se vuelva el cuello de botella (evita miles de syscalls
  write() propios de Python mientras generás datos de prueba).
- Los timestamps avanzan de forma monótona y realista (separados por
  --start-jump segundos, con jitter opcional) en vez de repetir "ahora"
  millones de veces, por si el receptor/reensamblador llega a validar orden.
- --mb genera hasta alcanzar (al menos) ese tamaño en megabytes; --lines
  genera un número exacto de líneas. Si das ambos, --lines manda.
"""

import argparse
import random
from datetime import datetime, timedelta

LINE_TEMPLATE = "Motion detected! {}\n"
FMT = "%d.%b %Y %H:%M:%S"
BUFFER_LINES = 50_000  # líneas por flush a disco


def generar(path, n_lines=None, target_mb=None, start_jump=2, jitter=0, seed=None):
    if seed is not None:
        random.seed(seed)

    t = datetime.now()
    written_lines = 0
    written_bytes = 0
    target_bytes = int(target_mb * 1024 * 1024) if target_mb else None

    with open(path, "w") as f:
        buf = []
        while True:
            if n_lines is not None and written_lines >= n_lines:
                break
            if target_bytes is not None and written_bytes >= target_bytes:
                break

            line = LINE_TEMPLATE.format(t.strftime(FMT))
            buf.append(line)
            written_lines += 1
            written_bytes += len(line)

            step = start_jump
            if jitter:
                step += random.randint(-jitter, jitter)
                step = max(step, 0)
            t += timedelta(seconds=step)

            if len(buf) >= BUFFER_LINES:
                f.write("".join(buf))
                buf.clear()

        if buf:
            f.write("".join(buf))

    return written_lines, written_bytes


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--lines", type=int, default=None, help="Cantidad exacta de líneas a generar")
    ap.add_argument("--mb", type=float, default=None, help="Tamaño objetivo aproximado del archivo en MB")
    ap.add_argument("--out", type=str, default="motion_log.txt", help="Archivo de salida (default: motion_log.txt)")
    ap.add_argument("--start-jump", type=int, default=2, help="Segundos entre lecturas consecutivas (default: 2)")
    ap.add_argument("--jitter", type=int, default=0, help="Variación aleatoria +/- segundos sobre start-jump")
    ap.add_argument("--seed", type=int, default=None, help="Semilla para reproducibilidad del jitter")
    args = ap.parse_args()

    if args.lines is None and args.mb is None:
        # Default: 1,000,000 líneas si no se especifica nada
        args.lines = 1_000_000

    lines, size = generar(
        args.out,
        n_lines=args.lines,
        target_mb=args.mb,
        start_jump=args.start_jump,
        jitter=args.jitter,
        seed=args.seed,
    )

    print(f"Listo: {args.out}")
    print(f"  Líneas escritas: {lines:,}")
    print(f"  Tamaño: {size / (1024*1024):.2f} MB")


if __name__ == "__main__":
    main()
