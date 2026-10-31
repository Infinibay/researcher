# Decisión: Codex App Server para la migración

Se elige Codex CLI 0.166.0 como runtime de destino de esta implementación,
manteniendo Infinidev como alternativa de adaptador. Es una elección de
integración y control demostrados; no una conclusión estadística sobre calidad,
latencia o coste entre modelos.

Ambos candidatos completaron la pequeña corrección de código del fixture.
Codex tiene evidencia de autenticación mediante suscripción administrada,
identidad nativa, control de turnos y el recorrido de investigación persistido.
La evaluación Infinidev 0.30.0 conservada en `runtime-evaluation.md` encontró
errores del bridge con schemas nullable y no completó los mismos gates de
investigación/control/aislamiento. No se modificó ese proyecto para ocultarlos.

La aplicación conserva operaciones, contexto, evidencia, aceptación y publicación.
Codex conserva inferencia y planificación interna. Ken publicado es obligatorio.
Los diez tools de investigación permanecen en MCP y el host los media como
funciones dinámicas, sin entregar el grant al peer generativo. Esta decisión
cuesta mantener y probar una API experimental fijada del runtime.

La prueba real inicial reveló que desactivar el host de Code Mode inutiliza
las herramientas del modelo elegido. Se corrigió ese requisito y se repitió
el recorrido con evidencia persistida; no se declaró exitosa la primera demo.
La nueva política exige validar configuración efectiva, tools, cierre y límites,
en lugar de inferir esas capacidades de un catálogo de metadatos.

El primer recorrido está conectado a la API autenticada. El reemplazo completo
del engine, herramientas de desarrollo, comunicación entre agentes y preguntas
humanas, Git/review/CI, restauración de datos, clientes, prompts y diseño siguen
pendientes. La ruta vieja no representa una alternativa operativa segura sólo
porque siga importándose. Ver `native-runtime-boundary.md`, las evidencias en
`docs/modernization/` y su matriz de cobertura aún incompleta.
