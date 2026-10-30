from talk_to_router import LOCAL_ROAS, ROAS_MUTEX, connect_to_router
import threading
import time

threading.Thread(target=connect_to_router).start();

while True:

  print("LEYENDO ROAS LOCALES:")
  #TODO: Revisar el acquire del mutex cuando se vaya a pedir el roa
  ROAS_MUTEX.acquire()
  for roa in LOCAL_ROAS:
    print(f"  {roa}")
  ROAS_MUTEX.release()