# Tablero de ejecución de la actualización

Actualizado: 2026-11-07. Objetivo activo: implementar **todo** el [plan](../superpowers/plans/2026-10-31-actualizacion-proyecto.md). Este tablero no reemplaza requisitos ni declara el plan terminado. [Diagnóstico del proceso](workflow-review.md).

## Seguimiento al cambiar de tarea

En cada transición de tarea principal, publicar en el chat la lista actualizada:
implementado con su alcance, tarea en curso y tareas pendientes. Decir qué se cerró
y cuál empieza. Política explícita del usuario del6noviembre; se mantiene después
de compactar. Primero todas las tareas gruesas; todos los detalles secundarios al final.
Indicar el tiempo medido del tramo cuando se disponga de él; si una estimación
del trabajo restante no está sustentada, decirlo en lugar de inventar un plazo
o porcentaje. No reconstruir tiempos históricos a partir de recuerdos del chat.

Formato de cada actualización: **terminado con evidencia / en curso / pendiente
en orden / detalles al final**. Añadir duración medida del bloque que termina y
hora de inicio del siguiente; durante un bloque, etiquetar el tiempo transcurrido
como tal, sin confundirlo con una estimación del trabajo restante. Mantener esta
lista en el documento además de publicarla en el chat, para retomarla tras compactar.
El usuario reiteró esta política en su último mensaje: acompañar cada cambio de
tarea con la lista y el tiempo. Actualizar el mismo resumen de capacidades para
que se pueda comparar el avance; no presentar microajustes como tareas principales.

## Estado comprobado

- Codex por suscripción y Ken publicado ensayados. Fuentes/citas, informes draft y revisión documental independiente conectados. Desarrollo admitido desde Tareas/Conversación con captura y comprobaciones explícitas; revisión independiente solicitada desde Tareas y aceptación del propietario conectada. Publicación local desde aceptación conectada; recuperación local de sólo lectura conectada; transporte remoto configurable conectado; recuperación remota y controles de Tareas conectados; ejecución/activación antiguas por tarea y proyecto retiradas; auxiliares de generación/proveedor, herramientas antiguas y sus cinco bibliotecas retirados. También se retiraron API interna, CLI, servicios/listeners y flows/helpers antiguos. También se retiraron autonomía, plantillas históricas y lectores de proveedor sin consumidores; se conserva el control de parada de trabajadores registrados.
- Interfaz: doce pilotos, 36/36 conceptos de escritorio y 12/12 móviles; todas las rutas tienen piloto y 0/12 páginas están completamente aceptadas.
- Última suite global: `9fb873c`,2210 casos,2178 pasan,31 fallan y1 error de fixture; sin omisiones. La carrera de backup encontrada se corrigió después con40 pruebas instaladas. No se declara una nueva corrida global verde; la referencia `0c8b8d9` queda como evidencia histórica.
- Los 43 escenarios amplios siguen abiertos en [coverage.json](coverage.json). No hay un porcentaje global defendible.

## Etapa actual: lector Chroma acotado; continúa compatibilidad Ken/ONNX

Bloque **13:37:40–13:50:53 UTC**, **13 min 13 s** hasta validar. El lector
desactiva descriptores de embeddings sólo en su copia desechable y conserva la
configuración original.14pruebas pasan; la importación instalada conserva105registros
y responde por HTTP, sin modelos. La auditoría mantiene los avisos de ONNX/Chroma;
no se cambiaron versiones publicadas ni se declara seguridad integral.
[Informe](dependency-reader-review.md), [auditoría](dependency-reader-audit.json).

**Lista actualizada al cambiar de tramo:**
- Implementado y comprobado: backend Codex/Ken, modelos, flujos principales,
  comunicación, persistencia y varias recuperaciones.
- Terminado ahora: neutralización de configuración de modelos del lector y
  validación de importación, **13 min 13 s** hasta validar.
- En curso principal: dependencias y seguridad.
- Siguiente: compatibilidad de Ken con ONNX corregido y propuesta de distribución
  coherente. **Todavía no iniciada.**
- Pendiente: licencias, recursos/recuperación restantes, datos históricos,
  evaluación humana/otros perfiles y aceptación de12páginas.
- Al final: detalles (incluido DD103), validación global y revisión independiente.

Siguen43escenarios amplios abiertos y0/12páginas plenamente aceptadas. Las listas
y tiempos persisten tras compactar; no hay un porcentaje global sustentado.

## Etapa anterior: dependencias y configuración persistida de Chroma

Inicio **2026-11-07 13:37:40 UTC**. El turno anterior fue progreso (`b56bccc`).
En curso: contraste de registros publicados y revisión del lector histórico.
PyPI mantiene Ken0.18.0 con ONNX1.20.1 exacto y Chroma1.5.9 sin versión corregida
indicada para sus avisos. La lectura directa de tablas requiere considerar la
cola aún no materializada; se está verificando el recorrido oficial de lectura
y las rutas que construyen funciones de embeddings antes de elegir el cambio.

Lista vigente: terminado recuperación acotada (**7 min 46 s** hasta validar);
en curso dependencias; después recuperación restante, comunicación humana/otros
perfiles, datos históricos y12páginas. Detalles secundarios al final.

## Etapa anterior: recuperación acotada comprobada; siguen dependencias

Bloque **13:26:25–13:34:11 UTC**, **7 min 46 s** hasta validar. Se corrigió la
reinscripción de restore con `storage`.59pruebas de fuente y59instaladas pasan.
En una VM real, SQLite revierte una transacción al llenarse128MiB; el servicio
cierra, cambia el kernel y se restaura otra instalación acotada que responde por
HTTP. Inspección independiente del disco confirma bases/código; cero modelos.
618archivos coinciden,24definiciones documentadas y83revisiones de prompts vigentes.
[Informe](storage-recovery-review.md), [VM](storage-recovery-vm.json).

**Lista actualizada al cambiar de tarea:**
- Implementado y probado en recorridos concretos: backend Codex/Ken, modelos,
  flujos principales, comunicación, persistencia y varias recuperaciones.
- Terminado ahora: reinscripción con volumen y recorrido de disco lleno,
  rollback, reinicio controlado y restauración, **7 min 46 s** hasta validar.
- Siguiente principal: actualización y seguridad de dependencias, incluidos
  Ken/ONNX y el lector Chroma. **No iniciada en este bloque.**
- Pendiente principal: recursos externos simultáneos; recuperación con recibo
  no escribible, pérdida abrupta de energía/inodos; datos históricos del dueño;
  evaluación humana y otros perfiles.
- Interfaz:12pilotos/48conceptos;0/12páginas completamente aceptadas.
- Al final: detalles acumulados (DD102 nuevo), validación global, revisión
  independiente y distribución.

Siguen43escenarios amplios abiertos. Este ensayo no cierra la aceptación global
de recuperación ni aporta un porcentaje total fiable. Lista y tiempos persistentes.

## Etapa anterior: recuperación con disco lleno y migración de almacenamiento

Inicio **2026-11-07 13:26:25 UTC**. El bloque anterior fue progreso y quedó
guardado en `0074b74`. En curso: reparar la reinscripción de una restauración
con política de volumen y comprobar escritura fallida/recuperación sobre disco
real desechable. La primera inspección encontró que faltaba capturar el recibo
de almacenamiento antes de publicar la nueva instalación como preparada.

Lista vigente: terminado grupo del servicio (**17 min 31 s** hasta validar);
en curso recuperación/migración; después seguridad, evaluación humana/otros
perfiles, datos históricos y aceptación de12páginas. Cuotas restantes siguen
abiertas. Todos los detalles secundarios después de las tareas principales.

## Etapa anterior: grupo de servicios comprobado; sigue recuperación de almacenamiento

Bloque **13:06:07–13:23:38 UTC**, **17 min 31 s** hasta validación. El lanzador
nativo aplica límites compartidos y un guardián retira el grupo si muere el
lanzador. Backup excluye al servicio y restore archiva sus controles originales.
56 pruebas de fuente y55 instaladas pasan. Original y restauración responden
por HTTP, muestran límites reales y cierran sus grupos; cero llamadas a modelos.
618 archivos coinciden,34 definiciones documentadas y83 revisiones de prompts
vigentes. [Informe](service-resources-review.md), [ensayo](service-resources-host.json).

**Lista actualizada al cambiar de tarea:**
- Implementado y probado en recorridos concretos: backend Codex/Ken, modelos,
  flujos principales, comunicación, persistencia y varias recuperaciones.
- Terminado ahora: recursos del API/descendientes, guardián de cierre y
  coordinación con backup/restore, **17 min 31 s** hasta validar.
- Siguiente principal: recuperación ante disco lleno y migración a almacenamiento
  acotado. **Todavía no iniciada en este bloque.**
- Pendiente principal: cuotas restantes de auxiliares/operaciones simultáneas,
  seguridad de dependencias, evaluación humana/otros perfiles y datos históricos.
- Interfaz:12pilotos/48conceptos;0/12páginas completamente aceptadas.
- Al final de las capacidades principales: detalles acumulados (incluido DD101),
  validación global, revisión independiente y distribución.

Siguen43escenarios amplios abiertos. No hay nueva suite global verde ni un
porcentaje global sustentado. Launcher y guardián permanecen fuera de este
presupuesto; tampoco se acredita el cierre de actores nativos. Lista y tiempos
se conservan tras compactar; no se hizo push ni despliegue.

## Etapa anterior: grupo de recursos del servicio principal

Inicio **2026-11-07 13:06:07 UTC**. El turno anterior fue progreso, guardado en
`1c853fb`. En curso: grupo propio de CPU/memoria/procesos para los servicios del
lanzador preparado, con cierre independiente si muere el lanzador. Este cierre
no acredita el cierre de actores nativos ni aceptación de sus resultados.
Último tramo terminado: temporales Chroma, **15 min 4 s** hasta validación.
Después: cuotas durables, recuperación/migración, seguridad, evaluación humana
y aceptación de12páginas. Detalles secundarios al final.

## Etapa anterior: temporales Chroma comprobados; siguen recursos globales

Bloque **12:45:45–13:00:49 UTC**, **15 min 4 s** hasta validación. El lector
usa un tmpfs con capacidad de datos compartida, dos salidas fijadas y log de64KiB;
ya no recibe carpetas del host para escritura.8pruebas finales y3comprobaciones
de descriptores pasan. La exportación/importación instalada conserva105registros,
104adjuntos textuales y1metadato; lectura HTTP comprobada y servicio cerrado.
Cero modelos. [Informe](chroma-capacity-review.md), [ensayo](chroma-capacity-import.json).

**Lista vigente:**
- Implementado y comprobado en recorridos concretos: backend Codex/Ken, modelos,
  flujos principales, comunicación, persistencia y varias recuperaciones.
- Terminado en este tramo: capacidad de datos temporal y salidas del lector
  Chroma, **15 min 4 s** hasta validación.
- En curso como tarea principal: completar los recursos agregados del sistema.
- Siguiente: memoria/procesos/CPU del supervisor; cuota durable de operaciones
  auxiliares y migración/recuperación de hosts acotados continúan principales.
- Pendiente principal: seguridad de dependencias, evaluación humana/otros
  perfiles y datos históricos del propietario.
- Interfaz:12pilotos/48conceptos;0/12páginas completamente aceptadas.
- Al final: detalles acumulados, validación global, revisión independiente y
  distribución. DD100 recoge11avisos de estilo.

La cuota temporal no prueba una cuota del volumen durable ni de memoria total.
Siguen43escenarios amplios abiertos, sin nueva suite global verde. La lista y
tiempos quedan persistentes tras compactar; no se inventa porcentaje restante.

## Etapa anterior: inicio de temporales Chroma y supervisor

Inicio **2026-11-07 12:45:45 UTC**. El turno anterior fue progreso: administración
comprobada y guardada en `7047b91`. En curso: reemplazar carpetas de escritura
del lector Chroma por temporales con capacidad de kernel y salidas concretas,
manteniendo copia original y errores inspeccionables. Siguen recursos del
supervisor, recuperación/migración, seguridad, evaluación humana y12páginas.
Último tramo terminado: administración, **12 min 28 s** hasta validación.
Detalles secundarios al final de todas las capacidades principales.

## Etapa anterior: administración comprobada; siguen recursos agregados

Bloque **12:29:30–12:41:58 UTC**, **12 min 28 s** hasta validación. Backup,
verificación, restore e importación histórica tienen proceso propio con memoria,
CPU y plazo acotados; los inventarios aplican su límite durante el recorrido.
28 pruebas finales dirigidas pasan. En el alcance ampliado,86casos distintos
pasan y4mantienen fallos históricos de expectativas de migración.49casos distintos
del paquete instalado pasan tras corregir el cwd del ensayo.616archivos coinciden,
20definiciones documentadas y83revisiones de prompts vigentes. Cero modelos.
[Informe](admin-resources-review.md), [corridas](admin-resources-results.json).

**Lista vigente:**
- Implementado y comprobado en recorridos concretos: backend Codex/Ken, modelos,
  flujos principales, comunicación, persistencia y varias recuperaciones.
- Terminado en este tramo: límites por operación administrativa y recorrido
  acotado de inventarios, **12 min 28 s** hasta validación.
- En curso como tarea principal: completar los recursos agregados del sistema.
- Siguiente: cuota de temporales/exportación de Chroma y memoria del supervisor.
  Este siguiente tramo todavía **no se inició**.
- Pendiente principal: migración/recuperación bajo volúmenes acotados, seguridad
  de dependencias, evaluación humana/otros perfiles y datos históricos.
- Interfaz:12pilotos/48conceptos;0/12páginas completamente aceptadas.
- Al final de las capacidades principales: detalles, validación global, revisión
  independiente y distribución. DD099 conserva18avisos de estilo/imports.

Siguen43escenarios amplios abiertos y no hay nueva suite global verde ni un
porcentaje global sustentado. Lista y tiempos permanecen tras compactar.

## Etapa anterior: inicio de recursos de administración y supervisor

Inicio **2026-11-07 12:29:30 UTC**. El bloque anterior es progreso comprobado
y quedó en el commit local `68f6b20`. En curso: límites de memoria/CPU/plazo para
backup, verificación, restauración e importación histórica, y admisión de
inventarios antes de acumular listas completas. La cuota agregada de temporales
de Chroma y el conjunto del supervisor siguen pendientes principales.

Lista vigente: terminado el aislamiento documental/semántico (**19 min 16 s**);
en curso recursos administrativos; después recursos restantes, seguridad de
dependencias, recuperación/migración, evaluación de comunicación y aceptación
de12páginas. Todos los detalles secundarios después de las tareas principales.

## Etapa anterior: trabajadores documentales/semánticos comprobados

Bloque **12:02:31–12:21:47 UTC**, **19 min 16 s**, hasta validación. Un cupo común
conservado hasta reap físico, Landlock/seccomp obligatorios y estado HTTP429 de
ocupado cubren los programas fijos de documentos y encoder local.98casos distintos
de fuente y44instalados pasan;614archivos coinciden y35definiciones documentadas.
83revisiones de prompts vigentes. Encoder local real; cero turnos generativos.
[Informe y límites](aux-workers-review.md), [pruebas](aux-workers-results.json).

**Lista actualizada al cambiar de tarea:**
- Implementado y comprobado en recorridos concretos: backend Codex/Ken, modelos,
  flujos principales, comunicación, persistencia y varias recuperaciones.
- Terminado en este bloque: frontera común documental/semántica y explicación
  de saturación, **19 min 16 s** hasta validación.
- Terminado previamente: volumen durable (**19 min 23 s**) y CPU/agotamiento
  del dominio (**15 min 11 s**).
- Siguiente principal: exportaciones/backup/restore y recursos restantes del
  supervisor, incluido trabajo del padre. **No iniciado**.
- Pendiente principal: migración/recuperación de hosts acotados; seguridad
  Ken/ONNX/Chroma; evaluación humana y otros perfiles; datos históricos;
  aceptación integral de12páginas.
- Interfaz:12pilotos/48conceptos,0/12páginas completamente aceptadas.
- Después de las capacidades principales: detalles acumulados, validación global,
  revisión independiente y distribución. DD098 recoge estilo/imports.

No hay nueva suite global verde ni porcentaje global sustentado. Siguen43escenarios
amplios abiertos. Lista y tiempos persistentes tras compactar; sin push/despliegue.

## Etapa anterior: inicio de la frontera de trabajadores

Inicio **2026-11-07 12:02:31 UTC**. Se está cerrando la frontera compartida de
extracción documental y búsqueda semántica: un solo trabajador concurrente por
proceso supervisor, restricciones obligatorias de lectura/escritura/red y
creación de procesos, conservación de límites CPU/AS/plazo y cierre por pidfd.
Las primeras pruebas pasan; formatos y encoder local real están en validación.
Todavía no se declara cerrado el conjunto de recursos auxiliares, exportaciones,
backups ni memoria del proceso supervisor.

**Lista actualizada:** terminado el volumen durable (**19 min 23 s** hasta
validación); en curso trabajadores documentales/semánticos; después recursos
auxiliares restantes, seguridad Ken/ONNX, comunicación humana/otros perfiles,
datos históricos y recuperación, aceptación de12páginas. Todos los detalles
secundarios permanecen para después de las capacidades principales.

## Etapa anterior: volumen durable comprobado

Bloque **11:38:40–11:58:03 UTC**, **19 min 23 s**, hasta validación. Una instalación
nueva puede usar un volumen ext4 dedicado con capacidad agregada verificada.
Una VM real llena128MiB con cuatro escritores, rechaza trabajo nuevo, retira su
dominio y conserva código y bases después de desmontar/montar. El montaje ausente
se rechaza sin recreación. Inspección independiente del disco confirma los datos.

84 casos distintos de fuente y55 instalados pasan;612 archivos coinciden y57
definiciones documentadas.83 decisiones de prompts vigentes; cero modelos.
[Informe y límites](storage-volume-review.md), [VM](storage-volume-vm.json),
[datos extraídos](storage-volume-disk-inspection.json).

**Lista actualizada al cambiar de tarea:**
- Implementado y comprobado en recorridos concretos: backend Codex/Ken, modelos,
  flujos principales, comunicación, persistencia y varias recuperaciones.
- Terminado en este bloque: volumen durable configurado, admisión por espacio y
  conservación tras llenado/remount, **19 min 23 s** hasta validación.
- Terminado previamente: CPU compartida y agotamiento, **15 min 11 s**.
- Siguiente principal: limitar operaciones auxiliares del supervisor y sus
  temporales/exportaciones fuera de la frontera actual. **No iniciado**.
- Pendiente principal: migración/recuperación de hosts con volumen acotado;
  seguridad Ken/ONNX; evaluación humana y otros perfiles; datos históricos;
  aceptación integral de12páginas. Disco lleno con DB activa y pérdida de energía
  siguen sin estar demostrados; no se difieren como detalles cosméticos.
- Interfaz:12 pilotos/48 conceptos,0/12 páginas completamente aceptadas.
- Después de las capacidades principales: detalles acumulados, validación global,
  revisión independiente y distribución. DD096 recoge estilo/imports.

No hay nueva suite global verde ni porcentaje global sustentado. Las instalaciones
anteriores sin política de almacenamiento siguen explícitamente no acotadas.
Siguen43escenarios amplios abiertos. Lista/tiempo persistentes; sin push/despliegue.

## Etapa anterior: inicio del análisis de almacenamiento

Inicio del bloque de almacenamiento: **2026-11-07 11:38:40 UTC**. Se están
revisando los directorios que pueden crecer y las opciones para imponer una cuota
agregada sin perder trabajo tras una caída. Todavía no hay una solución elegida,
implementada ni validada para esa cuota. La revisión del seguimiento solicitada
por el usuario forma parte de este bloque y no cuenta como otra tarea principal.

Último bloque cerrado: CPU compartida y explicación del agotamiento.

Bloque **11:18:23–11:33:34 UTC**, **15 min 11 s**, hasta validación.
La CPU se limita de forma compartida entre los hijos del dominio; memoria y
procesos conservan límites agregados. El OOM retira el grupo y sus contadores
quedan guardados. Un agotamiento real del runtime llega al mensaje del propietario,
sin inventar terminación nativa ni repetir inferencia.

Pasan120 pruebas dirigidas de fuente y66 instaladas, sin omisiones.610 archivos
coinciden;37 definiciones documentadas;83 revisiones de prompts vigentes. El
comando instalado check-host --probe verifica recursos reales Codex/Ken, limita
CPU/memoria/procesos y elimina su dominio. Cero llamadas al modelo. No se afirma
una cuota de disco ni límites para todo el servicio supervisor.
[Informe](domain-resources-review.md), [validación](domain-resources-results.json),
[comando instalado](domain-resources-host-probe.json).

**Lista actualizada al cambiar de tarea:**
- Implementado y comprobado en recorridos concretos: backend Codex/Ken, modelos,
  flujos principales, comunicación, persistencia y varias recuperaciones.
- Terminado en este bloque: CPU compartida, retirada del grupo por OOM y explicación
  del agotamiento, **15 min 11 s** hasta validación.
- Terminado previamente: entrega atómica del plan y explicación, **18 min 28 s**.
- En curso: almacenamiento durable con cuota agregada; análisis iniciado a las
  **11:38:40 UTC**. Pendiente también acotar los recursos de las operaciones de
  confianza que quedan fuera del dominio.
- Pendiente principal: Ken/ONNX y seguridad restante; evaluación humana y otros
  perfiles; datos históricos y recuperación; aceptación integral de12 páginas.
- Interfaz:12 pilotos/48 conceptos,0/12 páginas completamente aceptadas.
- Después de todas las tareas gruesas: detalles acumulados, validación global,
  revisión independiente y distribución. DD094/095 recogen estilo y telemetría parcial.

Siguen43 escenarios amplios abiertos; no hay nueva suite global verde ni porcentaje
sustentado. Lista y tiempo en cada transición, persistentes tras compactar. Sin push
ni despliegue.

## Etapa anterior: entrega atómica comprobada; seguía seguridad y recursos

Bloque **10:56:19–11:14:47 UTC**, **18 min 28 s**, hasta validación.
El plan y su explicación se guardan juntos; el host cierra el turno sin requerir
otra generación. Un único intento real entrega con**81.685/120.000tokens observados**,
tres tareas propuestas y una explicación con ejemplo. Estado nativo interrupted,
producto needs_review, propuesta elegible para decisión del propietario y cero
aceptaciones. Servicio y cuatro peers cerrados, cero grants locales activos.

Primer candidato:128 pruebas desde fuente y102 instaladas. Tras añadir la protección
del límite de bytes de explicación,50 pruebas finales de fuente y50 instaladas
pasan; no se repite el modelo.609 archivos coinciden,35 definiciones documentadas,
83 decisiones de prompts vigentes.136 contratos web y1 caso UI pasan; build terminado.
[Informe](atomic-planning-review.md), [ensayo](atomic-planning-live.json),
[resultados](atomic-planning-results.json).

**Lista actualizada al cambiar de tarea:**
- Implementado y comprobado en recorridos concretos: backend Codex/Ken, modelos,
  flujos principales, comunicación, persistencia y varias recuperaciones.
- Terminado en este bloque: entrega atómica de planificación y explicación,
  **18 min 28 s** hasta validación; aceptación integral del proyecto aún pendiente.
- Interfaz:12 pilotos y48 conceptos;0/12 páginas completamente aceptadas.
- En curso: límites agregados de CPU/memoria/procesos y explicación de agotamiento.
  Inicio **2026-11-07 11:18:23 UTC**. Disco y seguridad Ken/ONNX siguen pendientes
  principales; no se consideran resueltos por los límites de cgroup.
- Pendiente principal: evaluación humana y demás perfiles de comunicación;
  datos históricos y recuperación restante; aceptación integral de las12 páginas.
- Después de todas las tareas gruesas: detalles acumulados, validación global,
  revisión independiente y distribución. DD093 conserva8 avisos de estilo del corte.

Siguen43 escenarios abiertos, sin nueva suite global verde ni porcentaje global
sustentado. Lista y tiempo medido en cada transición, también después de compactar.
No hubo push ni despliegue.

## Etapa anterior: planificación requería una entrega explícita

Bloque **10:33:57–10:52:20 UTC**, **18 min 23 s**, hasta validación. El aviso
ahora estima margen con incrementos observados y reconoce el retraso del contador.
La reproducción falla antes y pasa después; catálogo5 conserva identidades2/3/4.
El primer candidato pasa105 pruebas de fuente y82 instaladas. Tras corregir sólo
la guía de lectura completa, pasan12 de fuente y12 instaladas;608 archivos
Python/SQL coinciden.18 definiciones documentadas;83 decisiones de prompts vigentes.

**La entrega aún falla:** un único intento nuevo guarda3 tareas en una propuesta,
pero el paso posterior de explicación eleva107804 a137720tokens, sobre120000.
El servicio y sus4 peers cerraron,0 grants locales activos y0 aceptaciones. No se
repitió el intento. Ken devolvía sólo símbolos por defecto: la lectura adicional
sí era necesaria. Se corrigió esa recomendación sin otra inferencia.
[Informe y siguiente contrato](planning-delivery-review.md),
[intento](planning-delivery-live.json), [validación](planning-delivery-results.json).

