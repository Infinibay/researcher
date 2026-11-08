# Aceptación de Tareas: primero contratos de creación y lectura

Inicio de inspección07:06:21UTC, basefa7976e. El plan global sigue activo.
No regenerar conceptos ni pulir cada control. Reutilizar workbench existente.

## Evidencia y límites del preflight

- frontend/src/components/pages/TasksPage.tsxhandleCreate captura campos pero no
  clave de operación ni solicitud duradera; useCreateTask envía POSTsin clave.
  backend/api/routes/tasks.pycreate_task inserta cada llamada y sus dependencias.
  Es evidencia de código sobre riesgo de duplicación tras respuesta perdida, no
  un incidente reproducido todavía. Escribir REDantes de cambiar el contrato.
- handleToggleDepGraph transforma HTTPnoOKy errores de red en[]y muestra el grafo.
  No permite distinguir dependencia ausente de consulta fallida. Debe representar
  estado desconocido/recuperación sin inventar aristas o ausencia de ellas.
- TaskInspector lee comentarios/dependencias por separado; revisar errores al
  ejecutar el recorrido. No dar todos sus controles por aceptados por el piloto.
- El formulario envía estimated_complexity mientras TaskCreate consume complexity.
  Comprobar valor elegido con un test real antes de declarar el contrato válido.
- Ken indexa el checkout original: blast_radiuscreate_task devuelve file not indexed.
  Rutas modernas verificadas directamente. OwnerPlanningRecords está en
  backend/planning/owner_records.py; paquetes en frontend/src/api/planningCommands.ts.
  No volver a adivinar sus nombres o extender la tabla69sin revisar su CHECKdekind.

## Trabajo principal y criterios

1. Reproducir duplicación y discrepancia de complejidad en API/SQLite reales.
   Elegir recuperación por intención exacta, respetar project/epic/milestone/
   dependencias, transacción/recibo y compatibilidad del cliente antiguo. Reutilizar
   protocolo de Planificación donde corresponda; revisar borrado/edición posterior,
   colisión, proyecto ajeno, rollback y concurrencia. Si cambia esquema, migración
   explícita e inversa segura, nunca edición retroactiva69.
2. UIguarda antes de enviar y recupera mismo cuerpo/clave tras pérdida/recarga.
   Un recibo tardío no selecciona otro proyecto. Verificar valor de complejidad,
   padres y dependencias. No iniciar inferencia al crear metadatos.
3. Lectura de dependencias fallida no se presenta como grafo sin dependencias.
   Error/recuperación explícitos y aislamiento entre proyectos.
4. Recorrido instalado de cola/detalle/trabajo/contexto/historia/enlaces/controles
   principales, teclado1440/390yAxe regional. Reusar fixture/domainactuales;0modelos
   por defecto. No confundir registros sintéticos con ejecución física o ciencia.
5. Registrar alcance, actualizar tablero y avanzar a Conversación/Ejecución.
   Mensajes/espaciado/estilo menores al final. U08requiere propósito y ejemplo
   relacionado de entrada/salida; no repetir preguntas abstractas ni autoaceptar.

Pendientes generales:4páginas (Tareas/Conversación/Ejecución/Proyectos), U08/C10,
contención original y gates finales.8/12páginas,41/43escenarios al inicio.

## Primer resultado verificado07:29:21UTC

Puntos1–3 implementados en alcance de creación/lectura de grafo: migración70,
recibos inmutables/rollback/concurrencia, alias explícito de complejidad, padres/
dependencias del proyecto y recuperación UI.30fuente/133instalados,154contratos/
52UI;9estados/13checks,0modelos yuna tarea ante tres entregas idénticas. La copia
sin confirmación tras desmontar el componente se conserva hasta recuperar en
el proyecto original. No cambiar producto para forzar su limpieza prematura.

Puntos4–5restan para página completa: Trabajo/historia/corrección/controles sobre
originales. Sigue8/12páginas,41/43escenarios. DetallesDD138al final.
[Pruebas y límites](../../modernization/task-creation-review.md).

## Trabajo siguiente: solicitudes y correcciones duraderas

Inicio07:33:01UTC, basef0d57bf. TaskRunWorkspace guarda InstructionIntent y la
corrección sólo en useRef; recarga/navegación pierde la clave del envío incierto.
Afecta también TaskConversation. Reproducir en DOM con mutaciones reales y red
controlada: respuesta perdida, desmontar/montar con contexto observado cambiado,
y exigir mismo cuerpo/clave. No inventar otra intención al recuperar.

