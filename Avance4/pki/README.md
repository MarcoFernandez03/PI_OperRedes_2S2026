# PERSONA UNO — GABO

> **Resumen de lo que tengo que hacer   :** Punto A - Certificados  y Punto B — ROA 

---

## PUNTO A — CERTIFICADOS (PKI)

Una CA raíz es una llave y un certificado autofirmado que dice “yo soy la autoridad de confianza”.Cada nodo emisor tiene su propia llave y un certificado firmado por la CA que dice “yo soy AS65003-17”. (Punto A)
Un ROA es una línea de texto que dice “la IP 10.1.0.5 pertenece a la isla 65003”, firmada con la llave del nodo. Un enrutador recibe un ROA, verifica la firma con el certificado del nodo y verifica que ese certificado lo firmó una CA de confianza. Si todo cuadra, confía en el ROA. (Punto B)

* **Objetivo Principal:** Implementar un script que automáticamente haga certificados para los CA usando openssl y luego otro script que firme los ROA. 
* **Objetivos Clave:**
* PUNTO A:
  * [ ] Generar la CA raíz (ca-<Equipo>.key y .crt).
  * [ ] Generar la llave y el certificado de cada nodo emisor.
  * [ ] Un script que arme el trusted-roots.pem verificando las huellas.
  * [ ] Una función que valide la cadena nodo -> raíz.
* PUNTO B:
  * [ ] Una función que cree un ROA (los 7 campos, con firma).
  * [ ] Una función que verifique un ROA (los 7 pasos del documento).

---

## Brainstorming
