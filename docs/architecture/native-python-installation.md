# Instalación Python del runtime nativo

La instalación usa20dependencias directas para API, CLI/TUI, MCP, captura/formatos
y recuperación semántica local. Las herramientas antiguas y sus cinco bibliotecas
CrewAI, crewai-tools, LiteLLM, Ollama y Chroma están retiradas. No existe el extra
`legacy`; tampoco se conservan los extras de proveedor `anthropic`/`gemini` ni
las seis distribuciones tree-sitter. El modelo pertenece al runtime nativo y su
[configuración explícita](model-configuration.md).

```bash
uv sync --locked
uv run --locked pytest backend/tests/api/test_startup.py backend/tests/cli/test_bootstrap.py
```

`uv.lock` pasa de177a86entradas al retirar dependencias opcionales y transitivas,
sin añadir paquetes ni cambiar versiones retenidas. El export de producción
`requirements.txt` conserva sus bytes: la instalación predeterminada ya omitía
esos extras. El número de entradas multiplataforma del lock no equivale al número
de distribuciones instaladas en un host. Se conserva Python3.12–3.13; ampliar el
rango requiere verificar el runtime y el kernel, no sólo resolver dependencias.

No se borran tablas, vectores, índices Chroma ni archivos históricos. Los datos
retenidos se consultan mediante interfaces nativas con procedencia explícita.
La restauración/importación de material que sólo existe en archivos o en un
índice antiguo sigue como tarea principal; retirar una librería no la ejecuta.
Las referencias de schema se conservan como documentación, no como clases
importables capaces de crear otro motor de agentes.

La evidencia de este corte, incluidos los fallos heredados que siguen abiertos,
está en [retirada de dependencias](native-legacy-dependencies.md),
[resultados actuales](../modernization/legacy-dependencies-results.json) y
[paquete instalado](../modernization/legacy-dependencies-packaging.json).

## Ensayo histórico anterior a la retirada de herramientas

Este apartado conserva la evidencia del corte inicial; no describe el paquete actual.
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

El estado vigente está en el [tablero de ejecución](../modernization/execution-dashboard.md).
La retirada de paquetes no demuestra cierre de procesos viejos, recuperación de
datos reales, aceptación de la interfaz ni eficacia de modelos/comunicación.
Los servicios/CLI heredados, operación, historial y presupuestos, migración/restore
y la evaluación integral conservan sus entregas principales.

[Evidencia del ensayo inicial](../modernization/native-installation-results.json),
[paquete inicial](../modernization/native-installation-packaging.json),
[console scripts iniciales](../modernization/native-installation-console.json).
