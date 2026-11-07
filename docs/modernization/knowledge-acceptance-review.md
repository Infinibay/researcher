# Fuentes, procedencia y vigencia del conocimiento: U01–U03

Inicio **2026-11-07 22:47:36 UTC**, base `f6f0630`.
Verificado **2026-11-07 23:04:16 UTC**, **16 min 40 s** desde el inicio hasta
verificar, sin documentación/checkpoint posteriores. Se cierran U01–U03 con el
alcance de esta matriz: **38/43 escenarios comprobados; cinco abiertos**.
El cierre se registra en [resultados](knowledge-acceptance-results.json). No se
declara una suite global verde: se conserva un fallo de fixture histórico y su
trabajo pendiente DD120, separado de los contratos de conocimiento.

## Cambio de producto

La búsqueda semántica ya recuperaba texto e identidad, pero omitía el estado,
tipo y atribución del hallazgo. Cada coincidencia incluye ahora `finding`, una
proyección acotada del mismo snapshot: proyecto, tarea, autor, fecha, estado,
tipo, confianza declarada, presencia de revisión y cantidad de citas.

Por ejemplo, encontrar «137 unidades» conserva `status=superseded` y
`finding_type=hypothesis` si esos son sus valores observados. La semejanza de la
consulta no los convierte en un hecho activo. `scientific_confidence` sigue
desconocida; una decisión registrada conserva `currentness=not_checked` hasta
leer y contrastar su sujeto. Los resultados no incluyen todo el cuerpo otra vez.

La proyección se construye fuera del encoder a partir del corpus actual. El
recibo reutilizable del worker contiene chunks y scores, no esta atribución;
reutilizar esos bytes para un texto idéntico no reutiliza metadatos viejos.
El cambio de estado durante el cálculo invalida el resultado antes de entregarlo.
No cambian migraciones, pesos, permisos, prompts, dependencias ni interfaz.

## Escenarios y evidencia

| Qué pasaría si… | Contrato comprobado |
| --- | --- |
| La web se lee pero falla guardar la evidencia | `ResearchService` adquiere y `SQLiteResearchStore` compromete fuente/recibo juntos. La aceptación nueva provoca un fallo real en la transacción: HTTP falla y no quedan filas. Recuperado el almacenamiento, la misma intención registra una sola captura/recibo, también ante retry. No se anuncia éxito antes del commit. |
| La misma URL cambia de 137 a 200 unidades | Capturas diferentes conservan IDs, hashes, fechas y texto separados. Repetir la intención original devuelve su captura de137. La lectura del dueño conserva la cita antigua y el estado superseded del hallazgo; no consulta la web actual ni reescribe el pasado. |
| La similitud recupera una hipótesis provisional o reemplazada | Cuatro casos nuevos recorren las API humana y de herramienta con ambos estados. Fallaban por ausencia de atribución y ahora conservan estado/tipo/autor, confianza declarada y revisión desconocida. La prueba de cambio durante consulta añade estado a texto/filas/permisos; rechaza la respuesta vieja. |
| Una cita o revisión perdió su evidencia | Las citas deben coincidir exactamente con la captura en el mismo proyecto. Los lectores verifican hash, muestran fuentes no disponibles y conservan declaraciones históricas como tales. El registro/revisión no se acredita por un rol, un número de confianza o una etiqueta `proof`. Los informes no importan hallazgos superseded o ajenos. |
| El cuerpo contiene contraevidencia al final | Capturas y lectores usan ventanas con offsets, hashes y continuaciones explícitas. El encoder offline considera todos los chunks del texto admitido; los casos reales recuperan texto tardío y páginas PDF. Un límite no se convierte en un recorte silencioso. |
| Cambian pesos, corpus o filtros entre páginas | Modelo, revisión, dimensión, hashes de assets y política de chunking identifican el productor. Un asset cambiado, fingerprint incorrecto o cobertura incompleta falla explícitamente. La continuación exige hashes de texto y metadatos; no combina versiones ni una muestra de los últimos500 registros. |
| Faltan assets o una fuente del buscador léxico falla | Semántica devuelve indisponibilidad sin sustituir silenciosamente el método. La búsqueda léxica conserva cobertura y errores por origen. Sólo un conjunto seleccionado y comprobado vacío se describe como `empty_scoped_set`; la ausencia de resultados no certifica que algo no exista. |
| Hay un escritor o se cancela mientras Ken prepara el índice | El propietario de `DevelopmentKen` serializa las consultas, exige cierre del escritor, compara contenido y cierra el MCP anterior antes de preparar otra revisión. Los ensayos actuales cubren código sin cambios, escritor activo y Stop durante reindexado, con kernel real y protocolo Ken controlado. |
| El índice publicado conserva una revisión anterior | El [ensayo real](knowledge-ken-revisions.json) usa `ken-rank==0.18.0` y el mismo directorio `.ken` para dos versiones del módulo sintético. Dos preparaciones y cuatro llamadas MCP recuperan el símbolo/valor actuales por semántica y lectura; el símbolo anterior no reaparece después del refresco. Se conservan los hashes y el cierre de todos los peers/dominio. |

