# Publicación remota de una versión aceptada

La publicación local y su recuperación están conectadas. El protocolo remoto de
push, PR y merge también dispone de [admisión durable y transporte propio
configurable](remote-runtime.md): Git/HTTP del host con etapas originales y cierre
local comprobado. La integración TLS usa Git real y una API Forgejo controlada.
Faltan recuperación remota, controles de Tareas, comprobación con Forgejo real y
cutover legacy; el recorrido completo sigue en curso.

## Push de versión exacta y recibo

`RemoteRepository` fija API HTTPS configurada, ID numérico del repositorio,
`owner/name` y URL de clone completa. Un repositorio recreado con el mismo nombre
no hereda la identidad anterior. El executor debe comprobar esa identidad a través
del puerto confiable antes y después del efecto; la URL no constituye por sí sola
una identidad inmutable del servidor.

`RemotePushIntent` conserva operación original, destino y SHA previo observado,
base/head exactos. La huella del recibo incluye todos esos campos y la identidad
remota. Una transacción `git push --atomic` envía el SHA exacto a la rama destino
y a `refs/heads/researcher-receipts/<huella>`. Cada referencia tiene su lease
explícito; la operación no fuerza un destino distinto del observado. Una rama
movida entre preflight y receive-pack rechaza el conjunto, sin recibo parcial.
Si el servidor no soporta push atómico, no existe fallback a dos escrituras.

Se comprueban los bytes/Git del candidato, la ascendencia base → head y los
metadatos originales. Coincidencia de archivos no prueba ascendencia: un commit
sin relación con la base se rechaza antes del efecto. Se conserva
el checkout abierto del origen. No se llama a hooks del repositorio ni se acepta
un remote con credenciales embebidas; el transporte propio suministra
la credencial fuera de argumentos, manifiestos y contexto del modelo.

Ejemplo: se acepta A y se pide crear `reviewed-change`. El remoto recibe A y su
recibo juntos. Se pierde la respuesta y otra persona mueve después esa rama a B.
La recuperación conserva «esta operación publicó A; ahora la rama apunta a B».
No convierte esa diferencia en permiso para volver a hacer push.

## Incertidumbre remota frente al cierre local

Cerrar el cliente no prueba que el servidor dejó de trabajar. Después de enviar
una petición, el servidor puede confirmarla aunque el cliente ya no esté vivo.
Por eso `reconcile_remote_push` permite únicamente lecturas, requiere el cierre
local original y adopta evidencia positiva del recibo. Si no aparece el recibo,
el resultado sigue siendo **incierto**. No se reutiliza la conclusión local
`not_applied` basándose solamente en una consulta remota vacía.

El controlador guarda la intención y la etapa antes de liberar el
primer efecto. Un retry de la solicitud HTTP del usuario recuperará ese registro;
no podrá llamar otra vez al método de push porque aún no haya visto un recibo.

## PR ligado a la intención original

`ForgejoPublicationClient` usa HTTPX asíncrono con origen de credenciales fijo,
timeouts, respuesta JSON completa acotada, sin redirects, proxy del entorno ni
reintentos automáticos. Los errores no incluyen respuestas crudas ni secretos.
El cliente anterior basado en curl permanece como consumidor legacy pendiente de
cutover; este módulo no afirma haberlo retirado.

`RemotePullIntent` fija repositorio, ramas, SHA de head/base, título y descripción.
La descripción conserva un marcador ligado a la intención completa. Antes de
crear se busca ese marcador en páginas completas y acotadas; un presupuesto
agotado no se etiqueta como ausencia. Una coincidencia debe conservar repositorio,
ramas y cuerpo originales. Varias coincidencias son ambiguas y bloquean adopción.

La creación comprueba las ramas y registra la observación devuelta. Si head/base
cambian después, la existencia del PR se conserva como historia, separada de
`candidate_current`. Un PR creado no constituye aprobación de esa otra versión.
Después de una respuesta perdida, la reconciliación sólo busca el PR original;
si no aparece todavía, conserva incertidumbre sin emitir otro POST.

## Merge: contrato del proveedor antes de habilitar el efecto

