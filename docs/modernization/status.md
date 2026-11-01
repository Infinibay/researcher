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
   broker dueño de G y perfil que impida migración fuera del dominio.
   Ese primer broker interno ya compone reserva global, publicación, bind local
   y G para análisis Python readonly. Conserva la supervisión al cerrar el cliente,
   revoca antes de esperar SQL y bloquea reactivar el intento retirado con una lease
   local antigua. Hay recuperación real antes/después de G sin DB original y
   defensa del perfil frente a sockets/controles y forks. Falta adoptarlo en los
   lanzadores productivos, perfiles Codex/Ken/negocio/desarrollo y aprovisionamiento.
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
10. **Migraciones/evidencia:** migraciones nuevas hasta versión 30, casos históricos,
    ensayos sobre copias sintéticas y comprobación de empaquetado. El último ensayo
    preservó 110 tablas, sus valores y rowids disponibles. No se migró una base del usuario.
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

- Suite completa:1415 casos;1312 pasan,100 fallan con las mismas identidades de la
  línea base y 3 se omiten. La suite global sigue roja.
- Runtime:482 pasan;43 pruebas dirigidas del coordinador/autenticación/RPC/sesión
  y recibos, incluyendo12 casos del coordinador administrado. Dos sesiones usan
  una sola renovación controlada; cancelar una conserva el servicio a la otra.
  En el checkpoint anterior:84 de autenticación/RPC/sesión/broker y recibos.
  Incluyen un ensayo negativo del SDK real sin red y un peer determinista para
  renovaciones; no se enviaron credenciales reales ni turnos nuevos. La wheel actual
  contiene31 módulos runtime idénticos y ejecutó el ensayo aislado correspondiente.
  En el checkpoint anterior:61 pruebas dirigidas de broker/nativo/proyección/dominio.
  Cuatro casos nativos incluyen Codex real sin cuenta, asset cambiado, kind
  incorrecto y un ELF de diagnóstico de la política del perfil. La wheel ejecutó
  Codex y análisis como hermanos y confirmó ambos cierres locales. En el checkpoint
  anterior se verificaron61 de broker/proyección/transporte/fuente.
  Incluyen cierre local idempotente, nueve comandos, SQL local ocupado durante
  Stop, fuente perdida/copiada, binding alterado, reserva con acuse perdido y
  reconciliación en otro proceso. En el checkpoint anterior:23 de fuente/arranque/
  conexiones/revocación y27 del checkpoint de transporte/cierre JSON-RPC. Se probaron
  tuberías bloqueadas, errores de protocolo, cierres independientes y carreras de
  arranque/cancelación; el paquete extraído ejecutó JSON-RPC real y cerró el dominio.
  En el checkpoint anterior:57 pruebas dirigidas,15 de broker
  y17 de dominio/asset sellado. Recuperación en tres fronteras con SIGKILL y sin DB
  original, dos DBs sobre fuente idéntica y límite de forks comprobados.
  El checkpoint del dominio Linux añadió16 casos reales; incluye recuperación
  antes de publicación, arranque congelado, FDs, señales y rechazo del propio cgroup.
  El checkpoint previo verificó69 pruebas dirigidas y150 repeticiones de peers.
  El registro de autoridad/recuperación añade44 casos. Se corrigieron metadatos
  malformados, bloqueo de handles tras fork y una carrera EACCES al cerrar peers;
  denegación sobre un init vivo conserva estado incierto y no lo señala.
  Frontend sin cambios en este checkpoint:28 pruebas y compilación TypeScript/Vite
  verificadas anteriormente tras los ajustes de contraste, cabecera móvil y foco.
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

Evidencia actual: [coordinador administrado y límites](subscription-provider-evidence.json),
[resultados actuales](subscription-provider-results.json),
[paquete actual verificado](subscription-provider-packaging.json),
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