Los lectores humanos actuales permiten abrir la cita, ver fecha/identidad y
distinguir texto capturado de una consulta al documento actual. Se inspeccionó
ese consumidor; no se presenta como otra auditoría visual ni como comprensión
humana demostrada. La aceptación de las doce páginas permanece separada.

## Verificación y fallo conservado

- RED: los cuatro casos de atribución semántica fallaron por ausencia de `finding`.
  Después del cambio pasan esos cuatro y cinco casos de invalidación concurrente:
  **nueve casos dirigidos**. Las dos aceptaciones de captura/transacción pasan.
- La selección instalada inicial conserva **210 casos correctos y un fallo** en
  [su recibo](knowledge-acceptance-initial-packaging.json). El fallo aplica
  inversa65 sobre el fixture actual68 antes de alcanzar su contrato histórico.
  El código de producto rechaza correctamente esa operación.
- DD120 registra ese caso y otro con la misma preparación observada por lectura,
  todavía no ejecutado. Se resolverán con prefijos reales en el cierre global;
  no se convierten en skips ni se debilita el producto. La selección de continuación
  declara expresamente esa exclusión y verifica los restantes contratos de
  recibos, presupuesto, cierre y permiso sobre el mismo artefacto.
- Los [675 archivos del paquete](knowledge-acceptance-artifact-comparison.json)
  coinciden con la fuente. Sólo cambia un módulo de producto y dos de pruebas.
  Los recibos instalados verifican también la instalación no editable y el origen
  de todos sus imports backend. Las selecciones solapadas no se suman.
- El ensayo Ken usa backend instalado, assets públicos ya preparados, fuentes
  sintéticas y procesos reales. El harness se conserva en
  `evals/security/run_ken_revisions.py`; reutiliza los transportes y preparación
  existentes con identidades distintas por operación. No usa una cuenta.

La continuación instalada terminó con **15 casos correctos, cero fallos y cero
skips**, en 7,713 segundos, en [su recibo](knowledge-continuation-packaging.json).
Las identidades JUnit de ambas selecciones son disjuntas y sus hashes de rueda
coinciden: **225 casos correctos y un fallo histórico pendiente**, no una selección
completa verde. Los 15 contratos nuevos/modificados, incluidos los helpers de
evaluación, tienen [docstrings en inglés](knowledge-acceptance-docstrings.json).
No se repite compilación web ni evaluación de prompts sin cambios en esos archivos.

## Límites

La captura HTTP nueva controla únicamente la adquisición web; almacenamiento,
transacciones, autorización y lecturas son reales. Los ensayos de encoder usan
pesos offline reales; las carreras de corpus usan un encoder controlado para
provocar el cambio exacto. Ken real comprueba un módulo y dos revisiones: no
certifica cobertura universal de lenguajes ni un escritor host hostil concurrente.

Las pruebas de snapshot/índice no validan científicamente las afirmaciones ni
demuestran comprensión humana. No hubo llamadas generativas, migración de datos
históricos, cambios visuales o evaluación global nueva. Los requisitos restantes
del plan conservan su alcance, incluidos DD120 y la revisión final independiente.