Persistir ambos cuerpos antes del transporte, con ámbito proyecto/tarea/kind,
parser estricto, validación de recibo y retirada sólo de la copia exacta. Reutilizar
validación de prepareInstruction para preservar importaciones seleccionadas; no
usar runId ficticio para reutilizar ownerActionStore. Solicitud aún no tiene runId.
El prefijo researcher: participa del archivo de cambio de instalación existente.
Copia dañada/fallo de guardado bloquea envío; descarte sólo explícito y sin afirmar
que revierte efectos. Recuperación de copia pendiente no depende de canStart de
un nuevo intento ni de elegir otro repositorio. No autoenvíos al montar.

Ensayo instalado: recuperar una admisión preexistente exacta sin programar otro
modelo, corregir mediante endpoint real/perder respuesta y recuperar el mismo
recibo tras recarga. Guardar pruebas de contexto/efectos/runs antes/después. No
iniciar trabajo generativo para probar identidad. Después continuar historial/
controles y errores de comentarios/dependencias del inspector. Detalles al final.

## Solicitudes/correcciones verificadas08:01:05UTC

Identidad duradera antes del transporte y recuperación entre Tareas/Conversación
implementadas. Dos REDDOM→57UI/157contratos verdes; caso instalado7estados/12checks,
mismaadmisión202,Stop202 yuna corrección1→2tras perder respuesta.0modelos. Labels
estables para texto restaurado. [Alcance](../../modernization/task-request-review.md).

Continúan: aceptación de resultados ylecturas/ediciones auxiliares del inspector
(comentarios/dependencias no pueden inventar vacío por fallo); después cierre de
página. No sustituir ese recorrido por otro test sólo de paquetes. Detalles al final.

## Frontera del inspector, inicio08:05:44UTC, base50fdaa3

La inspección del módulo actual descubre dos defectos principales adicionales:
set_task_dependencies valida sólo existencia, no proyecto; no versiona el cambio
ni notifica runtime como update_task. delete_task elimina asociaciones e historia
por cascada basándose sólo en status. Reproducir con API/SQLite antes de cambiar.

Resolver en OwnerPlanningRecords bajo la transacción existente: reemplazo
semántico del conjunto de relaciones, validación del proyecto, conservación de
cambios como evidencia de metadatos y retiro de autoridad del contexto anterior.
Reutilizar _advance_context y task_inputs_changed, sin migración inventada ni
revisión de dependencias iniciales creadas atómicamente antes de admitir tareas.
Los otros productores retenidos crean asociaciones al crear tareas/aceptar planes;
retiro completo de proyecto conserva su política explícita separada. No declarar
protección de SQL arbitrario fuera de estos escritores del producto.

Un reemplazo idéntico es no-op; errores o fallo de evento revierten conjunto,
versión y retiro juntos. Borrado manual rechaza historia nativa, pertenencia a un
plan aceptado o tareas dependientes; exigir quitar relaciones explícitamente evita
borrar sus condiciones por cascada. No cambiar semántica de admisión manual vs
planes aceptados sin revisar su contrato; ese gate no se deduce de la etiqueta UI.

Lecturas del inspector: loading/error/reintento y no falsos vacíos; no editar
prerrequisitos con lectura fallida. Luego aceptación real de resultado guardado y
petición de cambios reabriendo tarea, conservando recibo e informe originales.
Estos son contratos principales, no pulido;8/12páginas sigue sin incremento.

Hallazgo para el siguiente recorrido de resultado: presentRun('accepted') declara
canStart:false. TaskRunWorkspace lo usa aunque el resultado pertenezca al contexto
anterior y la tarea ya se haya reabierto con una corrección. Reproducir y resolver
al aceptar/pedir cambios; no confundir aceptación histórica con permiso de iniciar
el trabajo actual. Guardar datos y recibos originales. No declarar Tareas aceptada
sólo por completar la frontera del inspector.

## Inspector verificado08:54:41UTC

[Alcance](../../modernization/task-inspector-review.md):59fuente/113instaladas,
59UI/157contratos;10estados/15checks en navegador instalado,0modelos. Borrado,
proyecto y retiro de autoridad protegidos. No se acepta toda Tareas aún.
Siguiente bloque principal: resultado aceptado→pedir cambios→contexto nuevo→
solicitud nueva habilitada sin perder informe/recibo. La asimetría blocks manual
queda documentada para resolver después del recorrido. Detalles DD140 al final.

## Resultado y reapertura verificados09:01:45UTC

[Recorrido](../../modernization/task-reopen-review.md):70UI/157contratos verdes,
6estados/12checks instalados, aceptación y corrección exactas tras recarga.
La solicitud nueva queda habilitada sin modificar resultado/decisión históricos;
no se envía otro modelo. Backend sin cambios. Falta resolver contrato manual de
blocks y propagación al cambiar un padre con hijos activos; no basta quitar la
condición de pertenencia a plan en _task. Revisar admisión/claim/herramientas/
aceptación y contexto congelado antes de modificar autoridad. Edición auxiliar
por navegador también pendiente. Sigue8/12páginas. DetallesDD141al final.
