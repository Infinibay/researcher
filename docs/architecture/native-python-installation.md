# Instalación Python del runtime nativo

La instalación predeterminada usa20dependencias directas para la API, CLI/TUI,
protocolo MCP, captura/formatos y recuperación semántica local. CrewAI,
crewai-tools, LiteLLM, Ollama, Chroma y seis distribuciones tree-sitter pertenecen
al extra opcional `legacy`, que conserva lectores históricos de schemas/herramientas.
No habilita otro backend de inferencia. Se retiraron los extras de proveedor
`anthropic`/`gemini`; el modelo real pertenece a la configuración nativa existente.

```bash
uv sync --locked
uv run --locked pytest backend/tests/api/test_startup.py backend/tests/cli/test_bootstrap.py
```

El corpus histórico aún requiere migración y lectores opcionales:

```bash
uv sync --locked --extra legacy
```

No es el comando para activar agentes ni recuperar sesiones antiguas. El acceso
explícito a esos lectores valida sus dependencias antes de importar frameworks;
si faltan, devuelve `LegacyMetadataUnavailable` con la ruta de inspección opcional.
La base de datos y el catálogo MCP de negocio nativo no cargan esos lectores.
El entorno de desarrollo anterior se conserva para comprobar su compatibilidad.

`uv.lock` mantiene todas las opciones reproducibles, incluso las no instaladas:
188paquetes en el lock no significan188paquetes en la instalación predeterminada.
`requirements.txt` se exporta desde el lock sin extras ni dependencias de desarrollo;
no se mantiene a mano. Las versiones de las dependencias retenidas no cambian en
este corte. Se conserva el rango Python actual; ampliar soporte requiere su matriz
real de runtime/kernel.

## Prueba desde una instalación independiente

Se creó otro venv, no editable, usando el lock sin red y sin alterar `.venv`.
Incluye85distribuciones con las herramientas de pruebas y el proyecto. No está
instalado ninguno de los once paquetes antiguos. Se reinstaló el wheel final sin
cambiar dependencias, se verificaron todos sus archivos de aplicación —incluida
la extensión compilada— y `uv pip check` pasa.

El ensayo se ejecuta con Python `-I`, desde un directorio temporal fuera del
checkout y con configuración pytest separada. Los imports backend vienen del
venv nuevo; el checkout, el site-packages anterior y su configuración pytest no
pueden suministrar las dependencias omitidas. Un pedido explícito de catálogo
histórico falla con el error previsto, conservando la API nativa utilizable.

Los193casos pasan sin omisiones. Incluyen cuatro turnos nativos controlados con
kernel/broker/Git/SQLite reales: investigación con fuente/hallazgo/informe y
cálculo; planificación con requisitos históricos/cita/aceptación sin ejecución de
hijas; optimización con copia privada, candidato, check, revisor distinto y
aceptación. La fuente original se conserva y no se publica ningún cambio. La
política del proceso Codex fijado y la autenticación/renovación/retirada también
se prueban. No se llama a un modelo real ni se evalúa el ranking real de Ken.

Los console scripts instalados muestran ayuda sin activar el backend. La
inicialización explícita crea una base nueva con esquema54 e integridad correcta;
repetirla se rechaza y conserva exactamente los bytes existentes. Eso no prueba
restauración de un despliegue anterior.

## Componentes del host y alcance restante

El wheel Python no instala ni configura por sí solo el binario Codex, su cuenta
de suscripción, Ken publicado en su entorno propio, la delegación cgroup, los
recursos de autoridad o pesos semánticos. Este ensayo usa el mismo host Linux,
un SDK fijado instalado aparte, assets preparados y una fixture Ken controlada.
La instalación real de esos componentes y su evaluación siguen siendo entregas
separadas. Ver [runtime configurado](owned-product-runtime.md).

Los scripts `start.sh`, MCP/Git generales, consumidores legacy y tests antiguos
siguen como migración principal. El corpus global y el resto visual/prompts/modelos/
interacción humana, cierre de proyecto y restore/inversas43–54 siguen abiertos.
Una instalación Python sin frameworks antiguos no demuestra cierre de procesos
viejos no registrados ni aceptación integral del plan.

[Resultados](../modernization/native-installation-results.json),
[paquete y entorno instalado](../modernization/native-installation-packaging.json),
[console scripts](../modernization/native-installation-console.json).
