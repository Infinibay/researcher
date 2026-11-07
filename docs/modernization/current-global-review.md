# Verificación global y acción siguiente

La suite común de `9fb873c` terminó en23min46s:2210 casos,2178 aprobados,
31 fallidos y1 error de preparación, sin omisiones. Se ejecutó una vez, en serie,
con red bloqueada por defecto y pruebas vivas excluidas. [Recibo](current-global-results.json).
El turno anterior había producido el commit9fb873c: fue progreso verificable.

| Grupo | Casos | Evidencia y tratamiento |
| --- | ---: | --- |
| Carrera del backup |1| SQLite quitó `source.db-shm` después del inventario y antes de abrirlo. Defecto corregido con cuatro reproducciones reales y comprobación de las filas conservadas;40 casos instalados pasan. |
| Preparación histórica de migraciones |5| Un test borra56 debajo de versiones posteriores; cuatro intentan invertir58 desde59. Las guardas rechazan correctamente esos estados. Preparar prefijos históricos reales; no inventar una inversa59 ni debilitar las guardas. |
| Contrato de estados anterior |24| El helper permite cualquier estado conocido diferente, mientras los tests esperan un flujo más estrecho. Son los mismos24 fallos de la referencia anterior. La API nativa bloquea por separado los cambios genéricos de ciclo de vida. Alinear el contrato administrativo retenido y sus pruebas. |
| Fixture del recorrido de terminal |1| La prueba importa `coordination` desde otra carpeta pero no su dependencia `schema_target`. El recorrido del producto no llegó a ejecutarse. Corregir la composición de fixtures y volver a probarlo. |
| Presupuesto de prueba compuesto |1| El recorrido de desarrollo, captura y dos comprobaciones excedió20s. Las mismas aserciones pasan en23,614s con límite diagnóstico60s. Ajustar sólo el presupuesto acotado de esa prueba; no cambiar los límites del producto ni ocultar su resultado original. |

La [corrección del backup](backup-sidecar-results.json) reconoce archivos temporales
por su base SQLite verificada antes de consultar metadatos. Un archivo común con
sufijo parecido sigue siendo dato del usuario. Su desaparición impide publicar
una copia completa. Se probaron las carreras tanto en `source.db` como en una base
anidada, antes del `stat` y antes de la inspección de cabecera.

**La suite global no está verde.** No se volvió a ejecutar completa después del
arreglo; el resultado original y las pruebas dirigidas se conservan por separado.
Los30 casos fallidos restantes y el error de fixture requieren resolución antes
de aprobar ese control. DD081 mantiene su trabajo concreto para la pasada final,
según la política de completar primero las capacidades principales.

De los100 fallos antiguos,75 ya no se recopilan,1 pasa y24 siguen fallando. Que una
prueba haya sido retirada junto al motor anterior no demuestra que su sustituto
cumpla todos sus requisitos. La cobertura nueva se examina por sus propios casos.

Los ensayos más lentos duraron75,932s,61,159s y35,627s; sus identificadores figuran
en el recibo. La duración global incluye ensayos reales de procesos, Git, TLS y
SQLite con datos sintéticos, además de tests pequeños. No se confunde ese tiempo
con trabajo de implementación ni se atribuye todo a una única causa.

Ruff mantiene347 hallazgos y ESLint9 errores en el corte global. Las ubicaciones
están en [current-global-lint.json](current-global-lint.json), DD080. El arreglo
de backup tiene12 avisos en sus tres archivos, conservados en su propio recibo.

El siguiente bloque principal es la evaluación de contexto y comunicación:
`evals/context_alignment/` sigue pendiente, igual que la comparación de resultados
con modelos y la observación humana. También falta el comando `test:e2e`
unificado; los ensayos individuales no aceptan las12 páginas. Los43 escenarios
amplios siguen abiertos. Datos reales, recuperación más amplia, seguridad y
aceptación integral mantienen su alcance.
