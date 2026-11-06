# Cerrar una preparación conservando la carpeta

El propietario puede terminar la reserva de una preparación local detenida y
adoptar después la carpeta mediante otra solicitud. Cerrar no borra archivos,
no registra una fuente ni declara correcto su historial Git.

`POST /api/projects/{project}/source-operations/{key}/release` requiere
`release_key`, `operation_id` y `fence`. El servicio rechaza trabajadores vivos,
otro intento, creación remota o una fuente ya registrada. Comprueba el cierre del
dominio original con su journal real, o un recibo original anterior al dominio;
la ausencia de carpeta/proceso y los campos enviados por el cliente no son prueba.
La decisión queda en `reservation_release`, manteniendo el estado `stopped` y la
historia. Su reenvío exacto devuelve el recibo sin tocar un dueño posterior.

La operación cerrada deja de reservar la ruta y de bloquear la finalización por
reconciliación, pero sigue contando como historia para impedir un borrado
silencioso del proyecto. Sus antiguas autorizaciones no permiten claim, reparación,
observación ejecutable ni registro, incluso después de una nueva adopción.

La interfaz conserva la autorización antes del POST. Una respuesta perdida se
recupera leyendo la misma historia. «Preparar adopción de esta carpeta» sólo abre
un formulario; el propietario envía una solicitud nueva con identidad propia.
Otra solicitud pendiente de ese navegador nunca se sustituye por esta transición.

También se corrige la entrega entre SQLite y programación del trabajador: una
autorización de reparación guardada puede reenviarse con su misma clave si el
intento sigue detenido en el fence original, el origen de la base coincide y
ninguna reparación con esa clave fue admitida. La admisión incrementa el fence
antes de escribir. Un intento admitido, terminado o incierto no se vuelve a
ejecutar por reenviar su clave. La web conserva la clave guardada sin sustituirla
al ver únicamente el acuse de autorización.

[Pruebas y límites](../modernization/source-reservation-results.json),
[recorrido web](../design/audits/2026-11-06-source-reservation/report.md).
Los ensayos de restore/DD030 y formatos/límites pendientes no quedan resueltos
por este contrato. El pulido visual y de caché continúa diferido hasta terminar
las capacidades principales del plan.
