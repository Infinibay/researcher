# Publicación local desde Tareas

Se comprobó el nuevo control dentro del piloto de Tareas existente, con la API
real de propietario, pairing/CSRF, SQLite y el frontend compilado. Chromium local
se usó porque el host del navegador integrado no estaba disponible.

El fixture conserva revisión, aceptación y cierre sintéticos; la publicación se
admite pero se retiene en cola. La prueba física de Git/broker se realiza aparte.
No hubo llamadas a modelos ni modificaciones de repositorios del usuario.

Se inspeccionaron las cinco capturas: escritorio de 1440 px, móvil de 390 px,
respuesta perdida, recuperación tras recarga y confirmación del mismo recibo.
El texto explica rama local, conservación de archivos y pasos remotos pendientes.
El campo recuperado muestra la rama original y evita cambiarla durante el retry.
Dos POST con el mismo cuerpo/clave recuperan una sola admisión. La confirmación
significa «solicitud registrada», no «efecto Git terminado».

Cero errores de página, desbordamientos e incidencias Axe en el panel comprobado.
Esto no acredita accesibilidad global, aceptación completa de Tareas ni comprensión
con usuarios representativos. Mejorar el control de trabajos retenidos por falta
de capacidad y la presentación de estados corresponde a la pasada registrada en
`docs/modernization/deferred-details.md`.

[Recibo y capturas](evidence.json).
