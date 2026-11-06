# Proyectos: expediente, decisiones y recuperación

Se generaron tres conceptos independientes de escritorio y una adaptación móvil.
Se eligió [Expediente del proyecto](../../concepts/projects/selection.md) por su
lectura amplia y navegación discreta; [prompts, referencias y hashes](../../concepts/projects/manifest.json).
Se compararon la referencia y capturas reales: se conservan papel claro, tinta,
verde funcional, separadores, registro lateral y documento. La UI usa datos
persistidos, sin importar métricas, supuestos o actividad ficticia del concepto.
En móvil alterna lista/expediente con regreso y restitución de foco.

[Evidencia](evidence.json):15capturas,14imágenes únicas — dos capturas de actividad
idénticas pertenecen a continuaciones distintas. Escritorio1440 y móvil390,
0errores JS,0infracciones axe en cabecera/área Proyectos y sin overflow horizontal.
Se comprobaron selección/informe del plan exacto, edición concurrente rechazada y
posterior edición sobre la observación confirmada, borrador aislado al cambiar
proyecto, registro de carpeta existente y fuente temporalmente no disponible.
Creación y registro perdieron una respuesta y se recuperaron tras recargar.

Cuatro POST de planificación conservaron la misma intención/fuente y un solo
intento original. Stop perdió una respuesta; su reenvío conservó trabajo posterior
iniciado explícitamente. Son dos turnos controlados en total,0modelos reales.
Borrado de proyecto con historia rechaza; proyecto sin historia requiere diálogo,
Conservar recibe foco inicial, cancelar conserva y confirmar elimina el recurso.
Lista vacía y errores de lista/workspace usan respuestas GET controladas; no
prueban una base realmente vacía o caída del host. En error de workspace no se
inventa ausencia de fuentes.

API owner, CSRF, SQLite, scheduler y React son reales. Los informes/aceptaciones,
generación retenida y cierres de procesos de la fixture de navegador son
sintéticos explícitos. El ensayo instalado separado acredita kernel/broker y
cierre del Stop real. No hay modelo real ni evaluación de Ken/ranking en este QA.

La ejecución no fue una sesión ininterrumpida. Los primeros verificadores
supusieron foco inmediato antes de requestAnimationFrame, edición disponible antes
de terminar el refresh, un único texto de actividad y que el estado guardado
permanecería new; se corrigieron contra lo observado. Se continuó sobre la misma
fixture/intento original, recuperando una vez el paquete capturado en un contexto
QA nuevo y perdiendo de nuevo otra respuesta antes de la recarga real. Las
repeticiones de POST no generaron otro intento original. El ensayo adicional de
borrado encontró SQL heredado incompatible; el servidor anterior terminó143 antes
de iniciar el código corregido sobre la misma fixture, sin reiniciar trabajo.

Pendientes: comprensión humana, zoom/lector de pantalla/otros motores y aceptación
completa de la ruta; inicialización/clonado/creación/reparación Git, identidad de
creación tras hard delete/restore y paridad terminal. El shell compartido tiene
su propio alcance y no queda aceptado entero por las comprobaciones de Proyectos.
El nombre del botón Stop cuando sólo hay un grafo autorizado queda registrado
como detalle de comunicación para el pulido. No se declara el plan terminado.
