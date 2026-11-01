# Estado frente al plan de actualización

Fecha: 2026-11-01. Plan: [2026-10-31-actualizacion-proyecto.md](../superpowers/plans/2026-10-31-actualizacion-proyecto.md).
El objetivo completo sigue activo. Esta lista distingue componentes implementados
de fases cerradas; los pilotos y pruebas acotadas no completan la migración global.

Continuación: [tablero de ejecución](execution-dashboard.md).
La [revisión del proceso](workflow-review.md) retira el porcentaje subjetivo anterior
y organiza las siguientes entregas por resultados observables, sin reducir el plan.

Entrega previa: **Informes implementado y verificado**, tercer piloto visual; 20 estados de escritorio/móvil, lectura de citas y corrección sin reescribir el informe. En ese corte: 1498 aprobadas, los mismos 100 fallos heredados y 3 omitidas; frontend 36/36. [Evidencia y límites](reports-results.json). Tras Archivos quedan ocho rediseños y la aceptación completa de las doce rutas.

PDF: captura de adjunto con páginas/hash y lectura→búsqueda→cita→borrador conectadas;104 pruebas dirigidas también desde wheel. Suite actual:1512 aprobadas,100 fallos heredados exactos,3 omitidas. El worker ya tiene CPU/AS/plazo/IPC y cancelación/cierre; siguen pendientes URL/consumidores/Archivos. [Resultados](pdf-results.json).

Último corte de parser:1527 aprobadas,100 fallos heredados exactos,3 omitidas;158 pruebas dirigidas desde fuente y paquete.15 casos nuevos; sin inferencia adicional. [Evidencia y límites](parser-results.json).

Último corte:PDF por URL pública ya conecta descarga→parser limitado→fuente/páginas→cita→borrador.126 pruebas dirigidas y170 desde wheel. Suite1642:1539 aprobadas,100 fallos heredados exactos,3 omitidas. [Resultados y límites](pdf-web-results.json). Archivos tiene tres alternativas y móvil seleccionados; falta su código.

Última entrega: **Archivos implementado como cuarto piloto**. Subida con límites,
previa texto/PDF sin fuente implícita, descarga exacta y borrado conservando capturas
e informes.185 casos dirigidos desde fuente/wheel,41 frontend; suite1657:
1554 aprobadas,100 fallos heredados exactos,3 omitidas.
[Resultados y límites](files-results.json), [recorrido visual](../design/audits/2026-11-01-files/report.md).
La aceptación humana y la migración de consumidores antiguos siguen pendientes.

## Realizado, con el alcance indicado

1. **Inventario y línea base:** dependencias, datos, arquitectura, inferencias,
   capacidades y fallas existentes documentadas. Se conservaron las 100 identidades
   de pruebas fallidas originales para detectar regresiones nuevas.
2. **Entorno reproducible:** dependencias fijadas, lock de Python/MCP, toolchains y
   build del frontend verificados. Arranque/import sin inferencia automática y
   resolución explícita de la base. La instalación final y restauración no están cerradas.
3. **Runtime de destino:** comparación inicial Codex/Infinidev y elección documentada
   de Codex CLI 0.166.0. Infinidev conserva resultados/limitaciones como alternativa,
   sin afirmar equivalencia de calidad, coste o cobertura de todos los gates.
4. **Ken y suscripción:** Ken publicado ken-rank 0.18.0 obligatorio en el camino nuevo,
   integrado en procesos aislados y probado realmente. Pruebas de inferencia por la
   suscripción, sin fallback silencioso a una API por uso. Falta migrar rutas auxiliares.
   Ken comprueba la identidad admitida al abrir su fuente y el CLI monta el caché
   público verificado. Búsqueda y lectura reales se comprobaron sin generación nueva.
5. **Primer recorrido de investigación:** tarea → lectura de código con Ken/adjunto o
   web → fuente capturada → hallazgo provisional/cita → informe draft persistido y
   consultable por API. No equivale a disponer de todas las capacidades de desarrollo.