**Lista actualizada:**
- Implementado y comprobado en recorridos concretos: backend Codex/Ken, modelos,
  flujos principales, comunicación, persistencia y varias recuperaciones.
- Interfaz:12 pilotos y48 conceptos;0/12 páginas completamente aceptadas.
- Terminado en este bloque: margen observado y diagnóstico de la entrega,
  **18 min 23 s**; no equivale a terminar planificación.
- Terminado previamente: inventario de licencias, **13 min 38 s**; aislamiento
  del lector Chroma, **19 min 53 s**.
- En curso, siguiente implementación: guardar plan y explicación juntos y cerrar
  el turno por un recibo durable, sin inventar terminación nativa ni aceptación.
  Las condiciones de autoridad/cierre y los casos de fallo están en el informe.
  Inicio del bloque: **2026-11-07 10:56:19 UTC**. Contrato y consumidores en
  revisión; todavía no hay una entrega atómica implementada ni validada.
- Pendiente principal: seguridad Ken/ONNX y límites agregados; evaluación humana
  y otros perfiles; datos históricos y recuperación restante; aceptación integral
  de las12 páginas.
- Después de todas las tareas gruesas: detalles acumulados, validación global,
  revisión independiente y distribución. DD092 conserva9 avisos de estilo.

Siguen43 escenarios abiertos, sin nueva suite global verde ni porcentaje global
sustentado. No hubo push ni despliegue. La lista y tiempos medidos persisten tras
compactar; no repetir el ensayo fallido para buscar una respuesta favorable.

## Etapa anterior: inventario de licencias comprobado

Bloque **10:16:47–10:30:25 UTC**, **13 min 38 s**, hasta el corte de validación.
Se resuelven las139 ausencias anteriores:164 versiones Python y415 entradas npm
con declaraciones o revisiones de artefactos exactos;0 ausencias/errores/revisiones
pendientes del inventario. Pasan12 pruebas. Build web, wheel/sdist y metadata
instalada verificados;608 archivos Python/SQL del backend sin cambios.16
funciones y2 módulos documentados; hook de Vite con JSDoc. Cero modelos.

El build genera93 entradas de avisos,91 con texto y2 pendientes en DD091. Las
rutas de avisos responden mediante ASGI TestClient; no se afirma navegación real.
Licencia y copyright originales intactos. No es una aceptación de compatibilidad
integral ni de toda la distribución. [Informe](license-review.md),
[resultados](license-results.json), [inventario](license-inventory.json).

**Lista actualizada al cambiar de tarea:**
- Implementado y comprobado en recorridos concretos: backend Codex/Ken,
  configuración de modelos, flujos principales, comunicación, persistencia y
  varias recuperaciones. Su aceptación integral sigue pendiente.
- Interfaz:12 pilotos y48 conceptos;0/12 páginas completamente aceptadas.
- Terminado en este bloque: inventario y empaquetado de avisos, **13 min 38 s**,
  con el alcance y las dos omisiones de texto indicados arriba.
- Terminado previamente: aislamiento del lector Chroma, **19 min 53 s**;
  presupuesto visible y trabajo parcial, **18 min 56 s**.
- Siguiente principal: conseguir una entrega de planificación dentro del
  presupuesto anterior. No comenzó; registrar inicio al comenzar.
- Pendiente principal: seguridad Ken/ONNX y límites agregados; evaluación humana
  y otros perfiles de comunicación; datos históricos del propietario y demás
  recuperación; aceptación integral de las12 páginas.
- Después de todas las tareas gruesas: detalles acumulados, incluidos DD090
  (4 avisos Ruff) y DD091 (2 textos de licencia), validación global final,
  revisión independiente y preparación de la distribución concreta.

Siguen43 escenarios amplios abiertos, sin nueva suite global verde ni porcentaje
sustentado. La lista y los tiempos medidos se publican en cada cambio de tarea
principal y se conservan aquí después de compactar. No hubo push ni despliegue.

## Etapa anterior: lector Chroma aislado y migración comprobada

Bloque **09:51:10–10:11:03 UTC**, **19 min 53 s**, hasta el corte de validación.
El exportador separado requiere bubblewrap y abre Chroma sólo sobre una copia,
en namespaces propios, con entorno limpio y sin entrada estándar ni red del host.
El padre supervisa el plazo y rechaza enlaces en la salida; un fallo conserva la
copia parcial y no publica un manifiesto completo. No cambian los pins de paquetes.

Seis pruebas de la barrera pasan. El conjunto con el importador da20 aprobadas
 y1 fallo histórico de expectativa de esquema59, ya registrado anteriormente.
La comprobación completa final exporta105 registros, importa104 adjuntos textuales
más1 registro sin texto y verifica procedencia/acceso HTTP desde el backend instalado.
Cero turnos de modelo. Servicio original cerrado con salida143.19 definiciones
relevantes tienen docstrings. Lock e inventario de83 decisiones verificados.
[Informe](chroma-isolation-review.md), [pruebas](chroma-isolation-results.json),
[importación final](chroma-isolation-import.json).

**Lista actualizada al cambiar de tarea:**
- Terminado: aislamiento del lector Chroma y comprobación de su importación,
  **19 min 53 s**. Esto no declara corregida la biblioteca ni aceptada toda la seguridad.
- Terminado previamente: presupuesto visible/trabajo parcial, **18 min 56 s**;
  evaluación por perfiles, **29 min 48 s**; revisión estática, **8 min 55 s**.
- Siguiente principal: resolver las declaraciones de licencia pendientes y
  documentar las obligaciones según artefactos/versiones concretos. No empezó;
  registrar inicio al comenzar. El inventario anterior tiene139 ausencias.
- Pendiente funcional: distribución coherente de Ken con ONNX corregido;
  recursos agregados y demás seguridad/recuperación; entrega de planificación
  bajo su límite anterior; evaluación humana/otros perfiles/material científico;
  datos históricos del propietario y aceptación integral de12 páginas.
- Después de todas las capacidades principales: detalles acumulados, validación
  final y revisión independiente. DD089 conserva11 avisos de estilo.

Las auditorías renovadas siguen señalando19 entradas/12IDs en Ken/ONNX y5/4 en
Chroma, sin omisiones ni exclusiones. Siguen43 escenarios amplios abiertos y0/12
páginas completamente aceptadas. No se reconstruyó el wheel ni se repitió la suite
 global. Los límites del lector no son cuotas de disco/cgroup para un árbol entero;
el snapshot aún requiere escritores originales detenidos. La política de lista y
 tiempo medido en cada transición permanece tras compactar; detalles al final.

## Etapa anterior: presupuesto visible y trabajo parcial comprobados

Bloque **09:29:55–09:48:51 UTC**, **18 min 56 s**, hasta el corte de validación.
El catálogo4 conserva los presupuestos efectivos en las instrucciones y la
respuesta del host muestra consumo observado y margen. Los límites duros no
cambian. El aviso distingue la causa de interrupción y el trabajo parcial; no
confunde borrador, entrega y aceptación. Los ejemplos deben conservar el nivel
de la evidencia. Las identidades históricas de catálogos2/3 siguen disponibles.

Pasan132 pruebas distintas de fuente y80 instaladas, sin fallos ni omisiones;
608 archivos coinciden,324 productivos.33 definiciones y10 módulos documentados.
El inventario tiene83 decisiones estáticas vigentes tras revisar16 cambios.
Tres turnos nuevos de desarrollo: planificación vuelve a agotar120000tokens
tras guardar una propuesta; auditoría y medias de grupos entregan sus informes.
El ejemplo científico ya distingue medias de cambios individuales en este caso.
Todos los servicios y peers registrados cerraron. Ningún intento se repitió.
[Informe](delivery-budget-review.md), [pruebas](delivery-budget-results.json),
[recibos reales](delivery-budget-live.json), [paquete](delivery-budget-packaging.json).

**Lista actualizada al cambiar de tarea:**
- Terminado en este bloque: presupuesto visible, aviso de interrupción y
  conservación comprobada de trabajo parcial, **18 min 56 s**. Dos de tres
  comprobaciones de desarrollo entregan resultado completo; no se acepta la
  calidad integral de comunicación ni se declara resuelta planificación.
- Terminado previamente: evaluación de otros perfiles, **29 min 48 s**;
  revisión estática de prompts, **8 min 55 s**; VM activa, **15 min 57 s**.
- Siguiente de ese corte: seguridad Ken/Chroma/licencias. El bloque actual
  comprueba el aislamiento del lector; Ken y licencias siguen pendientes.
- Pendiente funcional: entrega de planificación dentro del presupuesto anterior;
  evaluación humana, otros perfiles/material científico real, datos históricos,
  demás recuperación y aceptación integral de12 páginas.
- Después de todas las capacidades principales: detalles acumulados, validación
  final y revisión independiente. DD088 conserva11 avisos de estilo.

Siguen43 escenarios amplios abiertos y0/12 páginas completamente aceptadas.
No hay nueva suite global verde ni porcentaje global sustentado. Política
persistente: lista y tiempo medido en cada transición; todas las tareas gruesas
antes de todos los detalles. La guía del último cuarto no garantiza entrega.

## Etapa anterior: evaluación por perfiles


Bloque **08:56:57–09:26:45 UTC**, **29 min 48 s**, hasta el corte de validación.
Ocho turnos reales por suscripción y Ken; cuatro pares con controles coincidentes,
dos con ambas explicaciones entregadas. Los dos casos científicos conservan
cálculos/citas y límites causales. La política actual falló al cerrar planificación
(131499tokens, límite120000) y auditoría (21llamadas, límite20), aunque guardó
trabajo. Además, un ejemplo del informe actual infirió valores individuales a
partir de una media. Son problemas funcionales pendientes, no éxitos ni pulido.

Los brazos sumaron10min8s y2065880tokens observados, no facturación. Ocho servicios
y todos sus peers cerrados;6despachos settled/2unknown. Se conservan las enmiendas
de presupuesto para casos aún no iniciados y del comparador de identidad; ninguna
respuesta se repitió.27 pruebas dirigidas pasan,34 definiciones documentadas.
[Informe](profile-communication-review.md), [resultados](profile-communication-results.json).

**Lista actualizada al cambiar de tarea:**
- Terminado: evaluación de cuatro casos en planificación, ciencia y auditoría,
  **29 min 48 s**. La calidad integral de la comunicación sigue sin aceptación.
- Terminado previamente: revisión estática de prompts, **8 min 55 s**;
  VM activa, **15 min 57 s**; recuperación de servicio, **21 min 39 s**.
- Siguiente de ese corte, realizado parcialmente en el bloque actual: hacer visibles los presupuestos y reservar margen para
  entregar/explicar; comunicar trabajo parcial guardado y conservar la fidelidad
  de ejemplos. No ajustar el ensayo
  reservado retrospectivamente ni repetir fallos hasta obtener una respuesta buena.
- Pendiente: otros perfiles/material científico real y revisión humana;
  seguridad Ken/Chroma/licencias, datos históricos, demás recuperación y
  aceptación integral de12 páginas.
- Después de todas las capacidades principales: detalles acumulados, validación
  final y revisión independiente. DD087 conserva3 avisos de imports.

Sin cambios productivos, nuevo wheel o suite global;43 escenarios amplios abiertos
 y0/12 páginas aceptadas. No hay porcentaje global sustentado. Lista y tiempo por
transición persistentes después de compactar.

## Etapa anterior: revisión estática de prompts

Bloque **08:45:38–08:54:33 UTC**, **8 min 55 s**, hasta el corte de validación.
El inventario actual tiene83 candidatos/287 archivos y83 decisiones vigentes:
69 revalidadas tras leer texto/consumidores y14 con dependencias iguales. Se
conservaron instrucciones y catálogo3. El evaluador de tamaños etiquetaba2 por
error; ahora toma la versión real. Se verificaron los siete hashes/tamaños.

Pasan45 casos distintos. La primera ejecución tuvo41 aprobados/4 omitidos por
configuración del fixture semántico; esos cuatro pasan luego con los assets
locales ya preparados. Ambos recibos se conservan. Cero generaciones LLM nuevas,
sin cambio productivo, wheel nuevo ni corrida global. [Informe](../prompts/review-2026-11-07.md),
[resultados](../prompts/revalidation-results.json).

**Lista actualizada al cambiar de tarea:**
- Terminado: revisión estática de prompts y consumidores, **8 min 55 s**.
  No equivale a comprobar su eficacia ni comprensión humana.
- Terminado previamente: VM con comando activo, **15 min 57 s**;
  recuperación de servicio, **21 min 39 s**; continuidad/preguntas, **19 min 50 s**.
- Siguiente principal: evaluación de comunicación en otros perfiles y material
  científico representativo. No empezó; publicar inicio al comenzar.
- Pendiente: revisión humana solicitada, seguridad Ken/Chroma/licencias, datos
  históricos del propietario, demás recuperación y aceptación integral de12 páginas.
- Después de todas las capacidades principales: detalles acumulados, validación
  final y revisión independiente. La advertencia Starlette/httpx se conserva en
  los resultados de este corte; no se cambia una dependencia por ella ahora.

Siguen43 escenarios amplios abiertos y0/12 páginas completamente aceptadas.
La última suite global sigue sin estar verde. No hay porcentaje global sustentado.
La política de lista y tiempos por transición permanece guardada tras compactar.

## Etapa anterior: recuperación de VM activa

Bloque medido **08:26:45–08:42:42 UTC**, **15 min 57 s**. Se comprobó el
reinicio del mismo invitado mientras su dueño, namespace del peer y comando hijo
seguían vivos. La restauración conserva el cálculo200, la instrucción/corrección
y tres peers con estados originales archivados; el comando interrumpido queda
`unknown`, sin ejecución repetida ni cierre inventado. Se corrigió esa omisión
en la reinscripción. La base original permanece igual.

La segunda VM pasó en23,95s y cerró su servicio y QEMU; la primera falló antes
admitir el peer por un retorno mal interpretado en el evaluador y se conserva.
Cero modelos/cuentas reales. Inspección independiente de ambas bases del disco
retenido confirma los datos.607 archivos coinciden,324 productivos;23 definiciones
documentadas. Pruebas fuente:27 aprobadas/3 fallos históricos de preparación;
instaladas:24 aprobadas/los mismos3 fallos. No se declara suite verde.
[Informe](active-reboot-review.md), [recibos](active-reboot-results.json),
[inspección del disco](active-reboot-disk-inspection.json).

**Lista actualizada al cambiar de tarea:**
- Terminado: reinicio de VM con un comando activo e historial de jobs restaurados,
  **15 min 57 s**. Alcance distinto de inferencia real o pérdida de energía.
- Terminado previamente: recuperación de servicio activo, **21 min 39 s**;
  continuidad/preguntas respondibles, **19 min 50 s**.
- Siguiente de ese corte: revalidación de prompts y consumidores, realizada en
  el bloque actual descrito arriba.
- Pendiente: evaluación humana/otros perfiles/científica, seguridad Ken/Chroma y
  licencias, datos históricos del propietario, aceptación integral de12 páginas
  y demás recuperación.
- Después de todas las capacidades principales: detalles acumulados, validación
  final y revisión independiente. DD086 conserva18 avisos de estilo; los3 fallos
  históricos ya estaban registrados en la suite global anterior y DD081.

No hubo nueva suite global ni aceptación de páginas. Siguen43 escenarios amplios
abiertos y0/12 páginas completamente aceptadas. No hay un porcentaje global
sustentado. La lista y el tiempo por transición se mantienen tras compactar.

## Etapa anterior: recuperación de servicio comprobada; VM activa siguiente

Inicio medido: **2026-11-07 08:03:22 UTC**. Corte de validación/registro:
**08:25:01 UTC**, **21 min 39 s**. La caída real encontró una concesión global
sin retirar: la pregunta se recuperaba, pero la continuación fallaba antes de
inferir. Se corrigió reutilizando el cierre comprobado de dominio, también al
recuperar recibos antiguos. No se liberan reservas de consumo desconocido.

Pasan59 pruebas de fuente/evaluador y38 del wheel;606 archivos coinciden,
324 productivos.40 definiciones documentadas. El caso corregido mata el servicio
con un actor real activo, recupera la pregunta, guarda la respuesta sin ejecutar
nada y permite una nueva instrucción que explica450segundos. Dominio retirado,
peers cerrados, cero limpieza adicional. Cinco despachos reales en total,
incluidos fallos conservados; todos los servicios cerrados.
[Informe y límites](service-crash-review.md), [recibos](service-crash-live.json),
[paquete](recovery-domain-packaging.json).

**Lista actualizada al cambiar de tarea:**
- Terminado en este bloque: recuperación ante caída del servicio y retiro global
  del intento, **21 min 39 s**. No equivale a toda la recuperación del sistema.
- Terminado previamente: continuidad/preguntas respondibles, **19 min 50 s**;
  correcciones/auditoría de dependencias, **26 min 14 s**.
- Siguiente principal: reinicio de la VM con un proceso activo y recuperación
  conservando su identidad/historial. Aún no comenzó; registrar inicio al comenzar.
  La prueba anterior de VM sólo tenía un registro preparado.
- Pendiente: demás recuperación, evaluación humana/otros perfiles/científica y
  revalidación de prompts, Ken/Chroma/licencias, datos históricos del propietario
  y aceptación integral de12 páginas.
- Después de todas las capacidades principales: detalles acumulados, validación
  final y revisión independiente. DD085 conserva6 avisos de estilo.

Se conservan dos fallos distintos: emparejamiento del evaluador tras SIGKILL y
concesión global del producto. La captura se retomó sin repetirla; su cierre
previo por limpieza no se atribuye a la API. Sólo se repitió la pregunta para
validar la corrección. No hubo frontend, otra suite global ni nueva prueba de VM.
Siguen43 escenarios amplios abiertos y0/12 páginas completamente aceptadas.

## Etapa anterior: preguntas y continuidad comprobadas; calidad integral pendiente

El catálogo3 exige registrar preguntas materiales mediante la herramienta. Las
admisiones directas sin hilo reciben pedidos anteriores de la misma tarea con
texto/hash y procedencia histórica sin autorización vigente. Tareas y Conversación
ya usaban hilo: conservan el alcance elegido y el reinicio explícito sin historial.

Pasan46 pruebas de fuente,46 del wheel y5 del verificador;605 archivos coinciden,
324 productivos.33 definiciones documentadas. En4 turnos reales con Ken: pregunta
persistida/pausa confirmada, respuesta guardada sin autoejecución, continuación450
segundos; corrección activa invalida el primer intento y el siguiente compara12/92
vigentes con35/535 originales. Dos servicios y todos sus peers cerrados.
[Informe y límites](communication-flow-review.md),
[recibos](communication-flow-live.json), [paquete](communication-packaging.json).

**Lista vigente al cambiar de tarea:**
- Terminado: continuidad de admisiones sin hilo y preguntas respondibles,
  **19 min 50 s** (07:41:07–08:00:57 UTC), hasta el corte de validación/registro.
  Los dos escenarios reales suman89,576s; no equivalen a la duración del bloque.
- Terminado previamente: correcciones/auditoría de dependencias, **26min14s**.
- Siguiente principal: recuperación ante interrupción/reinicio con una ejecución
  activa. Todavía no comenzó; publicar la lista y registrar inicio al comenzar.
- Pendiente de comunicación/prompts: observación humana, otros perfiles/recorridos,
  evaluación científica/representativa y60 revisiones estáticas desactualizadas.
  El inventario actual contiene83 candidatos,23 revisiones vigentes; no está verde.
- Pendiente: Ken/ONNX, Chroma/licencias, datos históricos reales del propietario,
  demás recuperación y aceptación integral de12 páginas.
- Después de todas las capacidades principales: detalles acumulados, validación
  final y revisión independiente. DD084 conserva10 avisos de estilo.

Se conservan el rechazo inicial de preparación sin inferencia y el fallo del
verificador que buscaba símbolos del ensayo anterior. Se revalidaron sus recibos
sin repetir respuestas; la corrección activa era el escenario aún pendiente.
No hubo frontend nuevo, otra suite global ni revisión humana. Siguen43 escenarios
amplios abiertos y0/12 páginas completamente aceptadas; sin porcentaje global
sustentado. La política de lista/tiempo en cada transición sigue tras compactar.

## Etapa anterior: correcciones y auditoría registradas; seguridad integral pendiente

Se actualizaron KaTeX, minimatch, selector-parser y filelock, con reproducciones
válidas del renderizado bajo contaminación previa y de truncamiento del archivo
de bloqueo. Pasan36 pruebas Python de fuente,5 del auditor y33 del wheel;
604 archivos coinciden,324 productivos. Pasan136 contratos frontend/10 DOM,
build y árbol. HTTP/WS real confirma aislamiento, CSRF y cierre al salir; servicio
cerrado, cero inferencias.16 definiciones documentadas.
[Informe y límites](dependency-security-review.md),
[resultados](dependency-security-results.json).

**Lista vigente al cerrar este bloque acotado:**
- Terminado: correcciones de cuatro dependencias, auditoría de todos los locks,
  inventario de licencias y configuración de mantenimiento verificada localmente.
  **26 min 14 s**,07:12:56–07:39:10 UTC, hasta el corte de validación y registro.
- Terminado en el bloque previo: siete comparaciones de contexto, **36min43s**;
  revisión humana todavía pendiente.
- Siguiente principal: comunicación; conectar preguntas materiales con su registro
  respondible y preservar el pedido original al corregir/reanudar. Todavía no
  comenzó: registrar su inicio al comenzar y publicar esta lista actualizada.
- Pendiente principal de seguridad: Ken/ONNX, exportador Chroma,139 declaraciones
  de licencia ausentes/revisión de compatibilidad y escenarios amplios. La
  automatización está preparada; no se publicó ni ejecutó en GitHub.
- Pendiente: datos históricos reales del propietario; recuperación ante fallos
  y actores activos; demás perfiles/evaluación humana y científica; aceptación
  integral de12 páginas.
- Después de todas las capacidades principales: detalles acumulados, validación
  global final y revisión independiente del conjunto. DD083 conserva3 avisos
  Ruff y9 errores ESLint; no hubo otra suite global ni aceptación de páginas.

La auditoría completa termina con hallazgos: ONNX tiene19 entradas/12 IDs distintos
bajo el pin de Ken0.18.0; Chroma tiene5 entradas/4 IDs distintos sin parche publicado
observado. El producto principal y npm no presentan avisos conocidos en este corte.
No se fuerza una combinación incompatible ni se ocultan los hallazgos. Siguen43
escenarios amplios abiertos y0/12 páginas completamente aceptadas; no hay porcentaje
global defendible. Sólo se cierra la entrega estrecha de los tres avisos frontend.

## Etapa anterior: comparación de contexto ejecutada; revisión humana pendiente

Se observaron **7 pares**,2 de desarrollo y5 reservados, con16 turnos reales por
suscripción y Ken. Modelo/esfuerzo, catálogo e inputs sustantivos coinciden;
los hashes comprueban las políticas efectivamente entregadas. La corrección activa
invalida el intento anterior y las dos respuestas siguientes dan20/220. Los14
servicios y sus peers están cerrados. Pasan19 pruebas dirigidas;51 definiciones
tienen docstrings y324 archivos productivos coinciden con la instalación.
[Resultados y límites](context-alignment-review.md),
[respuestas anónimas](context-alignment-human-review.md).

**Lista vigente al cerrar el bloque y preparar el siguiente:**
- Terminado en este tramo: evaluador, siete comparaciones reales, controles de
  procedencia/corrección y material para revisión humana. **36 min 43 s**
  (06:34:27–07:11:10 UTC), incluyendo preparación, diagnóstico, ejecución y registro.
  La suma de los14 brazos fue7min35s; no confundirla con la duración total.
- Pendiente dentro de comunicación: observación humana; preguntas materiales que
  quedaron sólo en prosa; continuidad del pedido entre admisiones; demás perfiles,
  recorridos y evaluación científica. No hay aceptación integral de comunicación.
- Siguiente principal: revisión de seguridad y dependencias. Todavía no comenzó;
  registrar su inicio al comenzar, sin sumar el intervalo de espera a esa tarea.
- Pendiente: ubicación/migración de datos históricos reales del propietario;
  recuperación ante fallos más amplios y actores activos; evaluaciones restantes;
  aceptación integral de12 páginas.
- Al final de todas las tareas gruesas: detalles acumulados, comprobaciones
  finales y revisión independiente de todo el plan. DD082 conserva12 avisos de
  estilo; los límites funcionales de comunicación permanecen en su evaluación.

Se conservan el rechazo de preparación sin modelo y la enmienda explícita del
comparador de UUID antes de los reservados. No se repitieron respuestas ni se
ajustaron prompts a los casos reservados. La revisión humana solicitada sigue
sin respuesta: no se inventan comprensión, esfuerzo o superioridad de una política.
Siguen43 escenarios amplios abiertos,0/12 páginas completamente aceptadas y una
suite global sin aprobar. No hay porcentaje global defendible.

## Etapa anterior: diagnóstico global cerrado y carrera del backup corregida

La suite común sobre `9fb873c` terminó: **2210 casos,2178 pasan,31 fallan y1 error
al preparar una prueba**, sin omisiones;23min46s de ejecución. Los776 archivos de
código/pruebas inspeccionados conservaron sus hashes durante la corrida. De los
100 fallos de la referencia antigua,75 ya no se recopilan,1 pasa y24 persisten.
No es una suite global verde. [Resultado y clasificación](current-global-results.json).

