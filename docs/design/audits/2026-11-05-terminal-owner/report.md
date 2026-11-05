# Consola owner: contexto y resultado visibles

Se comprobó la TUI Textual real en110×36, conectada mediante `OwnerClient` a una
API local y SQLite reales. La nota «Gracias. La nota no autoriza una tarea» quedó
registrada con recibo: una nota, cero `agent_events`, cero runs nativos y ningún
pendiente local. No se configuró runtime de inferencia en esta prueba.

[Captura PNG](owner-console.png), [SVG original](owner-console.svg) y
[evidencia](evidence.json). Se inspeccionó la captura renderizada con `rsvg-convert`.
El proyecto y servidor permanecen visibles; la respuesta distingue guardar una
nota, aplicar una corrección y pedir trabajo. El ejemplo investigar→corregir y
la ayuda explican el siguiente paso. La salida visual declara su límite de8000
líneas; los datos originales se conservan en el servidor y journal privado.

Una prueba separada de CLI/HTTP/broker/kernel/Git recorrió planificación→investigación→
desarrollo privado→revisión/aceptación con generación y Ken controlados. Esta imagen
no demuestra comprensión humana representativa ni esos efectos de inferencia.
No añade conceptos web ni páginas aceptadas al inventario12páginas.

Paridad avanzada, presentación de evidencia extensa, navegación/paginación más
cómoda y proyección viva quedan pendientes. No se reabre pulido de esta consola
antes de migrar los consumidores principales restantes.
