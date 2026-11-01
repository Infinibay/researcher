# Code-mode: ejecutable medido y readiness antes de inferencia

El primer ensayo conjunto real del broker, suscripción, Ken y negocio no superó
la aceptación: Codex terminó el turno sin enviar llamadas dinámicas a Ken/negocio.
Su respuesta informó que faltaba el ejecutable del host. Inspeccionar el paquete
confirmó que `codex-code-mode-host` se distribuye junto a `codex`, mientras que el
perfil del broker sólo montaba este último. Configuración y catálogo correctos
no demostraban que las herramientas fueran ejecutables.

La [documentación oficial](https://learn.chatgpt.com/docs/app-server) describe que
App Server inicia por defecto un host local de Code Mode. Para0.166.0 se contrastó
también el protocolo y framing con su código fuente fijado: handshake V1,
`session/open`, ejecución, delegación y cierre sobre stdio.

## Qué cambió

`host_tools=True` ahora exige otro `CodexAsset` inspeccionado, `code_host`, además
del binario principal y la política de NET privado. Falta de helper se rechaza
antes de la reserva global. El manifiesto conserva identidad/hash y el hash del
probe; cambiar una operación exige otra clave/intento, no reusar su recibo.

El perfil abre ese helper fuera de la fuente, revalida sus bytes/identidad y lo
monta desde el descriptor en lectura en
`/run/researcher-runtime/codex-code-mode-host`, junto al ejecutable principal.
Se añade sólo ese directorio privado al PATH. Sustituir el asset después de medirlo
no abre el gate. No se monta el paquete completo ni credenciales del host.

`broker_inference` ejecuta un readiness fijo antes de `thread/start`:

1. El host llama a `command/exec` con un programa Python fijo de la distribución,
   sin argumentos del modelo. Selecciona `externalSandbox` porque el sandbox de
   kernel del broker ya está aplicado; este RPC no puede retirarlo ni amplía la
   fuente readonly o el acceso de red. Shell sigue ausente del catálogo del modelo.
2. Dentro de esa misma concesión/cgroup/namespace/filtro, el programa abre el helper
   medido por stdio, negocia V1 y exige límites de recursos.
3. Abre una sesión con heap acotado, ejecuta JS que comprueba ausencia de globals
   Node/Deno, llama a una función fija de prueba y obtiene `137+63=200`.
4. Comprueba respuesta/delegación, cierra sesión, stdin y proceso. Sólo entonces
   permite crear el thread. Fallo implica cero turnos nuevos.

Esto es un probe de capacidad, no otro loop LLM ni un intérprete para programas
del usuario. No recibe código, paths, permisos o credenciales del modelo. El
readiness tiene deadline/frames/output acotados y no devuelve diagnósticos crudos.
Los descendientes conservan los límites y cierre del peer nativo original.

El helper0.166 observado mide77.997.328 bytes, SHA-256
`657f4e902726e05867c937b583049d5997e057f8cd0ab40450633c9c9ef8d630`.
Es la identidad del ensayo, no una autorización para instalar o cambiar binarios.

## Evidencia y límites

La prueba real sin cuenta/modelo inicia el App Server fijado dentro del perfil,
ejecuta handshake, JS y callback con el helper real y cierra todo el probe. Las
pruebas cubren helper ausente antes de reserva, archivo cambiado antes del gate y
helper que falla antes de cualquier thread/turn. Los protocolos controlados de
composición ahora también ejecutan ese helper real durante su readiness.

El ensayo de suscripción anterior conserva su resultado fallido: un turno,
catálogo16, ninguna llamada dinámica observada, fuente intacta y peers/dominio
cerrados. Pico1.456.132.096 bytes sin OOM, con límite2GiB; no mide la carga mixta
con un helper funcional. No prueba el recorrido de informes ni WebSocket: el
CONNECT era opaco y no se registró un handshake del proveedor.

El verificador del ensayo además intentó consultar un atributo de telemetría
inexistente y ocultó el fallo previo de aceptación. Se corrigió el harness para
futuros ensayos y se conservó ese error separado. No se repitió el turno ni se
convirtió una respuesta sin herramientas en éxito.

## Ensayos con el perfil corregido

El segundo intento ya ejecutó `ken_find`, `ken_read` y ocho llamadas de negocio
exitosas. Se interrumpió al superar el límite diagnóstico de100000 tokens
observados. El contador asigna el total acumulado informado por Codex; no suma
otra vez cada notificación. Ese total incluye entradas cacheadas. El verificador
no conservó el snapshot SQL después de la excepción y borró su DB sintética al
cerrar el directorio temporal: las respuestas exitosas no sustituyen esa evidencia.

El tercer intento usó claves nuevas y el límite350000 ya existente en el servicio,
sin modificar la política de producción ni repetir un turno incierto. El harness
se comprobó offline para capturar SQL también tras fallo y rechazar una DB ausente
sin crear otra. El ensayo terminó correctamente con120894 tokens acumulados:

- Ken real localizó y leyó `invoice.py`; negocio capturó dos adjuntos y los leyó.
- SQL conservó exactamente un finding provisional y un informe `draft`, leído por
  la herramienta después de escribirlo. La tarea permaneció `in_progress`.
- La respuesta distinguió inspección de ejecución: no afirmó haber corrido tests.
- Fuente intacta, peers registrados cerrados, dominio retirado y túneles drenados.
  Pico1571897344 bytes,64 PIDs observados, sin OOM bajo la política explícita2GiB.

El campo `host_business_closed:false` fue muestreado dentro de su contexto, antes
de su salida. No demuestra una fuga: el contexto salió después sin excepción,
pero no se registró directamente ese campo tras cerrarlo. Se conserva el valor y
su límite; no se repitió generación para sustituirlo. Los contratos de cierre y
retirada están probados aparte. Esto tampoco certifica inscripción de todo actor
del host ni WebSocket del proveedor a través del CONNECT opaco.

Faltan estado/resume durable, auth administrada, inscripción/orígenes y adopción
productiva. Un ensayo sintético a2GiB no es planificación de capacidad. La suite
global conserva las100 fallas heredadas:1443 pasan,100 fallan y3 se omiten;
599 casos runtime pasan. El wheel extraído pasa20 pruebas dirigidas, sin cuenta.

Evidencia: [ensayo conjunto fallido](../modernization/owned-joint-attempt.json),
[fix y contratos](../modernization/code-host-evidence.json),
[resultados](../modernization/code-host-results.json),
[paquete](../modernization/code-host-packaging.json),
[segundo intento y límite](../modernization/owned-joint-host-v2.json),
[tercer intento e informe persistido](../modernization/owned-joint-host-v3.json).