6. **Control del recorrido nuevo:** identidad de intento, reservas/presupuestos,
   claves idempotentes, Stop/corrección, preguntas/respuestas y recuperación sin replay.
   Propiedad/cierre de procesos y comandos registrados probados; integración completa
   de consumidores heredados y efectos externos todavía pendiente.
   La sesión productiva ya ofrece start/read/cancel y Python de biblioteca estándar
   para análisis, con fuente en lectura, sin red ni credenciales heredadas. No habilita
   todavía edición, paquetes científicos ni entrega de gráficos/archivos.
   Peers nativos y de comandos con admisión durable usan una vista fijada: rename o
   sustitución de la fuente/padre no redirigen sus acciones. No es exclusión global.
   El propietario puede paginar los comandos y leer sus salidas guardadas, también
   tras perder autoridad el agente. Hay API y visor en la tarea y su historial.
   El núcleo de almacenamiento de autoridad testificado ya está implementado:
   abre sólo estado previamente aprovisionado, detecta rewind y recupera commits
   interrumpidos. Sus pruebas incluyen SIGKILL, contención y cierre desde otro
   proceso tras perder la DB del proyecto. El perfil owned ya lo conecta al broker; aún no demuestra el dominio
   completo de actores del host ni sustituye todos los consumidores.
   La primitiva Linux de dominio también existe: nacimiento con clone3 dentro de
   un cgroup real y retirada sin esperar al lock de un arranque congelado. Un
   recuperador separado cerró un hijo vivo tras SIGKILL antes de publicar PIDs y
   pérdida de la DB original. Es un ensayo de constructor de confianza; faltan
   adopción predeterminada e inscripción completa de actores; el broker interno se describe abajo.
   Ese primer broker interno ya compone reserva global, publicación, bind local
   y G para análisis Python readonly. Conserva la supervisión al cerrar el cliente,
   revoca antes de esperar SQL y bloquea reactivar el intento retirado con una lease
   local antigua. Hay recuperación real antes/después de G sin DB original y
   defensa del perfil frente a sockets/controles y forks. Falta adoptarlo en los
   demás lanzadores, completar perfiles y aprovisionar el host; el perfil owned ya lo usa.
   Ya tiene adaptador asíncrono JSON-RPC con tuberías reales: cierre independiente
   de peers, Stop con trabajador reservado y recogida de arranques cancelados.
   El perfil owned ya adopta su transporte; no sustituye todos los lanzadores del servicio.
   Los adaptadores mantenidos de runtime, workspaces, vistas e investigación ya
   abren sólo la DB existente: perderla no crea otra vacía. El cierre del broker ya
   se proyecta sobre los peers originales, con eventos idempotentes, sin otra señal.
   Incluye arranques cancelados, pérdida de acuse de reserva y reconciliación en otro
   proceso desde el journal. SQL local ocupado o ausente no impide el cierre global.
   La conexión con negocio ya existe en el perfil owned; falta migrar los demás lanzadores.
   Hay un perfil nativo separado: App Server Codex0.166.0 real bajo el broker,
   manifiesto de ejecutable/perfil/gate, hogar privado sin credenciales heredadas
   y lectura de metadatos comprobada. La composición posterior ya ejecutó inferencia con la
   suscripción y Ken; no sustituye todavía todos los lanzadores productivos.
   El componente opcional de autenticación externa ya fija cuenta, limita renovaciones
   y atiende el control privado incluso con thread/start o turn/start pendientes.
   Retirar autoridad impide enviar respuestas encoladas. El SDK real aceptó un login
   ficticio local pero no pudo comprobar cuenta sin red; no es prueba de suscripción.
   Ya existe un coordinador del host: dos conexiones comparten una rotación por
   RPC administrado y una cancelación no retira la cuenta de las demás. Se probó
   con procesos controlados; faltan endpoint real inscrito, ensayo OAuth, autoridad
   entre procesos y adopción de la fábrica productiva.
   El perfil nativo ya admite DNS/CA públicos medidos y copias selladas. Codex real
   verifica TLS local y rechaza CA/nombre incorrectos. Un diagnóstico separado
   resolvió documentación pública y obtuvo HEAD200 por TLS1.3 sin credenciales.
   El puente del host ya implementa CONNECT/443 a destinos exactos, DNS público,
   límites compartidos y retirada de sockets; recibe streams por un canal privado
   SCM_RIGHTS. Ya se conectó al perfil privado del broker: Codex real usa el proxy,
   se bloquean acceso directo al host y redirecciones ajenas, y Stop cierra túneles
   antes de SQL. Una lectura real de cuenta ChatGPT funcionó sin thread/turn ni
   auth.json persistido. La generación conjunta con Ken ya se comprobó después; faltan WebSocket,
   renovación OAuth real y adopción como camino predeterminado.
   Ken publicado ya tiene perfil propio en ese broker, con identidad `ken`, fuente
   readonly, estado `.ken` writable, modelos offline verificados y MCP SDK sobre
   sus tuberías originales. Preparación/búsqueda/lectura reales funcionaron tanto
   desde fuente como desde wheel extraído. El primer límite de512MiB produjo OOM;
   con política explícita del host de2GiB pasó con pico aproximado1,3GiB. El default
   anterior se conserva y la política compartida queda registrada antes del nacimiento.
   La composición interna ya exige las cinco herramientas de Ken, sus esquemas y
   argumentos válidos, preparación cerrada del mismo intento y catálogo estable
   antes de thread/turn/herramientas. Un perfil explícito habilita code-mode del
   host y mantiene shell/plugins/agentes desactivados; se comprobó config real.
   El protocolo compuesto controlado ejercita Ken y negocio y bloquea un efecto
   posterior si detecta caída/cambio de Ken. La prueba generativa conjunta ya pasó;
   ya se usa en el perfil owned. El ciclo de vida de actores auxiliares fuera de ese perfil sigue
   siendo responsabilidad del host. No prueba disponibilidad continua entre checks.
   La conexión de negocio del host ya reutiliza las11 firmas/handlers del MCP y
   mantiene el token fuera de Codex, con HTTP asíncrono acotado y retirada de grant
   vivo antes del cierre. HTTP real y MCP aislado comparten recibos idempotentes;
   retirar autoridad desde el host bloqueó el otro transporte. Falta cablear esta
   propiedad a los demás consumidores. El perfil owned ya enlaza el mismo controlador/API.
   La inferencia conjunta real anterior pasó sobre
   un fixture sintético:10 llamadas, un finding provisional y un informe draft leído
   después de escribirlo; tarea sin aceptar y fuente intacta. Se midieron120894
   tokens nativos acumulados y pico1571897344bytes sin OOM a2GiB. El primer ensayo
   falló por helper ausente y el segundo por límite diagnóstico de tokens; quedan
   documentados. El helper medido y su prueba local preceden ahora al thread.
   Ahora hay estado nativo privado conservado: identidad vinculada al journal, un
   hogar por intento y reserva de turno antes del envío. Dentro de la concesión
   original aún viva puede reemplazarse un peer cerrado y reanudarse el mismo
   thread sólo con modelo/catálogo/instrucciones y metadatos coincidentes. Codex
   real lo comprobó sin modelo/cuenta; se usó historia fija inyectada sólo en el
   fixture para materializar el thread. No prueba reanudación generativa ni volver
   a adoptar una concesión retirada. Ya está conectado a la fábrica del perfil owned.
   **Entrada de producto nueva:** `owned-codex-v1` se selecciona por JSON desde el
   lifespan real y las rutas que usa la web. Comparte aplicación, store y LiveGrants
   mediante ASGI; un cambio de entorno no redirige negocio y una copia de la DB no
   conserva los tokens vinculados al intento. Reutiliza el controlador de comandos
   bajo el broker, con fuente readonly/red bloqueada/cuenta ausente. Stop y corrección
   durante preparación y turno cierran el dominio original. La prueba por HTTP con
   propietario/CSRF deja un finding provisional, un informe draft y cálculo200 con
   recibo, estado needs_review y ninguna aceptación implícita. Generación y Ken de
   ese fixture son protocolos controlados. El ensayo posterior por esta entrada
   usó la suscripción, Codex y Ken reales: un turno, 12 llamadas exitosas, cálculo200
   e informe persistido y leído íntegramente. El monitor falló por contención;
   se recuperaron recibos de cierre y HTTP200 sin otro turno. La telemetría de memoria
   perdida sigue desconocida: [evidencia acotada](owned-product-live.json).
   El perfil predeterminado sigue siendo el heredado hasta completar la migración;
   faltan bootstrap, OAuth, recovery completo, todos los consumidores y capacidades.