El [Swagger oficial de Forgejo](https://code.forgejo.org/swagger.v1.json), consultado
el 2026-11-05, define `head_commit_id` para el merge y no define un guard de SHA
previo de la rama base en `MergePullRequestOption`. Un GET previo seguido de POST
no constituye CAS de la base. La [documentación oficial de API](https://forgejo.codeberg.page/docs/v17.0/user/api/)
explica cómo consultar el contrato servido por cada instancia.

El protocolo implementado usa Git para avanzar la rama base desde el SHA exacto
observado hasta el head aceptado, con CAS, recibo atómico y ascendencia comprobada.
No genera otro merge commit ni acepta automáticamente una base nueva. Después,
`record_exact_merge` registra ese hecho en Forgejo con `Do=manually-merged`,
`MergeCommitID` y `head_commit_id` exactos, sin force_merge, borrado de rama ni
merge diferido. La prueba del recibo Git original es precondición; una etiqueta
de PR o un nombre de rama no la sustituye.

Son dos efectos separados. Perder la respuesta del registro de merge exige
consultar el PR y su merge SHA original; no permite repetir el Git CAS ni el POST.
Si el destino cambia después, se conserva el efecto histórico. Branch protection
se debe cumplir durante el push real; no se modifica ni se omite para lograr el
merge. Un servidor que sólo permita merge a través de su API requiere una
capacidad probada equivalente antes de habilitar este recorrido.
El transporte inicial usa HTTPS; la configuración TLS del Forgejo antiguo deberá
formar parte de la migración antes de habilitarlo.

## Qué pasaría si…

| Situación | Resultado del protocolo actual |
| --- | --- |
| Cambia el destino después del preflight | El CAS de receive-pack rechaza el push atómico; prueba con Git real. |
| Se confirma el push y se pierde la respuesta | Se conserva incertidumbre; lectura del recibo recupera historia sin otro push. |
| No aparece el recibo tras cerrar el cliente | Sigue incierto: falta prueba de finalización remota. |
| La rama cambia después de publicar | Efecto histórico y destino actual quedan separados. |
| Se recrea el repo en la misma URL | ID numérico distinto no puede adoptar el recibo original. La permanencia de esa identidad durante el request es una obligación del transporte/servidor que falta verificar. |
| HTTP redirige fuera del servidor configurado | No se sigue el redirect ni se reenvía la credencial. |
| Se crea un PR y se pierde la respuesta | El mismo marcador permite recuperarlo con GET; no se repite POST. |
| Head/base cambian en un PR existente | Se conserva existencia; `candidate_current` queda falso. |
| La consulta de PR alcanza el presupuesto | Error de lectura incompleta; no habilita creación por supuesta ausencia. |
| La API sólo protege el head al mergear | Git CAS protege el destino; el API registra después el mismo SHA ya aplicado. Transporte propio conectado; compatibilidad con instancia real pendiente. |
| Los archivos coinciden pero el head tiene historia ajena | Se rechaza antes del push: se exige ascendencia, además de diff/bytes. |
| Se pierde el POST del registro de merge | Se consulta el merge SHA del PR original; no se repiten ni Git ni POST. |

## Evidencia y siguiente integración

[Resultados](../modernization/remote-publication-results.json) y
[paquete](../modernization/remote-publication-packaging.json). Git real contra
remotos bare temporales prueba transferencia y transacción; el executor de
subprocesos es exclusivo de tests y no constituye autoridad productiva ni prueba
HTTPS. Los tests HTTP usan transporte controlado, no un servidor del usuario ni
una credencial real. No hubo inferencia ni efectos remotos reales del usuario.
[Docstrings en inglés](../modernization/remote-publication-docstrings.json).

La identidad de operación del puerto debe proceder del ID durable global del
efecto del host. La clave de una acción del usuario, cuyo ámbito es proyecto/tarea,
se conserva aparte; no se debe reutilizar sin ese ámbito como identidad remota.

La admisión durable ya liga la solicitud a la aceptación y publicación local.
Siguiente trabajo principal: recuperación remota con un observador nuevo de sólo
lectura, controles de Tareas y comprobación con una instancia real de Forgejo bajo
sus protecciones. El [transporte propio](remote-runtime.md) ya aplica credencial
del host, HTTPS, autoridad y cierre; no se expone como herramienta libre del
agente ni como subprocess sin broker. El objetivo completo y los escenarios
E06/E10/E12 continúan en curso.
