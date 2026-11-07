# Política de comprobaciones por proyecto

Cada proyecto necesita una decisión explícita del propietario antes de una
**nueva aceptación de código**. La migración 65 crea las tablas sin elegir por él.
Una revisión positiva del agente y un turno terminado no sustituyen esa decisión.

| Política | Requisito |
| --- | --- |
| `require_tests` | Al menos una prueba ejecutada, comprobaciones satisfactorias y ninguna omisión. Un comando genérico exitoso por sí solo no acredita pruebas. |
| `allow_missing` | Las pruebas ausentes o parcialmente/completamente omitidas quedan visibles; cada aceptación exige reconocer esos límites. |

Ambas bloquean resultados fallidos, invalidados, pendientes o sin evidencia
verificable. Ninguna permite saltarse una revisión rechazada, el contexto vigente
ni la identidad del candidato. No se ejecutan pruebas al cambiar la política.

El propietario elige en **Tareas → Código entregado → Qué pruebas exige este
proyecto**. El formulario explica el caso de un comando exitoso sin pruebas y
congela la revisión que se consultó al abrirlo. Guarda la solicitud en el navegador
antes de enviarla. Si se pierde la respuesta, «Consultar recibo de la política»
recupera esa decisión mediante GET; no repite el cambio. Un conflicto requiere
cerrar la decisión rechazada y consultar la revisión nueva.

La API usa `GET/POST /api/projects/{id}/check-policy` y
`GET /api/projects/{id}/check-policy/changes/{operation_key}`. Requiere sesión del
propietario y CSRF en POST; los tokens de herramientas no dan acceso. Funciona sin
runtime/modelo configurado. Una transacción serializa revisión, política, recibo
y evento. El mismo identificador y cuerpo recuperan el recibo original; cambiar
el cuerpo o usar una revisión vieja no sobrescribe decisiones posteriores.

La aceptación nueva envía `check_policy_revision` además de las huellas del
candidato y su revisión independiente. Guarda la política aplicada en su recibo.
Los cambios de política afectan decisiones nuevas, no reescriben las antiguas.
La vigencia del candidato, contexto, revisión y cierre se sigue verificando.

Las aceptaciones anteriores a esta migración mantienen sus recibos e identidad
de reintento. Se presentan como anteriores a las políticas de proyecto; no se les
inventa una elección retrospectiva. Una solicitud antigua que nunca se aceptó
necesita una nueva observación con la política vigente. La inversa de migración
sólo permite volver a 64 antes de registrar decisiones; no borra historia usada.

`ProjectCheckPolicies` es el adaptador de persistencia; `assess_code_checks` decide
sobre la evidencia ya capturada y `CodeAcceptances` vincula la decisión al código.
No se añade otro motor de ejecución ni capacidad de política para los agentes.
