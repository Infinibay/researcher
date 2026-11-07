# Continuación local: autorización y respuesta perdida

Frontend compilado y API del paquete no editable, puerto local5295, SQLite
sintética nueva. Ninguna cuenta remota ni runtime generativo configurados.

Se inspeccionaron las tres capturas: formulario de decisión en escritorio,
respuesta perdida en móvil y recibo recuperado en escritorio. El componente
completo se ve en las tres; los hashes largos ajustan dentro del ancho. Se
explica antes de guardar que el permiso no inicia un cálculo y que la reserva
anterior se conserva, con ejemplo de3000ms y otra reserva.

El POST sí llegó al servidor y confirmó su transacción; Playwright interrumpió
su respuesta. La recarga conservó el packet original y consultar el recibo
realizó un GET. Una sola escritura, una autorización y el mismo cálculo original
desconocido de3000ms. No aparecieron intentos ni dispatches adicionales a la
fixture inicial. Otro proyecto no puede recuperar ese recibo.

Tres estados,7 comprobaciones,0 errores de página; Axe del componente devuelve0
violaciones y no hay desborde horizontal del documento en1440/390px. Altura de
viewport2200px para capturar esta sección; no es aceptación del viewport móvil
habitual ni de la página completa. La captura real muestra detalles de locale,
texto técnico y densidad registrados enDD110 para la pasada final.

- [Decisión previa](01-local-authorization-desktop.png).
- [Respuesta perdida móvil](02-local-response-lost-mobile.png).
- [Recibo original recuperado](03-original-authorization-recovered.png).
- [Evidencia del navegador](browser-evidence.json) y [SQLite](database-evidence.json).

La ejecución nueva se prueba por separado con procesos reales en backend. Este
recorrido demuestra autorización/recuperación sin ejecutar el cálculo; no afirma
haberlo ejecutado desde la pantalla ni haber evaluado comprensión con una persona.