La carrera real del backup se reprodujo en cuatro combinaciones de base/ventana:
SQLite cerraba su última conexión y quitaba archivos temporales antes de que el
backup los abriera. Ahora se excluyen antes de consultar metadatos sólo si su base
se reconoce como SQLite. Se conservan filas confirmadas y archivos del usuario
con nombres parecidos; si desaparece uno de estos últimos, la copia se rechaza.
Pasan38 pruebas centrales de fuente,2 de compatibilidad y40 instaladas;602 archivos
Python/SQL coinciden,324 productivos. Las9 definiciones nuevas/modificadas tienen
docstrings. [Corrección](backup-sidecar-results.json), [paquete](backup-sidecar-packaging.json).

**Lista vigente al cambiar de tarea:**
- Terminado: evaluación global y clasificación inicial, **27min20s**
  (05:55:53–06:23:13 UTC);23min46s fueron ejecución de la suite.
- Terminado: carrera del backup, **8 min 27 s** (06:23:13–06:31:40 UTC),
  incluyendo reproducción, corrección, diagnóstico dirigido y verificación instalada.
- Siguiente principal: evaluación de contexto y comunicación; casos reservados,
  comparación de prompts y preparación de observación humana. Aún no comenzó.
- Pendiente: datos históricos reales del propietario; recuperación más amplia;
  evaluaciones reales/científicas restantes; seguridad; aceptación integral de12 páginas.
- Al final de las capacidades principales: DD080/081 y los demás detalles,
  seguido de revisión independiente de todo el plan.

DD081 conserva24 casos del contrato antiguo de estados,5 preparaciones históricas,
1 fixture ausente y1 límite de prueba pendiente. El caso de checks pasa en23,614s
con límite diagnóstico60s; el límite común20s y los límites del producto siguen
iguales. Ruff347/ESLint9 pendientes en el corte global;12 avisos en los tres
archivos del arreglo. No se repite una suite de24min por ese pulido. Siguen43
escenarios amplios y0/12 páginas completamente aceptadas. Falta `test:e2e` unificado
y evaluación humana; no se reemplazan por estas pruebas dirigidas.

## Etapa anterior: eventos y reconexión comprobados

HTTP y WebSocket recuperan el mismo historial confirmado, con cursor exacto por
ID. Cada cliente tiene su emisor y plazo; una conexión lenta no bloquea a otras.
Al reconectar se recuperan páginas pendientes. La pérdida de continuidad por
retención se explica y exige actualizar la vista, sin fingir un historial completo.

Pasan116 pruebas de fuente y116 instaladas,136 contratos frontend y9 DOM;
build estricto correcto.602 archivos Python/SQL coinciden,324 productivos;
48 definiciones nuevas/modificadas tienen docstrings. El navegador real recupera
488 eventos sin pérdidas ni duplicados antes del borrado, comprueba el aviso de
retención y el aislamiento entre proyectos. Tres estados escritorio/móvil.
[Contrato](../architecture/durable-events.md), [resultados](durable-events-results.json),
[paquete](durable-events-packaging.json), [navegador](../design/audits/2026-11-07-durable-events/report.md).

**Lista vigente al cambiar de tarea:**
- Terminado: historial durable, reconexión, aislamiento de clientes lentos y aviso
  de pérdida de continuidad. **30 min 06 s** (05:24:44–05:54:50 UTC),
  desde el inicio hasta cerrar este registro, incluyendo verificación/documentación.
- Siguiente principal: evaluación global actual y clasificación de fallos por
  capacidad pendiente. Todavía no comenzó; registrar el inicio al comenzar.
- Pendiente de ubicación: datos históricos reales del propietario.
- Después: recuperación ante fallos más amplios/actores activos; evaluaciones
  real, humana y científica; seguridad; aceptación integral de12 páginas.
- Después de todas las tareas gruesas: detalles secundarios y revisión
  independiente final de todo el plan. DD079 registra la superposición móvil,
  integración del panel, accesibilidad pendiente y tres avisos de lint.

La interfaz no está aceptada: Axe detectó contraste y una región sin foco; el
panel abierto tapa el selector móvil. El ensayo final cambia de proyecto cerrando
primero el panel, sin clic forzado. Estos hallazgos siguen abiertos para aceptación.
Siguen43 escenarios amplios y0/12 páginas completamente aceptadas. La última suite
global es anterior a estos cambios; no hay porcentaje global defendible.
Cero ejecuciones/modelos en este ensayo; todos los procesos propios cerrados.
La lista y el tiempo en cada transición permanecen tras compactar.

## Etapa anterior: historial y presupuesto conectados

Tareas pagina ejecuciones más allá de las30 del resumen. Tareas y Agentes permiten
inspeccionar intentos anteriores con su propio modelo, resultado y observaciones.
El presupuesto visible utiliza la misma cuenta que la admisión; distingue reserva,
medición parcial y ausencia de datos, sin inventar cuota/coste de la suscripción.
Consultar historia no cambia los controles del trabajo actual.

Pasan51 pruebas de fuente y51 instaladas,129 contratos frontend y8 pruebas DOM;
build estricto correcto.598 archivos Python/SQL coinciden,322 productivos;
18 definiciones Python nuevas/modificadas tienen docstrings. El navegador pasa
10 estados controlados en escritorio/móvil. [Contrato](../architecture/owner-history-budget.md),
[resultados](history-budget-results.json), [paquete](history-budget-packaging.json).

**Lista vigente al cambiar de tarea:**
- Terminado: lectura paginada de ejecuciones/intentos y presupuesto visible,
  con separación entre observaciones y reservas. **14 min 15 s**
  (05:09:35–05:23:50 UTC); incluye investigación, implementación y verificación.
- Siguiente principal: eventos durables, reconexión, clientes lentos y retención.
  Registrar el inicio cuando comience; este tramo todavía no está implementado.
- Pendiente de ubicación: datos históricos reales del propietario.
- Después: recuperación ante fallos más amplios/actores activos; evaluaciones
  real, humana, científica y global; seguridad; aceptación integral de12 páginas.
- Después de todas las tareas gruesas: detalles secundarios registrados y
  revisión independiente final del plan completo. DD078 conserva el pulido de
  este tramo, sin reabrir su capacidad principal.

Siguen43 escenarios amplios y0/12 páginas completamente aceptadas. No hay nueva
suite global ni porcentaje global defendible. No hubo modelos, migración real,
push, merge ni despliegue. La política de lista y tiempo en cada transición se
mantiene después de compactar; el tiempo transcurrido no es una estimación restante.

## Etapa anterior: recuperación después de nuevas escrituras comprobada

La restauración y reinscripción explican que una copia excluye las escrituras
posteriores; no suponen que el original siga disponible. Se comprobaron una copia
43, actualización58, escrituras nuevas y restauraciones separadas de la copia
vieja y actual, conservando los cambios en el original. El downgrade implícito
se rechaza. La política distingue inversas condicionadas de versiones sin inversa
publicada; no se afirma una vuelta atrás universal después de usar funciones nuevas.

Los recibos completos ya no bloquean la reinscripción al superar64KiB: un sobre
pequeño referencia detalles por hash/tamaño/identidad, hasta128MiB. Pasan321adjuntos,
recibos dañados/enlazados, formato1 y salida abrupta entre archivos. Las seis
pruebas antiguas fallidas y cuatro rechazos ambiguos se corrigieron usando
esquemas históricos reales, sin rebajar las guardas del producto. La inspección final detectó además que la
inversa wiki podía borrar33 bajo34/58: ahora exige33 como última versión y
conserva íntegra la base al rechazar. Pasan15 pruebas dirigidas de wiki, además
de la comprobación del paquete final.

**Verificación:**130 casos centrales de fuente y28 casos históricos corregidos;
160 casos del paquete instalado pasan, sin fallos ni omisiones.595 archivos
Python/SQL coinciden,320 productivos;31 definiciones nuevas/modificadas tienen
docstrings. Tiempo hasta verificar: **19 min 53 s** (04:47:44–05:07:37 UTC).
[Política y ejemplo](../architecture/migration-recovery-policy.md),
[resultados](recovery-policy-results.json), [paquete](recovery-policy-packaging.json).

**Lista vigente al cambiar de tarea:**
- Terminado en este tramo: recuperación con límites explícitos después de nuevas
  escrituras, metadatos grandes y pruebas de inversas preparadas correctamente.
- Siguiente principal: historial y presupuestos, contrastando UI/API y persistencia.
  El siguiente bloque todavía no comenzó; registrar su inicio al hacerlo.
- Pendiente de ubicación: datos reales del propietario y sus formatos/versiones.
- Después: evaluaciones real, humana, científica y global; seguridad; aceptación
  integral de12 páginas; revisión final de todo el plan.
- Al final: detalles secundarios. DD077 registra30 avisos de lint y dos líneas
  en blanco al final de archivos de prueba; no justifican repetir estos ensayos.

Los43 escenarios y las12 aceptaciones integrales siguen abiertos. La recuperación
ante fallos destructivos más amplios y actores activos conserva su alcance
pendiente. No hubo modelos, datos reales migrados, push, merge ni despliegue.

## Etapa anterior: importación histórica comprobada; siguen recuperación e inversas

Los comandos públicos preparan una instalación nueva desde SQL histórico y rutas
externas explícitas. Conservan informes sólo en archivos, adjuntos y Git/worktrees.
Un exportador aislado recupera texto/metadatos de Chroma; el servidor conserva
fragmentos con procedencia y hash, sin inventar documentos completos ni aceptación.
El ensayo real de Chroma recupera105 registros:104 adjuntos de texto y uno sólo
con metadatos. Captura como fuente y lecturas HTTP por proyecto pasan tras
reinscripción; el servicio termina, con cero turnos de modelo y sin cuenta real.

Pasan **139 pruebas de fuente y139 instaladas**.593 archivos Python/SQL coinciden,
319 productivos;43 definiciones nuevas/modificadas tienen docstrings en inglés.
El esquema58 incluye procedencia inmutable, rechazo de inversa con historial y
41 fronteras de interrupción18–58. Tiempo hasta verificar: **24 min 10 s**,
desde04:21:30 UTC. [Guía](../architecture/legacy-import.md),
[resultados y límites](legacy-import-results.json), [paquete](legacy-import-packaging.json).

**Lista vigente al cambiar de tarea:**
- Terminado en este tramo: importador de layouts externos, informes/adjuntos/Git,
  exportación Chroma paginada y procedencia hasta la captura de fuentes.
- Siguiente principal: política y rutas restantes de inversa/recuperación sin
  borrar historial utilizado. Revisar tamaños reales cuando exista su inventario.
- Pendiente de ubicación: datos históricos del propietario; la consulta sigue
  abierta. El ensayo sintético no cuenta como migración de esos datos.
- Después: historial/presupuestos; evaluaciones real, humana, científica y global;
  seguridad de dependencias; aceptación completa de12 páginas; revisión final.
- Al final de todas las tareas gruesas: detalles secundarios. DD076 conserva48
  avisos de lint; no repetir el ensayo por esos ajustes.

Los43 escenarios amplios y las12 aceptaciones integrales siguen abiertos. No se
promete compatibilidad con toda versión histórica de Chroma, ni coherencia con
escritores antiguos activos. No hubo push, merge ni despliegue. El siguiente bloque
aún no tiene hora de inicio: registrarla al comenzar, sin atribuirle esta espera.

## Etapa anterior: recuperación tras reboot comprobada; siguen datos históricos

Un proceso QEMU completa dos arranques con identificadores de kernel diferentes.
La autoridad anterior rechaza su uso; los comandos públicos capturan su evidencia,
restauran en otra ruta y crean autoridad nueva. El estado del proceso registrado
antes del reboot se conserva como historial, sin inventar cierre. Después pasan
un proceso no-op real y lecturas HTTP de tareas/adjuntos; servicio y VM terminan.
Se verifican Codex, Ken publicado y26 archivos de modelos, sin cuenta real ni
inferencia. Los cinco intentos previos y sus causas del entorno de ensayo quedan
registrados. [Resultados y límites](reboot-recovery-results.json).

Pasan **137 pruebas de fuente y137 del paquete instalado**, incluidos esquema56
a57 e inversa que rechaza borrar historial.588 archivos Python/SQL coinciden,
315 productivos;49 definiciones están documentadas. Tiempo hasta verificar:
**33min44s** (03:44:03–04:17:47 UTC). El ensayo exitoso completo llevó23,25s;
el tiempo del bloque incluye implementación y preparación/correcciones de la VM.

**Lista vigente:**
- Terminado: recorrido restaurado con suscripción/Ken y ahora recuperación tras
  reinicio controlado de una VM con conservación y lectura del historial.
- Siguiente principal: datos históricos y formatos externos. Sigue pendiente la
  respuesta sobre ubicación de los datos reales; avanzar con importadores/ensayos.
- Después: historial/presupuestos;
  evaluaciones real, humana, científica y global; seguridad de dependencias;
  aceptación integral de las12 páginas; revisión final del plan completo.
- Al final de las tareas gruesas: detalles secundarios registrados en
  [deferred-details.md](deferred-details.md); DD075 conserva45 avisos de lint.

Este ensayo no cubre pérdida de energía, un agente nativo ejecutándose durante el
reboot, datos históricos del propietario ni aceptación integral. Los43 escenarios
amplios y las12 aceptaciones completas siguen abiertos. No se reinició el equipo
del propietario ni se hicieron push, merge o despliegue.

## Etapa anterior: recorrido nativo restaurado comprobado; sigue recuperación tras reboot

El ensayo nuevo copia datos sintéticos a otra ruta y conserva una petición antigua
sin ejecutarla. Tras reinscripción, envía una única petición nueva mediante la
suscripción. Ken devuelve el código, Python calcula200 y se guardan un finding
provisional con dos citas y un informe draft. Un segundo arranque conserva todo.
Cinco peers y los dos servicios originales quedaron cerrados. La inspección
posterior de sólo lectura pasa con cero turnos nuevos.

Pasan12 pruebas del harness y sus15 definiciones nuevas/modificadas están
documentadas. Los312 archivos productivos coinciden con el wheel y su instalación;
el ensayo importó backend instalado. No se reconstruyó el paquete sin cambios
productivos ni se repitió el turno. Tiempo hasta verificar: **6min34s**
(03:34:13–03:40:47 UTC). [Uso](../../evals/operation/README.md),
[resultados](restored-host-evaluation-results.json).

**Lista vigente al cambiar de tarea:**
- Implementado: copia/restauración, reinscripción y ahora recorrido completo de
  modelo/Ken con conservación tras reinicio del servicio.
- Siguiente principal: recuperación/reinscripción tras cambio real de kernel;
  un reinicio del servicio no cubre el rechazo de la autoridad tras reboot.
- Pendiente de ubicación: datos históricos del propietario. Siguen layouts
  externos, informes sólo en archivos, documentos sólo en Chroma e inversas.
- Después: historial/presupuestos; evaluación real, humana, científica y global;
  seguridad, aceptación integral de12 páginas y revisión final.
- Al final: detalles secundarios. DD074 conserva tres avisos de lint y el ajuste
  de extensión del informe a la sencillez de una comprobación aritmética.

No se reinició el equipo del propietario, migraron sus datos ni hicieron push,
merge o despliegue. Los43 escenarios amplios y las12 aceptaciones integrales
siguen abiertos; este ensayo no demuestra comprensión humana o calidad científica.

## Etapa anterior: reinscripción implementada; sigue recorrido nativo restaurado

`enroll-restored-host` habilita una copia con recursos, autoridad y acceso nuevos.
Los planes copiados quedan pausados y el trabajo pendiente se conserva como
historial, sin afirmar cierre de actores/efectos originales. La activación se
publica al final; un proceso interrumpido conserva el bloqueo y se recupera desde
la copia original a otra ruta nueva. El navegador reconoce el cambio de base,
explica un ejemplo concreto y archiva solicitudes/borradores antes de entrar.

Pasan94 pruebas de fuente y94 del paquete instalado;583 archivos Python/SQL
coinciden,312 productivos. Las13 definiciones Python nuevas/modificadas tienen
docstrings y la sesión/aviso web tiene JSDoc. Pasan129 contratos frontend y4 DOM;
build correcto. Tres estados de navegador comprobados, dos capturas revisadas,
sin errores JS ni hallazgos Axe en escritorio/móvil. Tiempo medido hasta verificar:
**18 minutos30 segundos** (03:13:16–03:31:46 UTC).
[Guía](../architecture/installation-backup.md), [resultados](restored-enrollment-results.json),
[paquete](restored-enrollment-packaging.json), [aviso](../design/audits/restored-session/report.md).

**Lista vigente al cambiar de tarea:**
- Implementado en este tramo: reinscripción fresca, conservación del historial,
  pausa de planes, dos arranques del servicio nativo sin replay y protección del
  navegador ante una instalación distinta. Cero turnos de modelo.
- Siguiente principal: recorrido de modelo/Ken completo en la instalación
  restaurada; recuperación/reinscripción tras reboot real. El no-op de kernel y
  el reinicio de servicio no prueban esas dos obligaciones.
- Pendiente de ubicación: datos históricos reales; sigue la consulta al dueño.
  También siguen layouts externos, informes sólo en archivos, documentos sólo en
  Chroma e inversas/recuperación posteriores.
- Después: historial/presupuestos; evaluación real, humana, científica y global;
  seguridad, aceptación integral de12 páginas y revisión final.
- Al final: detalles secundarios registrados. DD073 conserva19 avisos Python,
  un aviso frontend heredado, aviso Starlette/httpx y tamaño de bundle.

Los43 escenarios amplios continúan abiertos y0/12 páginas están aceptadas
integralmente. No hubo cambios en bases del propietario ni push, merge o despliegue.

## Etapa anterior: copia/restauración de datos implementada; sigue reinscripción

Los comandos `backup-host`, `verify-backup` y `restore-host` capturan datos
consistentes, verifican manifiesto/hashes/conteos y restauran en otra carpeta.
Conservan archivos, adjuntos, Git/worktrees y cambios sin commit; los lectores
HTTP mantienen la separación por proyecto. La autoridad y el acceso antiguos
quedan como evidencia, con ejecución bloqueada hasta reinscripción explícita.
Pasan 82 pruebas de fuente y 82 instaladas; los 19 casos de restore se repitieron
tras sincronizar los directorios finales. Coinciden 581 archivos Python/SQL,
311 productivos. Las 42 definiciones nuevas/modificadas tienen docstrings.
Tiempo medido hasta verificar: 19 minutos 42 segundos (02:50:44–03:10:26 UTC).
[Guía](../architecture/installation-backup.md),
[resultados](installation-backup-results.json), [paquete](installation-backup-packaging.json).

**Lista vigente:**
- Implementado en este tramo: copia/verificación/restauración de datos de una
  instalación administrada. No se habilitó todavía ejecución en el host restaurado.
- Siguiente principal, dentro del mismo bloque: reinscripción del nuevo host,
  conciliación de intentos/entregas sin replay y recuperación tras reboot.
- Pendiente de ubicación: datos históricos reales. Las tres rutas predeterminadas
  están ausentes y se consultó al propietario; siguen informes sólo en archivos,
  documentos sólo en Chroma y layouts históricos externos.
- Después: historial/presupuestos; evaluaciones real, humana, científica y global;
  seguridad de dependencias, aceptación de las 12 páginas y revisión final.
- Al final: detalles secundarios; DD072 conserva 15 avisos de lint.

El bloque de restauración operativa permanece abierto. Siguen abiertos los 43
escenarios amplios y 0/12 páginas tienen aceptación integral. No se modificaron
bases del usuario ni se hicieron llamadas a modelos, push, merge o despliegue.

## Etapa anterior: cadena de migraciones comprobada; sigue restauración

Un catálogo único conserva el orden18–56, permite avances con destino explícito
sin downgrade y rechaza historial futuro o incompleto. Las39 interrupciones de
procesos antes del marcador revierten el paso y permiten continuar sobre la misma
base. Los preparadores históricos usan esquemas completos de su versión; se
conservan IDs, relaciones, paquetes, revisiones y rechazos de inversas con historial.
Pasan208 pruebas dirigidas de fuente y127 instaladas;577 archivos Python/SQL
coinciden (308 productivos).39 definiciones y22 módulos tienen docstrings.
Tiempo medido hasta verificar este tramo:21 minutos32 segundos
(02:27:50–02:49:22 UTC). La restauración completa todavía no está cerrada.
[Contrato](../architecture/forward-migrations.md),
[resultados](migration-chain-results.json), [paquete](migration-chain-packaging.json).

**Lista vigente:**
- Cerrado en este tramo: catálogo/avance18–56, recuperación de39 interrupciones,
  preparadores históricos corregidos y comprobación de inversas existentes.
- Siguiente principal: copia y restauración completa en otra ubicación; inventario
  de datos reales, recuperación/inversas posteriores y reboot/re-enrollment.
- Después: historial/presupuestos; evaluaciones real, humana, científica y global;
  seguridad de dependencias, aceptación completa de12 páginas y revisión final.
- Al final: detalles secundarios. DD071 conserva22 avisos de lint, un espacio de
  fin de archivo y el aviso heredado de Starlette/httpx.

Los43 escenarios amplios siguen abiertos;0/12 páginas aceptadas integralmente.
No hubo migración de datos del usuario ni nueva suite global. No se cuentan
los registros SQL de pruebas como ejecuciones o aceptaciones reales.

## Etapa anterior: Ken e inspección migrados; siguen datos y restauración

Ken publicado pasa 12 controles mediante el broker actual, con fuentes/memorias
separadas, modelos locales y cierre comprobado. La fixture del propietario crea
un comando real nuevo y lee sus resultados por HTTP y navegador, sin depender de
un ensayo histórico ni configurar inferencia. Pasan 23 tests dirigidos, la lectura
HTTP en 13 ventanas y 17 estados de escritorio/móvil sin hallazgos Axe ni errores
JS. Se documentan 29 módulos/clases/funciones y se revisan cuatro capturas.
Tiempo medido de este bloque: unos 14 minutos (02:13:12–02:27 UTC).
[Resultados y límites](remaining-evaluation-runners-results.json),
[revisión visual acotada](../design/audits/native-owner-fixture/report.md).

**Lista vigente:**
- Cerrado en este bloque: Ken por broker, inspección HTTP y captura de Tareas/
  Conversación con fixtures nuevos. Cero modelos y todos los actores cerrados.
- Siguiente: migraciones, inversas, restauración real y recuperación/re-enrollment
  tras reboot; comenzar por el inventario y los fallos conocidos de migración.
- Después: historial/presupuestos; evaluaciones real, humana, científica y global;
  seguridad de dependencias, aceptación completa de 12 páginas y revisión final.
- Al final: detalles secundarios. DD070 conserva cuatro avisos de lint y la
  altura de cabecera móvil. Siguen abiertos 43 escenarios y 0/12 aceptaciones integrales.

No se actualiza un porcentaje global ni se atribuye aceptación actual a los
experimentos históricos de candidatos. No hubo cambios productivos ni rebuild.

## Etapa anterior: tres evaluaciones de procesos migradas

Análisis, comandos y pérdida del padre usan el broker/dominio actual, bases
sintéticas y autoridades nuevas. Pasan los siete controles de análisis, Stop
de descendientes, aislamiento entre propietarios, cierre con SQLite bloqueado,
pérdida de RPC y recuperación sin repetir trabajo. Cero turnos de modelo.
Siete tests dirigidos pasan y 27 módulos/clases/funciones están documentados.
Tiempo medido del bloque: unos 23 minutos (01:49:44–02:12 UTC).
[Uso](../../evals/runtime/README.md), [recibos y fallos previos](kernel-evaluation-runners-results.json).

**Lista vigente:**
- Cerrado en este grupo: tres runners de procesos y sus pruebas reales. Se
  conservan resultados inciertos como tales y cuatro fallos del evaluador.
- Siguiente: aislamiento de Ken e inspección/captura del propietario con fixtures
  actuales. Los experimentos de candidatos siguen siendo históricos.
- Después: migraciones/inversas/restauración real y reboot; historial/presupuestos;
  evaluaciones real, humana, científica y global; seguridad de dependencias,
  aceptación completa de las 12 páginas y revisión final.
- Al final: detalles secundarios, incluidos los cuatro avisos DD069. Siguen
  abiertos los 43 escenarios amplios y 0/12 páginas tienen aceptación integral.

El cierre de un proceso padre se observa separado del vaciado de todo su cgroup.
Cada propietario independiente tiene su propia autoridad; no se amplía la
política de concurrencia de una instalación. Sin nueva suite global ni rebuild.

## Etapa anterior: seis escenarios nativos migrados

Investigación/corrección, Conversación, preguntas/respuestas, Stop, continuidad
y cálculo usan instalaciones sintéticas nuevas con autoridad propia y recursos
explícitos. Se reutiliza el launcher instalado; el modelo sigue configurable y
los límites del operador se conservan o reducen. Nueve admisiones por suscripción,
sin repetir un turno incierto. [Comandos](../../evals/runtime/README.md),
[resultados y límites](native-evaluation-runners-results.json).

