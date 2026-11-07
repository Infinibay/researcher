# Exportación histórica de Chroma: aislamiento del lector

Base `68fd706`. Bloque **09:51:10–10:11:03 UTC**, **19 min 53 s** hasta el corte
de validación, el 7 de noviembre de 2026. Se implementó y comprobó la barrera del
lector. La seguridad integral, Ken/ONNX y las licencias siguen pendientes.

## Problema y resultado

El exportador ya conservaba una copia cruda y abría otra copia para permitir
migraciones de formato. Sin embargo, importaba Chroma en el proceso del operador:
la dependencia podía observar su entorno, otros archivos y la red. El plazo
cooperativo del bucle no detenía un bloqueo dentro de `PersistentClient`.

Ahora sólo se carga Chroma en un proceso con namespaces separados de red,
montajes y procesos. Bubblewrap es obligatorio y no hay fallback sin aislamiento.
El hijo recibe el entorno limpio, entrada estándar cerrada y sólo las rutas
necesarias: intérprete/bibliotecas de confianza, script fijado mediante descriptor,
copia de lectura y salida temporal. El original y las credenciales quedan fuera.

El padre controla el plazo y termina el grupo original si no concluye. El lector
limita espacio de direcciones, CPU, archivos y descriptores. Antes de promover
la salida, el padre exige archivos regulares acotados y un recibo válido; no sigue
enlaces creados por la dependencia. El punto de entrada interno comprueba que se
hayan cambiado los namespaces para evitar su invocación accidental sin la barrera.
Esta comprobación es de uso correcto, no autenticación contra el operador que
puede modificar el programa o su entorno.

Una interrupción conserva `source/`, la copia parcial y `reader.log`; no produce
un manifiesto que declare completada la exportación ni inicia otro intento.
La importación sigue validando identidades, cantidades, archivos, hashes y
asignación explícita de cada colección a un proyecto.

## Pruebas observadas

Las seis pruebas finales de la barrera pasan, sin omisiones:

- Una dependencia controlada intenta leer un archivo y entorno sintéticos,
  acceder al original y conectar con un servidor local del host. Todos quedan
  inaccesibles; el original y el archivo de prueba conservan sus bytes.
- La entrada estándar también queda cerrada. La primera implementación todavía
  la heredaba: una prueba reprodujo la exposición y luego pasó con `DEVNULL`.
- Un lector bloqueado termina por el plazo del padre y conserva una copia parcial.
- Un enlace en la salida, creado al terminar el hijo, no hace que el padre lea
  un archivo del host ni publique un manifiesto completo.
- Sin bubblewrap, se rechaza antes de crear la exportación. El punto de entrada
  interno también rechaza una invocación accidental sin namespaces nuevos.
- Chroma1.5.9 real exporta105 registros de dos colecciones, incluidos texto,
  metadatos y un registro sin texto, sin cambiar los hashes de los originales.

El conjunto con pruebas del importador tuvo **20 aprobadas y1 fallo histórico**.
`test_chroma_fragments_keep_exact_text_identity_and_explicit_project` espera el
mensaje `imported history`, pero la inversión rechaza primero el esquema59 más
nuevo. El mismo caso figura en [la suite global anterior](current-global-results.json).
El backend y esa prueba no cambiaron en este bloque. No se declara suite verde.

La comprobación completa final usa el backend **instalado**, fuera de imports
del checkout: exporta, migra el esquema17 a59, conserva105 registros y104 adjuntos
textuales, y consulta una fuente por HTTP con su procedencia histórica. El registro
sin texto no se convierte en un documento inventado; el metadato `project_id` no
reemplaza la asignación del operador. Cero turnos de modelo y cero aceptación o
publicación de resultados. El servicio original terminó con salida143.

Se conservaron dos ensayos previos y el ensayo final, después de las correcciones.
El último registra y verifica el hash exacto del exportador. Los dos primeros
intentos de preparar pruebas tuvieron problemas de fixture: sockets deshabilitados
y un intérprete copiado sin su biblioteca compartida. No cuentan como reproducción
válida. La reproducción posterior sí observó acceso al entorno/original/red y un
lector que ignoraba el plazo. Los recibos permanecen en el directorio privado.

[Resultados y límites](chroma-isolation-results.json),
[exportación/importación final](chroma-isolation-import.json).
Las19 definiciones relevantes tienen docstrings;11 avisos de estilo van aDD089.
El lock de Chroma y el inventario de83 decisiones de prompts se verificaron.
No fue necesario reconstruir el wheel: el cambio productivo es el exportador
separado; el backend instalado conserva el paquete comprobado en el bloque anterior.

## Vulnerabilidades y alcance que permanece abierto

Se volvieron a auditar ambos locks. Ken conserva19 entradas/12IDs en ONNX1.20.1;
Chroma conserva5 entradas/4IDs. Ambos auditores devolvieron1 por hallazgos y ningún
paquete omitido. No se excluyó un aviso para obtener un resultado limpio.
[Auditorías y hashes](chroma-isolation-advisories.json).

La metadata publicada de [ken-rank](https://pypi.org/pypi/ken-rank/json) sigue en
0.18.0 y exige ONNX1.20.1; [ONNX](https://pypi.org/pypi/onnx/json) publica1.23.2.
Cambiar esa dependencia por la fuerza no satisface la distribución actual de Ken.
Hace falta comprobar una distribución coherente con el pin corregido. La fuente
local y el paquete publicado no se modificaron ni se publicó otra versión.

[Chroma1.5.9](https://pypi.org/pypi/chromadb/json) sigue siendo la versión publicada
consultada. El [aviso sobre configuración de modelos](https://github.com/advisories/GHSA-f4j7-r4q5-qw2c)
describe un endpoint de servidor y no enumera versión corregida. El exportador
usa `get_collection(..., embedding_function=None)`, no ese servidor ni la
propiedad que construye una función de embeddings desde configuración. Esto
acota la ruta revisada; no prueba ausencia general de vulnerabilidades de lectura.
[Metadata consultada](chroma-isolation-upstream.json).

Quedan fuera de esta comprobación una cuota agregada de disco, límites de cgroup
para el árbol completo y modificaciones hostiles concurrentes del origen durante
el snapshot. No se cambia su precondición de escritores detenidos. La migración
de datos históricos del propietario sigue pendiente de localizar esos datos;
el ensayo usa datos sintéticos. Licencias, seguridad restante y aceptación del
conjunto siguen abiertas; los avisos de estilo se atienden al final.
