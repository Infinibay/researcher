# Aceptación conjunta del motor: E01–E06

**E01–E06 quedan comprobados** para los contratos descritos abajo. El plan completo
sigue abierto. Basee9120e8; bloque **2026-11-07 18:21:28–18:35:37 UTC**,
**14 min 09 s hasta validar**; documentación/checkpoint posteriores excluidos.
Se sustituyen pendientes antiguos de cobertura por evidencia actual. No se
interpreta una lista de archivos históricos como prueba de aceptación.

| Escenario original | Resultado comprobado | Evidencia actual |
| --- | --- | --- |
| E01: resultados cruzados entre ejecuciones | Dos fuentes Git y dos intentos/proyectos editan value.py de forma distinta; captura concurrente y lectura inversa desde conexiones independientes retienen diff, workspace, actor, intento y proyecto originales. Editar después la copia del autor no cambia el candidato; una lectura desde otro proyecto falla. La revisión congela la identidad del candidato. | Nuevo test_engine_boundaries; test_code_candidate, test_code_candidate_state, test_code_review_state. |
| E02: texto blocked/exhausted o rechazo convertido en éxito | Una respuesta nativa completed con texto blocked/exhausted/invalid sigue siendo sólo propuesta needs_review: tarea incompleta, cero aceptaciones y un intento. Los resultados de fallo/interrupción son estados distintos; aceptación de código/investigación exige evidencia y decisión independientes. Rechazo no se transforma en aprobación ni dispara rework sin límite. | Tres casos nuevos de texto libre; test_coordination, test_runtime_service, test_result_acceptance, test_code_acceptance; aceptación E07 conserva rechazo sin rework. |
| E03: Stop da por cerrado trabajo que sigue vivo | Intención/fence y revocación preceden a la afirmación de cierre. El Stop real del proyecto devuelve primero closure=unconfirmed y sólo termina tras retirar su dominio. Reindexación Ken y CI lentos drenan su dueño; el CI no escribe su archivo tardío. Parser/trabajadores registrados mantienen el intento incierto hasta cerrar. Fallo de join/timeout no se convierte en prueba de terminación. | test_owned_project_stop; tres integraciones de test_development_session; test_runtime_service, test_run_recovery y test_parser_process. El refresco acotado compartido fue probado en E08 con los mismos fuentes. |
| E04: resultado tardío tras vencimiento/corrección | Lease vencida no renueva ni escribe; expire exige reconciliación antes de otra toma de propiedad. Stop/corrección invalidan autoridad antes de aceptar. Un aviso tardío se conserva una sola vez con su intento original, sin restaurar permisos ni aceptar tarea; checks que terminan tras corrección quedan como historia. | test_coordination, test_code_candidate_state, test_code_review_state y test_check_result_after_context_correction_is_retained_without_approval. |
| E05: reinicio pierde trabajo/preguntas/correcciones | Un coordinador nuevo conserva simultáneamente solicitud en cola, pregunta pendiente y corrección atribuida. La pregunta se reconcilia y responde sin reanudar su hilo antiguo. Recuperar el recibo original tampoco arranca trabajo. Sólo el comando explícito request_start inicia la solicitud corregida original; repetirlo no duplica. Reservas inciertas permanecen. | Nuevo test_engine_restart_context; test_admission_binding, test_run_recovery, test_runtime_service y evidencia de presupuesto de E08. |
| E06: efecto aplicado y respuesta/checkpoint perdidos | Operación/recibo estable preceden al efecto. Una publicación Git real aplica el commit y pierde su retorno: un observador nuevo recupera el marcador sin segundo write ni turno. Push remoto real a repo bare conserva recibo aun si se mueve después el destino. PR/merge con respuesta perdida recuperan marcador original sin otro POST; ausencia remota sigue incierta. Fuentes/hallazgos conservan el mismo recibo tras repetición. | test_owned_publication, test_remote_publication, test_remote_recovery, test_publication_recovery, test_forgejo_publication, test_persistence. |

## Comprobaciones y alcance

Desde fuente pasan los cinco casos nuevos: uno de candidatos homónimos, tres de
texto libre y uno de reinicio conjunto. El primer ensayo de reinicio esperaba que
repetir submit arrancase la cola; falló correctamente. Se leyó el contrato y se
corrigió el ensayo: submit recupera recibo; retry_start expresa nueva intención de
arrancar. El caso final verifica ambos caminos y el replay del mismo comando.
No se cambió producto para satisfacer esa expectativa incorrecta.

Primera selección instalada: **203pases,0fallos,0omisiones** en168,001s,
648archivos Python/SQL coincidentes,344productivos,265módulos desde el paquete.
Después se añadió el caso conjunto de reinicio. Selección final: **20pases,0fallos,
0omisiones** en12,621s,649archivos coincidentes,344productivos,214módulos.
Hay **219casos distintos** entre ambas corridas; cuatro se solapan. No son219casos
ejecutados en la segunda corrida ni una suite global nueva.

Todos los fuentes Python/SQL de producto y los ensayos anteriores son idénticos
entre ambos wheels. La comparación inicial de todos los archivos detectó que la
extensión C recompilada difería; no se afirmó igualdad binaria completa. Tras
retirar únicamente información de depuración y .note.gnu.build-id con objcopy,
los bytes restantes coinciden. El recibo conserva esa diferencia y el SHA256
normalizado. Las garantías de la corrida amplia se reutilizan sobre código de
runtime idéntico, no sobre una sustitución no verificada.

Siete definiciones Python nuevas tienen docstrings ingleses; ambos módulos están
documentados. El inventario de prompts sigue válido:302archivos,85revisados,
0pendientes. No se modificó backend de producto ni frontend, no se repitió build
web/navegador y no se acepta una página por estas pruebas. Cero turnos reales.

[Primera corrida](engine-boundaries-packaging.json),
[corrida final](engine-boundaries-final-packaging.json),
[comparación de artefactos](engine-boundaries-artifact-comparison.json),
[resultados](engine-boundaries-results.json), [docstrings](engine-boundaries-docstrings.json).

## Límites preservados

La prueba nueva de candidatos usa Git/SQLite reales y prueba de cierre del
controlador sintética y explícita; la propiedad física se comprueba por separado
con el broker/kernel reales. No demuestra dos modelos ejecutándose a la vez:
la concesión global actual serializa su dominio. La lectura concurrente de dos
candidatos es independiente de ese límite de ejecución.

Los ensayos nativos usan generación/Ken controlados. PR/HTTP usa transporte del
proveedor controlado; Git sí aplica efectos reales a repositorios temporales.
No se afirma aceptación en una cuenta externa ni calidad de modelos/revisores.
Stop prueba cierre del trabajo local poseído y conserva incertidumbre en efectos
remotos; no certifica cómputo oculto del proveedor ni anula un efecto ya aplicado.
El caso de reinicio reabre la base bajo nuevo coordinador y usa identidades
nativas históricas sintéticas; no simula una caída eléctrica del host. Las
obligaciones de operación/reboot/restauración del plan conservan sus pruebas y
límites propios. Tampoco es evaluación humana ni aceptación global de interfaz.

La suite global histórica con fallos sigue visible. E09–E12, comunicación, datos,
interfaz, dependencias/distribución y la revisión completa permanecen en alcance.
