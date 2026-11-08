# Solicitudes y correcciones que sobreviven a una recarga

TaskRunWorkspace conservaba la solicitud y la corrección sólo en memoria. Una
recarga perdía su clave local aunque el servidor pudiera haberlas registrado.
Ahora guarda el cuerpo original antes de enviarlo y lo recupera por proyecto,
tarea y tipo de operación. El cambio sirve a **Tareas y Conversación**.

La recuperación conserva texto, contexto, conversación, selección de repositorio
y material anterior. Reutiliza la validación existente de instrucciones sin crear
una clave nueva al leer una copia. Una solicitud previa a admisión todavía no tiene
run ID: no se inventa uno para reutilizar otro almacén. El prefijo `researcher:`
participa del archivo de cambio de instalación existente; una prueba comprueba
que el nuevo host no recibe la solicitud del anterior.

Copia dañada o fallo de almacenamiento impiden enviar. El recibo debe coincidir
con la solicitud original antes de retirar su copia exacta. Una respuesta de otro
proyecto no la confirma. Recuperar una intención pendiente no queda bloqueado por
las condiciones de iniciar otra nueva, y no elige otro repositorio por la recarga.
El descarte es explícito: no cancela trabajo ni revierte una corrección registrada.
Sin observador montado puede quedar pendiente una copia cuya respuesta llegó a
la red; se recupera con la misma clave al volver, sin inventar otra intención.

Dos pruebas DOM reprodujeron pérdida de texto/identidad al desmontar y montar con
un contexto observado más reciente; ambas pasan con la corrección. Se añadieron
fallo de guardado, copia dañada y recibo ajeno. **57 pruebas UI y 157 contratos**
pasan; tipos y build también. Los helpers nuevos y funciones relevantes modificadas
llevan JSDoc; el nuevo evaluador Python tiene módulo y tres funciones documentados.
La selección frontend pasa ESLint; Ruff del evaluador queda en DD139. No se declara
estilo o documentación global completos.

El navegador instalado v4 recorre **7 estados y 12 comprobaciones**, 1440/390,
sin errores de página, desbordamiento o violaciones Axe regionales. Recupera por
202 una admisión existente después de perder su respuesta y pasar de Tareas a
Conversación. Stop202 detiene ese mismo run. Guarda una corrección real por200,
pierde la respuesta, vuelve a Tareas y recupera el mismo recibo: **contexto1→2 una
sola vez**, con idénticos texto, clave, origen y expected_version. Historial/modelo
sin envío se leen del original; el enlace de otro proyecto no se retargetea.

La admisión y su propuesta inicial son un fixture sintético cerrado por APIs de
dominio, nunca generado por un modelo. **Un run antes/después,0 dispatches y0 IDs
de turno**, fuentes/metadatos/asociaciones conservados, servicio143. Esto prueba
recuperación de admisión existente y corrección/Stop reales; no primera admisión
generativa, cierre físico de un agente real o aceptación científica/humana.

Dos preparaciones fallaron por campos supuestos en el evaluador (`content`,
`body`); el contrato real usa `message`. Se conservaron sus logs/recibos: sin
servicio iniciado, sin dispatches/turnos y peers lógicos cerrados. El tercer caso
llegó a la corrección, pero al restaurar su texto la etiqueta envuelta del textarea
incluía el contenido. Se separaron label/textarea y label/select con IDs explícitos;
el recorrido completo posterior pasa. No se cambió el servidor para satisfacer
fixtures ni se repitió una inferencia incierta. Todos los casos son sintéticos.

Backend sin cambios: mismo wheel b2103c057f25443db82254c626f0f1b7962eaa7f23c35bbf499509d8a74ada51,
689 fuentes coinciden. Sus 133 pruebas instaladas son el recibo anterior, no una
nueva suite. No cambio de esquema70 ni reconstrucción/instalación por este trabajo
frontend. Warning de bundle DD121; captura móvil de historia no encuadra todo el
disclosure y no se presenta como revisión visual completa de ese detalle.

**07:33:01–08:01:05UTC,28min4s hasta verificar/inspeccionar**; documentación y checkpoint
posteriores excluidos. Siguen **8/12 páginas y41/43 escenarios**. Falta completar
Tareas con aceptación de resultados y lecturas/ediciones auxiliares del inspector;
luego Conversación, Ejecución y Proyectos, U08/C10 y gates finales. No transformar
estos recibos en comprensión del usuario ni calidad de una explicación generada.
[Resultados](task-request-results.json), [artefactos](task-request-artifacts.json),
[capturas](../design/audits/2026-11-08-task-request-recovery/report.md).
