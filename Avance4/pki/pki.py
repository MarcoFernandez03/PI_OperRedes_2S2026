import os
import subprocess

DIAS_CA = 1825
DIAS_NODO = 365

#_openssl evita repetir el subprocess.run en cada comando. Recibe solo los argumentos y le antepone "openssl".
def _openssl(args):
    try:
        return subprocess.run(["openssl"] + args, check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"openssl {args[0]} falló:\n{e.stderr}") from e

# La función generar_ca genera una nueva autoridad certificadora (CA) para un equipo específico.
def generar_ca(equipo, directorio, cnf="ca-ext.cnf"):
    os.makedirs(directorio, exist_ok=True)
    key = os.path.join(directorio, f"ca-{equipo}.key")
    crt = os.path.join(directorio, f"ca-{equipo}.crt")

    if os.path.exists(key) or os.path.exists(crt):
        raise FileExistsError(f"Ya existe una CA para {equipo}")

    _openssl(["genpkey", "-algorithm", "RSA",
              "-pkeyopt", "rsa_keygen_bits:2048", "-out", key])
    os.chmod(key, 0o600)

    _openssl(["req", "-new", "-x509", "-key", key,
              "-config", cnf, "-extensions", "v3_ca",
              "-subj", f"/CN=CA-{equipo}/O={equipo}/C=CR",
              "-sha256", "-days", str(DIAS_CA), "-out", crt])

    _openssl(["verify", "-CAfile", crt, crt])
    return key, crt

def generar_nodo(equipo, isla, num_emisor, directorio, cnf="nodo-ext.cnf"):
    cn = f"AS{isla}-{num_emisor}"
    ca_key = os.path.join(directorio, f"ca-{equipo}.key")
    ca_crt = os.path.join(directorio, f"ca-{equipo}.crt")
    key = os.path.join(directorio, f"{cn}.key")
    csr = os.path.join(directorio, f"{cn}.csr")
    crt = os.path.join(directorio, f"{cn}.crt")

    if os.path.exists(key) or os.path.exists(crt):
        raise FileExistsError(f"Ya existe el nodo {cn}")

    _openssl(["genpkey", "-algorithm", "RSA",
              "-pkeyopt", "rsa_keygen_bits:2048", "-out", key])
    os.chmod(key, 0o600)

    _openssl(["req", "-new", "-key", key,
              "-subj", f"/CN={cn}/O={equipo}/C=CR", "-out", csr])

    _openssl(["x509", "-req", "-in", csr, "-CA", ca_crt, "-CAkey", ca_key,
              "-CAcreateserial", "-days", str(DIAS_NODO), "-sha256",
              "-extfile", cnf, "-extensions", "v3_nodo", "-out", crt])

    _openssl(["verify", "-CAfile", ca_crt, crt])
    return key, crt

 # ————————————————————————
if __name__ == "__main__":
    print(generar_nodo("SHELL", 65003, 17, "out"))