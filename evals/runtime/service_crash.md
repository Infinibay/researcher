# Caída del servicio durante un turno real

`run_service_crash.py` prepara instalaciones sintéticas nuevas con el producto
instalado, Codex por suscripción y Ken. Requiere `--live`, `--assets` y `--output`;
`--only effect|question` limita el ensayo a uno de los dos recorridos.

Cada recorrido admite como máximo dos pedidos explícitos. El primero llega a
una escritura real confirmada: captura de un adjunto o pregunta material. Un
worker de evaluación retiene la respuesta de la captura, o el callback posterior
al commit de la pregunta. No sustituye el modelo, las transacciones, la política
de prompting ni la implementación de recuperación.

El supervisor verifica la identidad del namespace nativo todavía vivo y conserva
su pidfd. Mata exclusivamente el Popen original del servicio, espera su salida y
reinicia la misma instalación con el launcher normal. Recupera por HTTP usando
intento/fence/clave exactos, consulta otra vez el mismo recibo y comprueba:

- Cierre de los peers y retiro de la concesión global original.
- Capturas, operaciones, preguntas, correcciones e inputs conservados byte a byte.
- Consumo remoto desconocido conservado; ningún despacho o aceptación nuevos.
- Pregunta contestable tras confirmar la pausa; responder no ejecuta otro turno.
- Sólo la segunda instrucción explícita permite continuar con el pedido original.
- Ninguna captura repetida ni concesión residual al cerrar los servicios.

La limpieza de emergencia del evaluador se registra aparte. Si tiene que retirar
un recurso residual después de un supuesto éxito, el ensayo falla. Una limpieza
anterior impide atribuir ese cierre a la API; conservar esa limitación al analizar
un intento retomado. Los directorios existentes no se reutilizan para ejecutar el
caso desde cero. Conservar los resultados fallidos y verificar sus recibos antes
de decidir si hace falta otra llamada real.

Esto prueba una caída del servicio sobre datos sintéticos. No prueba reinicio de
kernel, pérdida de energía, recuperación distribuida, cancelación remota ni
comprensión humana. La VM requiere su ensayo separado.