Cinco runners reales terminan correctamente. El de cálculo terminó su trabajo,
pero su harness confundía el catálogo de negocio de 45 herramientas con las 54
de la composición nativa. Se corrigió el check; los artefactos originales y el
recibo HTTP tras reinicio se verificaron sin nueva generación. Se conserva el
fallo original. Pasan 38 casos dirigidos; 307 archivos productivos coinciden con
el paquete instalado y 26 definiciones tienen docstrings. El consumo de Stop y
del turno que pregunta permanece desconocido. No hay nueva suite global.

**Lista vigente:**
- Cerrado en este grupo: seis escenarios portados y comprobaciones documentadas;
  corrección, preguntas, recibos repetidos, continuidad, cálculo y cierres reales.
- En curso: runners de comandos, pérdida del padre, herramientas de análisis,
  aislamiento de Ken y captura/inspección del propietario; experimentos de
  candidatos conservados como históricos, sin atribuirles aceptación actual.
- Después: migraciones/inversas/restauración real y reboot; historial/presupuestos;
  evaluaciones real, humana, científica y global; seguridad de dependencias,
  aceptación completa de 12 páginas y revisión final.
- Al final: detalles secundarios, incluidos los cinco avisos de estilo DD068.
  Los 43 escenarios amplios siguen abiertos y ninguna página tiene aceptación integral.

## Etapa anterior: configuración retirada; runners todavía en migración

Se retiran 75 opciones sin consumidores, la derivación de embeddings por proveedor
y el escritor global de settings.json. Quedan diez ajustes usados por DB,
recuperación de fuentes y vistas de Git; modelos y autoridad siguen en la
configuración nativa versionada. No se borran ni importan datos del usuario.
[Contrato y migración](../architecture/retained-configuration.md),
[resultados](configuration-retirement-results.json).

Pasan 157 casos de configuración/consumidores y 38 de perfiles/MCP; dos requieren
assets semánticos explícitos y se omiten. El paquete coincide en 570 archivos y
sus 155 casos comparables pasan entre las ejecuciones documentadas. Dos checks
son sólo del checkout. La corrección del entorno instalado verifica 196 imports
del paquete. Catálogo MCP real de 45 herramientas y recorrido HTTP/WebSocket
completos, sin turnos de modelo. No hay suite global nueva.

**Lista vigente:**
- Hecho: migración frontend; ahora retirada de configuración sin consumidores y
  del escritor global. Se conservan modelo configurable y datos históricos.
- En curso: migración de runners. Se recuperaron catálogo y helper HTTP
  instalado; la [tabla de escenarios restantes](../../evals/runtime/README.md)
  no se cuenta como aceptación actual.
- Después: migraciones/inversas/restauración real y reboot; historial/presupuestos;
  evaluaciones real, humana, científica y global; seguridad de dependencias,
  aceptación completa de 12 páginas y revisión final.
- Al final: detalles secundarios DD067 (cuatro avisos de estilo y avisos del
  harness). Siguen 43 escenarios abiertos y ninguna página aceptada integralmente.

## Etapa anterior: frontend migrado

React19.3, Vite8, TypeScript6, Tailwind4 y el stack de documentos actualizado
compilan desde una instalación limpia. Pasan126 contratos y3pruebas DOM;
Resumen y Ejecución completan15estados controlados de navegador. Se conserva
el foco por teclado también en colores forzados. El acceso suma2estados normales
sin avisos Axe y1con una discrepancia de contraste pendiente; ese runner sigue
saliendo1. [Decisiones y límites](../architecture/frontend-dependencies.md),
[resultados](frontend-dependencies-results.json).

**Lista vigente al cambiar de tarea:**
- Cerrado en su alcance: migración compatible del frontend, instalación limpia,
  pruebas DOM y configuración de lint. No acepta todas las páginas ni seguridad.
- Siguiente: configuración y runners históricos restantes; después migraciones,
  inversas, restauración real y recuperación tras reboot.
- Pendiente principal: historial/presupuestos; evaluación real, humana,
  científica y global; aceptación de12páginas, seguridad de dependencias y
  revisión final. Siguen43escenarios abiertos y0páginas aceptadas integralmente.
- Al final: detalles secundarios. DD066 conserva12incidencias de lint,
  bundle grande, configuración SSR deprecada y discrepancia Axe en colores
  forzados. Los3avisos de seguridad únicos (16entradas de dependencias) quedan
  explícitamente abiertos antes de aceptar el producto.

Tiempo medido en este tramo de reanudación: aproximadamente10minutos hasta
guardar los recibos, desde21:51Argentina; no incluye la preparación anterior
al resumen de contexto. No hay estimación global fiable ni porcentaje nuevo.
La imagen nativa anterior todavía contiene las dependencias frontend anteriores.

## Etapa anterior: contenedor nativo comprobado

La imagen incluye Ken publicado en un entorno separado, con dependencias fijadas
por hashes, y bubblewrap con las capacidades requeridas. El recorrido real desde
el paquete instalado completa investigación con Ken y cálculo, guarda hallazgo
e informe y conserva ambos tras reiniciar. Cinco peers cerrados, dos cierres143,
cgroup retirado y ninguna sesión antigua aceptada. Coinciden 308 archivos
productivos Python/SQL. [Guía de instalación](../architecture/native-container-operation.md),
[evidencia](native-container-results.json).

La autoridad conserva el observador de PID del host para el backend de control;
los agentes mantienen namespaces privados. El ensayo anterior completó la
investigación pero rechazó correctamente el reinicio con otro observador. Se
conserva esa evidencia; no se relajó la validación ni se repitió ese intento.
El alcance probado es Linux/UID1000 con Podman rootless; reboot, re-enrollment,
restauración real y otros entornos no quedan aceptados por este recorrido.

**Lista vigente al cambiar de tarea:**
- Cerrado recientemente: host nativo; ahora imagen con Ken y recorrido nativo
  completo con reinicio y configuración documentada.
- Siguiente: actualizar las dependencias del frontend y resolver compatibilidades
  del conjunto. La aceptación integral de sus páginas sigue siendo otra tarea.
- Pendiente principal: configuración/runners históricos restantes;
  migraciones/inversas/restauración real y recuperación tras reboot;
  historial/presupuestos; evaluaciones real, humana, científica y global;
  aceptación de 12 páginas y revisión final. Siguen 43 escenarios abiertos.
- Al final: detalles secundarios. DD065 conserva un aviso nuevo de lint y uno
  anterior; no se repiten builds ni turnos reales sólo por ese pulido.

## Etapa anterior: host nativo preparado y recorrido real comprobado

Se añaden `init-host`, `check-host --probe` y `researcher-start --installation`.
Usan recursos explícitos ya instalados, crean almacenamiento nuevo y conservan
separado el testigo de autoridad. El modelo queda en configuración. El recorrido
del paquete instalado sirve web/API, exige emparejamiento y usa la suscripción:
Ken lee código, un comando calcula 200, se guardan hallazgo provisional e informe
borrador y ambos sobreviven al reinicio. Los cinco peers quedan cerrados y los
dos cierres del servicio se observan. [Guía](../architecture/native-host-installation.md),
[evidencia y límites](host-installation-results.json).

Se corrigió un fallo reproducido bajo uvloop al cerrar pipes, conservando la
entrega de EOF. Pasan 23 pruebas de preparación/CLI y 35 de transporte/Git; las
tres regresiones de cierre pasan también con asyncio. El paquete pasa 55 casos;
un check requiere `start.sh` del checkout y pasa allí. Coinciden 571 archivos
Python/SQL, con 27 definiciones nuevas/modificadas documentadas. El primer intento
real incierto se conserva; el éxito corresponde a otra instalación sintética,
sin repetir esa admisión. No hay suite global nueva ni restauración real aceptada.

**Lista vigente al cambiar de tarea:**
- Cerrado en esta etapa: preparación/arranque del host con recursos existentes,
  corrección del transporte y recorrido real por HTTP con reinicio.
- Siguiente en operación: admisión nativa desde el contenedor y aprovisionamiento
  portable; revisar configuración y runners históricos restantes.
- Pendiente principal: dependencias frontend; migraciones/inversas/restauración
  real; historial/presupuestos; evaluación real, humana, científica y global;
  aceptación integral de 12 páginas y revisión final. Siguen 43 escenarios abiertos.
- Al final: todos los detalles secundarios. DD064 conserva nueve avisos de estilo
  y avisos heredados; no se repiten admisiones reales por ese pulido.

## Etapa anterior: sandbox y launcher retirados; sigue el aprovisionamiento nativo

El producto exige el perfil explícito `owned-codex-v1`. Se retiraron pods,
imagen histórica, helper de archivos y launcher anterior; la sesión compartida
del runtime nativo se conserva. No se borran fuentes, adjuntos ni datos.
[Mapa y migración](../architecture/native-sandbox-retirement.md),
[resultados y límites](sandbox-retirement-results.json).

**Comprobado:** 164 casos de fuente y 162 del paquete instalado pasan en las
selecciones y correcciones documentadas; dos checks de manifiestos son sólo de
fuente. El wheel reconstruido desde sdist contiene 568 archivos Python/SQL
idénticos a fuente e instalación, sin archivos eliminados de builds anteriores.
Se retiraron 38 funciones de test, incluidas tres de pods antes omitidas; no se
cuentan como fallos reparados. Catálogo: 83 candidatos en 271 archivos, siete AST
revalidados sin cambios de instrucciones. No hay nueva suite global ni modelos.

**Lista vigente:**
- Cerrado recientemente: imagen web/API y ensayo de Forgejo; ahora sandbox y
  launcher históricos, con configuración y guía de migración vigentes.
- En curso: aprovisionamiento del host nativo, recursos/cuenta/Ken y admisión
  completa; quedan configuración antigua y runners históricos por revisar.
- Pendiente principal: dependencias frontend; migraciones/inversas/restauración
  real; historial/presupuestos; evaluación real, humana, científica y global;
  aceptación integral de 12 páginas y revisión final. Siguen 43 escenarios abiertos.
- Al final: todos los detalles secundarios. DD063 conserva tres avisos de lint
  y una línea vacía; no se repiten recorridos por esos detalles.

## Etapa anterior: operación — Forgejo ensayado; sigue el host nativo

Forgejo queda fijado en15.0.11 por digest, con HTTPS, puerto local y directorios
explícitos de datos/TLS. El override rootless conserva el mapeo UID1000 ensayado.
El recorrido real9.0.3→15.0.11 conserva cuenta, token, repositorio, ramas y PR;
verifica clone/push sobre TLS y creación/reconciliación con el cliente nativo.
`doctor` completa28 comprobaciones y sale0, con un aviso de configuración antigua
anotado en DD062. El backup se restaura en otra carpeta con9.0.3; conserva el
estado original. La copia actualizada mantiene su segunda PR y commit nuevo.
[Guía](../architecture/forgejo-upgrade.md), [resultados](forgejo-upgrade-results.json).

**Lista vigente:**
- Implementado recientemente: imagen web/API con persistencia; actualización de
  configuración Forgejo y ensayo completo de upgrade/backup/restore con datos
  sintéticos. Ninguna instancia ni datos del usuario fueron migrados.
- En curso: operación del host nativo, sus recursos y admisión; queda retirar el
  sandbox histórico sin consumidores y verificar el despliegue completo.
- Pendiente principal: dependencias frontend; migraciones/inversas/restauración
  real de Researcher; historial/presupuestos; evaluación real, humana, científica
  y global; aceptación integral de12páginas y revisión final. Los43escenarios
  siguen abiertos;48conceptos y12pilotos no equivalen a aceptación integral.
- Al final: todos los detalles secundarios, incluido DD062. No se repite el
  ensayo por orden de imports o por el aviso heredado de configuración.

## Etapa anterior: web/API empaquetadas y persistencia comprobada


La imagen de web/API ya se construyó y probó con Podman aislado: instala el wheel
y su extensión nativa, incluye la web compilada y ejecuta como UID1000. Los
314 archivos productivos Python/SQL instalados coinciden con fuente. Los adjuntos
pueden conservar su ubicación explícita o usar el directorio de datos, fuera de
site-packages; health consulta esa ubicación. Se recuperó el fixture API y se
adaptó el cambio genérico de estado al rechazo nativo, conservando la edición
de metadatos.

**Comprobado:** 91 pruebas API/configuración y tres de salud pasan. La imagen
rechaza arranque sin base e inicialización sobre datos existentes; sirve la web,
exige emparejamiento, crea un proyecto y conserva un adjunto descargable tras
reiniciar. Ambos cierres se observan y la sesión antigua queda invalidada.
No hubo llamadas a modelos. [Contrato](../architecture/container-operation.md),
[resultados](operation-image-results.json).

Esto no acepta aún el despliegue completo: siguen Forgejo, el aprovisionamiento
del host y la admisión nativa dentro del contenedor. El build conserva las
dependencias frontend existentes; sus actualizaciones planificadas siguen siendo
trabajo principal. No hay nueva suite global ni aceptación integral de páginas.

**Lista vigente:**
- Implementado recientemente: retirada de componentes antiguos; imagen instalada
  de web/API con prueba real de persistencia, reinicio y acceso del propietario.
- En curso: operación/despliegue; siguiente paso, actualización y ensayo de
  backup/upgrade de Forgejo, seguido de aprovisionamiento/admisión nativa.
- Pendiente principal: migraciones/inversas/restauración real; historial y
  presupuestos; actualización de dependencias frontend; evaluación real, humana,
  científica y global; aceptación integral de las 12 páginas y revisión final.
  Los 48 conceptos y 12 pilotos no equivalen a páginas completamente aceptadas.
- Al final: todos los detalles secundarios registrados. DD061 conserva nueve
  avisos de lint, el aviso de tamaño del bundle y la deprecación de TestClient.

## Etapa anterior: autonomía y plantillas/proveedores históricos retirados

Se retiran 54 módulos: autonomía, su scope antiguo de cancelación, 39 plantillas
de roles/tecnologías y dos configuradores de proveedor. Se conserva el registro
existente de control de parada, sin scheduler nuevo. El cierre ahora incluye
hilos sin objeto de flow y distingue una petición de Stop del cierre observado.
Mensajes, tareas e instrucciones nativas se conservan.
[Contrato y mapa](../architecture/native-autonomy-retirement.md).

**Comprobado:** 169 pruebas pasan en fuente y 169 en el paquete instalado; quedan
los mismos tres fallos de fixtures de migración. Se reutilizó el recibo instalado
anterior después de comprobar sus bytes contra el commit, sin repetir ese baseline.
Coinciden 578 archivos Python/SQL; 244 imports backend proceden del entorno
instalado, con 83 distribuciones compatibles. Hay 22 definiciones nuevas/modificadas
documentadas. Se retiran 49 funciones de test obsoletas y se conservan otras dos
renombradas. Prompts: 83 candidatos en 279 archivos, 515 archivados, sin revisión
estática pendiente. Las instrucciones nativas no cambian; no hay nueva suite global.

**Lista vigente:**
- Cerrado recientemente: herramientas/bibliotecas, API interna/CLI, comunicación,
  flows/helpers, autonomía y plantillas/lectores de proveedor antiguos.
- Siguiente tarea principal: operación, arranque, imágenes y fixtures de integración
  que todavía presuponen servicios retirados.
- Pendiente principal: migraciones/inversas/restauración real; historial completo y
  presupuestos; evaluación real, humana, científica y global; aceptación integral
  de las 12 páginas y revisión final. Siguen 43 escenarios abiertos, 12 pilotos y
  48 conceptos; ninguna página está completamente aceptada todavía.
- Al final: todos los detalles secundarios; 15 avisos de estilo y una línea vacía
  final quedan en DD060. Los tres fallos de migración no son detalles de estilo.

## Etapa anterior: flows y helpers antiguos retirados

Se retiran 21 módulos y se conservan fuera de los flows las tres operaciones de
metadatos que consume la API. Los snapshots indican su origen histórico y que no
permiten reanudar el runtime nativo; no trasladan aprobaciones antiguas.
El bus compartido y la parada observada se mantienen.
[Contrato y mapa](../architecture/native-flow-retirement.md).

**Comprobado:** 218 pruebas pasan desde fuente y 218 desde el paquete instalado;
los tres fallos de fixtures de migración se reproducen con mensajes idénticos en
el paquete anterior. No hay omisiones. Coinciden 639 archivos Python/SQL; los 261
imports backend proceden del entorno instalado, con 83 distribuciones compatibles.
Las 17 definiciones nuevas/modificadas tienen docstrings. Se retiran 68 funciones
de test obsoletas; los cinco fallos antiguos de flows retirados no se cuentan como
reparados. Prompts: 227 candidatos en 333 archivos, 371 archivados y ninguna
revisión estática pendiente. No hay nueva suite global.

**Lista vigente:**
- Cerrado recientemente: herramientas/bibliotecas antiguas, API interna/CLI,
  servicios de comunicación/listeners y flows/helpers sustituidos o sin consumo.
- Siguiente: controladores de autonomía y lectores históricos restantes,
  preservando la parada de trabajadores registrados y sus datos.
- Pendiente principal: operación e imágenes; fixtures API históricos;
  migraciones/inversas/restauración y datos históricos; historial completo y
  presupuestos; evaluación real, humana, científica y global; aceptación integral
  de 12 páginas y revisión final. Siguen 43 escenarios abiertos, 12 pilotos y 48 conceptos.
- Al final: todos los detalles secundarios. Los 17 avisos de estilo y tres líneas
  vacías finales quedan en DD059; los fallos de migración y fixtures API son trabajo principal.

## Etapa anterior: servicios antiguos de comunicación y listeners retirados

Se retiran nueve módulos y se conservan los mensajes nativos, las notas del
propietario, el historial y el control de parada sobre trabajadores registrados.
El archivado ahora comprueba el proyecto y confirma su evento en la misma
transacción; el lector histórico no reinterpreta mensajes nativos aunque se
eliminen sus metadatos. [Contrato y mapa](../architecture/native-communication-services.md).

**Comprobado:** 179 pruebas pasan desde fuente y 179 en el paquete instalado;
los mismos cinco fallos de helpers/routers antiguos se reproducen en el paquete
anterior. No hay omisiones. Coinciden 664 archivos Python/SQL; los 265 imports
backend proceden del entorno instalado, con 83 distribuciones compatibles.
Las 20 definiciones nuevas/modificadas tienen docstrings. Se retiran 54 funciones
de test obsoletas sin contarlas como fallos reparados. Prompts: 233 candidatos en
353 archivos, 365 archivados, sin revisión estática pendiente ni cambios de
instrucciones en este corte. No hay una nueva suite global.

**Lista vigente:**
- Cerrado recientemente: herramientas y bibliotecas antiguas, API interna/CLI de
  pods y servicios de comunicación/listeners sustituidos por contratos nativos.
- Siguiente: helpers y entradas restantes de flows, controladores de autonomía
  y lectores históricos; incluye los cinco fallos de flows todavía reproducibles.
- Pendiente principal: operación e imágenes; migraciones/inversas/restauración
  y datos históricos; historial completo y presupuestos; evaluación real, humana,
  científica y global; aceptación integral de 12 páginas y revisión final.
  Siguen 43 escenarios abiertos, 12 pilotos y 48 conceptos.
- Al final: detalles secundarios. Los avisos de estilo y espacio al final de un
  test quedan en DD058; no se repiten recorridos por ese pulido.

## Etapa anterior: API interna y CLI de pods retirados

Se retiran tres módulos de API interna (13 operaciones), el CLI de pods y sus
instalaciones antiguas de CLI/MCP/Claude Code en la imagen histórica. Se conservan
el terminal del propietario y los contratos nativos de tareas, mensajes,
continuidad, hallazgos, revisión y publicación. No se modifica ningún dato ni
se elimina ningún caso de test. [Mapa de capacidades](../architecture/native-internal-retirement.md).

**Comprobado:** 140 pruebas pasan desde fuente y 140 desde el paquete instalado;
ambos conservan dos fallos de migración/inversa, reproducidos con mensajes
idénticos en el paquete anterior. No hay omisiones. Los 674 archivos Python/SQL
coinciden y los 279 imports backend proceden del entorno instalado; sus 83
distribuciones son compatibles. Se documentan tres definiciones modificadas o
nuevas. Prompts: 233 candidatos en 361 archivos, 365 archivados y ninguna revisión
estática pendiente. No se construyó la imagen ni se ejecutó una suite global.

**Lista vigente:**
- Cerrado recientemente: herramientas y bibliotecas antiguas; API interna y
  CLI de pods, manteniendo sus capacidades mediante los contratos nativos.
- Siguiente: servicios de comunicación, listeners y lectores/helpers de flows
  restantes, incluidos los siete fallos de flows y el detector de conversación.
- Pendiente principal: operación e imágenes; migraciones/inversas/restauración
  y datos históricos; historial completo y presupuestos; evaluación real, humana,
  científica y global; aceptación integral de 12 páginas y revisión final.
  Siguen 43 escenarios abiertos, 12 pilotos y 48 conceptos.
- Al final: detalles secundarios. El aviso de imports de este corte queda en
  DD057; no se aplazan como estilo los fallos de migración o flows.

## Etapa anterior: bibliotecas antiguas retiradas

Se retiran CrewAI, crewai-tools, LiteLLM, Ollama y Chroma, el extra `legacy`,
cinco auxiliares sin uso, la exportación diferida de la clase base y dos fixtures
de persistencia. El lock pasa de 177 a 86 paquetes sin cambiar las versiones
retenidas ni el export de producción. No se alteran datos históricos.
[Cambios y límites](../architecture/native-legacy-dependencies.md).

**Comprobado:** 129 pruebas pasan desde fuente y 124 en el paquete instalado;
ambos conjuntos conservan siete fallos de flows antiguos y tres omisiones por
imagen de pod. Los siete fallos se reproducen en el código anterior con el
entorno histórico: no es una comparación con dependencias idénticas. Coinciden
676 archivos Python/SQL y los 256 imports backend proceden del entorno instalado,
con 83 distribuciones compatibles sin las bibliotecas retiradas. El auditor de
prompts pasa sus dos tests; siguen 234 candidatos en 365 archivos, sin revisión
estática pendiente. No hay una nueva suite global ni aceptación integral.

**Lista vigente:**
- Cerrado recientemente: herramientas web, tareas, comunicación, proyecto y
  conocimiento, sus cinco bibliotecas antiguas y auxiliares sin consumidores.
- Siguiente tarea principal: servicios, lectores, rutas internas y CLI heredados,
  incluidos los fallos de flows y del detector de conversación antiguo.
- Pendiente principal: operación; migraciones/inversas/restauración y datos
  históricos; historial completo y presupuestos; evaluación real, humana,
  científica y global; aceptación integral de las 12 páginas y revisión final.
  Siguen 43 escenarios abiertos, 12 pilotos y 48 conceptos.
- Al final: todos los detalles secundarios registrados; los cuatro avisos de
  estilo de este corte quedan en DD056. Los fallos de flows son trabajo principal.

## Etapa anterior: herramientas antiguas de conocimiento retiradas

Se retiran13herramientas/15módulos después de cubrir búsqueda conjunta nativa y
lectura de informes históricos con texto retenido en DB y procedencia explícita.
Hallazgos, revisión, Wiki e informes conservan sus contratos nativos.
[Mapa completo y límites](../architecture/native-knowledge-retirement.md).

**Comprobado:**140 pruebas de fuente pasan; dos fallan y una se omite inicialmente.
La prueba omitida pasa después al configurar el encoder local ya preparado.
En el paquete instalado pasan141, fallan las mismas dos y no hay omisiones.
Ambos fallos de migración/inversa se reproducen en el paquete anterior; siguen
pendientes en su bloque principal.682 archivos Python/SQL coinciden,266 imports
proceden del entorno y hay83 distribuciones sin frameworks antiguos.20
definiciones nuevas/modificadas documentadas.234 candidatos de prompt en370
archivos,364 archivados, sin revisión estática pendiente.21 tests de wrappers
retirados sin contarlos como fallos reparados. No hay nueva suite global.

**Lista vigente:**
- Cerrado recientemente: herramientas web, tareas, comunicación, proyecto y
  conocimiento, con los reemplazos nativos indicados en sus mapas.
- Próxima tarea principal: cinco bibliotecas antiguas y auxiliares sin consumidores;
  después servicios/lectores/rutas internas/CLI heredados restantes.
- Pendiente principal: operación; migraciones/inversas/restore y datos históricos,
  incluidos informes con bytes sólo en archivos; historial completo y presupuestos;
  evaluación real, humana, científica y global; aceptación integral de12páginas
  y revisión final. Siguen43escenarios abiertos,12pilotos y48conceptos.
- Al final: detalles secundarios registrados; dos avisos de imports y una línea
  vacía al final de un test quedan enDD055.

## Etapa anterior: herramientas antiguas de proyecto retiradas

Se retiran ocho herramientas y nueve módulos. Se cubre la carencia encontrada:
hitos opcionales en la propuesta, revisión visible, creación atómica con las
tareas y conservación del plan completo en su entrega posterior. Dos lecturas
nativas permiten consultar épicas/hitos por proyecto, sin confundir etiquetas
de estado o fechas propuestas con autorización o resultados aceptados.
[Mapa y decisiones](../architecture/native-project-retirement.md).