7. **Contexto y procedencia:** versiones al corregir o cambiar trece entradas de tarea;
   retiro de autoridad antigua; respuesta asociada a pregunta/versión; repositorio
   admitido inmutable y comienzo de cola explícito. Registro exacto de la entrada
   inicial de Researcher, historia anterior acotada y clasificación de su procedencia.
   Dos turnos reales compararon base 137 con corrección a 200 sin repetir 137 en la nueva
   solicitud; ambos informes siguieron borrador y el registro original no cambió.
8. **Acceso del propietario:** sesión local, CSRF, separación entre usuario y grants de
   herramientas; el modelo no recibe cookie/credencial del propietario. Faltan clientes
   y superficies heredadas por migrar y aceptación completa en navegador.
9. **Interfaz inicial:** Tareas y Conversación tienen pilotos implementados; navegación
   responsive compartida, bandeja de preguntas por proyecto, historial, fuentes,
   correcciones y consulta de entrada. Existen 9/36 conceptos de escritorio y 3/12
   adaptaciones móviles, generados e inspeccionados, con selección razonada.
   Informes ya tiene tres alternativas y móvil elegidos; falta implementarlo.
   **0/12 páginas tienen aceptación visual completa**. Playwright/Chromium ya ejecuta
   los pilotos: 8 estados de escritorio y 9 móviles pasan los controles automáticos;
   salto al contenido, foco y navegación se comprobaron. Falta aceptación integral.
