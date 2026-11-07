# Presupuesto: recorrido real de guardado y recuperación

Frontend compilado servido por la API local en5293, con datos sintéticos y sin
runtime configurado. La sesión y CSRF son reales. Se interceptó únicamente la
primera respuesta POST, después de que el servidor confirmara su escritura, para
ensayar pérdida de respuesta.

Se registraron cuatro estados, dos escrituras y seis comprobaciones. Recargar y
consultar el recibo recuperó la primera decisión sin otro POST. Una segunda
decisión redujo el total de500a50, manteniendo100reservados y mostrando el exceso.
SQLite conserva el único despacho desconocido sembrado antes del navegador y su
ejecución cancelada; no se crearon otros. Los dos recibos registran revisiones1/2.

[Interacciones y recibos](browser-evidence.json), [estado SQLite](database-evidence.json).

- [Edición escritorio](01-edit-desktop.png): inspección visual completa del panel.
- [Edición móvil](02-edit-mobile.png): captura parcial por el contenedor con scroll.
- [Respuesta perdida](03-response-lost.png).
- [Total inferior a la reserva](04-lower-below-reservation.png).

Axe del panel no encontró violaciones y el documento exterior no desbordó en los
cuatro estados. No equivale a conformidad de la página completa. Las acciones
móviles funcionaron; la captura móvil no muestra todos los controles a la vez.
Densidad/encuadre quedan enDD108después de las capacidades principales. Cero
modelos y ninguna aprobación humana de comprensión inferida de estos resultados.
