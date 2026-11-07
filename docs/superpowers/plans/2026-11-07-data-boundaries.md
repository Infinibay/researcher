# Datos y persistencia — D01–D04

Inicio real: 2026-11-07 19:56:34 UTC. Base: 6b2f938.

- [x] Contrastar plan, rutas activas y pruebas existentes; conservar cadena 18–65.
- [x] Reproducir integridad/readiness, bloqueo del loop, evento duplicado y retry posterior a commit.
- [x] Corregir las fronteras demostradas conservando los controles nativos tipados.
- [x] Validar migraciones, API, transacciones y cancelación desde el paquete instalado.
- [x] Registrar alcance, límites, docstrings, tiempos y lista actualizada.

Las rutas antiguas de CRUD siguen vivas, aunque la ejecución antigua se retiró.
La prueba debe cruzar SQLite y HTTP reales. Un escritor ocupado no equivale a
cancelación confirmada: Stop debe seguir atendible y mostrar cierre real después.
No repetir efectos tras un commit incierto. No aceptar D01–D04 por un control estrecho.
Los detalles visuales y las demás obligaciones del plan permanecen separados.

D01–D04 comprobados con el alcance de [la matriz](../../modernization/data-boundaries-review.md).
26 de 43 escenarios completos; 17 abiertos. Siguiente D05–D09; no iniciado.