10. **Migraciones/evidencia:** migraciones nuevas hasta versión 32, casos históricos,
    ensayos sobre copias sintéticas y comprobación de empaquetado. El último ensayo
    preservó 110 tablas, sus valores y rowids disponibles. La31 conserva peers/rowids,
    referencias y objetos personalizados y revierte fallos. La32 conserva el historial
    nativo cerrado y permite un único reemplazo vivo; conserva unicidad de negocio
    y revierte fallos del índice. No se migró una base del usuario.
11. **Inicialización explícita y arranque:** comando `researcher-bootstrap` para bases
    y autoridad NUEVAS, con rutas privadas y rechazo de estado existente/parcial.
    API, CLI y launcher rechazan DB ausente/vacía; cleanup de grants, credenciales
    y log probado también ante cancelación. La fábrica owned usa el inicializador
    real en su fixture. No es instalación de host ni restore completo.
    [Guía](bootstrap.md), [resultados](bootstrap-results.json), [paquete](bootstrap-packaging.json).
12. **Revisión independiente inicial:** plan, escenarios y mapa de consumidores fueron
    analizados con contexto limpio. Hay 71 herramientas individuales en 11 categorías.
    Esa revisión no sustituye la revisión final de toda la rama implementada.

## Parcial o pendiente para completar el plan

1. **Reemplazo completo de engine/loop/autonomía/flows:** migrar todos los consumidores
   y retirar los loops LLM paralelos, incluyendo LoopEngine/CrewAI y configuración vieja.
2. **Todas las capacidades retenidas:** conectar las 71 herramientas/11 categorías al
   runtime/host correcto. Faltan edición/desarrollo productivo, consumidores de shell,
   coordinación entre agentes, búsqueda/documentos/PDF/CSV/DOCX/JSON/XML, wiki y otras
   rutas. Tener una primitiva o un mapa de migración no significa tenerlas integradas.
3. **Desarrollo y publicación completos:** tarea → cambio → pruebas → revisión
   independiente → aceptación sobre repo/base/head/contexto exactos → Git/PR/merge/CI,
   con reconciliación de efectos remotos inciertos y sin autoaprobar por terminar un turno.
4. **Prompts completos:** inventariar y revisar el 100% de roles, tareas, herramientas,
   resúmenes, memoria y protocolos. Hay guía y prompt mínimo del runtime revisado;
   faltan la aplicación integral de las skills de libros y sus reescrituras/evaluaciones.
