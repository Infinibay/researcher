# Límites compartidos del dominio de ejecución

El engine ya tenía límites compartidos de memoria y procesos, pero no de CPU.
Este cambio añade CPU al mismo dominio y conserva las observaciones del kernel
antes de retirarlo. Si una ejecución falla y se observaron procesos terminados
por falta de memoria o nacimientos rechazados por el límite de procesos, el
usuario recibe esa información junto con la indicación de revisar el trabajo
guardado. No se repite inferencia ni se inventa una finalización nativa.

Bloque **2026-11-07 11:18:23–11:33:34 UTC:15 min 11 s** hasta validación.
Base3336803. Este bloque no completa los límites de almacenamiento ni toda la seguridad.

## Política y alcance

`BrokerLimits.cpu_millis` es un entero entre100 y8000, predeterminado2000.
Se traduce a `cpu.max` con período100000µs:2000 permite el equivalente de dos
núcleos compartidos;250 permite un cuarto de núcleo compartido. No se asigna ese
presupuesto por separado a cada proceso hijo. El kernel limita CPU por grupo;
`memory.oom.group` permite tratar sus procesos como un conjunto ante agotamiento.
[Documentación del kernel](https://cdn.kernel.org/doc/html/latest/admin-guide/cgroup-v2.html).

La política se verifica en el dominio vacío antes de liberar el primer actor y
queda en el recibo de autoridad. `memory.max`, `memory.swap.max=0` y `pids.max`
conservan su función; se añade `memory.oom.group=1` para evitar que un agotamiento
deje hermanos actuando. El nacimiento rechaza un planificador fuera de
SCHED_OTHER/BATCH/IDLE. El filtro heredado de los payloads impide cambiarlo mediante
sched_setscheduler, sched_setparam o sched_setattr, evitando introducir clases
de tiempo real no cubiertas por esta política.

La preparación exige ahora los controladores cpu/memory/pids. Un host sin CPU
delegada se rechaza antes de crear su instalación. Una configuración anterior
sin cpu_millis recibe el valor predeterminado en las nuevas admisiones; no se
reescriben recibos históricos ni se adopta un dominio anterior bajo otra política.
El [ejemplo de configuración](../config/host-assets.example.json) lo declara.

El alcance es el árbol de procesos del dominio, no todo el sistema operativo:
el servicio Python supervisor y operaciones de confianza fuera de ese dominio
no pasan a estar limitados por esta modificación. La concesión global existente
mantiene un dominio activo por autoridad, además de los límites de admisión del
servicio; esto no demuestra aislamiento entre instalaciones con autoridades distintas.

## Observaciones y comunicación

Tras detener el árbol y comprobar que está vacío, se leen los contadores disponibles
antes de quitar el cgroup. Se conservan en el recibo de retirada, también en la
recuperación de un dueño anterior. Incluyen uso y throttling de CPU, procesos
terminados por OOM, eventos de OOM del grupo y nacimientos denegados por pids.max.
Un fallo de lectura queda como `observed:false`; no se transforma en ceros y
no impide la parada física.

El runtime entrega la observación sólo para el intento, proyecto, run, fence y
contexto originales. El coordinador la usa para explicar un intento fallido o
que requiere reconciliación. El throttling de CPU es normal bajo una cuota;
por sí solo no se presenta como fracaso. Tampoco se sustituye Stop o una corrección
por un diagnóstico nuevo. El texto de memoria dice que hubo procesos terminados
por falta de memoria: el contador por sí solo no prueba qué límite provocó el OOM.

La interfaz existente muestra ese mensaje en «Lo que ocurrió». No se cambió su
composición ni se declara una nueva auditoría visual. La observación no habilita
aceptación y no es prueba alternativa de cierre físico.

## Evidencia

- **86 pruebas** del dominio, broker, host, runtime y planificación pasan.
- **2 pruebas añadidas** comprueban el agotamiento real de memoria a través del
  runtime completo y el rechazo de un host sin controlador CPU. Pasan.
- **32 pruebas** de fronteras, recuperación, publicación y RPC nativo pasan.
- **66 pruebas desde el wheel instalado**, fuera del checkout, pasan sin omisiones.
  Los610 archivos Python/SQL del paquete coinciden con fuente e instalación.
- El caso de CPU crea tres hijos ocupados bajo una cuota compartida de250.
  Observa throttling y menos de un segundo de CPU agregado en el tramo de1,5s.
  El caso de procesos permite tres hijos bajo pids.max=4 y observa nueve rechazos.
  El caso de memoria toca las páginas asignadas y observa la terminación del grupo.
- En el producto completo, un peer de generación controlada agota un dominio de
 256MiB. Queda un intento fallido, una única reserva de inferencia, todos los peers
 cerrados, cero grants activos y un mensaje específico de memoria. No se envía
 una llamada real al modelo.
- `researcher-bootstrap check-host --probe` se ejecutó desde la instalación final
  sobre recursos reales de Codex/Ken:26 artefactos Ken verificados, límite CPU
  `200000 100000`, memoria2147483648 y128 procesos. El hijo terminó con0 y el
  dominio fue eliminado. Esto no demuestra una tarea de investigación ni
  disponibilidad remota de la suscripción.

[Resultados](domain-resources-results.json), [paquete](domain-resources-packaging.json),
[comando instalado](domain-resources-host-probe.json),
[docstrings](domain-resources-docstrings.json).

## Pendientes que siguen siendo principales

El almacenamiento necesita una cuota agregada comprobable que conserve cambios
útiles después de un crash. Una inspección periódica o RLIMIT_FSIZE por archivo
no equivalen a esa cuota. No se monta ni modifica el filesystem del operador en
este bloque. También siguen abiertos los recursos de los trabajos de confianza
fuera del dominio, Ken/ONNX, la aceptación integral de seguridad, datos históricos,
comunicación humana y las12 páginas. Los43 escenarios amplios no se cierran por
esta entrega; no hay nueva suite global verde, push ni despliegue.

Doce avisos de estilo se guardan en DD094. La mejora de observaciones parciales
cuando falta un contador se registra en DD095; el comportamiento actual declara
la observación desconocida y mantiene las barreras y la parada.
