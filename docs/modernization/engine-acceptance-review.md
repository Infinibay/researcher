# Aceptación del loop y auditoría de inferencia — E07/E08

Base `294943d`. Bloque **2026-11-07 16:18:09–16:30:03 UTC**, **11 min 54 s
hasta validar**. La documentación y el checkpoint posteriores no se incluyen.

**E07 queda completo en el contrato del plan. E08 continúa abierto**, con un
pendiente concreto: presupuesto durable acumulado de auxiliares locales por
proyecto. No se declara aceptación global del producto.

## Qué pasaría si el engine sigue activo sin avanzar

| Caso del plan | Comportamiento comprobado |
| --- | --- |
| Sólo llegan notas o razonamiento | El plazo sin progreso vence aunque sigan llegando eventos. El caso con hijo real y50notas conserva estado fallido, explicación y consumo desconocido; no propone ni acepta un resultado. |
| Una revisión pide cambios | La nueva variante hace que el revisor controlado proponga `needs_revision` mediante las herramientas reales. Candidato, validación Git, SQLite, broker y cierre son reales. La revisión queda confirmada y la tarea sin aceptar. Tres pasadas posteriores del dispatcher conservan exactamente dos runs y dos dispatches, sin trabajadores ni grants vivos. |
| Una revisión pierde validez al confirmar | La propuesta original permanece; el resultado se clasifica sin confirmar y no autoriza aceptación. |
| Se busca esconder un rechazo con otra revisión favorable | Se conserva la objeción confirmada del mismo candidato. La historia permite64antecedentes y bloquea65de forma explícita. |
| Una entrega termina o el propietario la detiene | El dispatcher no repite una entrega ya intentada ni libera dependientes sin aceptación vigente. Stop pausa el grafo y el reinicio no lo repone automáticamente. Continuar exige una decisión nueva. |
| Se agota tiempo, herramientas, salida o tokens observados | La sesión se interrumpe; las llamadas del host reservan cupo antes de ejecutar la herramienta. Se mantienen límites y consumo acumulado entre observaciones/turnos. |

Los generadores de estas pruebas son dobles controlados. Prueban el control del
producto, incluyendo su dueño físico, y no la calidad de una revisión generada
por un modelo real. Los mecanismos antiguos de think/rework ilimitado fueron
retirados; no se conserva un loop equivalente fuera del dueño nuevo.

## Qué pasaría si se consume fuera del presupuesto mostrado

La inspección de289archivos Python de producto encuentra una entrada propia
`turn/start`. El servicio comparte la reserva transaccional para investigación,
planificación, desarrollo y sus revisiones. Las pruebas comprueban rechazo antes
del despacho, contención por el último cupo, máximo acumulado sin devolución por
telemetría vieja, consumo desconocido tras reiniciar y refrescos acotados sin
fallback ni replay. La edición web del presupuesto conserva sus pruebas previas
y recibos; no se volvió a implementar ni se repitió su recorrido visual.

El inventario anterior confundía estado histórico con implementación actual.
Se reemplazó por el [mapa actual](../architecture/inference-inventory.md), con
rutas retiradas, límites y exclusiones explícitas. El stub de warmup sigue
presente, pero rechaza antes de HTTP y no es una ruta de generación activa.
Las seis familias de SDK/proveedores antiguos examinadas no están instaladas en
el entorno verificado. La inspección AST no prueba ausencia de cualquier import
dinámico, llamada transitiva o ejecución externa de otra instalación.

**Pendiente funcional E08:** `semantic.py` devuelve lotes/vectores/recursos, y
`source_query` devuelve esa observación después de comprobar autoridad. El
agregador `project_work_usage` suma sólo `runtime_inference_dispatches`. Por eso
falta reservar y conservar el trabajo auxiliar local por operación/intento/
proyecto, con cupo compartido entre acceso humano y agente. Los límites actuales
de worker/servicio y la plaza compartida son útiles, pero no crean esa cuota.

El próximo bloque debe cubrir reserva antes del trabajo, concurrencia por el
último cupo, respuesta perdida/reinicio sin borrar consumo, medición desconocida,
cancelación/cierre físico y lectura por el propietario. Mantener unidades
locales separadas de tokens generativos. Incluir semántica y delimitar extracción
documental; no introducir un cliente LLM para implementar la contabilidad.

## Evidencia y correcciones del ensayo

- Tres variantes del recorrido de revisión pasan desde fuente; son un
  subconjunto de las91pruebas del paquete instalado, no94casos distintos.
- **91pasan,0fallan,0omitidas** desde directorio externo al checkout, con sockets
  bloqueados salvo Unix y credenciales sintéticas. Se comprueban248módulos
  backend importados de la instalación y629archivos iguales entre fuente,
  wheel e instalación;332son de producto.
- La nueva variante primero encontró dos errores de preparación: carpeta de
  marcador ausente y Git correctamente rechazando un origen sucio. Se cambió
  el selector del doble a una entrada explícita del ensayo, sin relajar Git.
  Después se observó `supported` frente al rechazo esperado y se incorporó la
  variante al generador controlado. No se presenta esto como un fallo productivo.
- La aserción inicial del inventario confundía presencia del stub con proveedor
  activo. Se leyó el código y se corrigió la clasificación, sin borrar el stub.
- No cambiaron módulos productivos ni prompts. Se conservaron docstrings en
  los módulos y definiciones relevantes del ensayo. Cero llamadas al modelo.

[Resultados](engine-acceptance-results.json),
[paquete instalado](engine-acceptance-packaging.json),
[inventario y hashes](engine-acceptance-inventory.json).
Los logs/XML están en `.superpowers/sdd/2026-10-31-actualizacion-proyecto/engine-acceptance-*`.

Quedan **41de43escenarios amplios abiertos**, además de los entregables y la
aceptación integral de12páginas. La última suite global sigue siendo la corrida
histórica documentada, con fallos; esta selección dirigida no la reemplaza.
Recuperación/storage, datos históricos, evaluaciones humanas/modelos, dependencias
y distribución continúan como trabajo principal. Los detalles registrados van
después, seguidos de validación global y revisión independiente.