5. **Comunicación evaluada:** casos reservados y comparación antes/después, comprensión
   observada con personas, esfuerzo del usuario, metáforas/diagramas accesibles y
   contenido estructurado seguro. Los casos numéricos actuales son evidencia parcial.
6. **Contexto más amplio:** revisar dependencias/proyecto/épicas/fuentes/archivos/Git/
   permisos, comandos tipados de edición con concurrencia/recibos y autoría verificada.
   Faltan checkpoints/compactación del historial largo; la entrada inicial registrada
   no incluye toda instrucción interna del proveedor ni resultados posteriores.
7. **Operación y aislamiento completos:** integrar el nuevo registro de autoridad
   con aprovisionamiento/broker y publicación global antes del gate; exclusión entre bases,
   alias/transferencia de propietario, restauración/despliegue con generación comprobada,
   lifecycle y borrado seguro de proyectos, presupuestos conservados y observabilidad.
8. **Datos e infraestructura final:** backup/restore completo, históricos reales,
   parsers/índices y servicios conservados —incluido decidir sus upgrades—, bootstrap,
   instalación limpia, CLI/TUI y documentación final de operación.
9. **Frontend restante:**27 conceptos de escritorio y 9 adaptaciones móviles; selección
   e implementación de las otras 10 rutas: inicio, proyectos, épicas, agentes, wiki,
   hallazgos, informes, archivos, repositorios y flujo. También paneles/diálogos compartidos.
10. **Aceptación de toda la web:** capturas comparables, móvil, teclado/foco, lector de
    pantalla, zoom, estados de error/espera/recuperación y E 2 E en las 12 páginas,
    incluidas las 2 que ya tienen piloto. Sincronización/catch-up, paginación y retención
    completas siguen pendientes. Build y SSR no sustituyen esas pruebas.
11. **Cierre técnico:** resolver o reemplazar correctamente las 100 fallas heredadas,
    completar checks y escenarios C/E/D/U del plan, revisión independiente final de
    toda la rama, retirada de código obsoleto y entrega verificable. No se hizo merge,
    push ni despliegue. El modelo se elige hoy por JSON global con reinicio; no hay
    selector web/per-agente/proyecto.

## Verificación más reciente

- Suite completa actual:1596 casos;1493 pasan,100 fallan con EXACTAMENTE las mismas
  identidades de la línea base y3 se omiten.27 advertencias. La suite sigue roja.
- Bootstrap:23 casos nuevos aprobados; comandos reales, journal/arranques/cleanup,
  launcher probado con servicios sustituidos por guardias. Wheel/SDist offline;
  14 archivos comparados y264 módulos backend importados sólo del wheel extraído.
  Su entry point creó estado, rechazó repetición y sirvió dos veces conservando datos.
  No hubo turno de modelo ni instalación del host. Ruff pasa en archivos modernos;
  la CLI heredada conserva dos BLE001 previos sin cambios.
- Las siguientes comprobaciones de entrada/composición pertenecen a checkpoints
  anteriores y conservan su alcance; no se reetiquetan como una nueva inferencia:
- Runtime:626 pasan.10 casos nuevos cubren la entrada productiva configurada,
  controlador/source fijos, DB copiada rechazada, Stop/corrección durante preparación
  y turno, informe para revisión sin aceptación y comando nativo real sin cuenta.
- La prueba HTTP atraviesa lifespan, sesión propietaria/CSRF, RuntimeService y la
  fábrica nueva. Generación/Ken son controlados; API/SQLite/kernel/cierre son reales.
  Otro caso ejecuta Codex0.166 real para cálculo200 y rechazo de red/escritura fuente.
- Paquete:44 módulos runtime,9 fixtures/tests y3 fuentes API coinciden con el wheel:
 56 comparaciones.58 pruebas dirigidas pasan desde el wheel extraído con dependencias
  explícitas. Build offline y Ruff/format de los14 archivos modernos pasan. No prueba
  instalación limpia, OAuth administrado o inferencia real por la nueva entrada.
