# Tablero de ejecución de la actualización

Actualizado: 2026-11-06. Objetivo activo: implementar **todo** el [plan](../superpowers/plans/2026-10-31-actualizacion-proyecto.md). Este tablero no reemplaza requisitos ni declara el plan terminado. [Diagnóstico del proceso](workflow-review.md).

## Estado comprobado

- Codex por suscripción y Ken publicado ensayados. Fuentes/citas, informes draft y revisión documental independiente conectados. Desarrollo admitido desde Tareas/Conversación con captura y comprobaciones explícitas; revisión independiente solicitada desde Tareas y aceptación del propietario conectada. Publicación local desde aceptación conectada; recuperación local de sólo lectura conectada; transporte remoto configurable conectado; recuperación remota y controles de Tareas conectados; ejecución/activación antiguas por tarea y proyecto retiradas; auxiliares de generación/proveedor retirados; quedan consumidores, herramientas y dependencias antiguos.
- Interfaz: seis pilotos, 18/36 conceptos de escritorio y 6/12 móviles; seis rutas pendientes y 0/12 páginas completamente aceptadas.
- Última suite global completada al retomar `0c8b8d9`: 2148 casos, 2045 pasan, 100 fallan y tres se omiten. Mismos 100 identificadores heredados; no se afirman causas idénticas. Pasan 965 casos del runtime. La política Git añadida después tiene verificación separada.
- Los 43 escenarios amplios siguen abiertos en [coverage.json](coverage.json). No hay un porcentaje global defendible.

## Etapa actual: retirar efectos Git competidores y conservar historia

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
