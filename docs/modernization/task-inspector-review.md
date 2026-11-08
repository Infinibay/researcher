# Frontera de comentarios, dependencias y borrado de Tareas

El inspector distingue carga, error y ausencia confirmada. Un fallo no habilita
el editor de relaciones ni inventa una lista vacía. Las notas explican que no
aceptan resultados ni retiran autoridad. Las relaciones entrantes se consultan
explícitamente; el GET anterior conserva su contrato de sólo salientes.

Cambiar dependencias valida el proyecto y reemplaza sólo el tipo solicitado.
Relaciones, nueva versión de contexto y retirada del trabajo anterior se guardan
juntas; fallo de evento revierte todo. Reordenar el mismo conjunto no cambia la
versión. La notificación al runtime ocurre después del commit. Borrar una tarea
rechaza historial nativo, pertenencia a un plan aceptado o dependientes; no borra
sus condiciones por cascada. No hay migración nueva: sigue el esquema 70.

Verificación: **59 pruebas fuente, 113 instaladas, 59 UI y 157 contratos** pasan,
sin omisiones en las selecciones Python. Tipos y build pasan. Wheel limpio desde
sdist, SHA bb330f5f3a773cd4358e5b5d2e876735fec070c22d63de109538cb70d9b2469e:
690 fuentes/367 archivos de producto coinciden con instalación no editable;
250 módulos backend importados desde ella. 83 paquetes compatibles. Los cinco
módulos Python seleccionados documentan sus 58 definiciones, sin omisiones.

Navegador instalado: **10 estados y 15 comprobaciones**, escritorio/móvil,
lecturas fallidas y reintento, dirección entrante correcta, recuperación de la
solicitud original entre páginas, Stop202 y corrección1→2 una vez tras perder
respuesta. Un run original antes/después, cero dispatches e IDs de turno; fuente,
metadatos y relaciones conservados, servicio143. Datos/admisión sintéticos, sin
modelo. Se inspeccionó la captura de relaciones entrantes. No se prueba aquí la
edición por navegador ni la aceptación de toda la página, ciencia o comprensión.

**08:05:44–08:54:41UTC:48min57s hasta verificar/inspeccionar.** Documentación y
checkpoint posteriores excluidos. Continúan 8/12 páginas y41/43 escenarios.
Siguiente: aceptar resultado, pedir cambios y permitir trabajo en el nuevo
contexto conservando informe y recibo históricos. Detalles DD140 al final.
[Resultados](task-inspector-results.json), [paquete](task-inspector-packaging.json),
[documentación](task-inspector-docstrings.json), [huellas](task-inspector-artifacts.json).

## Revisión independiente del contrato de dependencias manuales

Un subagente con contexto limpio revisó código/documentación en sólo lectura.
`SqliteRunStore._task` aplica la barrera de prerrequisitos a tareas derivadas de
planes aceptados; una relación blocks manual no recibe esa barrera. La arquitectura
nombra expresamente tareas derivadas. Esto demuestra una asimetría y un contrato
incompleto, no una obligación universal previamente acordada con el usuario.
La palabra prerrequisitos añadida a la UI en este bloque tampoco constituye
prueba histórica independiente de intención.

Recomendación del revisor: comprobar blocks para ambos orígenes, manteniendo la
aceptación del plan como condición adicional sólo para tareas derivadas. Una
excepción del propietario requeriría una decisión explícita y registrable, no
inferirla de una solicitud ordinaria. **No implementado en este bloque.** Resolver
como trabajo principal: pending, done sin aceptación, aceptación desactualizada,
aceptación vigente, tipos no bloqueantes, cambio entre admisión y claim y cambio
del contexto padre con un hijo activo. No promover metadatos done a aceptación.
Esta revisión parcial no sustituye la revisión independiente final del branch.
