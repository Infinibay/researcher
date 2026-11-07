# Artefactos y Git — D05–D09

Inicio real: 2026-11-07 20:15:44 UTC. Base: adf04f6.

- [x] Contrastar requisitos y rutas actuales; informes ya canónicos en SQLite.
- [x] Reproducir pérdida de bytes al fallar el commit de borrado y carga sin registro tras crash.
- [x] Registrar intención durable de carga/borrado y reconciliar sólo la operación original.
- [x] Conectar historial y recuperación explícita a Archivos; conservar alcance y restos inciertos.
- [x] Validar crash, disco/DB, concurrencia, migración, backup/restore y paquete instalado.
- [ ] Contrastar D06–D09 con evidencia actual y resolver brechas principales.
- [x] Documentar alcance, docstrings, tiempos y lista actualizada.

No eliminar restos inciertos ni crear una carga nueva para ocultar una fallida.
Los lectores/capturas mantienen sus fronteras; la recuperación no inicia inferencia.
Lo fino se registra para después de las capacidades grandes.

D05 verificado el 2026-11-07 a las 20:41:51 UTC (26 min 07 s); documentación y checkpoint
posteriores excluidos. [Matriz y límites](../../modernization/reference-operations-review.md).
D06–D09 siguen pendientes; el siguiente tramo tendrá su inicio real propio.
