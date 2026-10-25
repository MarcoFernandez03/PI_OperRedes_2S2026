import os
import subprocess

DIAS_CA = 1825


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