- Ensayo conjunto real:un turno por suscripción con Codex0.166/helper y Ken0.18,
 10 llamadas dinámicas (Ken find/read y8 de negocio exitosas), un finding provisional,
  un informe draft persistido/leído, tarea in_progress, fuente intacta y todos los
  peers registrados/dominio/túneles cerrados. Pico1571897344bytes/no OOM a2GiB;
 120894 tokens acumulados incluyen entrada cacheada, no son facturación.
  El campo de cierre de negocio se muestreó antes de salir del contexto; se conserva
  false con esa limitación, sin afirmar cierre observado de todos los actores host.
  No prueba producción, estado/resume, renovación OAuth ni WebSocket. No se hizo
  generación adicional para reemplazar ese campo del verificador.
- Se conservan dos ensayos previos:helper ausente (cero herramientas) y corte por
  presupuesto diagnóstico100000 tras llamadas exitosas (sin snapshot SQL retenido).
  El último usa el límite350000 ya configurado en el servicio y snapshot también
  tras fallo, verificado offline. No se alteró la política productiva por el ensayo.
- El ensayo Ken anterior con wheel comprobó preparación/catálogo/lectura mediada,
  dos peers cerrados, dominio retirado y fuente intacta. Su pico aproximado1,30GiB
  con límite2GiB no es carga mixta de inferencia. El OOM a512MiB sigue documentado.
  En ese ensayo Ken anterior no hubo acceso a cuenta ni generación. Su build
  offline y lock del script se comprobaron; se añadieron sus dependencias directas sin bajar versiones.
- Ensayo real separado: account/read reconoce ChatGPT por el perfil privado, sin
  thread/start ni turn/start; auth.json ausente y dominio/peer/canales cerrados. No
  se guardaron tokens ni datos personales de cuenta. No prueba renovación OAuth,
  generación por suscripción, permisos de modelo ni integración de Ken en el perfil.
- El diagnóstico público anterior resolvió y verificó learn.chatgpt.com con TLS1.3
  y HEAD200 sin credenciales. Es conectividad observada, no entitlement.
- Los ensayos de autenticación/coordinador anteriores cubren saturación, errores
  redactados, retirada durante lectura/escritura y cancelación de consumidores/cierre.
  Las pruebas anteriores de dominio incluyen SIGKILL, pérdida de DB, contención,
  cierre independiente y reconciliación. Sus resultados detallados están enlazados
  abajo y en el registro de avance; no cierran las fases de integración pendientes.
- Frontend sin cambios en este checkpoint: última verificación de28 pruebas y
  compilación TypeScript/Vite conservada en la evidencia de navegador.
- Ensayo real de continuidad:2 turnos por suscripción, Ken real,4 peers cerrados,
  fuentes sin editar,2 informes draft y ninguna aceptación/publicación implícita.
- Ensayo de análisis:1 turno adicional por suscripción, Ken real, catálogo de 15
  herramientas, cálculo ejecutado,1 informe draft y3 peers cerrados. El verificador
  inicial usó una columna incorrecta; se comprobaron los artefactos existentes sin
  repetir generación. CLI real sin inferencia:7 casos de cálculo/lectura/aislamiento.
- Inspección del propietario:servidor HTTP real sobre copia del ensayo anterior,
  sin runtime configurado ni inferencia nueva;14 lecturas reconstruyeron los95 bytes
  de salida. Nueve tablas conservaron sus valores tanto en original como en copia.
- Ensayos sin generación:Ken real buscó/leyó con la vista privada y admisión del
  host conservada;Codex CLI real pasó7 casos con raíz lógica comprobada,fuente intacta
  y peers cerrados.Se retiraron explícitamente los intentos diagnósticos cerrados.
- QA visual:17 estados reales capturados e inspeccionados en Chromium con sandbox,
  sin infracciones detectadas por axe en esos estados. Se corrigieron carga same-origin,
  contraste, cabecera móvil, salto inicial y foco/desplazamiento entre secciones.
  Login, estados interactivos completos, lector de pantalla, zoom y comprensión humana
  siguen pendientes;0/12 rutas aceptadas. Dependencias:18 avisos npm preexistentes
  (5 bajos,3 moderados,10 altos), sin nuevos paquetes vulnerables por Playwright/axe.

