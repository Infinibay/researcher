# Puente de salida del host

`TunnelProxy` y `EgressChannel` implementan la parte del host del nuevo perfil
nativo privado. Sólo reciben sockets por un canal Unix heredado; no abren un proxy
TCP público. Ya están conectados al [perfil del broker](native-proxy.md), retirando
allí la ruta directa. La fábrica productiva todavía usa su lanzador anterior.

## Contrato implementado

`EgressPolicy` requiere entre uno y dieciséis nombres DNS exactos. No admite
wildcards, nombres de una sola etiqueta, IPs literales ni puertos elegidos por el cliente. El
protocolo acepta únicamente CONNECT hacia un host permitido por el puerto 443.
Exige una autoridad Host coincidente; rechaza duplicados, framing de cuerpo,
credenciales de proxy y headers ajenos al contrato. Las respuestas de rechazo son
constantes y no repiten la solicitud.

Después de autorizar el nombre se valida **cada** dirección DNS. Una respuesta
mixta pública/privada rechaza todo el destino; no se elige sólo la dirección
conveniente. El mismo helper público que usa la ingesta web descarta loopback,
direcciones privadas/reservadas/multicast y transiciones IPv6 no admitidas. El dial
recibe una dirección numérica validada, conservando 443 y sin volver a resolver el
nombre. Se prefiere IPv4 cuando ambas familias están disponibles. No se sigue un
redirect HTTP ni se reintenta el dial desde este puente.

TLS y sus mensajes permanecen opacos en el túnel. El SDK debe verificar el
certificado y la identidad remota; este puente no inspecciona SNI, HTTP cifrado,
rutas ni pertenencia de una cuenta. Una lista DNS y un IP fijado no acreditan por
sí solos autorización de aplicación ni evitan toda forma de domain fronting en
infraestructura compartida. El perfil final debe limitar también qué ejecutables
y herramientas pueden usar la red, manteniendo TLS válido en el cliente real.

Los helpers `public_address` y `resolve_addresses` se extrajeron a
`backend/network_destinations.py`: el runtime no importa el adaptador de
investigación. Éste conserva su traducción a `SourceUnavailable`. El resolver
predeterminado conserva un proceso DNS directo, con entorno mínimo, timeout de
hasta tres segundos y recogida del hijo. Su inscripción dentro de la autoridad
completa del despliegue sigue pendiente; no queda demostrada por esta extracción.

## Recursos, retirada y recibos

Los valores predeterminados por propietario son:

| Recurso | Límite |
| --- | --- |
| Túneles simultáneos | 8 |
| Conexiones admitidas durante su vida | 64 |
| Header CONNECT | 16 KiB y 3 segundos |
| Resolución/conexión | Hasta 3 segundos por operación |
| Vida de un túnel | 180 segundos, incluyendo admisión |
| Inactividad | 30 segundos |
| Payload reenviado por túnel | 16 MiB entre ambas direcciones |
| Payload acumulado del propietario | 128 MiB |
| Buffers de reenvío | Hasta 64 KiB por dirección |

Los headers incompletos también respetan el plazo total del túnel. La suma de
bytes es compartida y se comprueba bajo lock justo antes de escribir, sin esperar
por I/O bloqueante dentro de ese lock. Alcanzar el límite no reenvía un byte extra.
Se preservan cierre de media conexión y backpressure; un cliente lento no crea una
cola sin límite. Estos contadores no son consumo de tokens ni cuota de suscripción.

`withdraw()` retira admisión y cierra los sockets conocidos sin esperar DNS ni
SQL. Una resolución tardía no inicia el dial y un socket que llega tarde se cierra
antes de recibir payload. `close()` espera recogida acotada; si no la confirma,
devuelve un error de cierre incierto. Una operación DNS ya iniciada puede seguir
hasta su timeout; retirar autoridad no afirma que no hubiera paquetes previos.

Cada trabajo devuelve sólo `TunnelReceipt(outcome, uploaded, downloaded)`, sin
payload, headers ni errores crudos de dependencias. Los resultados distinguen
finalización, denegación, deadline, límite de bytes, retirada y fallo de I/O. Un
túnel terminado no es un turno aceptado ni una tarea completada.

## Canal heredado

`EgressChannel` crea un socketpair Unix SEQPACKET. Su extremo hijo se duplica bajo
lock con `duplicate_child()`; el caller posee esa copia hasta terminar spawn. La
retirada no puede convertir ese descriptor fijado en otro FD reutilizado. El
caller debe cerrar su copia propia y llamar `close_child_end()` después de spawn,
para que la desaparición real del helper produzca EOF.

Cada mensaje debe contener el byte `F` y exactamente un descriptor SCM_RIGHTS. Se
recibe con CLOEXEC. Framing truncado, marcadores distintos, descriptores múltiples
o recursos que no sean streams conectados retiran el canal y cierran los recursos
recibidos. El número total de entregas también está acotado, incluyendo rechazos
por saturación. EOF retira todos los túneles; el propietario debe llamar `close()`
para drenar también el reader y el pool.

## Integración del perfil y trabajo restante

El [perfil privado](native-proxy.md) ya compone helper, canal y broker. G precede
al helper; éste cierra FDs y el nativo instala su filtro estricto. Stop/cierre de
peer retira túneles y drena recursos antes del recibo. La política/código figuran
en el manifiesto. Las pruebas incluyen SDK real, TLS, redirección denegada, ausencia
de ruta al host, pérdida de canal, descendientes y carreras de arranque/cierre.
Falta WebSocket real del SDK y la composición productiva; no se deducen del éxito
HTTPS. Configurar proxy conservando host networking tampoco ofrece ese aislamiento.

Después siguen endpoint administrado inscrito, convivencia por cuenta, estado
nativo persistente, OAuth real, Ken/negocio/code-mode y fábrica productiva. El plan
completo de engine, herramientas, prompts, comunicación y doce páginas continúa.