**Comprobado:**82 pruebas pasan en fuente y82 en el paquete instalado, sin fallos
ni omisiones; seis pruebas web y la compilación pasan.697 archivos Python/SQL
coinciden,256 imports proceden del entorno instalado y hay83 distribuciones sin
frameworks antiguos.30 definiciones Python nuevas/modificadas documentadas y
JSDoc revisado.278 candidatos de prompt en385 archivos,319 archivados y ninguna
revisión estática pendiente. Se retira un test del stub antiguo, sin contarlo
como fallo reparado. No hay nueva suite global ni aceptación integral de páginas.

**Lista vigente:**
- Cerrado recientemente: web; contexto/comentarios/continuidad; herramientas de
  tareas; comunicación nativa y retirada de sus herramientas; herramientas de
  proyecto, incluidos hitos y lectores nativos.
- Próxima tarea principal: herramientas de conocimiento; después, las cinco
  bibliotecas antiguas y los servicios/lectores/rutas internas/CLI restantes.
- Pendiente principal: operación; migraciones/restore y datos históricos;
  historial completo y presupuestos; evaluación real, humana, científica y
  global; aceptación integral de las12 páginas y revisión final. Siguen43
  escenarios abiertos,12 pilotos y48 conceptos; no hay porcentaje defendible.
- Al final: detalles secundarios. Tres avisos de estilo, singular/plural de la
  vista de hitos y tamaño del bundle quedan en el registro de detalles diferidos.

## Etapa anterior: herramientas antiguas de comunicación retiradas

Se retiran seis herramientas (siete módulos) y dos registros de preguntas. Se
conservan los recorridos nativos de mensajes, preguntas al propietario y entrega
de resultados. Dos lecturas nativas recuperan avisos del proyecto/globales con
procedencia, vigencia y ventanas de texto; los avisos no conceden autoridad.
[Mapa y límites](../architecture/native-communication-retirement.md).

**Comprobado:** 71 pruebas pasan en fuente y 71 instaladas. Ambas baterías
conservan un fallo del detector antiguo de ping-pong, reproducido en el paquete
previo `ad86106`; ese fallo sigue como trabajo principal de servicios heredados.
Dos tests del auditor de prompts pasan. 704 archivos Python/SQL coinciden,
236 imports proceden del entorno y hay83 distribuciones sin frameworks antiguos.
16 definiciones nuevas/modificadas tienen docstrings;307 candidatos de prompt en
394 archivos,288 archivados y ninguna revisión estática pendiente. Se retiran31
tests antiguos sin contarlos como fallos reparados; el diálogo se conserva en
el contrato nativo con recibos explícitos.

**Lista vigente:**
- Cerrado recientemente: web; contexto/comentarios/continuidad; retirada de tareas;
  comunicación nativa y retirada de sus herramientas/registros antiguos.
- En curso: proyecto, conocimiento y las cinco bibliotecas legacy restantes.
- Pendiente principal: servicios/lectores/rutas internas y CLI heredados;
  operación; migraciones/restore y datos históricos; historial completo y
  presupuestos; evaluación real, humana, científica y global; aceptación integral
  de las12 páginas. Siguen43 escenarios abiertos,12 pilotos y48 conceptos.
- Al final: detalles secundarios; avisos de estilo ya registrados enDD054.

El retiro de wrappers no declara retirado todo el subsistema de comunicación.
El detector de bucles, servicios y rutas internas aún tienen consumidores. No
se infiere un porcentaje global ni una reducción de los fallos históricos.

## Etapa anterior: comunicación nativa implementada

Cinco herramientas permiten descubrir destinatarios admitidos, listar y leer
mensajes, enviar y reconocer recepción. El host determina emisor, intento y
contexto. Preguntas y respuestas conservan identidad exacta; observaciones y
suposiciones se muestran separadas. Un mensaje o acuse no autoriza trabajo ni
demuestra comprensión. El archivo de conversaciones muestra estos registros y
el lector antiguo no los convierte en eventos de activación.
[Contrato y límites](../architecture/native-agent-messaging-design.md).

**Comprobado:** 66 pruebas pasan en fuente y 66 en el paquete instalado; cinco
tests de conversación web, compilación web y dos tests del auditor de prompts
pasan. La migración55→56 conserva mensajes históricos sintéticos y revierte un
fallo antes del recibo. 714 archivos Python/SQL coinciden, 244 imports proceden
del entorno y hay83 distribuciones sin frameworks antiguos. 62 definiciones
nuevas/modificadas tienen docstrings; cinco descripciones nuevas revisadas,
333 candidatos en403 archivos,260 archivados y ninguna revisión estática pendiente.

**Lista vigente:**
- Cerrado recientemente: web; contexto/comentarios/continuidad; retirada de tareas;
  recorrido nativo de mensajes/recibos y su proyección en conversación.
- En curso: terminar el mapa y retirar los wrappers antiguos de comunicación.
- Después: proyecto, conocimiento y las cinco bibliotecas legacy restantes.
- Pendiente principal: operación; migraciones/restore y datos históricos;
  historial completo/presupuestos; CLI; evaluación real, humana, científica y
  global; aceptación integral de las12 páginas. Siguen43 escenarios abiertos,
  12 pilotos y48 conceptos. No hay porcentaje global defendible.
- Al final: detalles secundarios, incluidos13 avisos Ruff enDD054.

Este lote no cierra la familia antigua, no prueba datos reales ni comprensión
humana y no reduce por inferencia los fallos de la suite global histórica.
Los fallos de migración/inversa y conocimiento siguen como trabajo principal.

## Etapa anterior: herramientas antiguas de tareas retiradas

Se retiran 15 módulos/14 herramientas después de mapear sus capacidades al host
nativo y al espacio de tareas. No se alteran datos históricos. Se mantienen
planificación, claim único, correcciones, revisión, aceptación, lecturas,
comentarios y última nota. [Mapa y decisiones](../architecture/native-task-retirement.md).

**Comprobado:** 120 pruebas pasan en fuente y 120 instaladas; ambas baterías
conservan dos fallos de migración/inversa reproducidos sobre el commit anterior.
El lote de compatibilidad pasa 14 y conserva tres fallos previos de conocimiento.
Dos tests del auditor de prompts pasan. 709 archivos Python/SQL coinciden,
268 imports proceden del entorno y hay 83 distribuciones sin frameworks antiguos.
Nueve definiciones nuevas/modificadas documentadas; 328 candidatos de prompt en
400 archivos, 260 archivados y ninguna revisión estática pendiente.

**Lista vigente:**
- Cerrado recientemente: web; contexto/comentarios/continuidad; retirada de tareas.
- En curso: comunicación entre agentes, con identidad, entrega y efectos explícitos.
- Después: proyecto, conocimiento y las cinco bibliotecas legacy restantes.
- Pendiente principal: operación; migraciones/restore y datos históricos;
  historial completo/presupuestos; CLI; evaluación real, humana, científica y
  global; aceptación integral de las 12 páginas. Siguen 43 escenarios abiertos,
  12 pilotos y 48 conceptos. No hay porcentaje global defendible.
- Al final: detalles secundarios, incluido un import sin usar DD053.

Se retiran 26 tests del contrato viejo y se traslada uno de diálogo; no se
cuentan como fallos reparados. Los fallos de datos/restore y conocimiento siguen
en sus bloques principales, no en la lista de pulido.

## Etapa anterior: contexto de tareas y continuidad nativos

El catálogo nativo incorpora consulta de tareas/dependencias/historial, comentarios
con autor real y notas de continuidad que separan observaciones de suposiciones.
Las notas requieren la revisión observada antes de sustituirse; sus textos no
aprueban ni activan trabajo. [Contrato](../architecture/native-task-workspace.md).

**Comprobado:** 73 pruebas relacionadas pasan en fuente y 73 en el paquete
instalado; cuatro variantes semánticas se omiten en cada batería por no configurar
su modelo local. Dos tests del auditor de prompts pasan. 726 archivos Python/SQL
coinciden, 252 imports proceden del entorno y hay 83 distribuciones sin frameworks
antiguos. 54 definiciones nuevas/modificadas documentadas; siete descripciones
revisadas, 384 candidatos en 415 archivos y ninguna revisión estática pendiente.

**Lista vigente:**
- Cerrado: sustitución web y este avance de contexto/comentarios/última nota.
- En curso: completar el mapeo y retirar herramientas antiguas de tareas,
  comunicación, proyecto y conocimiento; cinco bibliotecas legacy siguen pendientes.
- Pendiente principal: operación; migraciones/restore, incluidos datos históricos
  y fallo54/55; historial completo/presupuestos; CLI; evaluación real, humana,
  científica y global; aceptación integral de las 12 páginas. Siguen 43 escenarios
  abiertos, 12 pilotos y 48 conceptos, sin porcentaje global defendible.
- Al final: todos los detalles secundarios, incluidos tres avisos de estilo DD052.

Los wrappers de tareas aún no se retiran. La continuidad conserva la última nota,
no todas sus versiones. No se modificaron datos reales ni se hicieron llamadas pagadas.

## Etapa anterior: herramientas web antiguas retiradas

Captura directa y Spider comparten política inicial de robots/frecuencia. HTML
conserva enlaces y tablas mediante el parser local acotado; búsqueda, artículos,
fuentes y citas usan sus recorridos nativos. Se retiran diez módulos antiguos,
`ddgs` y `primp`; `trafilatura` se conserva con consumidor nativo. Los datos
históricos no se alteran. [Contrato y límites](../architecture/native-web-retirement.md).

**Comprobado:** 218 pruebas principales en fuente y 218 instaladas, sin fallos ni
omisiones; dos tests del auditor de prompts y una repetición MCP pasan después de
actualizar descripciones. 722 archivos Python/SQL, 240 imports instalados y 83
distribuciones sin frameworks antiguos. El paquete final sólo añade un docstring
de test, verificado por diff y hashes, sin repetir toda la batería.
37 definiciones nuevas/modificadas documentadas; 377 candidatos de prompt en
412 archivos, 204 archivados, cero revisiones estáticas pendientes.

**Siguiente principal:** tareas/comunicación/proyecto/conocimiento y cinco
bibliotecas legacy restantes. Después operación, migraciones/restore —incluidos
web_cache/Chroma sin originales y el fallo54/55—, historial/presupuestos, CLI y
evaluación real/humana/científica/global. Spider remoto conserva límites explícitos
de observación; no se afirma haber controlado sus redirecciones o subrecursos.
Siguen 12 pilotos, 48 conceptos, 0 páginas aceptadas integralmente y 43 escenarios
abiertos. Detalles secundarios al final, con cuatro avisos de estilo DD051.

## Etapa anterior: política de captura web, directa implementada

La captura directa de HTML/texto/PDF comprueba robots antes de cada destino y
comparte cuota entre solicitudes. Conserva DNS/TLS, plazo, Stop y procedencia;
los rechazos no guardan fuentes parciales. [Contrato](../architecture/direct-web-policy.md).

**Comprobado:**161pruebas en fuente y161en el paquete instalado,0fallos/omisiones;
732archivos Python/SQL coinciden,207imports son del entorno,85distribuciones sin
frameworks antiguos.50definiciones nuevas/modificadas documentadas. Inventario de
prompts394candidatos/421archivos,187archivados,0revisiones estáticas pendientes.
DNS/socket/proveedores controlados;0llamadas reales a modelos/proveedores.

**En curso:** terminar política de Spider y retirar wrappers web; la cuota local
no demuestra control sobre redirecciones/subrecursos remotos. Después siguen
tareas/comunicación/proyecto/conocimiento y cinco bibliotecas legacy; operación,
migraciones/restore, historial/presupuestos, CLI y evaluación real/humana/global.
12pilotos48conceptos0páginas aceptadas integralmente;43escenarios abiertos.
El fallo54/55 anterior permanece para migraciones; esta batería no lo incluye.
Detalles secundarios al final, incluyendo el orden de imports DD050.

## Etapa anterior: adaptadores de ejecución y documentos retirados

Se retiran23módulos de shell/Git/RAG/SQL genérico y documentación CrewAI. Los
recorridos nativos conservan ejecución, publicación tras aceptación, parsers,
recuperación semántica local y documentación capturada. Datos e índices Chroma
existentes permanecen; su migración/exportación no se declara terminada.
[Contrato y límites](../architecture/native-adapter-retirement.md).

**Comprobado:**132pruebas de fuente y107del wheel pasan; ambas baterías conservan
una falla de versión54/55 en el test de arranque de publicación, para el bloque
migraciones.0omisiones.730fuentes coinciden; una auditoría posterior sin ejecutar
pruebas comprueba211imports del entorno.46tests de wrappers retirados no cuentan
como reparaciones.394candidatos de prompt/420archivos,187entradas archivadas,
0revisiones estáticas pendientes. Función nueva y módulos afectados documentados.

**Siguiente principal:** política de captura web (robots.txt/frecuencia), antes de
retirar los wrappers web; después tareas/comunicación/proyecto/conocimiento y las
cinco bibliotecas legacy restantes. Luego operación, migraciones/restore,
historial/presupuestos, CLI y evaluación real/humana/científica/global.
Siguen12pilotos48conceptos0páginas aceptadas integralmente. Detalles secundarios
al final; estilo web ya registradoDD048.

## Etapa anterior: herramientas de código e índice duplicado retirados

Ken queda como descubrimiento/lectura/memoria técnica; comandos poseídos realizan
las escrituras en la copia privada. Ensayo de edición, alta/baja, rename/move,
actualización de imports/callers, refresco Ken, candidato y check exacto. Se retiran
44módulos y seis requisitos tree-sitter; las tablas/filas ci_* se conservan.
[Contrato y límites](../architecture/native-code-operations.md).

**Comprobado:**153casos distintos con última observación satisfactoria en dos
baterías de fuente;73pruebas del wheel pasan sin omisiones,757fuentes coinciden y
238imports proceden sólo del entorno nativo. Se corrigió la reinterpretación
repetida del historial y la carga indirecta de servicios web al importar Git en
el broker aislado.16definiciones documentadas;451candidatos de prompt/443archivos,
130entradas archivadas,0revisiones estáticas pendientes. Generación/Ken controlados;
no nueva evaluación de calidad con modelos. Detalles de lint aplazadosDD049.

**Siguiente principal:** restantes herramientas heredadas de shell/Git,
coordinación/tareas/proyecto/conocimiento/fuentes y sus cinco bibliotecas legacy.
Resolver capacidades útiles que falten antes de retirar cada implementación.
Después operación, migraciones/restore, historial/presupuestos, CLI y evaluación
real/humana/científica/global. Siguen12pilotos48conceptos0páginas aceptadas
integralmente. Todos los detalles secundarios al final.

## Etapa anterior: Spider migrado y SDK opcional retirado

Captura avanzada de una página por MCP/API/fuente SQLite, con modos explícitos
smart/browser/http y markdown/texto. Clave y créditos del host; contenido para
citas/hallazgos, sin dar autoridad a instrucciones de la página. Transporte
acotado compartido con Context7. [Contrato](../architecture/spider-sources.md).

**Comprobado:**122pruebas relacionadas en fuente y71en el paquete instalado,
798fuentes coincidentes,234imports sólo del entorno y85distribuciones sin legacy
ni SDK Spider.0fallos/omisiones;0llamadas a modelos o proveedores reales.
Se retiran un módulo, sus tres tests específicos y el extra spider; el lock
elimina tres paquetes, sin cambios de versiones restantes.38definiciones
documentadas;546candidatos/486archivos,35entradas archivadas y0pendientes de
revisión estática. DD048 conserva sólo estilo.

**Siguiente principal:** cerrar el conjunto de herramientas heredadas restantes
según sus reemplazos nativos y resolver capacidades únicas de los índices/edición
estructural antes de retirar sus dependencias. Después operación, migraciones/
restore, historial/presupuestos, CLI y evaluaciones reales/humanas/científicas/
globales. Se mantienen12pilotos48conceptos0páginas aceptadas integralmente.
Todos los detalles secundarios al final.

## Etapa anterior: Context7 migrado a fuentes nativas

Búsqueda de bibliotecas y documentación JSON/texto pasan por el MCP de negocio,
API y fuentes SQLite. Clave opcional sólo en el host; cuota externa explícita,
versiones y reglas del proveedor tratadas como evidencia atribuida. Se retiran
los tres módulos CrewAI anteriores. [Contrato](../architecture/context7-sources.md).

**Comprobado:** 87 pruebas relacionadas en fuente y36en el paquete instalado,
796fuentes coincidentes,231imports sólo del entorno y85distribuciones sin legacy.
MCP/HTTP/SQLite/cita real con DNS/socket de proveedor controlados; un turno nativo
de investigación controlado.0llamadas a modelos o Context7 reales.42definiciones
documentadas. Inventario549candidatos/485archivos,31entradas archivadas,0pendientes
de revisión estática; evaluación de eficacia sigue abierta. DD047 sólo estilo.

**Siguiente principal:** Spider, demás herramientas e índices antiguos y retirada
final de dependencias. Luego operación, migraciones/restore, historial/presupuestos,
CLI y evaluación real/humana/científica/global. Se mantienen12pilotos,48conceptos
y0páginas completamente aceptadas. Todos los detalles secundarios al final.

## Etapa anterior: constructores, catálogo por rol y memoria CrewAI retirados

Se eliminan trece módulos antiguos y se conservan las identidades, memoria y
ejecuciones históricas en SQLite. Los consumidores de contexto usan las lecturas
nativas de Wiki/hallazgos; las capacidades actuales tienen herramientas para
consultar sus revisiones. El snapshot del catálogo antiguo queda como documento.
[Contrato y límites](../architecture/legacy-catalog-removal.md).

**Comprobado:** 47 pruebas en fuente pasan; 30 en el paquete instalado, con 797
fuentes coincidentes y un recorrido de investigación controlado. Cinco
definiciones documentadas; Ruff sin incidencias en los archivos revisados.
Prompts: 553 candidatos / 487 archivos, 25 entradas archivadas en total y ninguna
revisión pendiente. No cambia la aceptación de las doce páginas.

**Siguiente principal:** herramientas individuales, Context7/Spider e índices
antiguos, antes de cerrar la retirada de dependencias. El extra `legacy` todavía
existe: no se declara CrewAI completamente retirado. Después continúan operación,
migraciones/restore, historial/presupuestos, CLI, evaluaciones reales/humanas y
aceptación global. Todos los detalles secundarios siguen para el final.

## Etapa anterior: motor de inferencia antiguo retirado

Se eliminan doce módulos de `backend.engine` y sus pruebas específicas; los
consumidores reales de la señal de parada pasan a `runtime.legacy_scope`.
Se conservan datos históricos y control de trabajadores registrados. Los imports
de ejecución antigua ya no tienen implementación disponible en el wheel.
[Contrato, reemplazos y límites](../architecture/legacy-engine-removal.md).

**Comprobado:** 137 pruebas relacionadas pasan y una prueba de migración sin
modificar falla por su fixture53/55; queda en migraciones. El paquete instalado
pasa 32 pruebas, incluyendo investigación/planificación controladas, con 814 fuentes
coincidentes y sin el paquete retirado. Ocho definiciones documentadas.
Prompts: 560 candidatos / 500 archivos, 18 entradas archivadas, 0 revisiones pendientes.
No se repitió la suite global ni cambió la aceptación de las doce páginas.
Las cifras históricas de fallos no describen el inventario actual tras retirar
157 funciones de prueba obsoletas; esa retirada no se cuenta como reparación.

**Siguiente principal:** consumidores del catálogo/herramientas legacy y sus
dependencias; después los bloques restantes de operación, migraciones/restore,
historial/presupuestos, CLI, evaluación real/humana y aceptación global.
Los detalles DD046 se conservan para después de todas las tareas principales.

## Etapa anterior: controles generales conectados al runtime nativo

La cabecera consulta actividad real registrada y deja de decidir por etiquetas
`completed`/`executing`. La detención conserva su solicitud exacta después de
una respuesta perdida y una recarga; recuperar el recibo no amplía el alcance al
trabajo nuevo. La planificación tardía no cambia el proyecto elegido después.
El cierre del controlador anterior se conserva en su expediente.

**Comprobado:** siete estados de navegador a 1440/390 px, sin incidencias Axe/JS ni
desbordamiento; 123 pruebas frontend pasan y build en 3,96 s. Cuatro módulos y 18 funciones
con JSDoc. [Resultado y límites](../design/audits/2026-11-06-project-controls/report.md).
No es una prueba nueva de cierre físico, wheel o suite global. Siguen doce pilotos,
48 conceptos comprobados y 0 páginas con aceptación integral.

**Siguiente principal:** continuar retirando los consumidores antiguos del engine
y resolver sus bloqueos funcionales; después migraciones/restore, operación,
historial/presupuestos, CLI, evaluaciones reales/humanas y validación global.
DD045 conserva sólo el ajuste visual secundario de la cabecera. La lista del chat
se actualiza en cada cambio de tarea, manteniendo todos los pendientes originales.

## Etapa anterior: doce páginas piloto; continúa el engine y la retirada antigua

Ejecución consulta planes/grafos/entregas reales, muestra dependencias y evidencia
recibida, separa historia del avance vigente y conserva enlaces originales.
Reutiliza los controles existentes; una pausa con respuesta perdida se recupera
con el mismo paquete después de recargar. Diez estados HTTP controlados sin
incidencias Axe/JS; 123 pruebas frontend y build pasan. Doce declaraciones JSDoc.
[Recorrido y límites](../design/audits/2026-11-06-flow/report.md).

Se verificaron **36 imágenes desktop, 12 móviles y doce selecciones** por presencia,
hash y manifest ([auditoría](../design/concept-artifact-audit.json)). Esos entregables
quedan comprobados; doce pilotos no significan aceptación integral.
**Siguiente principal:** completar el uso del runtime nativo en los consumidores
restantes del engine, incluida la coherencia de controles/estado globales.
El pulido DD044 espera a que terminen todas las capacidades principales.

## Etapa anterior: Agentes implementado; continúa Ejecución

Agentes ya consulta ejecuciones nativas con identidad/tarea/intento, modelo y
consumo observado, paginación y Stop original. Desconocido sigue siendo desconocido;
un estado guardado no demuestra actividad actual. Tres conceptos y móvil,
selección registro con detalle.19backendPASS,123frontend/build3.94s y8capturas
controladas sin incidencias Axe/JS;6defsPython y10TS/JS documentadas.
[Recorrido y límites](../design/audits/2026-11-06-agents/report.md).
La aceptación integral, historial completo de intentos/presupuestos y cierre
físico global siguen pendientes. DD043 sólo conserva detalles secundarios.
**Siguiente principal: Ejecución**, última ruta pendiente de conceptos/piloto.

## Etapa anterior: Planificación implementada; continúan Agentes y Ejecución

Planificación conserva grupos/hitos y añade consulta de propuestas originales,
suposiciones y dependencias. Tres conceptos y móvil; selección árbol con detalle.
Nueve capturas finales con fixturesHTTP,0Axe/JS;123testsfrontend/build4.19s y
14funciones documentadas. [Recorrido y límites](../design/audits/2026-11-06-planning/report.md).
No es aceptación integral ni prueba de recuperación del CRUD preexistente. El
CRUD sin operation_key y sus garantías de historia siguen en engine/operación;
DD042 conserva sólo ajustes secundarios. Próxima principal: Agentes, luego Ejecución.

## Etapa anterior: Resumen implementado; continúa Planificación

Resumen tiene tres conceptos y adaptación móvil, selección delegada y recorrido
conectado a workspace/tareas/preguntas existentes. Enlaces originales, errores
parciales y cambio de proyecto; sin inferir aceptación por porcentajes de tareas.
Cinco capturas con fixtures,0Axe/JS/escrituras;123testsfrontend y build4.04s.
[Resultados y límites](../design/audits/2026-11-06-home/report.md).
Sigue siendo piloto; DD041 conserva pulido de densidad/cabecera para después de
las tareas gruesas. Próxima principal: Planificación, después Agentes y Ejecución.

## Etapa anterior: catálogo de prompts revisado y versionado

La revisión estática propia tiene578entradas candidatas de512archivos, con decisiones
explícitas ligadas a fuente/consumidores;0decisiones nuevas u obsoletas sin revisar.
No son578prompts únicos ni pruebas de eficacia. El catálogo nativov2 centraliza
política y selecciona siete capacidades; el adaptador anterior conserva un perfil
de referencia. Los perfiles fueron reescritos o conservados con motivo y el warmup
directo se rechaza antes de HTTP. La instantánea original conserva la política enviada.

**Verificación:**12tests acotadosPASS3.12s;20instaladosPASS7.678s/834miembros
coincidentes/230imports sóloentorno/85distribuciones. Un turno de producto/Ken
controlados;0modelos reales/remotos del usuario.21defsPython documentadas,0faltantes.
Planificación vuelve a pasar2.33s. Batería previa65PASS/3FAIL: dos casos corregidos
por wording/fixture de schema; el timeout de checks a60s también aparece en
wheel85f7acd. Queda en engine/validación global, no en pulido. La migración29→actual
sigue fallando en el fixture anterior por un trigger ausente de43, también en85f7acd.

