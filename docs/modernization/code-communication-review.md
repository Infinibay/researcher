# Comunicación al revisar código: un par real

Dos revisores reales por suscripción OpenAI, `gpt-6.1-sol/low` y Ken publicado,
revisaron un candidato sintético que descarta observaciones iguales a cero.
Ambos registraron **needs_revision**, con propuesta confirmada sobre el sujeto
exacto, citas de archivo verificadas y explicación española de entrada/salida.
[Recibos](code-communication-live.json), [verificación](code-communication-results.json),
[explicaciones y propuestas](code-communication-responses.json).

## Autor controlado y presupuesto declarado

El autor **no genera con un modelo**. Un transporte de protocolo controlado lee
el código con Ken, escribe los bytes registrados mediante la herramienta Python,
espera el cierre del comando y termina. Conserva entrada original, propiedad de
procesos, captura Git y cierre productivos; no se fabrican filas de candidatos o
peers. Se reutiliza el fixture de protocolo, cambiando sólo la rama de edición
y el modelo anunciado. Ese nombre anunciado no demuestra inferencia real.

El revisor usa después el runtime real, su propio intento y herramientas readonly.
El sistema necesita **dos reservas internas por instalación**, autor controlado y
revisor; sólo el segundo consume una generación de la suscripción. La configuración
privada del fixture declara dos reservas y414000 tokens de capacidad contable:
64000 para el transporte y350000 para el revisor. El archivo original de recursos
permanece igual. El turno generativo conserva sus techos de180s/20herramientas/
350000tokens, o límites menores. El consumo del transporte queda **desconocido**
en sus recibos; no se convierte en cero observado ni gasto de la cuenta.

El [registro corregido](code-communication-evidence/registration.json) congela el
contrato, tests, políticas, transporte y siete archivos del evaluador antes de
ver resultados. Base `5878edf`; hashes identifican los cambios aún sin commit.
Un revisor con contexto limpio contrastó el montaje antes de implementarlo.

## Fallo previo conservado

El primer transporte terminó con `RpcDisconnected` tras una única petición Ken,
antes de admitir un revisor real. Los23peers y grants cerraron. Se conservan
[registro, fuente anterior y resultado](code-communication-evidence/failed-controlled-transport/).
Su fila de intento sigue como estaba, con reserva desconocida; no se reescribe
para aparentar un cierre de producto que no ocurrió.

La función decodificaba cualquier respuesta como JSON, aunque Ken devuelve texto.
Una prueba sin cuenta reproduce `JSONDecodeError`; ahora sólo se decodifican los
recibos de comandos. Es un defecto concreto verificado del evaluador, consistente
con el primer corte; el stderr original del hijo no se conservó, por lo que la
atribución causal del corte queda identificada como inferencia. La
[enmienda](code-communication-evidence/transport-correction-amendment.json) precede
los dos resultados reales. No se repitió una respuesta generativa fallida.

## Controles y lectura

Se comprobó igualdad byte a byte de la entrada original del autor, la petición,
base, árbol y diff, requisitos y checks. La captura productiva crea otro commit
por su hora: únicamente se normalizan el head y hashes de sujeto derivados,
después de comprobar que cada referencia coincide con su recibo original. Se
conservan [paquetes, entradas y diffs originales](code-communication-evidence/).
Catálogo, contexto sustantivo y selección de modelo/esfuerzo coinciden.

| Brazo | Veredicto | Tokens observados del revisor | Tramo autor+revisor |
| --- | --- | ---: | ---: |
| Histórico | needs_revision, confirmado | 148544 | 106,182s |
| Actual, catálogo9 | needs_revision, confirmado | 179488 | 111,300s |

Total: **328032 tokens observados de los revisores y217,482s** de los tramos
corregidos. Preparación inicial, el intento fallido y análisis/documentación fuera
de ese total; no es facturación ni cuota restante.

La lectura del implementador, **sin cegamiento**, encuentra apoyo para los cuatro
criterios registrados. Los rastros contienen paquete, entrada original y diff
completos; Ken devuelve el archivo requerido. Cada cita propuesta coincide con
hash, línea y texto del candidato. Ambos ejecutaron cuatro pruebas: dos pasan y
dos fallan por los ceros, con código1, output completo y cierre físico. Las
explicaciones conservan esa diferencia; no presentan como probada una corrección
que sólo proponen.

| Entrada de ejemplo | Contrato pedido | Candidato revisado |
| --- | --- | --- |
| 0 y10 | Media5 | 10 |
| 0 y0 | Media0 | None |
| Sin registros | None | None |

Cero representa una observación; ausencia de registros representa una colección
vacía. Los ejemplos anteriores son fixtures, no datos empíricos ni un defecto
descubierto en una función productiva de Researcher.

Original y tests sin cambios;79/83peers por instalación cerrados, cero grants,
servicios-15. Ningún candidato aceptado o publicado. Confirmar la revisión valida
su vinculación y procedencia; **no equivale a aprobar el candidato**.

## Alcance restante

Cuatro RED iniciales y **40 comprobaciones dirigidas finales pasan**. Inventario
85/322vigente, cero revisiones pendientes; módulos y funciones nuevos documentados
en inglés. Un aviso Ruff I001 de imports se difiere en DD153. Sin nueva política
productiva, instalación de wheel o suite global.

Con este par se completa la comparación acotada de los tres perfiles que faltaban.
Los siete perfiles activos tienen observaciones comparativas de distintos cortes;
no significa que todos se hayan reevaluado con catálogo9 ni acredita superioridad,
representatividad o comprensión humana. U08, comunicación en UI durante espera/
error/parcial y observación/adaptación humana siguen abiertos. No repetir pares
pagados para obtener respuestas más elegantes.
