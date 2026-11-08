# Regresión del código actual — 8 de noviembre de 2026

La ejecución sobre `d278653` quedó **incompleta**: 2.050 casos aprobaron y 25
fallaron. Se interrumpió de forma controlada antes del límite de 30 minutos del
ejecutor para conservar diagnósticos, JUnit y limpieza de fixtures. Pytest registró
28 min 26 s; el controlador, 28 min 28 s. No hubo cambios de código durante la
ejecución. [Recibo y fallos originales](global-regression-2026-11-08.json).

La colección completa contiene **2.568 casos**. Los 493 restantes terminaron en
otro proceso: 491 aprobados, un fallo de inversa histórica y un error de fixture
del recorrido de terminal, en 5 min 28 s. Las 705 fuentes, tests y recursos
comprobados conservaron sus hashes. En conjunto: **2.541 aprobados, 26 fallidos,
un error y cero omisiones**. Son dos procesos; ese recorrido completa cobertura
por casos, pero no acredita el orden ni las interacciones de una única suite global.
El último resultado global completo sigue siendo el de `9fb873c`; no hay una
nueva validación global verde.

## Tratamiento por grupos

| Grupo | Casos fallidos | Evidencia y siguiente comprobación |
| --- | ---: | --- |
| Frontera de persistencia API | 3 | El observador antiguo no ve la escritura y los hijos no terminan en el commit esperado. La creación ahora delega en `OwnerPlanningRecords`; comprobar el punto de observación sobre la transacción real, conservando las exigencias de atomicidad y respuesta de health/WebSocket. |
| Inversas históricas | 6 | Las inversas de política de checks y retención rechazan esquemas posteriores. Preparar prefijos históricos coherentes y conservar el rechazo de versiones futuras e historia utilizada. No debilitar esas guardas. |
| Revisiones y checks compuestos | 9 | Se exceden los 20 segundos de la prueba. Reproducir un caso dirigido con diagnóstico; un timeout no demuestra por sí solo bloqueo del producto ni autoriza ampliar todos los límites. |
| Stop frente a escritura contendida | 1 | Falla la observación esperada. Verificar primero que el test alcanza el escritor y la cancelación que pretende medir. |
| Lector de roster retirado | 1 | El test intenta esperar con `await` una respuesta síncrona. Contrastar el contrato actual antes de corregir su consumidor. |
| Fixture del evaluador | 1 | El servicio controlado no produce el único archivo de emparejamiento requerido y no llega al fallo de escenario buscado. Corregir la preparación del fixture sin relajar el control de procedencia. |
| Proyecciones e inicio del servicio | 2 | Los estados cambian a `reconciling` al abrir el lifespan. Separar recuperación de inicio y lecturas posteriores antes de atribuir la mutación a una consulta o archivo de conversación. |
| Identidad del endpoint | 1 | Cambiar una variable de entorno después del inicio conserva la identidad. Comprobar el reemplazo físico de la base fijada por el servicio; cambiar configuración no demuestra ese reemplazo. |
| Fixture del planificador | 2 | La fixture emite `researcher_plan_deliver`; el test todavía espera `researcher_plan_propose`. Contrastar y conservar el contrato de procedencia y entrega actual. |

El error restante ocurre durante la preparación de fixtures del recorrido de
terminal; ese caso todavía no acredita su comportamiento. El cuerpo del error
queda conservado en JUnit. No se atribuye a la lógica del terminal antes de
resolver su preparación y ejecutar sus aserciones.

Estos grupos orientan la investigación; **no declaran corregidos los fallos** ni
clasifican automáticamente todos como problemas de tests. Se conservarán los
resultados originales y se aplicarán cambios solo después de contrastar cada
causa con sus productores y consumidores.

## Integridad del recibo y del proceso

JUnit añadió una entrada anónima al interrumpirse. El parser inicial la contó
incorrectamente como aprobada. El recibo normalizado excluye esa entrada y
reconcilia las 2.075 identidades completas contra la colección original: 2.050
aprobadas, 25 fallidas, cero errores y cero omisiones. Los logs y JSON iniciales
se conservan sin modificar; no se presenta la entrada incompleta como un pase.

Se usó CPython 3.12.9 con las fuentes del repositorio, no una suite completa del
wheel instalado. La configuración de pytest está en `pyproject.toml`: sockets
externos bloqueados por defecto, Unix permitido y límites individuales acotados.
Las fixtures locales poseen sus excepciones. El entorno de proveedores se retiró;
los assets locales de recuperación se indicaron explícitamente. Los controladores
cpu/memory/pids se conservaron y la cuota del ejecutor fue de ocho CPU.

Para las siguientes ejecuciones largas, registrar los identificadores de cada
caso en el log privado y conservar un cierre gradual antes del límite del
controlador. El log anterior de puntos ocultaba qué caso estaba activo; el tramo
restante usa salida detallada. Esta mejora de observación no modifica aserciones
ni límites del producto.