[Inventario y criterios](../prompts/inventory.md), [resultados](prompt-catalog-results.json),
[paquete](prompt-catalog-packaging.json). Baseline/casos reservados preparados;
comparación con modelos y comprensión humana/científica siguen pendientes. Sin
cambios frontend, no nuevas capturas/build ni aceptación global por esta entrega.

| Bloque | Estado actual |
| --- | --- |
| Runtime Codex/Ken, control y recuperación | Recorridos implementados; evaluación global abierta |
| Investigación y desarrollo con evidencia/revisión/aceptación | Recorridos funcionales; capacidades y aceptación global pendientes |
| Fuentes Git y configuración de modelos | Implementados en los alcances documentados |
| Prompts y comunicación humano–agente | Catálogo/revisión estática implementados; comparación con modelos y comprensión humana pendientes |
| Engine, coordinación entre agentes y retirada heredada | Incompleto |
| Dependencias e infraestructura restantes | Actualización parcial |
| Interfaz web | Doce pilotos y 48 conceptos comprobados; aceptación integral de las doce páginas pendiente |
| Migración/restore, operación, historial/presupuestos y CLI/TUI | Parcial; validación integral pendiente |
|43escenarios, doce páginas, evaluación humana/científica y revisión final | Pendientes de aceptación integral |
| Pulido secundario de todos los bloques | Después de todas las tareas gruesas |

## Etapa anterior: configuración de modelos por ámbito

La cabecera permite guardar/restablecer modelo y esfuerzo con prioridad
agente-del-proyecto → proyecto → global → host. Los cambios afectan a intentos
nuevos; cada intento conserva su pareja, origen y revisión. El catálogo real de
Codex se comprueba antes del thread/turn; una pareja ausente produce explicación
sin sustitución ni fallback facturado. Un guardado perdido conserva el borrador.
La elección guardada se distingue del modelo de inferencia realmente registrado.

**Verificación:**103backendPASS42.86s;123frontendPASS/build5.26s. Wheel no editable
11PASS12.237s,831miembros coincidentes/233imports sóloentorno/85distribuciones,
1turno de producto/Ken controlados y1de protocolo hijo,0modelos reales/remotos del
usuario. Cuatro capturas1440/390px,0Axe/JS/desbordamiento en diálogo;4PUT,
0turnos por configurar,hostJSONintacto.44defsPython/20módulos/nombresTS documentados.
[Contrato](../architecture/model-configuration.md), [resultados](model-settings-results.json),
[paquete](model-settings-packaging.json), [web](../design/audits/2026-11-06-model-settings/report.md).

**Siguiente principal:** inventariar y revisar todo el catálogo de prompts,
incluidas instrucciones nativas y composición dinámica, usando las skills de libros
pertinentes y evaluaciones que distingan evidencia de suposición. Después continuar
con las restantes capacidades principales, incluidas las cuatro rutas. El pulido
de todas las tareas queda para el final, sin reabrir ahora estilo/caché/selector.
Los43escenarios/global/restore/DD030/inversas43–54/instalación/aceptación12páginas/
revisión final siguen abiertos.24/36conceptosdesktop,8/12mobile,8pilotos,0aceptadas.

## Etapa anterior: reserva cerrada y adopción independiente

El propietario puede cerrar una preparación local detenida después de comprobar
su cierre original, conservar carpeta/historia y preparar una nueva adopción.
La operación antigua ya no reserva la ruta ni permite reparar/observar con su
antigua autoridad. Una reparación guardada antes de cancelar su entrega al
scheduler puede retomar la misma autorización si nunca fue admitida.

**Verificación:**35pruebas backend en fuente pasan46.60s;122frontend/build5.17s.
Cuatro capturas1440/390px,0erroresJS/Axe/desbordamiento en la región revisada;
1cierre con respuesta perdida,1adopción nueva,1reparación con clave conservada.
HEAD/config/inode/contenido preservados,4grants reales retirados,0turnos nativos.
23defsPython y85módulos/nombresTS documentados,0faltantes. No se repitió el ensayo
de wheel ni la suite global. [Contrato](../architecture/source-reservation.md),
[resultados](source-reservation-results.json),
[web](../design/audits/2026-11-06-source-reservation/report.md).

**Siguiente principal:** configuración de modelos utilizable desde producto,
con alcance global/proyecto/agente explícito y elección conservada por intento.
Después, las demás capacidades principales de prompts/comunicación/ciencia,
cuatro rutas, migración/restore/operación y retirada antigua. Todos los detalles
secundarios se resuelven al final de todas las tareas gruesas; ver DD038.
43escenarios/validación global/instalación/inversas43–54/aceptación12páginas/
revisión final siguen abiertos.24/36conceptosdesktop,8/12mobile,8pilotos,0aceptadas.

## Etapa anterior: historia original entre navegadores

Repositorios abre una operación guardada desde otra sesión sin recrear el POST.
El localizador de historia conserva proyecto/clave/identidad/elecciones/fence
mínimo y se guarda separado de la solicitud pendiente. Se puede volver a esa
solicitud intacta. Los controles usan el intento observado; una respuesta tardía
no cambia la operación o proyecto actual. Observación valida ahora ID/fence antes
de programar, con compatibilidad bodyless anterior. Historia no expone el POST
original de alta como recuperación automática.

**Verificación:**121frontendPASS/build5.13s,4contratos nuevos de transporte/storage.
16owner/source/remotePASS32.44s y16instaladas32.224s/223imports sóloenv/
826miembros coincidentes/85distribuciones;0turnos nativos/modelos/remotos del usuario.
No se presenta como otra batería global186. Tres contextos de navegador,
5capturas finales1440/390px,0POST de efectos en la verificación readonly,
2respuestas tardías,0incidencias Axe/errores JS/desbordamiento. La secuencia
original observó/reparó una vez la fuente detenida;4grants reales cerrados.
4defsPython/75módulos o nombresTS documentados;5avisos estáticos diferidosDD037.
[Contrato](../architecture/source-history.md), [resultados](source-history-results.json),
[paquete](source-history-packaging.json), [web](../design/audits/2026-11-06-source-history/report.md).

**Siguiente principal:** resolver una reserva retenida de forma explícita para
poder adoptar su carpeta, conservando archivos e historia; luego recuperar una
reparación guardada que no llegó a programarse. DD030/restore, formatos/límites,
configuración/modelos/prompts/libros, evaluación humana/científica,43escenarios/
global/install/inversas43–54/cuatro rutas/aceptación12páginas/revisión final siguen
siendo el plan completo.24/36desktop,8/12mobile,8pilotos,0/12aceptadas sin cambios.
La caché de30s/frescura/fecha de consulta, densidad y foco quedan para pulido;
los controles obsoletos ya son rechazados, no se retargetean.

## Etapa anterior: continuar Git interrumpido conservando trabajo

El owner puede autorizar una reparación ligada al intento observado, con clave
propia conservada antes del POST. La continuación reutiliza la asignación privada
original y el broker real; completa etapas faltantes sin reset, force checkout ni
clone sobre el destino. Conserva archivos modificados, índice/config/HEAD existentes
y distingue cambios locales de la revisión registrada. La observación readonly
ya no registra un checkout incompleto como borrados atribuidos al usuario.

Cierre temprano distingue dueño no admitido, entrega claim/allocate cancelada y
dominio real retirado sin concesión: no fabrica un dominio o tarea para probarlos.
Reenvíos de la autorización activa/completada no reejecutan el driver. Clones sin
commit vuelven a observar el remoto elegido bajo una nueva autorización; no se
promete conservar una versión anterior que nunca quedó capturada.

**Verificación:**11casos principales24.658s;40regresiones68.00s previas a las últimas
correcciones. Wheel final186PASS0FAIL0SKIP161.986s,273imports instalados/
825miembros coincidentes/85distribuciones;1turno nativo/Ken controlados,
0modelos reales/remotos del usuario.117frontend/build4.79s,5capturas1440/390px,
0incidencias Axe en la región revisada,1preparación/1reparación tras perder su
respuesta y recargar;2grants reales retirados.47definiciones Python/63módulos o
nombres TS documentados.25avisos de estilo/estática sin sintaxis/nombres indefinidos,
diferidosDD036. [Contrato](../architecture/source-repair.md),
[resultados](source-repair-results.json), [paquete](source-repair-packaging.json),
[web](../design/audits/2026-11-06-source-repair/report.md).

**Siguiente principal:** abrir y recuperar la historia original desde otro navegador.
Después, resolución de reservas/adopción y entrega de reparación guardada sin
programación; formatos especiales/SHA256 en metadata reconstruida/submódulos/
presupuestos, historias viejas/restore/DD030, configuración/modelos/prompts/libros,
evaluación humana/científica,43escenarios/global/hostinstall/inversas43–54,
cuatro rutas y aceptación de12páginas/revisión final siguen siendo el plan completo.
No se actualiza un porcentaje global. Continúan24/36desktop,8/12mobile,8pilotos,
0/12páginas aceptadas. No reabrir ahora pulido/lista lateral/imports.

## Etapa anterior: crear y reconocer un remoto vacío

El propietario elige explícitamente servidor configurado, cuenta/organización,
nombre y visibilidad. Se confirma la identidad numérica del namespace; no hay
fallback de organización a usuario. La creación registra un único POST antes de
salir y conserva un marcador original. Una respuesta perdida se recupera con
consultas readonly; existencia,404o marcador ajeno no autorizan otro POST. No se
crea una carpeta, origin, publicación, tarea nativa ni registro local sustituto.
Stop de fuente/proyecto cierra el cliente real sin afirmar rollback remoto.

**Verificación:**11casos principales15.13s;65regresiones en fuente57.40s antes del
último test/copia de error. La wheel final no editable comprueba todo el código
actual:175PASS0FAIL0SKIP136.915s,270imports/822miembros coincidentes,
85distribuciones/sin frameworks antiguos;1turno nativo/Ken controlados,
0modelos reales y0remotos del usuario. Frontend116PASS/build4.90s.
Cinco capturas reales1440/390px,0incidencias Axe en la región revisada,
1POST administrativo/1observación/1POST remoto.49definiciones Python y57módulos/
definiciones TS documentados;7avisos estáticos diferidosDD035. Sin nuevas rondas
de conceptos: siguen24/36desktop,8/12mobile,8pilotos y0/12páginas aceptadas.
[Contrato](../architecture/remote-source-creation.md), [resultados](remote-source-results.json),
[paquete](remote-source-packaging.json), [web](../design/audits/2026-11-06-remote-source/report.md).

**Siguiente principal:** reparar etapas locales incompletas y recuperar el caso
sin concesión Git original, conservando contenido y autoridad real; después,
historia entre navegadores. La evaluación de presupuesto total de tiempo/red,
Forgejo completo, restore/inversas, mezclas/admisiones nativas tardías,
43escenarios,12páginas y todo el objetivo original siguen abiertos. La política
macro-first se conserva: no reabrir ahora estilo, imports ni densidad del formulario.

## Etapa anterior: Stop físico antes de esperar SQLite

El lease y broker reales se capturan antes del primer G. Stop rechaza fences
obsoletos, retira el dueño original y después espera intención/recibos. Proyectos
valida una lectura completa y congela sus identidades; un recibo antiguo vuelve
sin retirar un clone posterior. El cierre de aplicación y el Stop general drenan
admisión sin habilitar dueños administrativos tardíos.

**Verificación:**5casos de prioridad7.11s con Git/TLS real,70regresiones en fuente
61.14s y1proyecto con proceso nativo controlado2.18s. Wheel no editable final:
164PASS0FAIL0SKIP121.553s,267imports instalados/820miembros coincidentes,
85distribuciones/sin frameworks antiguos.1turno nativo controlado,0modelos reales
ni escrituras a remotos del usuario.45definiciones Python documentadas, sin
faltantes;11avisos estáticos, incluidos heredados, diferidosDD034. Sin cambios
frontend ni nuevas rondas de conceptos/capturas. [Resultados](source-control-results.json),
[paquete](source-control-packaging.json), [contrato](../architecture/source-control.md).

**Siguiente principal:** crear remoto como elección separada de namespace,
visibilidad y origen configurado, con identidad original y observación sin repetir
un POST desconocido. Después, reparar etapas locales incompletas/sin concesión
original e historia entre navegadores. Las mezclas/admisiones nativas tardías,
43escenarios,12páginas y todo el objetivo original siguen pendientes de aceptación.

## Etapa anterior: preparación explícita de fuentes y ciclo de vida

**Resultado utilizable:** crear Git local, adoptar Git existente y clonar HTTPS
con intención/dueño/intento/fence administrativos propios; ninguna tarea de
inferencia inventada. Reutiliza broker global/kernel y ejecutor Git existentes.
Controles web/HTTP, Stop individual/proyecto/lifespan y recuperación readonly de
Git terminado antes de perder el registro. Se conservan carpetas parciales,
configuración y origin; se protegen borrado, registro alternativo y cierre del
proyecto. La vieja vía de alta/remoto/origin/force push ahora rechaza antes de
cualquier efecto. Auth de clone usa el origen y TLS configurados explícitamente.

**Verificación:**124PASS instalados95.923s,261imports desde el entorno limpio,
819miembros coincidentes/85distribuciones/sin frameworks antiguos. Un caso de
compatibilidad del extra antiguo se verificó aparte en fuente; no se instala
CrewAI para él.0modelos/binarios nativos de inferencia;1adaptador de inferencia
sintético en el caso de error de shutdown.115frontend1.747s/build4.98s;
10capturas desktop/móvil,0errores JS/axe en regiones revisadas/overflow.
150definiciones Python y54definiciones/módulos TS documentados, sin faltantes.
25avisos estáticos de archivos tocados, incluidos heredados; pulido DD033.
[Resultados](source-setup-results.json), [paquete](source-setup-packaging.json),
[contrato](../architecture/source-operations.md),
[QA](../design/audits/2026-11-06-source-setup/report.md).

**Siguiente al cerrar ese checkpoint:** comprobar prioridad física de Stop bajo SQLite contendido
sin perder la barrera de admisión/cierre ya corregida; luego crear remoto de forma separada con namespace/visibilidad
explícitos e identidad recuperable; luego reparar etapas init/commit/clone/checkout
incompletas y casos sin concesión original. Observar Git ya terminado no resuelve
esos casos. Historia desde otro navegador, restore/inversas43–54 y aceptación de
la página siguen abiertos. El brief `source-remote-creation-brief.md` conserva el
siguiente corte. No repetir explorador, conceptos ni pruebas físicas por pulido.

Se mantiene todo el plan: cuatro rutas sin conceptos/código,0/12páginas aceptadas,
settings/modelos/prompts/libros/semántica/ciencia/comprensión humana/terminal,
historia/presupuesto,43escenarios/suite global/host install/restore/DD030 y revisión
final. Ningún porcentaje global nuevo ni declaración de objetivo completado.

## Etapa anterior: explorador de Repositorios


**Resultado utilizable:** explorador seleccionado entre tres conceptos desktop y
uno móvil. Registro y lectura separados; árbol/archivo fijados al mismo commit
completo, actualización explícita y blob ajeno rechazado. Código literal y Markdown
con texto original; navegación móvil/foco y enlace exacto al origen de un PR.
Registro de carpeta existente recupera la misma selección tras respuesta perdida.
No inicia modelos ni declara aceptación/publicación desde el estado histórico.

El lector antiguo devolvía SHA abreviado, ocultaba error como lista vacía y podía
leer el Git padre desde una carpeta sin repositorio. Ahora exige raíz exacta,
política Git sin credenciales/helpers/textconv, deadline15s y errores explícitos;
rutas NUL/Unicode y SHA-1/SHA-256 conservan la identidad. **No representa propiedad
de ejecución nativa ni una migración completa de todo el lector.**

**Verificación:**22PASS6.832s fuente y22PASS7.642s wheel no editable,189imports
instalados/808miembros/85distribuciones/sin frameworks antiguos.0turnos nativos,
0modelos/efectos remotos.112tests frontend1.790s/build4.96s;15capturas navegador,
0errores JS/axe en regiones revisadas/overflow. Capturas finales13–15 verifican
código móvil visible y Markdown/texto original.14definiciones Python/40TS
documentadas;0avisos nuevos/3heredados/4resueltos.
[Resultados](repositories-results.json), [paquete](repositories-packaging.json),
[contrato](../architecture/repository-explorer.md),
[QA](../design/audits/2026-11-06-repositories/report.md).

**Siguiente al cerrar ese checkpoint:** crear local/adoptar Git/clonar/crear remoto/reparar con
propiedad e intención recuperable propias; reemplazar `RepositoryManager.init_repo`
y su endpoint que todavía mezclan alta remota/origin/forcepush. El ejecutor nativo
actual exige tarea/fuente de desarrollo reales; no fabricar una tarea para setup.
El brief `repository-setup-brief.md` conserva la decisión y alternativas. Lectores
grandes/síncronos, submódulos y anotaciones remotas con identidad retenida también
necesitan integración. DD032 conserva sólo pulido del explorador.

El plan completo sigue activo: cuatro rutas restantes/aceptación de las doce,
settings/modelos, prompts/libros/semántica/ciencia/comprensión humana, terminal,
historia/presupuesto,43escenarios/suite global, instalación/restore/inversas43–54,
identidad de creación tras borrado DD030 y revisión final. No hay porcentaje global
nuevo defendible ni sustitución de esos requisitos por un piloto.

## Etapa anterior: Proyectos y trabajo observado

**Resultado:** expediente elegido entre tres conceptos desktop/uno móvil, alcance
editable con hash de la observación, selección aislada y fuentes existentes bajo
la raíz real. Actividad nativa se lee del store, no de la etiqueta del proyecto.
Planes e informes enlazan su solicitud original. Creación, registro, planificación
y Stop conservan la intención al perder respuesta/recargar. Stop congela sólo los
intentos/grafos observados; su recibo no prueba cierre. El borrado protege historia
bajo el write lock y confirma sólo proyectos sin ejecución; conserva archivos y
estadísticas globales. Consulta fallida significa desconocido, no carpeta ausente.
Sin nuevo loop/modelo/tabla de órdenes ni Git o remoto implícito.

**Verificación:** wheel final no editable/nativo:84PASS0FAIL0SKIP35.165s,
235imports instalados/807miembros coincidentes/85distribuciones/sin frameworks
antiguos; consola MCP stdio real. Stop kernel/broker real1.608s,1turno controlado,
0modelos/publicaciones. Fuente83pasan antes del arreglo final de borrado y6pasan
borrado/consumidor después; no se confunden esas revisiones. Frontend106pasan y
build4.85s. Navegador15capturas/14imágenes únicas, ownerAPI/SQLite/React reales con
generación/cierre sintéticos;0errores JS/axe en regiones revisadas/overflow.
44definiciones Python/64TS documentadas,0avisos nuevos/2heredados.
[Resultados](projects-results.json), [paquete](projects-packaging.json),
[contrato](../architecture/project-workspace.md),
[QA](../design/audits/2026-11-06-projects/report.md).

El siguiente bloque indicado en ese corte era Repositorios. Arriba figura el
explorador actual y el setup aún pendiente; los límites de Proyectos permanecen.

## Etapa anterior: informe y cierre explícito del proyecto

**Resultado:** informe determinista atribuido sobre alcance original/actual, plan,
entregas y todas las tareas del proyecto. Exige aceptaciones actuales, cierre y
revisión existentes; una etiqueta done no sustituye evidencia. El propietario
revisa el informe, escribe su declaración y reconoce cada candidato sin publicar.
Recibo/informe/snapshot/estado/evento quedan atómicos en la transacción existente.
CRUD/helper antiguos ya no pueden declarar completed. Cambiar alcance deja el
cierre anterior como historia; reenviar su solicitud no vuelve a cerrar nada.
Sin nuevo modelo, tabla, controller o publicación. Web conserva la decisión tras
pérdida de respuesta/recarga y permite leer fuentes completas con teclado.

**Verificación:**34PASS19.455s fuente;7consumidores antiguos pasan por separado.
Wheel no editable/sin frameworks antiguos:123PASS0FAIL0SKIP391.279s, con cuatro
inversas heredadas excluidas y listadas.253imports backend sólo instalados,
804miembros coincidentes. Cadena real329.733s: plan/dos autores/comprobaciones/
revisiones/aceptaciones; cierre con reconocimiento incompleto rechazado y cierre
exacto aceptado/repetible. Fuente137 intacta/dos candidatos200 sin publicar,
cinco turnos controlados,0modelos reales/Ken controlado.102tests frontend,
TypeScript/build5.06s. Siete estados navegador escritorio/móvil,0errores JS,
0infracciones axe en área revisada/overflow horizontal; no aceptación de página
completa ni comprensión humana.26definiciones Python documentadas/28TS revisadas,
dos imports diferidos DD029. [Resultados](project-completion-results.json),
[paquete](project-completion-packaging.json),
[contrato](../architecture/project-completion.md),
[navegador](../design/audits/2026-11-06-project-completion/report.md).

La siguiente entrega indicada en ese corte era Proyectos; su resultado y siguiente
paso actuales están arriba. Los límites del informe anterior siguen vigentes.

## Etapa anterior: material de código aceptado para sucesoras

**Resultado:** entregas nuevas esquema3 describen paquete, entrada original y diff
binario de la predecesora aceptada. Autor sucesor y revisor de su autor exacto
leen ventanas base64 con hash/tamaño/cobertura, bajo lease original, dependencia,
contexto y repositorio reales. La aprobación anterior no se hereda; aceptar no
publica. Entregas2 ya preparadas conservan sus bytes. Corregida selección de una
revisión aceptada más reciente que ocultaba el resultado productivo. Sin otra
tabla, loop o capa de permisos. Captura del candidato usa el plazo seleccionado
del run, mínimo60/máximo300s y cierre original; no reintenta un timeout.

**Verificación:** fuente118casos:114PASS4FAIL57.30s; las cuatro inversas heredadas
siguen en DD003. Paquete no editable/sin frameworks antiguos:115PASS0FAIL0SKIP,
cuatro inversas excluidas explícitamente,386.404s. Cadena real331.122s: plan,
autor A/comprobación/revisión/aceptación, autor B que lee/aplica material exacto,
comprobación/revisión/aceptación. Fuente137 intacta, dos candidatos200 aceptados,
0publicaciones. Cinco turnos controlados;0modelos reales/Ken controlado.250imports
backend sólo del entorno instalado,802miembros coincidentes.55definiciones
documentadas; tres avisos de imports diferidos DD028. Sin cambio frontend ni
aceptación visual nueva. Un ValueError anterior no se reprodujo y sigue sin causa
exacta; no se declara corregido. Fallo de captura60s y retrabajo conservados en
[los resultados](predecessor-material-results.json),
[paquete](predecessor-material-packaging.json),
[contrato](../architecture/predecessor-code-material.md).

**Siguiente principal:** cierre explícito e informe integral del proyecto. Leer
el brief `project-completion-brief.md` del directorio de seguimiento antes de
ampliar infraestructura. No volver al pulido de lectores/catálogos/recibos.
Metadata no registrada/adopción manual restante, consumidores antiguos, settings,
todas las páginas/prompts/evaluaciones,43escenarios, suite global, instalación/
restore/inversas y revisión final siguen dentro del objetivo completo.

## Etapa anterior: material exacto de ramas y publicación nativa del resultado nuevo

**Resultado:** Tareas/Conversación aceptan rama registrada + commit completo como
datos para un autor nuevo. La preparación Git propia captura diff binario completo,
base/árbol/hash antes de congelar la entrada. Rama movida/faltante, salida parcial,
cierre no probado, contexto cambiado, metadata reservada o exceso de límites
impiden el modelo. Recibo de captura y copia preparada quedan juntos; no nueva
tabla/controller ni cambio del recibo de admisión. La UI explica selección frente
a adquisición y aprobación antigua frente a aceptación actual.

**Verificación:**92casos fuente pasan. Final wheel no editable/sin frameworks
antiguos:93PASS0FAIL0SKIP151.763s,248imports backend sólo del entorno instalado y
798miembros coincidentes. Cadena real kernel/broker/Git/SQLite: rama anterior999,
entrada congelada exacta, autor nuevo adapta200, comprobación, revisor distinto,
aceptación y publicación local del candidato nuevo. Fuente137/ramavieja999
conservadas, refnueva200; repetición devuelve recibo sin otra inferencia. Dos turnos
nativos controlados + una publicación host en este ensayo;0modelos reales/Ken
controlado.99tests frontend y TypeScript/build pasan, sin aceptación visual.
57definiciones documentadas;11avisos de imports diferidos DD027,8heredados.
[Resultados](prior-branch-results.json), [paquete](prior-branch-packaging.json),
[contrato](../architecture/prior-branch-input.md).

**Siguiente principal:** material de predecesoras para sucesoras del grafo y cierre
integral/informe del proyecto, manteniendo controles de aceptación. La selección
explícita de una rama registrada ya funciona; descubrir/admitir metadata no
registrada, lectores Git/consumidores antiguos restantes, settings/visuales/prompts/
evaluaciones/global/restore/revisión final y resto íntegro del plan siguen abiertos.
No volver a pulir recibos/guards/imports por detalles de estilo.

## Etapa anterior: retirar efectos Git competidores y conservar historia

