import os
import subprocess

DIAS_CA = 1825

def _openssl(args):
    try:
        return subprocess.run(["openssl"] + args, check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"openssl {args[0]} falló:\n{e.stderr}") from e