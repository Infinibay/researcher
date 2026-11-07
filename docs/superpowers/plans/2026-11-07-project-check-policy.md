# Política de comprobaciones por proyecto — brecha E11

Inicio del bloque E09–E12: 2026-11-07 18:39:36 UTC.

La aceptación distingue resultados de CI, pero aplica una única regla de
reconocimiento de pruebas ausentes/omitidas. E11 exige una política explícita por
proyecto. Se añade esa capacidad; el pulido se registra para la pasada final.

Decisión: el propietario elige entre exigir pruebas ejecutadas sin fallos ni
omisiones, o permitir ausencia/omisiones con reconocimiento explícito. Ninguna
opción permite fallos, infraestructura incierta o revisión rechazada. Un comando
exitoso no demuestra pruebas ejecutadas. Sin decisión de proyecto, se bloquean
aceptaciones nuevas; no se inventa una elección durante la migración.

La política tiene revisión y recibo inmutable, se modifica sólo por la API del
propietario con CSRF y se muestra en Código entregado. La aceptación nueva incluye
la revisión observada y guarda la política aplicada. Cambios posteriores afectan
aceptaciones nuevas, no reescriben decisiones históricas. Los recibos antiguos y
sus reintentos mantienen sus bytes e identidad; la vigencia de código/revisión
sigue comprobándose. Guardar una política no inicia ejecución ni publicación.

- [x] Migración incremental y política con revisión/recibo y recuperación.
- [x] Vinculación de aceptación, preservación histórica y clasificación precisa.
- [x] Control web con explicación, revisión observada y recuperación de respuesta perdida.
- [x] Pruebas de alcance, concurrencia lógica, fallos, historial y autorización.
- [x] Verificación de paquete instalado y frontend; evidencia y tablero actualizados.

No implica aceptación completa de E09/E10/E12, de páginas ni del producto.

Cierre E11: 2026-11-07 19:02:40 UTC. Ver evidencia en
[project-check-policy-review.md](../../modernization/project-check-policy-review.md).
E09/E10/E12 siguen abiertos; no es cierre del plan completo.
