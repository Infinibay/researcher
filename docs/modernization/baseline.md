# Línea base de implementación

Se reconstruyó el commit `e7b5719` en un worktree aislado y Python 3.12.9. El entorno original sólo tenía Python 3.14, incompatible con el requisito `<3.14` de la versión de CrewAI instalada; no se modificó ese Python del sistema.

La suite original terminó con **710 aprobados, 100 fallidos y 3 omitidos** (813 casos, 106,19 segundos). Se quitaron credenciales de proveedores del entorno del proceso y se bloquearon sockets externos, permitiendo sockets Unix para asyncio. Los casos fallidos están enumerados en [baseline-results.json](baseline-results.json); no se consideraron aprobados ni se omitieron para obtener una suite verde.

El frontend original compila con Node **24.22.2**, descargado de nodejs.org y verificado contra su SHA-256 publicado. `npm ci --ignore-scripts` utilizó el lock existente. `npm run build` terminó correctamente, con advertencia por un chunk principal de 1.397,48 kB (405,56 kB gzip). No es una verificación visual ni de accesibilidad.

No se iniciaron agentes, contenedores, Forgejo ni servidores contra datos del usuario. No se consumió la suscripción. Las carreras, Stop y efectos duplicados aún necesitan las reproducciones controladas y pruebas de integración del plan.

## Contratos de instalación

- `pyproject.toml` declara dependencias directas y herramientas de desarrollo; `uv.lock` fija la resolución.
- `requirements.txt` es un export para consumidores existentes, generado con `uv export --locked --no-dev --no-emit-project --format requirements-txt --output-file requirements.txt`.
- `uv sync --locked` instala el entorno del proyecto. `uv run --locked pytest` ejecuta por defecto con red externa bloqueada y timeout por test. Las pruebas vivas se identificarán y ejecutarán por separado, con límites de uso.
- El servidor MCP independiente usa metadata de script y `scripts/infinibay_mcp_server.py.lock`: `uv run --locked --script scripts/infinibay_mcp_server.py`. FastMCP 4 requiere MCP 2, mientras CrewAI 1.15 requiere MCP 1; separarlos evita acoplar dos protocolos incompatibles durante la transición.
- La política de `uv --locked` se contrastó con su [documentación oficial](https://docs.astral.sh/uv/concepts/projects/sync/); la versión de Node pertenece a una rama [LTS mantenida](https://nodejs.org/en/about/previous-releases).

## Primer cambio de datos

La ruta se resuelve una sola vez mediante `backend.config.paths`: override explícito/`INFINIBAY_DB`, alias `INFINIBAY_DB_PATH`, base existente conocida o `.data/infinibay.db` para un workspace nuevo. Varias bases distintas requieren elección explícita; no se mueven ni fusionan automáticamente. CLI, settings, conexiones y script de inicio comparten el contrato.

Un workspace vacío recibe el schema completo en una transacción. Una base con tablas y sin historial reconocido se rechaza sin sobrescribirla. Los errores de migración se propagan al arranque en lugar de quedar sólo en logs. Esto todavía no demuestra todas las migraciones históricas ni backup/restore del plan.
