# PKI y firma de ROA (Puntos A y B)

Módulo de certificados digitales y registros ROA del proyecto integrador (Etapa 3, RPKI).
Cubre:

- **Punto A:** CA raíz del grupo, certificados de nodos emisores, truststore compartido y validación de la cadena de confianza.
- **Punto B:** formato, firma y verificación de los registros ROA.

Ubicación en el repositorio: `Avance4/pki/`

---

## Índice

1. [Idea general](#1-idea-general)
2. [Requisitos](#2-requisitos)
3. [Estructura de archivos](#3-estructura-de-archivos)
4. [Uso rápido](#4-uso-rápido)
5. [Referencia de la API](#5-referencia-de-la-api)
6. [Formato del ROA y firma](#6-formato-del-roa-y-firma)
7. [Cómo se valida un ROA](#7-cómo-se-valida-un-roa)
8. [Decisiones de interfaz](#8-decisiones-de-interfaz)
9. [Guía de integración para los demás módulos](#9-guía-de-integración-para-los-demás-módulos)
10. [Seguridad](#10-seguridad)
11. [Pruebas](#11-pruebas)
12. [Limitaciones y pendientes](#12-limitaciones-y-pendientes)
13. [Problemas frecuentes](#13-problemas-frecuentes)

---

## 1. Idea general

Un **ROA** (Route Origin Authorization) es un registro que dice: *"la IP X pertenece a la isla (sistema autónomo) Y"*. Para que un enrutador pueda confiar en él sin confiar en el repositorio que lo guarda, el ROA va **firmado** y el certificado de quien firma está respaldado por una **CA**.

La PKI es **plana, de un solo nivel**: la CA raíz de cada grupo firma directamente los certificados de sus nodos, sin CA intermedias.

```
  CA raíz del grupo (ca-SHELL.crt)         <- autofirmada, es el "trust anchor"
        │  firma
        ▼
  Certificado del nodo (AS65003-17.crt)    <- CN = AS<ISLA>-<NUM_EMISOR>
        │  su llave privada firma
        ▼
  ROA|10.1.0.5|65003|17|1792957052|1792960652|<firma base64>
```

Flujo de punta a punta:

```
[Una vez]    generar_ca() + generar_nodo()        -> archivos .key / .crt
                     │
[Cada 60 s]  crear_roa()  (usa AS65003-17.key)    -> línea ROA firmada
                     │
                     ▼
              Repositorio (P2)  ──►  Enrutador (P3)
                                          │
                  verificar_roa(linea, cert, raices)
                  (cert viene del comando CERT; raices del truststore)
```

---

## 2. Requisitos

| Requisito | Detalle |
|---|---|
| Python | 3.9 o superior |
| `cryptography` | **42 o superior** (se usan `not_valid_before_utc` / `not_valid_after_utc`) |
| `openssl` | En el `PATH`. Solo lo usan `generar_ca` y `generar_nodo` |

```bash
pip install -U cryptography
openssl version
```

---

## 3. Estructura de archivos

```
Avance4/pki/
├── pki.py            # Punto A: CA, nodos, validación de cadena, transporte de certificados
├── roa.py            # Punto B: crear, parsear, firmar y verificar ROAs
├── truststore.py     # Punto A: construcción del trusted-roots.pem con huellas
├── ca-ext.cnf        # Extensiones X.509 de la CA (sección [ v3_ca ])
├── nodo-ext.cnf      # Extensiones X.509 de los nodos (sección [ v3_nodo ])
├── test_pki.py       # Pruebas (casos válidos y de ataque)
├── fingerprints.txt  # Tabla de huellas SHA-256 de las raíces confiables
├── trust-anchors/    # ca-<Equipo>.crt de todos los grupos (públicos)
└── out/              # Salida generada (llaves, certificados, truststore). NO subir a git
```

### Archivos de configuración

`ca-ext.cnf`:

```ini
[ v3_ca ]
basicConstraints = critical, CA:TRUE, pathlen:0
keyUsage = critical, keyCertSign, cRLSign
subjectKeyIdentifier = hash
```

`nodo-ext.cnf`:

```ini
[ v3_nodo ]
basicConstraints = critical, CA:FALSE
keyUsage = critical, digitalSignature
```

---

## 4. Uso rápido

Todos los ejemplos se corren desde `Avance4/pki/`.

### 4.1 Crear la CA raíz del grupo (una sola vez)

```python
import pki
llave, cert = pki.generar_ca("SHELL", "out")
# -> out/ca-SHELL.key  (privada, permisos 600)
# -> out/ca-SHELL.crt  (pública, se comparte)
```

Si la CA ya existe lanza `FileExistsError`. Esto es intencional: regenerar la CA invalida todos los certificados de nodo ya emitidos.

### 4.2 Emitir el certificado de un nodo emisor

```python
import pki
llave, cert = pki.generar_nodo("SHELL", 65003, 17, "out")
# -> out/AS65003-17.key / .csr / .crt     (CN = AS65003-17)
```

Vigencia: 365 días. La función verifica el certificado contra la CA antes de devolver.

### 4.3 Construir el truststore

1. Poner en `trust-anchors/` los `ca-<Equipo>.crt` de todos los grupos.
2. Anotar en `fingerprints.txt` las huellas que cada grupo anunció **por un canal alterno** (chat del curso):

   ```
   # huellas anunciadas por chat
   ca-SHELL B1:F8:0D:E2:...:06:51
   ca-OTRO  00:A5:AF:FB:...:95:40
   ```

   Para obtener la huella propia:

   ```bash
   openssl x509 -in out/ca-SHELL.crt -noout -fingerprint -sha256
   ```

3. Generar el bundle:

   ```python
   from truststore import actualizar_truststore
   aceptadas, rechazadas = actualizar_truststore(
       "trust-anchors", "fingerprints.txt", "out/trusted-roots.pem")
   print(aceptadas)    # ['ca-SHELL']
   print(rechazadas)   # [('ca-FALSO', 'no tiene huella registrada'), ...]
   ```

### 4.4 Firmar un ROA

```python
from roa import crear_roa
linea = crear_roa("10.1.0.5", 65003, 17, "out/AS65003-17.key", vigencia=3600)
# 'ROA|10.1.0.5|65003|17|1792957052|1792960652|NmHFAr6B...'
```

### 4.5 Verificar un ROA

```python
import pki
from roa import verificar_roa

raices = pki.cargar_truststore("out/trusted-roots.pem")
cert = pki.cert_desde_b64(cert_b64)      # cert_b64 viene del comando CERT

ok, motivo = verificar_roa(linea, cert, raices)
if not ok:
    print("ROA descartado:", motivo)
```

---

## 5. Referencia de la API

### `pki.py`

| Función | Descripción |
|---|---|
| `generar_ca(equipo, directorio, cnf="ca-ext.cnf") -> (ruta_key, ruta_crt)` | Crea la CA raíz. Subject = Issuer = `CN=CA-<equipo>, O=<equipo>, C=CR`. RSA-2048, SHA-256, 1825 días. Llave con permisos `0600`. Verifica la autofirma. Lanza `FileExistsError` si ya existe. |
| `generar_nodo(equipo, isla, num_emisor, directorio, cnf="nodo-ext.cnf") -> (ruta_key, ruta_crt)` | Crea llave, CSR y certificado del nodo, firmado por la CA que esté en `directorio`. CN = `AS<isla>-<num_emisor>`. 365 días. Verifica contra la CA. Lanza `FileExistsError` si el nodo ya existe. |
| `cargar_truststore(ruta) -> list[Certificate]` | Lee un `.pem` con una o varias raíces concatenadas. |
| `cert_a_b64(cert) -> str` | Certificado -> DER -> base64 en **una sola línea** (formato de `CERT\|...`). |
| `cert_desde_b64(texto) -> Certificate` | Inversa de la anterior. Lanza `ValueError` si el base64 es inválido. |
| `validar_cadena(cert, raices, ahora=None) -> (bool, motivo)` | Valida nodo -> raíz (ver sección 7.1). |
| `_ext_raiz_ok(cert)`, `_ext_nodo_ok(cert)` | Internas: comprueban las extensiones críticas. |
| `_openssl(args)` | Interna: ejecuta `openssl` y relanza `RuntimeError` con el `stderr` si falla. |

### `roa.py`

| Función | Descripción |
|---|---|
| `cargar_llave(ruta) -> PrivateKey` | Lee una llave privada PEM sin contraseña. |
| `crear_roa(ip, isla, num_emisor, ruta_llave, vigencia, ahora=None) -> str` | Construye y firma el ROA. `vigencia` en segundos. `ahora` (opcional) permite fijar la hora en pruebas. Lanza `ValueError` si la IP es inválida. |
| `parsear_roa(linea) -> dict` | Valida 7 campos e IP. Devuelve `ip, isla, num_emisor, emision, vence, firma, mensaje`. Lanza `ValueError`. |
| `verificar_firma(roa, cert) -> bool` | Verifica solo la firma de un ROA ya parseado. |
| `verificar_roa(linea, cert, raices, ahora=None) -> (bool, motivo)` | **Función principal.** Encadena los pasos 1 a 6 de la validación. |

### `truststore.py`

| Función | Descripción |
|---|---|
| `huella(cert) -> str` | SHA-256 del certificado, en hexadecimal minúscula sin `:`. |
| `cargar_huellas(ruta) -> dict` | Lee `fingerprints.txt` como `{nombre: huella}`. Ignora líneas vacías y comentarios (`#`). |
| `actualizar_truststore(carpeta, ruta_huellas, destino) -> (aceptadas, rechazadas)` | Filtra las raíces por huella y extensiones, y escribe el bundle de forma atómica. Si ninguna raíz es aceptable, **no modifica** el destino existente. |

---

## 6. Formato del ROA y firma

### Formato

Una línea de texto con 7 campos separados por `|`:

```
ROA|IP|ISLA|NUM_EMISOR|EMISION|VENCE|FIRMA
```

| Campo | Tipo | Significado |
|---|---|---|
| `ROA` | texto fijo | Tipo de registro |
| `IP` | IPv4 | Dirección que se autoriza |
| `ISLA` | entero | Sistema autónomo autorizado a anunciarla (ej. 65003) |
| `NUM_EMISOR` | entero | Nodo de esa isla que firma |
| `EMISION` | segundos Unix UTC | Inicio de validez |
| `VENCE` | segundos Unix UTC | Fin de validez |
| `FIRMA` | base64, una línea | Firma RSA del texto anterior |

### Qué se firma

El texto **exacto** desde `ROA` hasta `VENCE`, **sin** el `|` final ni salto de línea:

```
ROA|10.1.0.5|65003|17|1792957052|1792960652
```

- Algoritmo: RSA-2048 con SHA-256, padding PKCS#1 v1.5.
- Llave: la del **nodo emisor**, nunca la de la CA.
- La firma (256 bytes) en base64 ocupa 344 caracteres; el ROA completo mide ~388 y cabe en un bloque de 512 bytes del repositorio.

> Un solo byte distinto en el texto firmado hace fallar la verificación. Es la causa más común de fallos de interoperabilidad entre grupos.

### Comprobación manual con OpenSSL

La firma es compatible con OpenSSL, así que otros grupos pueden verificarla sin Python:

```bash
printf '%s' 'ROA|10.1.0.5|65003|17|1792957052|1792960652' > msg.txt
echo '<FIRMA_BASE64>' | base64 -d > sig.bin
openssl x509 -in AS65003-17.crt -pubkey -noout > pub.pem
openssl dgst -sha256 -verify pub.pem -signature sig.bin msg.txt
# Verified OK
```

(Usar `printf` o `echo -n`: un salto de línea final cambia el mensaje y la firma no verifica.)

---

## 7. Cómo se valida un ROA

### 7.1 Cadena del certificado (`validar_cadena`)

Basado en RFC 5280 (sección 6). Como la PKI es plana, la cadena es solo nodo -> raíz.

1. El certificado del nodo está dentro de su vigencia.
2. Las extensiones del nodo son correctas y críticas: `CA:FALSE` y `digitalSignature`.
3. Existe en el truststore una raíz cuyo `subject` es el `issuer` del nodo.
4. La raíz está dentro de su vigencia y tiene `CA:TRUE` y `keyCertSign` (críticas).
5. La firma del certificado del nodo verifica con la llave pública de esa raíz.

Si hay varias raíces con el mismo nombre, prueba cada una antes de rechazar.

### 7.2 El ROA (`verificar_roa`)

Se ejecuta en este orden y se detiene en el primer fallo:

| # | Comprobación | Motivo si falla |
|---|---|---|
| 1 | Siete campos, empieza con `ROA`, IP válida, números válidos | `formato inválido: ...` |
| 2 | `EMISION <= ahora <= VENCE` | `ROA fuera de su rango EMISION-VENCE` |
| 3 | Cadena del certificado válida (7.1) | `certificado no válido: <motivo>` |
| 4 | `CN` del certificado == `AS<ISLA>-<NUM_EMISOR>` del ROA | `CN ... no coincide con ...` |
| 5 | `VENCE <= notAfter` del certificado | `VENCE es posterior al notAfter del certificado` |
| 6 | La firma verifica con la llave pública del certificado | `la firma no verifica` |

El paso 4 es el que impide que un nodo legítimo firme ROAs a nombre de otra isla: el certificado de `AS65003-17` no sirve para un ROA de `AS65004`.

### 7.3 Lo que NO hace este módulo (paso 7 del diseño)

La comprobación del **anuncio de ruta** (que la IP y la isla del `ADVERTISE` coincidan con el ROA, y que `VENCE` siga vigente *en ese instante*) la hace el enrutador (Punto E), porque ocurre al evaluar un anuncio y no al validar el ROA. Resultado esperado:

| Resultado | Condición | Decisión |
|---|---|---|
| VALID | Hay un ROA para esa IP con esa isla | Aceptar |
| INVALID | Hay un ROA para esa IP a nombre de **otra** isla | Descartar |
| UNKNOWN | No hay ROA para esa IP | Aceptar |

---

## 8. Decisiones de interfaz

Puntos que el documento de diseño no fija del todo y que se resolvieron así. **Deben acordarse con todo el equipo y con los otros grupos** para que interoperen.

| Tema | Decisión |
|---|---|
| Formato de `<cert_b64>` en `HELLO`/`CERT` | **DER en base64, una sola línea** (`cert_a_b64`/`cert_desde_b64`). El PEM no sirve porque tiene saltos de línea y el protocolo es de una línea por mensaje. |
| Resultado de las validaciones | Tupla `(bool, motivo)`. El diseño exige registrar el motivo del descarte. |
| Hora | Segundos Unix UTC. Todas las funciones aceptan `ahora` opcional para pruebas. |
| Nombre de archivos de nodo | `AS<ISLA>-<NUM_EMISOR>.key/.csr/.crt`, igual que el CN. |
| Nombre de archivos de CA | `ca-<Equipo>.key/.crt`. |
| Tabla de huellas | `fingerprints.txt`, una línea `nombre huella` por raíz. |

---

## 9. Guía de integración para los demás módulos

### Repositorio (P2: puntos C y D)

```python
import pki

# Responder al comando CERT|<num_emisor>:
respuesta = "OK|" + pki.cert_a_b64(cert_del_nodo)

# Validar el certificado que llega en HELLO|OWNER|<id>|<cert_b64>:
cert = pki.cert_desde_b64(cert_b64)            # ValueError si viene mal formado
ok, motivo = pki.validar_cadena(cert, raices)  # si no ok -> ERR_PERMISO

# Validar un ROA recibido en PUT (formato, vigencia y firma):
from roa import verificar_roa
ok, motivo = verificar_roa(linea, cert, raices)
```

El `owner` se identifica con el CN del certificado (`AS<ISLA>-<NUM>`). Al guardar el ROA conviene comprobar que su `NUM_EMISOR` coincide con el del `HELLO`.

### Enrutador (P3: punto E)

```python
import pki
from roa import verificar_roa

raices = pki.cargar_truststore("/etc/rpki/truststore/trusted-roots.pem")

# Por cada línea ROA de LIST (fuera de la sección crítica):
cert = pki.cert_desde_b64(respuesta_de_CERT)
ok, motivo = verificar_roa(linea, cert, raices)
if ok:
    tabla_nueva.append(linea)
else:
    log(f"ROA descartado: {motivo}")
```

Recomendación: pedir `CERT` una sola vez por `NUM_EMISOR` por ciclo y reutilizar el certificado para todos los ROAs de ese emisor.

### Nodo emisor / receptor (P4: integración)

```python
from roa import crear_roa

# Firmar una vez:
linea = crear_roa(ip, isla, num_emisor, "AS65003-17.key", vigencia=3600)

# Cada 60 s: reenviar la MISMA línea con PUT (no volver a firmar).
# Cuando queden < 300 s de vigencia: crear_roa() de nuevo y PUT para reemplazarlo.
```

> `crear_roa` **no** limita `vigencia` al `notAfter` del certificado. El nodo debe elegir `vigencia` de modo que `emision + vigencia <= notAfter`; si no, `verificar_roa` rechazará el ROA (paso 5).

---

## 10. Seguridad

- **Las llaves privadas (`*.key`) nunca se suben a git ni salen de su máquina.** La llave de la CA solo debe existir en la máquina de quien firma certificados. Agregar al `.gitignore`:

  ```
  *.key
  *.srl
  out/
  ```

- Las llaves se crean con permisos `0600` (solo lectura/escritura del dueño).
- Los `.crt` y `.csr` son públicos; los `.crt` de `trust-anchors/` sí pueden versionarse.
- La confianza se establece por **huella verificada por un canal alterno**, no por estar el archivo en una carpeta compartida. Una raíz sin huella registrada o con huella distinta se rechaza.
- El truststore se reescribe con archivo temporal + `os.replace` (atómico): ningún proceso lee un bundle incompleto.
- La CA tiene `pathlen:0` y `keyCertSign`/`cRLSign`: no puede firmar otras CA ni ROAs. El nodo tiene `CA:FALSE` y solo `digitalSignature`.
- Un ROA mal formado, con firma o base64 inválidos, o con campos no numéricos se rechaza con motivo; no lanza excepciones al llamador de `verificar_roa`.

---

## 11. Pruebas

```bash
python3 test_pki.py
```

Casos cubiertos (todos deben imprimir `PASA`):

| Caso | Resultado esperado |
|---|---|
| ROA válido | Aceptado |
| ROA vencido | Rechazado: fuera de rango EMISION-VENCE |
| ROA aún no emitido | Rechazado: fuera de rango EMISION-VENCE |
| Isla falsa (CN no coincide) | Rechazado: CN no coincide |
| `VENCE` posterior a `notAfter` | Rechazado |
| Campo alterado (IP cambiada) | Rechazado: la firma no verifica |
| Formato malo (`ROA\|1\|2`) | Rechazado: formato inválido |
| Certificado de una CA no confiable | Rechazado: emisor no está en el truststore |
| Certificado del nodo vencido | Rechazado: fuera de vigencia |
| `cert_a_b64` / `cert_desde_b64` | Una sola línea y ida y vuelta sin pérdida |

Para aislar el caso del **certificado vencido** (y que no lo tape el rango del ROA), crear el ROA con una hora futura y verificar con esa misma hora:

```python
f = time.time() + 400*86400
verificar_roa(crear_roa("10.1.0.5", 65003, 17, llave, 3600, f), cert, raices, f + 10)
# (False, 'certificado no válido: certificado del nodo fuera de vigencia')
```

Inspección manual de un certificado:

```bash
openssl x509 -in out/AS65003-17.crt -noout -subject -issuer -dates -ext basicConstraints,keyUsage
openssl verify -CAfile out/ca-SHELL.crt out/AS65003-17.crt
```

---

## 12. Limitaciones y pendientes

- **Sin revocación:** no hay CRL ni OCSP. Un certificado comprometido sigue siendo válido hasta su vencimiento o hasta retirarlo a mano del truststore.
- **Sin RFC 3779:** la autorización isla-IP se comprueba con el CN, según el diseño.
- **`generar_nodo` hace todo en una máquina** (llave, CSR y firma de la CA). Pendiente: separarlo en (a) generar llave + CSR en cada nodo y (b) firmar una CSR recibida, para que ninguna llave privada de nodo viaje.
- **Republicación y renovación de ROAs** (reenviar cada 60 s, firmar uno nuevo cuando queden < 5 min) es lógica del nodo emisor; este módulo solo aporta `crear_roa`.
- **Llaves sin contraseña:** simplifica el despliegue en el laboratorio, pero en un entorno real deberían protegerse.
- **Interoperabilidad con otros grupos** sin probar aún: formato de `cert_b64`, formato de `fingerprints.txt` y orden de campos deben confirmarse con ellos.

---

## 13. Problemas frecuentes

| Síntoma | Causa probable | Solución |
|---|---|---|
| `AttributeError: ... has no attribute 'not_valid_after_utc'` | `cryptography` < 42 | `pip install -U cryptography` |
| `FileExistsError: Ya existe una CA/nodo ...` | La CA o el nodo ya estaban generados | Es intencional. Borrar los archivos solo si se acepta invalidar lo ya emitido |
| `RuntimeError: openssl req falló` | Falta el `.cnf` o la sección no existe | Ejecutar desde `Avance4/pki/` o pasar `cnf=` con la ruta correcta |
| `la firma no verifica` en un ROA recién creado | Se modificó el texto, se agregó un `\n` o `\|` extra, o el certificado no corresponde a esa llave | Verificar con el certificado del **mismo** nodo que firmó |
| `emisor no está en el truststore` | La raíz no está en `trusted-roots.pem` o su huella fue rechazada | Revisar `fingerprints.txt` y la lista `rechazadas` de `actualizar_truststore` |
| `CN ... no coincide con ...` | El ROA declara una isla/emisor distinto al del certificado | El certificado debe ser el del `AS<ISLA>-<NUM_EMISOR>` del ROA |
| `import cryptography` falla o se comporta raro | Un archivo o carpeta del proyecto se llama `cryptography`/`ssl` | Renombrarlo (no usar nombres de librerías) |
| `FileNotFoundError` con `ca-ext.cnf` | Se ejecutó desde otra carpeta | Correr desde `Avance4/pki/` |