Evidencia actual: [resultados actuales](owned-factory-results.json),
[contratos y límites del perfil](owned-factory-evidence.json),
[paquete actual](owned-factory-packaging.json),
[entrada de producto](../architecture/owned-product-runtime.md),
[configuración de ejemplo](runtime-owned.example.json),
[resultados de estado anteriores](native-state-results.json),
[estado conservado y límites](native-state-evidence.json),
[paquete actual](native-state-packaging.json),
[contrato de estado y reanudación](../architecture/native-state.md),
[resultados del helper anteriores](code-host-results.json),
[helper y readiness](code-host-evidence.json),
[paquete actual](code-host-packaging.json),
[ensayo conjunto exitoso y límites](owned-joint-host-v3.json),
[intento previo cortado por presupuesto](owned-joint-host-v2.json),
[intento previo sin helper](owned-joint-attempt.json),
[contrato del helper](../architecture/native-code-host.md),
[resultados de negocio anteriores](host-business-results.json),
[negocio compartido y límites](host-business-evidence.json),
[HTTP y MCP reales](host-business-live.json),
[paquete actual](host-business-packaging.json),
[contrato de negocio del host](../architecture/host-business.md),
[resultados de composición Ken anteriores](ken-host-results.json),
[composición del host y límites](ken-host-evidence.json),
[Ken publicado mediado](ken-host-live.json),
[paquete actual](ken-host-packaging.json),
[contrato de admisión y pendientes](../architecture/broker-inference.md),
[resultados del perfil Ken anterior](broker-ken-results.json),
[Ken bajo el broker](broker-ken-evidence.json),
[Ken publicado y memoria](broker-ken-live.json),
[paquete de Ken](broker-ken-packaging.json),
[contrato de Ken e integración pendiente](../architecture/broker-ken.md),
[perfil privado y límites](native-proxy-evidence.json),
[resultados actuales](native-proxy-results.json),
[paquete actual](native-proxy-packaging.json),
[metadatos autenticados](native-proxy-account-metadata.json),
[contrato del perfil](../architecture/native-proxy.md),
[puente del host y límites](egress-evidence.json),
[resultados del puente](egress-results.json),
[paquete del puente](egress-packaging.json),
[contrato e integración pendiente](../architecture/native-egress.md),
[DNS/TLS y límites](native-network-evidence.json),
[resultados DNS/TLS](native-network-results.json),
[paquete DNS/TLS](native-network-packaging.json),
[diagnóstico público sin credenciales](native-network-live.json),
[contrato DNS/TLS](../architecture/native-network.md),
[coordinador administrado y límites](subscription-provider-evidence.json),
[resultados del coordinador](subscription-provider-results.json),
[paquete del coordinador](subscription-provider-packaging.json),
[autenticación y límites](subscription-evidence.json),
[resultados de autenticación](subscription-results.json),
[paquete de autenticación](subscription-packaging.json),
[contrato de autenticación](../architecture/subscription-auth.md),
[transporte nativo y límites](broker-native-evidence.json),
[resultados del transporte nativo](broker-native-results.json),
[paquete verificado](broker-native-packaging.json),
[proyección del cierre](broker-projection-evidence.json),
[fuente existente](existing-source-evidence.json),
[transporte/cierre](broker-stdio-evidence.json),
[paquete y JSON-RPC aislado](broker-stdio-packaging.json),
[broker/gate anterior](peer-broker-evidence.json),
[contrato implementado y pendientes](../architecture/peer-broker.md),
[paquete y ensayo aislado](peer-broker-packaging.json),
[dominio Linux](execution-domain-evidence.json),
[resultados del dominio](execution-domain-results.json),
[contrato y límites](../architecture/execution-domain.md),
[paquete nativo](execution-domain-packaging.json),
[registro de autoridad](authority-journal-evidence.json),
[resultados del registro](authority-journal-results.json),
[contrato implementado y límites](../architecture/witnessed-authority-journal.md),
[paquete](authority-journal-packaging.json), [medición local histórica](authority-journal-benchmark.json),
[vista fijada](peer-workspace-evidence.json),
[resultados del checkpoint anterior](peer-workspace-results.json), [bootstrap propuesto](../architecture/workspace-authority-bootstrap.md),
[navegador](browser-evidence.json),
[recorrido visual](../design/audits/2026-11-01-owner-workspace/report.md),
[resultados del checkpoint de navegador](browser-results.json), [entrada/continuidad](run-input-evidence.json),
[resultados](ken-identity-results.json), [identidad de Ken](ken-identity-evidence.json), [consulta del propietario](owner-command-evidence.json),
[análisis](analysis-evidence.json),
[ensayo de análisis](analysis-live.json), [continuidad](run-input-live.json),
[migración](run-input-migration.json), [cobertura](coverage.json),
[inventario visual](../design/inventory.md) y [registro de avance](progress.md).