**Resultado:** merge/creación de ramas y cleanup local/remoto/stale/periódico
antiguos rechazan antes de Git/red/estado/eventos, incluso sin tarea ni admisión
previa/repositorio registrado. Se conservan refs/archivos/historia. PR expandido
explica la diferencia entre aprobación antigua y aceptación actual, muestra los
registros de origen y lleva a Tareas. `owner-entry` no inventa contexto, bytes
presentes ni admisiones. La publicación exacta nativa mantiene su implementación.

**Verificación:**85PASS0FAIL0SKIP25.05s fuente;85PASS26.039s desde wheel no editable
sin frameworks antiguos.207imports backend sólo instalados;796miembros coinciden.
Git real137/999, PR sin tarea, clon no disponible, rama/historia intactas, ninguna
llamada remota/hilo cleanup; owner API y contratos nativos de publicación/datos.
97tests frontend pasan; TypeScript y Vite4.81s.42definiciones documentadas,
0avisos nuevos en producción;7de tests y semántica menor de404 diferidos DD026.
0modelos reales. No ensayo nuevo integral de publicación física ni aceptación
visual; no se afirma suite global verde.
[Resultados](native-git-results.json), [paquete](native-git-packaging.json),
[contrato](../architecture/native-git-retirement.md).

**Siguiente principal:** importar material exacto de ramas sin archivos retenidos
y cerrar la cadena de publicación retenida. Los archivos de worktree/copia privada
ya tienen selección explícita como datos para un autor nuevo; el bridge no reemplaza
la importación de una rama. Revisar lectores Git y agentes/conocimiento/consumidores
antiguos pendientes, sin volver al pulido de guards/MCP/launcher. Proyecto integral,
sucesoras, settings/visuales/prompts/evaluaciones/restore/global y resto íntegro del
plan siguen abiertos.

## Etapa anterior: arranque instalado sin setup incidental

**Resultado:** `start.sh` delega a `researcher-start`; API y web se ejecutan sobre
loopback con sus procesos originales. No source de `.env`, instalaciones,
model pull, provisión Forgejo/contraseña predeterminada ni `.pids`/pkill.
`--check` es lectura de prerrequisitos; `--api-only` sirve fuera del checkout web.
Sin configuración nativa se informa modo de inspección. Runtime/Ken/cuenta reales
siguen bajo validación del host/API, no se infieren de este check.

**Verificación:**40casos fuente pasan;35casos compatibles pasan desde wheel
instalado sin frameworks antiguos,0omisiones5.22s.157imports backend sólo del
entorno instalado;794miembros del wheel coinciden. Dos arranques reales seguidos
API+Vite con Node24.22.2: readiness, HTTP200 del índice, SIGTERM→143/cierre de ambos
puertos, proceso ajeno vivo, `.pids` intacto, `.env` inerte, fila137 y esquema
conservados e integridad SQLiteok.1.02s y1.17s.0modelos reales, modo inspección.
11definiciones documentadas,0avisos nuevos en producción;2avisos de tests DD025.
La protección que rechaza credenciales dentro del workspace se conservó y se
observó en el ensayo. No nueva aceptación visual ni host nativo provisionado.
[Resultados](native-startup-results.json), [paquete](native-startup-packaging.json),
[contrato](../architecture/native-startup.md).

**Siguiente bloque principal:** Git/material retenido/publicación y consumidores
antiguos de agentes/conocimiento/pruebas, preservando resultados necesarios.
Cierre integral, sucesoras, settings/visuales/prompts/evaluaciones, restore,
43escenarios/suite global y revisión final siguen pendientes. No volver al
pulido de launcher/MCP/metadata salvo un fallo principal reproducido.

## Etapa anterior: entrada MCP nativa común

**Resultado:** `researcher-mcp` y los dos scripts compatibles comparten catálogo,
DTOs, transporte HTTP y SDK MCP1.30.0 del runtime. Sin FastMCP adicional, SQL,
identidad por variables antiguas ni aceptación/publicación por herramientas de
investigación. Autoridad y revocación permanecen en la API; Ken sigue separado
como MCP obligatorio del host. README y mapa de capacidades actualizados.

**Verificación:** paquete no editable, entorno nativo sin frameworks antiguos:
83PASS0FAIL0SKIP35.49s;216imports backend sólo del entorno instalado y792miembros
coincidentes con el wheel. Protocolo SDK real en memoria/subproceso y comando
instalado; API/SQLite confirma aislamiento y revocación. Ambos scripts locked
arrancan help offline.0modelos reales.29definiciones documentadas;5avisos de estilo
registrados DD024, sin otra pasada de pulido. Fuente inicial79PASS4SKIP por datos
semánticos no configurados; los cuatro sí corren en la prueba instalada.
[Resultados](native-mcp-results.json), [paquete](native-mcp-packaging.json),
[contrato](../architecture/native-mcp-entry.md).

**Siguiente bloque principal:** retirar bootstrap de proveedores/instalaciones y
arranque antiguo `start.sh`, preservando estado y cierre de procesos propios;
Git/material retenido/publicación, agentes/conocimiento y pruebas antiguas siguen
abiertos. Cierre integral del proyecto, sucesoras, settings/visuales/prompts y
resto íntegro del plan siguen activos. Este corte no prueba host/cuenta/Ken reales,
restore o suite global ni añade aceptación visual.

## Etapa anterior: instalación Python nativa independiente

**Resultado:**20dependencias directas por defecto; once paquetes de frameworks,
proveedores, vector DB y parsers antiguos quedan en el extra histórico `legacy`.
Lock/export regenerados; extras de proveedor viejos retirados. Los pedidos de
lectores antiguos sin extra fallan antes de cargar frameworks, con explicación
precisa. README usa la entrada nativa; no hay otra tabla, controller o loop.

**Verificación:** venv nuevo, no editable, sin heredar `.venv`;85distribuciones
incluyendo pruebas y proyecto, ninguno de los once paquetes antiguos. Wheel final:
193PASS0FAIL0SKIP160.52s,294imports backend del entorno nuevo y787fuentes
Python/SQL coincidentes;527archivos de aplicación instalados coinciden, extensión
incluida. Cuatro turnos controlados kernel/broker/Git/SQLite: investigación,
planificación y optimización/check/revisor/aceptación.0modelos reales.
CLI/bootstrap instalados, init esquema54/integridad y rechazo conservando base
existente;`uv pip check` pasa.21casos del entorno anterior también pasan.
13definiciones documentadas,0avisos Ruff nuevos. No nueva aceptación visual.
[Resultados](native-installation-results.json), [entorno](native-installation-packaging.json),
[contrato](../architecture/native-python-installation.md).

**Siguiente bloque principal:** entradas/consumidores antiguos de MCP/Git/agentes/
conocimiento e instalación `start.sh`, preservando capacidades necesarias. Este
venv no equivale a provisionar host/cuenta/SDK/Ken reales ni restaurar un despliegue.
Cierre integral del proyecto, material de sucesoras/publicación retenida,
settings/visuales/prompts/evaluaciones y el resto íntegro del plan siguen activos.

## Etapa anterior: retirar inferencia auxiliar y fallback de proveedor

**Resultado:** configuración/cliente/probes antiguos rechazan antes de construir
modelos, generar o reintentar. No se exportan API keys ni se parchean clientes;
capacidades no observadas quedan desconocidas. El lector histórico usa texto
atribuido y límites explícitos; DeepResearch antiguo deriva al propietario antes
de web/modelo. La investigación real sigue en la sesión nativa admitida.

El catálogo de herramientas/base antiguo se carga solo por petición explícita.
La API puede importarse y construirse en frío sin CrewAI/LiteLLM, sin crear DB ni
mantenimiento. Los lectores de schemas históricos siguen disponibles.

**Verificación:**142casos dirigidos y56de autenticación/arranque pasan (se solapan).
Wheel final179PASS0FAIL0SKIP67.59s,362imports sólo del paquete. Investigación
nativa controlada con kernel/broker/SQLite: fuente/hallazgo/informe y comando real,
fuente137intacta/cálculo200, peers cerrados y grant retirado; no aceptación inventada.
Protocolo real de búsqueda del Codex fijado comprobado sin cuenta ni generación.
0turnos de modelo real.52definiciones revisadas;1docstring de helper heredado y
4avisos de estilo en hooks inertes quedanDD023;7avisos heredados/22resueltos.
[Resultados](auxiliary-results.json), [paquete](auxiliary-packaging.json),
[contrato](../architecture/native-auxiliary-inference-cutover.md).

## Etapa anterior: retirar activación antigua de proyectos

**Resultado:** MainProjectFlow/BrainstormingFlow/TicketCreationFlow son entradas
de solo lectura al propietario. FlowManager no crea trabajadores ni borra eventos;
Start/Resume/listeners y engine antiguos rechazan activación antes de la primera
admisión. Stop conserva los trabajadores/callbacks realmente vivos sin resetear
historia. Handlers de mensajes/salud/progreso/revisión/rework y helpers Crew/agent
task ya no ejecutan modelos ni completan proyectos.

El planificador nativo conserva requisitos/planes/ideas históricos e inventario
real de tareas como fuentes atribuidas, con límites explícitos y sin reproducir
sesiones/aprobaciones. No hay nueva tabla o loop; esquema54 sin cambios.

**Verificación:**128casos dirigidos pasan. Primer wheel233PASS1fallo de fixture:
comparaba tareas del proyecto con el total de dos proyectos. Final29PASS0FAIL0SKIP
9.24s,322imports sólo del paquete;525miembros de aplicación idénticos y
solo el test cambia su contador. Ensayo nativo readonly con kernel/broker/SQLite
reales: cita requisito histórico137→propuesta→cierre→aceptación del grafo una vez,
sin arrancar hijos y fuente137 intacta.0modelos reales.92definiciones comprobadas,
0docstrings/avisos nuevos faltantes en producción;2tests heredados sin docstring y
7avisos de tests diferidosDD022. No nueva aceptación visual ni suite global verde.
[Resultados](project-producer-results.json), [paquetes](project-producer-packaging.json),
[contrato](../architecture/native-project-producer-cutover.md).

## Etapa anterior: retirar ejecución antigua por tarea

**Resultado:** DevelopmentFlow/CodeReviewFlow son entradas de solo lectura al
propietario. Se retiraron sus loops/CI/rework/automerge, el despacho/reset/espera
de tareas de MainProjectFlow y la recuperación/limpieza del scavenger. Las doce
categorías persistidas tienen entrada nativa; ocho producen archivos del repo,
`review` produce una auditoría de solo lectura y `plan` conserva su grafo nativo.
Planificador/API/interfaz usan el mapa compartido. Esquema54 conserva historia y
bloquea claims/done antiguos; admisión por sí sola tampoco permite completar.

**Verificación:**166pruebas dirigidas y97frontend pasan (grupos se solapan).
Wheel aislado:235PASS0FAIL0SKIP169,47s,396imports sólo del paquete. Kernel/Git/SQLite
reales y3turnos controlados: optimización→candidato→check→revisión independiente→
aceptación83,12s; auditoría readonly→fuente/hallazgo/informe1,85s, fuente sin cambios.
0turnos de modelo real. TypeScript/Vite4,84s.101definiciones comprobadas; falta un
docstring en un test heredado y un import de test tiene aviso nuevo, anotados en
DD021.0avisos nuevos de producción;12heredados,29resueltos. No aceptación visual,
suite global verde ni cierre físico global afirmados.
[Resultados](code-flow-results.json), [paquete](code-flow-packaging.json),
[contrato](../architecture/native-task-flow-cutover.md).

## Etapa anterior: importar rutas de trabajo anterior

**Resultado:** Tareas/Conversación permiten usar archivos elegidos de worktrees
antiguos o copias privadas sin candidato. Conservan bytes, modo ejecutable, enlace
literal sin seguir y ausencia observada, sin atribuir contexto o autoría desconocidos.
Se inspeccionan origen y rutas antes de elegir la huella. La admisión y reintento
usan el recibo existente; no hay otra tabla o loop. La carpeta antigua no indexada
`.worktrees` se conserva fuera de la copia nueva, sin editar reglas de ignorado.
Los cambios de código, índices ambiguos y namespaces comprometidos se rechazan.

**Verificación:** primer wheel, 509 pruebas pasan en 225,73 s; cuatro casos históricos
excluidos. Incluye 2 turnos controlados con kernel/broker/Git/SQLite reales en
85,33 s: origen antiguo200→autor nuevo→check→revisor independiente→aceptación,
fuente137 y worktree200 conservados, sin publicación. 447 imports sólo del paquete.
Después se agregó únicamente el rechazo de metadata ya preparada en el índice,
usando flags que ya se leían: sin nuevas llamadas Git o capacidades. El wheel final
pasa 93 casos de Git real/datos/HTTP/protocolo en17,96s,297imports sólo del paquete
y778fuentes coincidentes. No se repitió la cadena física para ese guard negativo.
96frontend/compilación pasan;42definiciones documentadas,0avisos Ruff nuevos.
No se afirman suite global verde, modelos/comprensión ni aceptación visual nueva.
[Resultados](file-import-results.json), [paquete](file-import-packaging.json),
[contrato](../architecture/selected-old-file-import.md).

## Etapa anterior: reutilizar cambios nativos como entrada nueva

**Resultado:** Tareas/Conversación permiten seleccionar un candidato nativo anterior
por intento y huella. Conservan diff completo, entrada original y procedencia como
datos para un autor nuevo, separados de la solicitud/correcciones actuales. No se
trasladan carpeta, permisos, pruebas, revisión ni aceptación. El recibo existente
conserva la selección frente a pérdida de respuesta y reintento. No hay otra tabla,
migración o loop. Un fallo real de inactividad tras herramientas terminadas también
queda corregido, con reproducción corta y controles de límites conservados.

**Verificación:**63casos dirigidos y45de protocolo/adopción pasan (se solapan).
El primer paquete pasó461y falló1fixture de revisor;4casos históricos excluidos.
Sólo cambiaron2tests y coinciden los521miembros de aplicación entre ambos wheels.
El final pasa46casos en258,36s,356imports sólo del wheel y776fuentes coincidentes.
Recorrido real de kernel/broker/Git/SQLite,3turnos controlados: candidato previo→
retirada→autor nuevo aplica diff recibido→pruebas nuevas→revisión independiente→
aceptación.2candidatos/2checks/1revisión/1aceptación, origen137intacto; sin publicación.
94frontend y compilación pasan;40definiciones documentadas,0avisos Ruff nuevos.
Sin nuevo ensayo de modelo real, comprensión humana, aceptación visual o suite
global verde. [Resultados](code-carryover-results.json),
[paquete](code-carryover-packaging.json), [contrato](../architecture/native-code-carryover.md).

**Siguiente bloque previsto entonces (histórico):** importar explícitamente archivos de worktrees
antiguos enlazados/sucios o copias sin candidato capturado, usando el recorrido de
entrada y autoría existente. Conectar selección al despacho de sucesoras de planes
y retirar los resultados/consumidores de desarrollo/revisión antiguos. La exclusión
global y todo el resto del plan permanecen pendientes. No pulir ahora el selector
ni reconstruir otro registro de ejecución. En ensayos largos, estabilizar primero
los contratos de fixtures y ejecutar la cadena física desde el wheel final.

## Etapa anterior: activadores antiguos del proyecto acotados

**Resultado:** la admisión nativa real excluye los productores antiguos registrados
del proyecto completo, también para tareas sin run propio. Mensajes, recuperación
y arranque comprueban el proyecto; el despacho usa evento/contexto guardados.
Stop conserva referencias a hilos vivos y callbacks; la solicitud nativa espera
si sigue una ejecución antigua registrada o no se pudo observar su cierre.
No se resetean tareas nativas ni se borran candidatos anteriores.

**Verificación:**21casos nuevos,145de regresión dirigida y417del wheel pasan
(los grupos se solapan);4casos históricos excluidos.435imports sólo del paquete,
773fuentes coincidentes. Recorrido científico de4turnos controlados con
kernel/broker/Git reales en44,61s; paquete167,81s.92frontend y compilación pasan.
107definiciones documentadas;4avisos menores nuevos quedan enDD019. Sin nueva
inferencia real, suite global verde, evaluación humana o aceptación visual.
[Resultados](project-owner-results.json), [paquete](project-owner-packaging.json),
[contrato y límites](../architecture/native-project-owner-cutover.md).

**Siguiente bloque previsto entonces (histórico):** migrar el resultado de desarrollo/revisión y
trabajo parcial/candidatos previos al recorrido nativo existente. La exclusión
atómica/global entre procesos, productores desconocidos, tipos restantes e
inferencia auxiliar sigue pendiente. No ampliar ahora el registro de hilos ni
pulir paneles/metadatos. Todo el resto del plan permanece en alcance.

## Etapa anterior: investigación científica y evidencia de comandos

**Resultado:** pregunta/métodos, alternativas, hipótesis, experimentos, síntesis
temática, informe, wiki y revisión usan las capacidades nativas existentes.
La salida real de un comando cerrado se captura como fuente citable; conserva
origen, bytes/hashes, errores y límites. No se añadió otro loop ni registro de
hipótesis. ResearchFlow/ResearchReviewFlow ahora sólo indican la acción owner;
`research` pasa al mismo límite que `investigation`. No hay aceptación por etiqueta
o por agotar revisiones. La aceptación explícita libera el trabajo dependiente.

**Verificación:**80pruebas dirigidas pasan. Ensayo broker/kernel/Git real con
4turnos controlados: planificador→autor científico→revisor independiente→desarrollo
privado dependiente tras aceptar. Hipótesis/experimento/conclusión,2fuentes,
informe/wiki; fuente137intacta,0aceptaciones de código y peers cerrados.
El paquete amplio pasó287casos y falló1expectativa de una etapa retirada;
4casos históricos excluidos. Tras adaptar esa prueba al contrato público,
el wheel final pasa46casos sin omisiones. Todos los miembros de aplicación y
binarios coinciden entre ambos paquetes; sólo cambió ese test. Migración52→53
atómica conserva historia;64definiciones documentadas;17avisos Ruff heredados,
ninguno nuevo. No se afirma suite global verde, calidad de modelos, comprensión
humana o aceptación visual nueva. [Resultados](scientific-results.json),
[paquete](scientific-packaging.json), [contrato](../architecture/native-scientific-research.md).

**Siguiente bloque previsto entonces (histórico):** cortar los activadores reales restantes de
AgentLoop/MessageHandler/listeners/FlowManager y los recorridos de desarrollo,
revisión y tipos pendientes, preservando datos/candidatos previos. Revisar sus
consumidores y la adopción explícita de trabajo parcial antes de retirar una
capacidad. No volver sobre metadatos de comandos, estilo o paneles secundarios.
El resto íntegro del plan —incluidas interfaz y evaluaciones humanas— sigue activo.

## Etapa anterior: investigación exploratoria y entradas antiguas


**Resultado:** `investigation` produce un resumen tipado de alcance, áreas con
hallazgos citados, límites y siguientes pasos. Usa el propietario y despacho
existentes, Ken y sandbox de lectura. Conserva revisión documental independiente y
aceptación explícita; sólo después libera el trabajo dependiente.

Las entradas reales de InvestigationFlow, TaskFlowHandler, TakeTask, revisión y
retrabajo devuelven una indicación owner con referencias originales. MainProjectFlow
termina ese despacho sin evaluar progreso ni declarar completo el proyecto; el
scavenger no lo vuelve a ofrecer. No se inicia otro loop ni se reclama esa tarea.

**Verificación:**51backend dirigidas y238del paquete inicial pasan;4casos conocidos
excluidos explícitamente. Tras actualizar las instrucciones del planificador,
20casos del wheel final —incluido el recorrido con kernel/Git— pasan sin omisiones.
Se comprobó que ése es el único archivo cambiado entre ambos paquetes. Broker/kernel/Git real: planificación→
investigación→aceptación→desarrollo privado dependiente,3turnos originales con
generación/Ken controlados, fuente137intacta,0aceptaciones de código.405imports sólo
del wheel inicial y353del final;767fuentes Python/SQL coincidentes; import exploratorio sin inicializar
LoopEngine/MainProjectFlow. Migración51→52 atómica y repetible conserva registros
históricos;83definiciones documentadas.28avisos Ruff heredados y2I001 nuevos quedan
anotados enDD017. Sin inferencia real ni evaluación de comprensión humana; no se
afirma suite global verde o aceptación visual nueva. [Resultados](investigation-results.json),
[paquete](investigation-packaging.json), [contrato](../architecture/native-investigation.md).

**Siguiente bloque previsto entonces (histórico):** migrar los resultados propios de investigación
científica y sus consumidores, preservando métodos/evidencias y revisión, sin otro
loop LLM. Continuar por los demás tipos y las entradas de AgentLoop/listeners hasta
cerrar la exclusión física global legacy. Adopción de drafts/candidatos, interfaz,
comunicación/evaluaciones y todos los demás requisitos del plan siguen pendientes.
No volver sobre detalles secundarios del resumen o del handoff en esta pasada.

## Etapa anterior: adopción explícita de grafos corregidos


**Resultado:** las correcciones de tarea o proyecto pueden adoptarse mediante otra
decisión exacta del propietario, conservando plan, aceptación y autorización
originales. La revisión guarda diferencias, efectos/consumo anteriores y resultados
aceptados vigentes que retiene. Sustituye entregas sin inventar intentos, mantiene
el despacho pausado y exige reanudar la revisión observada. No crea otro loop.
API, terminal y Tareas conservan la misma decisión tras pérdida/reinicio/recarga.

**Verificación:** 133backend dirigidas y135del wheel pasan,3inversas antiguas
excluidas explícitamente.92frontend/compilación pasan. Ensayo broker/kernel/Git real,
generación/Ken controlados: fallo→cierre→reinicio→corrección de proyecto→adopción y
reanudar→investigación aceptada→desarrollo privado dependiente, fuente137intacta,
0aceptaciones de código. Seis estados web,2POST idénticos→1revisión y controles
reanudar/pausar ligados a ella;0errores/desbordamientos/Axe en el panel examinado.
Migración50→51 conserva identidad y revierte fallo provocado;74definiciones Python
documentadas. DosI001heredados del store se conservan comoDD016; sin suite global
verde ni evaluación real de prompting/comprensión. [Resultados](plan-reauthorization-results.json),
[paquete](plan-reauthorization-packaging.json), [contrato](../architecture/corrected-graph-reauthorization.md).

**Siguiente bloque previsto entonces (histórico):** migrar los consumidores reales de flows/autonomía,
claims/listeners y herramientas al único owner, preservando resultados de dominio.
Empezar por el recorrido de investigación exploratoria y su admisión/claims nativos;
comprobar las entradas actuales antes de cortar el consumidor legacy. No otra
reimplementación del journal, broker o panel de recuperación. Adopción de drafts y
candidatos, tipos restantes, exclusión física global legacy y todos los demás
requisitos del plan siguen en alcance. Los detalles de presentación se posponen.

## Etapa anterior: sucesoras de entregas interrumpidas

**Resultado:** una decisión owner sobre evidencia exacta crea una sola entrega
sucesora de un intento cerrado. Conserva run/peers/efectos/consumo/paquete anterior;
no reinicia sesiones ni presupuestos. Usa el dispatcher existente. Pausa permanece
pausa; los resultados pasan por revisión/aceptación existentes y los dependientes
reciben la identidad del nuevo autor. API, terminal y Tareas conectados, con
solicitudes originales preservadas tras pérdida de respuesta/reinicio/recarga.

**Verificación:** 118pruebas backend dirigidas pasan, con3inversas antiguas
excluidas y documentadas; 88frontend y compilación pasan. Ensayo broker/kernel/Git
real con generación/Ken controlados: fallo nativo inicial→cierre→reinicio→sucesora
investigadora→aceptación→desarrollo privado dependiente; fuente137 intacta y cero
aceptaciones de código. Seis estados web escritorio/móvil, una sucesora después de
respuesta perdida/recarga, cero desbordamientos/errores de página/Axe en el panel.
Migración49→50 preserva bytes y rollback de fallo comprobado. Wheel116PASS,368imports
sólo paquete y757fuentes coincidentes.52definiciones Python documentadas; sin
evaluación de inferencia/comprensión real ni suite global verde.
[Resultados](plan-continuation-results.json), [paquete](plan-continuation-packaging.json),
[contrato](../architecture/plan-delivery-continuations.md).

**Siguiente bloque principal:** reautorizar explícitamente grafos corregidos y
continuar la migración real de flows/autonomía/claims/listeners/herramientas al
único owner. Adopción de runs manuales y candidatos, exclusión física global legacy
y todos los demás entregables siguen en alcance. Una observación tardía que cambia
la evidencia de una sucesora autorizada la bloquea; falta el control explícito de
sustitución de esa autorización aún no emitida. No otra pasada de pulido del panel.

## Etapa anterior: terminal y notas sobre el único owner

**Resultado:** orchestrator y entradas CLI/TUI usan la misma API owner del runtime.
No crean otro equipo/motor/DB ni hacen DONE/review/merge por texto. Notas owner
quedan como conversación sin activación. El cliente conserva paquete/versiones y
recibo original tras pérdida/reinicio; URL/IDs no sustituyen identidad física DB.
Las entregas nuevas conservan material/origen/supuestos del plan; revisar una
instrucción coordinada ya no la atribuye como cita literal del propietario.

