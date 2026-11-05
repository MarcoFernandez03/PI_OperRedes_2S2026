from talk_to_router import LOCAL_ROAS, ROAS_MUTEX, connect_to_router
import threading
import time

# Call when a new announcement is received with (IP, ISLA)
def validar_anuncio(ip, isla):

  ROAS_MUTEX.acquire()
  roa = LOCAL_ROAS.get(ip)
  ROAS_MUTEX.release()
  if roa is None or roa[1] < time.time():
    return "UNKNOWN"   # Accepted
  if roa[0] == isla:
    return "VALID"     # Accepted
  print(f"ANUNCIO INVALIDO: {ip} anunciado por isla {isla}, ROA dice {roa[0]}")
  return "INVALID"     # descarded

def leer_roas():
  threading.Thread(target=connect_to_router, daemon=True).start();
  while True:

    print("LEYENDO ROAS LOCALES:")
    ROAS_MUTEX.acquire()
    for ip, (isla, vence) in LOCAL_ROAS.items():
      print(f"  {ip} -> isla {isla}, vence {vence}")
    ROAS_MUTEX.release()
    time.sleep(5)