## Ampliación posterior: artículos identificados

El catálogo nativo añade `researcher_capture_paper` para URL/DOI/arXiv. Se conserva la
petición/versión y se usa el mismo parser/captura con hashes, permisos y recibos. DOI
puede devolver HTML de presentación; no se presenta como acceso al artículo completo.
La fachada nativa llega a cita exacta e informe draft sin inferencia adicional.
Verificación actual:245 casos dirigidos desde fuente/wheel;31 casos nuevos. Suite1688:
1585 aprobadas,100 fallos heredados exactos,3 omitidas.
[Contrato y consumidores pendientes](../architecture/paper-capture.md),
[resultados](paper-results.json), [paquete](paper-packaging.json).

Los roles CrewAI, flows y recuperación semántica de `pdf_search` aún requieren migración.
El nuevo buscador literal no se declara equivalente a embeddings. No hay cambios de UI
ni más páginas aceptadas en esta ampliación:4 pilotos y0/12 aceptadas completamente.


## Última ampliación: recuperación semántica local

`researcher_source_query` recupera paráfrasis con un modelo multilingüe fijado, completo
por chunks y con pasajes/offsets/páginas exactos. Preparación explícita, worker limitado,
cancelación/reap y permisos revalidados; no utiliza el backend remoto de embeddings.
En el ensayo nativo de PDF recuperó contraevidencia más allá de los12.000 caracteres,
guardó un finding provisional y un draft de texto fijo; la tarea sigue in_progress.
No es una evaluación de comprensión/síntesis LLM ni de validez científica.

Verificación actual:271 pruebas dirigidas desde fuente/wheel;26 casos nuevos. Suite1714:
1611 aprobadas,100 fallos heredados exactos,3 omitidas.606 fuentes Python/SQL coinciden
con el paquete. [Contrato y límites](../architecture/semantic-source-retrieval.md),
[resultados](semantic-results.json), [ensayo](semantic-product-evidence.json),
[paquete](semantic-packaging.json). Se promovieron tres dependencias ya instaladas sin
cambiar sus versiones. Interfaz sin cambios:4 pilotos,0/12 aceptadas completamente.

Siguen pendientes formatos/roles/flows/consumidores heredados, evaluación representativa,
inscripción de todos los actores/presupuestos globales y el resto del plan completo.


## Última ampliación: documentos estructurados

CSV/JSON/XML/DOCX ya se capturan con estructura y hash original. Lectura, búsqueda
literal/semántica local y citas usan el mismo snapshot normalizado; los locators se
recuperan con paginación. Word conserva párrafos/tablas del cuerpo con omisiones
explícitas, y CSV declara la suposición de encabezados. La previa del propietario
explica esos límites y no crea una fuente de investigación.

Verificación:305 casos dirigidos desde paquete;34 nuevos en la suite completa.
Suite1748:1645 aprobadas,100 fallos heredados
exactos,3 omitidas.41 frontend/build y8 estados reales de navegador; no hubo turnos
LLM adicionales. [Contrato](../architecture/structured-sources.md),
[resultados](formats-results.json), [paquete](formats-packaging.json),
[recorrido](../design/audits/2026-11-01-structured-files/report.md).

Los roles/flows/registries heredados siguen activos hasta completar sus capacidades
de conocimiento, búsqueda y revisión. No se anuncia retirada del RAG anterior ni
aceptación adicional de UI:4 pilotos y0/12 páginas completamente aceptadas. El plan
completo, auditoría de docstrings incluida, permanece activo.
