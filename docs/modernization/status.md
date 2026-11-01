# Estado frente al plan de actualización

Fecha: 2026-11-01. Plan: [2026-10-31-actualizacion-proyecto.md](../superpowers/plans/2026-10-31-actualizacion-proyecto.md).
El objetivo completo sigue activo. Esta lista distingue componentes implementados
de fases cerradas; los pilotos y pruebas acotadas no completan la migración global.

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
   proceso tras perder la DB del proyecto. No está conectado al broker/PeerRegistry
   productivo ni demuestra el dominio completo de actores del host.
   La primitiva Linux de dominio también existe: nacimiento con clone3 dentro de
   un cgroup real y retirada sin esperar al lock de un arranque congelado. Un
   recuperador separado cerró un hijo vivo tras SIGKILL antes de publicar PIDs y
   pérdida de la DB original. Es un ensayo de constructor de confianza; faltan
   adopción productiva e inscripción de actores; el broker interno se describe abajo.
   Ese primer broker interno ya compone reserva global, publicación, bind local
   y G para análisis Python readonly. Conserva la supervisión al cerrar el cliente,
   revoca antes de esperar SQL y bloquea reactivar el intento retirado con una lease
   local antigua. Hay recuperación real antes/después de G sin DB original y
   defensa del perfil frente a sockets/controles y forks. Falta adoptarlo en los
   lanzadores productivos, composición completa de perfiles y aprovisionamiento.
   Ya tiene adaptador asíncrono JSON-RPC con tuberías reales: cierre independiente
   de peers, Stop con trabajador reservado y recogida de arranques cancelados.
   Esto permite adoptar su transporte; no sustituye aún los lanzadores del servicio.
   Los adaptadores mantenidos de runtime, workspaces, vistas e investigación ya
   abren sólo la DB existente: perderla no crea otra vacía. El cierre del broker ya
   se proyecta sobre los peers originales, con eventos idempotentes, sin otra señal.
   Incluye arranques cancelados, pérdida de acuse de reserva y reconciliación en otro
   proceso desde el journal. SQL local ocupado o ausente no impide el cierre global.
   Falta conectarlo al estado de negocio y a los lanzadores productivos del intento.
   Hay un perfil nativo separado: App Server Codex0.166.0 real bajo el broker,
   manifiesto de ejecutable/perfil/gate, hogar privado sin credenciales heredadas
   y lectura de metadatos comprobada. Aún no ejecuta inferencia/suscripción/Ken en
   ese perfil; no sustituye los lanzadores productivos por este ensayo.
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
   auth.json persistido. Faltan generación con Ken, WebSocket, renovación OAuth
   real y adopción de la fábrica productiva.
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
   posterior si detecta caída/cambio de Ken. Falta la prueba generativa conjunta y
   la adopción productiva; el ciclo de vida de negocio/análisis aportados sigue
   siendo responsabilidad del host. No prueba disponibilidad continua entre checks.
   La conexión de negocio del host ya reutiliza las11 firmas/handlers del MCP y
   mantiene el token fuera de Codex, con HTTP asíncrono acotado y retirada de grant
   vivo antes del cierre. HTTP real y MCP aislado comparten recibos idempotentes;
   retirar autoridad desde el host bloqueó el otro transporte. Falta cablear esta
   propiedad al API/broker productivo y probar inferencia conjunta real.
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
   correcciones y consulta de entrada. Existen 6/36 conceptos de escritorio y 2/12
   adaptaciones móviles, generados e inspeccionados, con selección razonada.
   **0/12 páginas tienen aceptación visual completa**. Playwright/Chromium ya ejecuta
   los pilotos: 8 estados de escritorio y 9 móviles pasan los controles automáticos;
   salto al contenido, foco y navegación se comprobaron. Falta aceptación integral.
10. **Migraciones/evidencia:** migraciones nuevas hasta versión 31, casos históricos,
    ensayos sobre copias sintéticas y comprobación de empaquetado. El último ensayo
    preservó 110 tablas, sus valores y rowids disponibles. La31 conserva peers/rowids,
    referencias y objetos personalizados y revierte fallos. No se migró una base del usuario.
11. **Revisión independiente inicial:** plan, escenarios y mapa de consumidores fueron
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
9. **Frontend restante:**30 conceptos de escritorio y 10 adaptaciones móviles; selección
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

- Suite completa:1542 casos;1439 pasan,100 fallan con las mismas identidades de la
  línea base y 3 se omiten. La suite global sigue roja; no hay nuevas fallas.
- Runtime:595 pasan. Los19 casos añadidos cubren HTTP asíncrono, límites/cierre,
  catálogos compartidos y negocio real vía API/SQLite, con validación y revocación.
  Las pruebas anteriores de Ken/composición nativa, migraciones, HTTPS, Stop y
  recuperación siguen incluidas en la suite completa.
- Paquete actual:40 módulos runtime y cuatro fuentes HTTP/pruebas cambiadas
  coinciden con el código. El wheel extraído pasa29 casos. Con bibliotecas de ese
  wheel y el script/lock heredado aportados explícitamente al harness, el ensayo
  real HTTP/MCP comparte11 esquemas y recibos, conserva un único informe draft y
  aplica la retirada viva entre transportes. No prueba el layout CLI instalado.
- El ensayo Ken anterior con wheel comprobó preparación/catálogo/lectura mediada,
  dos peers cerrados, dominio retirado y fuente intacta. Su pico aproximado1,30GiB
  con límite2GiB no es carga mixta de inferencia. El OOM a512MiB sigue documentado.
  Aquí no hubo acceso a cuenta, generación ni imágenes. Build offline y lock del
  script se comprobaron; se añadieron sus dependencias directas sin bajar versiones.
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

Evidencia actual: [resultados actuales](host-business-results.json),
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
