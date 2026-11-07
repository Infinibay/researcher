# Aceptación del motor E01–E06

Base e9120e8; inicio18:21:28UTC. Mantener todos los requisitos del plan31octubre.

- [x] E01: dos ejecuciones con archivos homónimos; candidatos físicos aislados,
  lectura inversa/concurrente y revisión vinculadas al proyecto/intento original.
- [x] E02: agotado, bloqueado, inválido o rechazado no completa trabajo; resultado
  nativo y aceptación de tarea siguen separados, sin éxito por texto libre.
- [x] E03: Stop no afirma cierre por timeout/join; generación, refresco/espera,
  herramientas locales y comprobaciones lentas conservan dueño hasta cierre.
- [x] E04: vencimiento/corrección/Stop invalidan autoridad antes de aceptar resultados
  tardíos; conservar observaciones históricas sin promoverlas a resultado vigente.
- [x] E05: reiniciar conserva intención, preguntas/correcciones y reservas; distinguir
  reconciliación, nueva solicitud explícita y prohibición de replay nativo incierto.
- [x] E06: identidad/recibo antes del efecto; pérdida tras commit se observa sin
  repetir publicación/PR/comentario o turno completo. Ausencia remota sigue incierta.
- [x] Ejecutar selección instalada relevante y actualizar cobertura sólo para los
  requisitos probados. Reusar recibos válidos; resolver únicamente brechas funcionales.

Nuevas pruebas limitadas a garantías aún débiles: captura real de dos candidatos
homónimos con lecturas invertidas y texto libre de resultado sin completar tareas.
No ampliar infraestructura por detalles; persistirlos para el final.

Verificados E01–E06:219casos instalados distintos en dos corridas, con comparación
de código/artefactos; cinco casos nuevos pasan.14min09s hasta validar.
[Alcance y límites](../../modernization/engine-boundaries-review.md). El plan sigue activo.
