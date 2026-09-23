import os
import shutil
import tempfile

from tabla_rutas import TablaRutas
from logica_rutas import procesar_announce, procesar_advertise, procesar_data

IP_A, IP_B, IP_C = '10.0.0.1', '10.0.0.2', '10.0.0.3'

lib_original = os.path.join(os.path.dirname(__file__), '..', 'memoria', 'libmemoria.so')

with tempfile.TemporaryDirectory() as directorio_libs:
	rutas_libs = []
	for nombre in ('A', 'B', 'C'):
		ruta = os.path.join(directorio_libs, f'libmemoria_{nombre}.so')
		shutil.copy2(lib_original, ruta)
		rutas_libs.append(ruta)

	tabla_A = TablaRutas(ruta_lib=rutas_libs[0])
	tabla_B = TablaRutas(ruta_lib=rutas_libs[1])
	tabla_C = TablaRutas(ruta_lib=rutas_libs[2])

	resultado = procesar_announce(IP_A, IP_B, tabla_B)
	assert resultado == IP_A, f'esperaba propagar {IP_A}, dio {resultado}'
	print(f'B aprende vecino directo A -> propaga ADVERTISE|{resultado}')

	resultado = procesar_announce(IP_C, IP_B, tabla_B)
	assert resultado == IP_C
	print(f'B aprende vecino directo C -> propaga ADVERTISE|{resultado}')

	assert tabla_B.buscar_siguiente_salto(IP_A) == IP_A
	assert tabla_B.buscar_siguiente_salto(IP_C) == IP_C
	print('tabla de B tras los ANNOUNCE:', tabla_B.todas_las_rutas())

	resultado = procesar_advertise(f'ADVERTISE|{IP_A}', IP_B, IP_C, tabla_C)
	print('DEBUG resultado:', repr(resultado), 'IP_A:', repr(IP_A))
	assert resultado == IP_A
	print(f'C aprende de B que existe A -> repropaga ADVERTISE|{resultado}')

	tabla_A.cerrar()
	tabla_B.cerrar()
	tabla_C.cerrar()