**Verificación:** selección amplia137PASS/2FAIL (inversas40/41 ante esquemas posteriores;
la inversa42 ya conocida se excluyó explícita). Núcleo final37PASS.
CLI/HTTP/broker/kernel/Git:4turnos originales con generación/Ken controlados,
respuesta perdida/cliente reabierto, investigación→código privado→revisión→aceptación,
fuente137 intacta y cero merge/publicación automática. TUI110×36 real sobre HTTP/DB:
1nota/0activaciones, captura inspeccionada. Frontend86PASS; wheel96PASS,364imports
sólo paquete,753fuentes;3inversas excluidas y documentadas.142definiciones Python
documentadas. No hay suite global verde ni inferencia/comprensión real evaluada.

**Siguiente bloque principal:** migrar de verdad flows/autonomía/claims/listeners y
herramientas restantes al mismo owner, conectar recuperación/sucesores y
reautorización de grafos corregidos. Paridad terminal avanzada y binding web de
endpoint siguen dentro del alcance. No otra pasada de pulido de terminal o publicación.
[Contrato](../architecture/terminal-owner-client.md), [guía](terminal-owner.md),
[resultados](terminal-owner-results.json), [paquete](terminal-owner-packaging.json),
[captura](../design/audits/2026-11-05-terminal-owner/report.md).

## Etapa anterior: despacho aprobado y entregas causales

**Resultado:** el propietario ejecuta una versión exacta del plan aceptado. El
coordinador del runtime existente conserva una entrega original por tarea, espera
resultados aceptados vigentes y pasa sus fuentes/límites al siguiente agente.
Reinicio sólo programa runs originales aún sin intento; Stop pausa el despacho
antes de retirar peers. Una premisa cambiada invalida el grafo autorizado y bloquea
aceptaciones posteriores basadas en ella. No hay otro loop LLM ni activación por chat.

**Verificación:**8 casos nuevos, incluido planificador→investigación→aceptación→
desarrollo privado con broker/kernel/Git reales y generación/Ken controlados.
Primera selección amplia:115/117pasan; expectativa antigua de3tipos corregida y
los10casos de desarrollo público pasan después. Sigue fallando la inversa42 ante
esquemas posteriores (DD003). Wheel aislado:100pasan, ese caso excluido explícito;
353imports sólo paquete,744fuentes coincidentes. Frontend86/build y8estados browser
pasan;2POST originales de ejecutar/pausar tras pérdida/recarga dejan una autorización,
un hijo detenido y dependiente sin run.58Python/14TS documentados. Sin suite global verde.

**Siguiente bloque principal:** retirar los consumidores competidores de autonomía,
orchestrator/flows, claims y mensajes, CLI/TUI mediante el mismo servicio; conectar
recuperación/sucesores y reautorización del grafo corregido. No basta borrar
get_engine ni convertir el chat en comandos. Mantener alcance completo de herramientas,
prompts, libros/evaluaciones, interacción, páginas y migraciones. No pulir ahora el panel.
[Contrato](../architecture/accepted-plan-execution.md), [resultados](plan-execution-results.json),
[paquete](plan-execution-packaging.json), [auditoría](../design/audits/2026-11-05-plan-execution/report.md).

## Etapa anterior: planificación nativa y aceptación del grafo

**Resultado:** iniciar el proyecto admite una tarea `plan` en el runtime Codex/Ken
existente; ya no arranca CrewAI, equipo ficticio ni loops desde esa ruta. Propone
un grafo acotado con citas literales, atribución y suposiciones separadas. El
propietario revisa en Tareas y acepta la propuesta exacta después del cierre:
se crean épicas/tareas/dependencias pendientes, sin ejecutar ninguna. Repetir el
inicio o la aceptación devuelve sus identidades originales.

El cambio de premisas invalida contexto/autoridad del plan y sus tareas hijas;
las dependencias requieren resultados aceptados vigentes. Se conservan historia
y correcciones atribuidas. Los listeners/autonomía antiguos registrados también
bloquean el nuevo inicio, aunque el thread del flow haya terminado.

**Verificación:**94 backend, incluido recorrido físico con generación/Ken
controlados;100 del wheel con362 módulos sólo paquete y740 fuentes coincidentes;
83 frontend/build. Navegador: nueve estados1440/390px sin errores/desbordamiento/
Axe en header y panel. Dos inicios y dos aceptaciones idénticos tras respuesta
perdida/recarga dejan un turno/propuesta y un grafo, con cero ejecuciones hijas.
76 definiciones Python y19 TypeScript documentadas. No hay suite global actual
verde ni evaluación representativa del prompting/comprensión.

**Siguiente bloque principal:** despacho durable de trabajo aprobado y handoffs
entre agentes, consumiendo el mismo runtime y resultados aceptados. Retirar los
llamadores competidores de autonomía/orchestrator/flows/CLI/TUI y demostrar exclusión
física legacy. La aceptación actual no autoriza despacho automático; no presentarla
como engine completo. No ampliar ahora publicación ni pulir el panel del plan.
[Contrato](../architecture/native-project-planning.md), [resultados](native-planning-results.json),
[paquete](native-planning-packaging.json), [auditoría](../design/audits/2026-11-05-native-planning/report.md).

## Etapa anterior: controles remotos de Tareas

Consulta de destino registrado, decisiones separadas push/PR/merge y observación
remota con paquetes originales ante pérdida de respuesta/recarga.92 backend/92wheel,
80 frontend/build y nueve estados visuales pasan en ese checkpoint; testigos
remotos del browser sintéticos explícitos. Adopción tras retirada, continuidad de
merge parcial y compatibilidad real siguen abiertas. [Recibo histórico](remote-tasks-results.json).

## Etapa anterior: recuperación remota de sólo lectura

Esquema46 con identidad/cierre HTTP y observador nuevo después de retirar Git/
HTTP originales. GET/ls-remote exactos, contexto histórico y candidato ausente;
no issue/inferencia/replay.88 dirigidas y88 del wheel; integración TLS real de
respuesta perdida en PR/registro de merge y Stop con finalización posterior del
servidor.58 definiciones documentadas. [Recibo histórico](remote-recovery-results.json).

## Etapa anterior: transporte HTTPS remoto propio

Configuración opcional de HTTPS/PAT del host, Git exacto por broker/dominio y HTTP
acotado. Sin configuración se rechaza capacidad. Git confiable comparte red del
host con argv/origen/configuración fijados, sin ACL de destinos del kernel.
82 pruebas dirigidas,82 del wheel y una integración TLS Git/REST controlado pasaron;
73 definiciones documentadas. [Recibo histórico](remote-transport-results.json).

## Etapa anterior: admisión y etapas remotas durables

Esquema45, run nuevo por acción explícita, identidad global del host y reserva
única antes de cada efecto. Git/registro HTTP del merge son etapas separadas;
la incertidumbre no autoriza repetición. API y scheduler estrictos, sin inferencia.
61 pruebas dirigidas y61 del wheel; dos integraciones locales compartidas y77
frontend/build pasaron en ese checkpoint. El transporte configurado de la etapa
actual completa su gate sin conceder un fallback genérico.
[Recibo histórico](remote-runtime-results.json).

## Etapa anterior: protocolo interno remoto

**Avance:** push del SHA aceptado y recibo remoto en una transacción atómica,
con CAS del destino. Una respuesta perdida se reconcilia por evidencia positiva;
la ausencia remota tras cerrar el cliente sigue siendo incierta. Cliente Forgejo
HTTPX acotado, origen/ID numérico fijados y PR con marcador de intención original.
La recuperación no vuelve a emitir POST; head/base movidos quedan como historia.
Merge interno: Git CAS al head aceptado con ascendencia comprobada, seguido del
registro del mismo SHA en Forgejo; cada etapa conserva su incertidumbre.

**Verificación:** 34 casos dirigidos pasan, 14 nuevos: Git real con remotos bare
(incluida carrera después del preflight) y HTTPX controlado. El subprocess es
exclusivo de fixture; no demuestra red/credencial/autoridad productiva ni TLS.
[Contrato y límites](../architecture/remote-publication.md),
[resultados](remote-publication-results.json), [paquete](remote-publication-packaging.json).

**Pendiente inmediato:** admisión y etapas durables remotas, transporte con
propietario/dominio/credencial del host, integración HTTPS, API/Tareas y coordinación durable de las dos etapas
del merge exacto. Este checkpoint no habilita efectos remotos del producto. El
contrato de merge de Forgejo ofrece guard de head, no CAS de base; no simularlo
con un GET seguido de POST. La recuperación local anterior permanece conectada.

## Etapa anterior: recuperación local conectada

**Resultado:** ante publicación incierta, Tareas puede comprobar qué ocurrió.
El journal prueba cierre original de broker/dominio con procedencia exacta antes
de crear un intento nuevo de lectura. Su permiso admite sólo destino/recibo,
con `.git` fijado en lectura; no reutiliza la autoridad de escritura ni abre
inferencia. Puede conservar el efecto histórico después de corregir el contexto.
Resultado/evento/recibo distinguen publicado, no aplicado e incierto.

**Verificación:** 42 pruebas dirigidas pasan, incluidas recuperación genérica y
prueba negativa de cierre local sin evidencia global. Dos integraciones físicas
pasan en 128.69 s: publicación normal y commit con respuesta perdida,
seguido de nuevo observador y una sola transacción total. Generación controlada;
ningún turno de modelo en publicación/recuperación. Frontend: 77 pruebas y build; cinco
capturas escritorio/móvil inspeccionadas, dos consultas idénticas tras respuesta
perdida/recarga, cero errores/desbordamiento/Axe en panel. Browser con testigos
sintéticos explícitos, no prueba Git. 47 definiciones/módulos documentados.

**Siguiente capacidad principal:** push/PR/merge con identidad remota exacta y
consulta antes de retry; también exclusión física legacy. Interrupción de un
observador antes del recibo, inversas43/44 y controles de capacidad quedan
registrados en [deferred-details.md](deferred-details.md).
[Contrato](../architecture/code-publication.md), [resultados](publication-recovery-results.json),
[paquete](publication-recovery-packaging.json).

## Etapa anterior: publicación local conectada

La entrega `e402453` conecta solicitud owner, aceptación exacta, nuevo intento del
host, broker/capsule y Tareas para crear una rama nueva. Preserva archivos/tarea
y no usa inferencia. Pruebas dirigidas25, integración física1, frontend76/build,
wheel25 y79definiciones documentadas. Consumidores ampliados34PASS/1FAIL: fixture
inverse42 ante nuevo esquema43; no se atribuye a los100 fallos heredados.
[Recibo histórico](publication-connected-results.json).

**Baseline histórico:** `0c8b8d9`, anterior a ambas integraciones: 2045 pasan,
100 fallan y tres se omiten. [Alcance](resumed-baseline-results.json). No es una
suite global verde de la implementación actual.

## Etapa anterior: entrada pública de desarrollo y revisión

**Resultado:** el adaptador con aislamiento admite `code`/`bug_fix`; los anteriores
conservan investigación. El host captura el candidato después del turno y ejecuta
recetas explícitas congeladas en las instrucciones originales. Captura o pipeline
fallidos no se ocultan detrás de un turno completado. Tareas solicita otro revisor
con el objeto exacto; cuerpo/clave sobreviven respuesta perdida y recarga.

**Verificación terminada:** diez casos dirigidos, con recorrido owner HTTP completo
hasta aceptación, comprobación real y origen intacto; 51 consumidores pasan.
Generación y Ken controlados, sin inferencia real nueva. Frontend 75 pruebas/build;
seis capturas inspeccionadas en tres anchos, cero errores de página/desbordamiento
y cero Axe en el panel nuevo. El navegador tiene procedencia física sintética y
retiene la revisión en cola; dos envíos idénticos dejan una admisión y ningún
intento nuevo. 22 definiciones Python documentadas; seis archivos pasan Ruff/formato.

**Paquete:** 84 casos pasan en el wheel ampliado; después se añadió sólo el
docstring faltante de `workspace`. Comparación completa de payloads/AST sin
docstrings y 11 casos del wheel final pasan; 698 fuentes coinciden.

**Verificación interrumpida para la pausa del propietario:** suite global. La primera invocación omitió el plazo de
integración y heredó 20 segundos; se detuvo con SIGINT/salida 2 y se reemplazó con
180 segundos. No se atribuyen sus timeouts al producto sin investigar. Las cifras
globales de arriba son históricas. La invocación corregida se detuvo mediante
SIGINT y terminó con salida 2 por petición explícita de pausa; no queda ejecutándose.
El propietario retomó el objetivo el 2026-11-05 y la nueva ejecución terminó;
su resultado y límites figuran en la etapa actual.
[Contrato](public-development.md),
[auditoría](../design/audits/2026-11-02-public-development/report.md).

**Siguiente entrega:** publicación reconciliable con nueva autoridad y validación
del destino exacto, conservando el veto de evidencia obsoleta o revisión rechazada.
Ninguna aceptación previa autoriza a reutilizar el dominio cerrado del autor.

**Checkpoint de publicación:** 35 casos dirigidos pasan tras reproducir cinco
entradas que el merge antiguo no rechazaba. Preflight de tarea/repositorio/origen
físico ahora bloquea esos casos y conserva repositorios legacy no relacionados.
No constituye exclusión entre procesos ni resuelve primera admisión concurrente;
el publicador reconciliable sigue pendiente. [Recibo](legacy-publication-results.json).
El propietario pidió commit/push de la rama y después pausa. Reanudó explícitamente
el objetivo el 2026-11-05; continúa activo.

## Etapa anterior verificada: aceptación explícita de código

**Resultado:** el propietario inspecciona commit/contexto, diff capturado, resultados
y revisión; acepta únicamente la observación exacta con reconocimiento de límites
cuando corresponda. Revisión rechazada/inconclusa/sin confirmar, fallos y trabajo
sin cerrar bloquean aceptación. Ausencia de pruebas nunca se etiqueta como éxito.
Recibo, evento y estados se guardan juntos; una corrección reabre la tarea y
conserva la decisión histórica. Publicación sigue separada y pendiente.

**Validación:** RED de contrato/almacenamiento y de lectura de captura en preparación;
111 casos compartidos pasan y dos integraciones reales de coordinador pasan con
generación controlada. Bootstrap del wheel: 50 pasan. Ampliación: 217 pasan sin
fallos ni omisiones en 349,94 segundos, 362 módulos sólo del paquete y 696 fuentes
coincidentes. Suite global anterior al ajuste final del historial: 2023 pasan, mismos 100 fallos heredados y tres
omisiones en 1090,75 segundos; no es una suite global verde. Las 66 definiciones
Python nuevas/modificadas tienen docstrings; 23 archivos pasan Ruff y 21 formato,
con deuda previa en los dos módulos grandes restantes.

**Interfaz:** 72 pruebas y build pasan. Once capturas, tres anchos, cero incidencias
Axe dentro del panel nuevo y cero errores de página. Dos envíos con cuerpo/clave
idénticos simulan pérdida antes y después del guardado: una aceptación y un evento
en SQLite; otra recarga recupera el recibo sin tercer envío. La inspección visual
detectó que campos pendientes vacíos no representaban el cuerpo guardado; nueva
prueba roja y corrección verifican casilla/nota originales. Se conservan ambos
recibos y capturas anteriores. No hay aceptación general de la página ni estudio
de comprensión; el fixture del navegador usa procedencia sintética explícita.

**Ajuste final:** una regresión demostró que una revisión favorable podía ocultar
una objeción anterior del mismo candidato. Ahora la objeción confirmada bloquea,
y la propuesta sin confirmar se conserva con su fuerza explícita. Historial
acotado sin omitir una cola; objeciones materiales ligadas a la huella. Pasan
30 casos dirigidos, 56 de bootstrap y 97 del wheel final en 131,24 segundos,
con 343 módulos sólo del paquete y 696 fuentes coincidentes. La captura once
verifica el desacuerdo visible y ausencia de aceptación. La suite global previa
no se atribuye a estos bytes; no hubo otra ejecución global.

[Contrato](code-acceptance.md), [resultados](code-acceptance-results.json),
[paquete](code-acceptance-packaging.json), [docstrings](code-acceptance-docstrings.json),
[auditoría](../design/audits/2026-11-02-code-acceptance/report.md).

**Continuación prevista entonces:** conectar la entrada pública de desarrollo al recorrido
existente de edición/captura/comprobaciones/revisión/aceptación y completar la
publicación reconciliable. La publicación debe revalidar código/destino y mantener
el veto de revisión rechazada o evidencia obsoleta. Continúan todas las obligaciones
de motor/roles/herramientas/comunicación/prompts/interfaz/operación del plan.
La entrada pública ya se conecta en la etapa actual; publicación sigue pendiente.

## Etapa anterior: revisión nativa del candidato

**Resultado:** otro actor/intento/hilo inspecciona el candidato en lectura, recibe petición/entrada originales y comprobaciones completas, y guarda una propuesta con citas y límites. Git se valida antes/después en el dominio original; tras cerrar sesión/herramientas/Ken, el host verifica otra vez las citas y confirma el protocolo. El coordinador retiene como fallo una terminación nativa sin confirmación. No acepta ni publica tareas.

**Verificación:** seis integraciones con generación controlada y Git/SQLite/kernel reales. Primer wheel: 336 pruebas pasan, sin fallos ni omisiones, en 718,39 segundos; 375 módulos sólo del paquete. Suite global de ese artefacto: 1993 pasan, 100 fallan y tres se omiten; 913 casos del runtime pasan. El ensayo real encontró que el índice reservado `.ken` invalidaba Git final. El ajuste limitado a dos archivos tuvo primero un fallo y dos casos que pasaban, y después 26 casos de Git/captura que pasan. Sólo permite estado raíz reservado no indexado; rechaza cambios de código, nombres similares y metadata indexada. Bootstrap final: 63 pasan. Wheel corregido: 83 pasan sin fallos ni omisiones en 302,80 segundos, incluidas las seis integraciones; 339 módulos sólo del paquete y 691 fuentes coincidentes. No se atribuye la suite global anterior a los bytes posteriores. Las 138 definiciones nuevas/modificadas tienen docstring; 38 archivos Python pasan Ruff, 36 formato, con deuda previa en los otros dos.

**Ensayo real:** suscripción, Codex 0.166.0, gpt-6.1-sol y ken-rank 0.18.0. Detectó 100,2 frente a 120, citó la fuente, explicitó limitaciones y registró `needs_revision`; protocolo confirmado, procesos cerrados y origen intacto. Autor/fallo controlados: no es evaluación representativa. Hubo dos turnos reales de revisor, incluido el anterior al ajuste que conservó propuesta sin confirmar. El fixture inicial del verificador cambió presupuesto y se rechazó antes de inferencia; se conserva su recibo. Ken find/read funcionaron; callers devolvió error y el revisor lo declaró como límite.

[Contrato](code-reviews.md), [resultados](native-code-review-results.json), [paquete final](native-code-review-packaging.json), [paquete anterior al ajuste](native-code-review-before-ken-fix-packaging.json), [ensayo real](native-code-review-live.json), [docstrings](native-code-review-docstrings.json).

**Continuación prevista en aquel checkpoint:** aceptación humana, publicación y admisión pública. La aceptación ya se integra en la etapa posterior descrita arriba; publicación y admisión pública siguen pendientes. Mantener el veto de revisión rechazada o evidencia obsoleta sobre publicación, y las decisiones humanas separadas de terminar un turno. Después, completar el cutover de los consumidores/loops antiguos, sin otro coordinador LLM. Todas las obligaciones restantes de comunicación, prompts, conocimiento, interfaz y operación siguen en alcance.

## Etapa anterior verificada: admisión e inspección de revisión

**Resultado implementado:** una revisión interna congela candidato, requisitos, autor/hilo originales y todas las comprobaciones. Exige otro actor, ejecución e hilo; conserva el repositorio original y monta el directorio del candidato en lectura. Revalida el objeto antes de abrir la puerta del proceso. Una comprobación pendiente sigue siendo desconocida y un resultado tardío que cambia la evidencia invalida la revisión actual, preservando la historia.

**Criterio de aquella etapa cumplido:** recibo sin repetición, objeto inmutable, procedencia cerrada, otro hilo, límites sin truncamiento silencioso, montaje real en lectura y corrección antes del despacho probados; migración 40 e inversa sin pérdida verificadas. En ese artefacto la sesión nativa de revisión estaba deshabilitada: su intento no congelaba entrada ni consumía presupuesto de inferencia.

**Validación:** 20 casos nuevos del protocolo y uno de fallo del recurso de migración. Los conjuntos dirigidos de 108, 109 y 20 casos pasan y se solapan. Bootstrap del wheel: 29 pasan en 7,55 segundos; ampliación posterior: 199 pasan en 86,16 segundos, sin fallos ni omisiones, con 350 módulos sólo del wheel y 679 fuentes coincidentes. Las 55 definiciones nuevas/modificadas están documentadas. No hubo una nueva suite global; la referencia histórica y los 100 fallos heredados siguen visibles arriba.

**Límites:** los fixtures de autor y Git son sintéticos; las dos pruebas de kernel demuestran montaje en lectura y rechazo antes del despacho. Faltan validación Git antes/después, sesión nativa, decisiones, aceptación/publicación y admisión pública. No hubo cambios de frontend/locks ni llamadas de modelo; los ensayos anteriores con suscripción/Ken conservan su alcance histórico.

[Contrato](code-reviews.md), [resultados y límites](code-review-state-results.json), [paquete](code-review-state-packaging.json), [docstrings](code-review-state-docstrings.json). El ejecutor de comprobaciones anterior conserva su [contrato y evidencias](code-checks.md).

La etapa nativa posterior descrita arriba reemplaza aquella siguiente acción; los recibos de admisión conservan su alcance histórico.

## Cola posterior, manteniendo el alcance

1. Completar investigación útil: migración de consumidores de búsqueda/documentos/conocimiento y revisión científica; migrar herramientas por capacidades, con sus prompts y contratos.
2. Desarrollo completo: edición/candidato, pruebas, revisión, Git/CI y efectos externos reconciliables. Resolver requisitos de aislamiento antes de habilitar cada efecto.
3. Migrar autonomía, roles, flows y comunicación entre agentes al mismo dueño durable; no añadir otro loop LLM. La comunicación humano–agente se verifica en cada recorrido.
4. Extender diseño a las demás páginas, con conceptos y selección por página; completar aceptación de los seis pilotos existentes.
5. Completar inventario/evaluaciones de todos los prompts y llamadas auxiliares, migraciones/restauración, dependencias, instalación, CLI/TUI y retirada del motor anterior. Trabajar estas obligaciones dentro de las entregas que las toquen; este orden no las aplaza todas al final.
6. Verificación global, revisión independiente de toda la rama y entrega. No cerrar el objetivo con un subconjunto.

## Reglas de ejecución desde este diagnóstico

- **Política explícita del usuario, 2026-11-05:** primero las capacidades principales. Si el resultado central de la tarea funciona, anotar los detalles secundarios en [detalles diferidos](deferred-details.md) y avanzar; resolverlos después, durante el pulido. No enroscarse en esos detalles ni ampliar el diseño por ellos. Al retomar o compactar contexto, leer esta regla antes de elegir la siguiente acción.
- Un recorrido activo. Como máximo, otro frente independiente con archivos y contrato separados; delegar investigación o trabajo definido, evitando revisiones genéricas recurrentes.
- Cada bloque declara resultado observable, criterio de salida, dependencias y pruebas necesarias **antes** de editar. Un experimento de 45–60 minutos sin resolver una incertidumbre exige reconsiderar la alternativa y registrar qué falta; no autoriza ignorar un requisito.
- Antes de ampliar infraestructura, identificar el escenario obligatorio y el fallo reproducido que bloquea el recorrido. Si no lo bloquea, asignarle una entrega posterior y una prueba, conservándolo en el plan.
- Ejecutar pruebas dirigidas durante el desarrollo. Si cambia bootstrap/importación de procesos, probar primero el wheel con el recorrido dirigido. Ampliar a los consumidores afectados al cambiar contratos compartidos, persistencia o aislamiento. Las etapas internas conservan evidencia de ese alcance; ejecutar la suite global al integrar un recorrido de producto y antes de la aceptación final. No sustituir la aceptación global por estas etapas ni repetir una suite sobre los mismos bytes por redactar documentación.
- Repetir un ensayo real sólo por un cambio relevante o una pregunta sin resolver. Conservar resultados parciales y comprobar el verificador sin inferencia antes de usar la suscripción.
- Reusar evidencia válida para la misma revisión/configuración. Un cambio de esos inputs invalida únicamente las conclusiones afectadas.
- Mantener aquí sólo estado actual y próximos resultados; detalles y logs en el ledger/evidencias. Al retomar: leer este tablero, el último bloque relevante y los archivos necesarios, sin reconstruir toda la historia.
- Reportar: resultado utilizable nuevo, criterio cumplido, bloqueo concreto y siguiente entrega. Contar commits/tests como validación o actividad, no como porcentaje del producto.
- Registrar por entrega tiempo transcurrido, esperas identificables, retrabajo y criterio aceptado. Recalibrar previsiones con las próximas dos entregas; no prometer una aceleración ni fecha sin esos datos.
