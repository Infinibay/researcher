# Dos fallos Ken con causas distintas

Desde `dac2b4e`, **03:53:45–03:57:01 UTC: 3 min 16 s hasta verificar**.
Cero turnos de modelo; no se modifica el código del Ken propio ni el intento original.

## Búsqueda de pruebas: combinación de argumentos no admitida

La llamada original pidió `scope="tests", response_format="compact"`. En Ken
0.18.0, `ken/mcp/server.py:1028–1030` rechaza esa combinación antes de llegar a
`find_tests`: compact/evidence está limitado a files/symbols. No faltaba una prueba
en el proyecto ni falló su ejecución. La llamada de análisis no era válida.

En el MCP aislado real se reproduce `isError=true` con esos argumentos. Quitando
`response_format`, el mismo proyecto responde con `isError=false`. Por separado,
`ken.search.find_tests` sobre una copia SQLite en memoria devuelve
`{"ok":true,"path":"observations.py","tests":[]}`. Eso describe el índice de
esta fuente de un solo archivo; no acredita exhaustividad para otros proyectos.

No hace falta convertir artificialmente un error en éxito. La continuación debe
orientar al agente hacia los argumentos admitidos y comprobar sus resultados.

## Llamadores: gramática ausente dentro del entorno aislado

El MCP devuelve `isError=false`, pero el contenido dice `ok:false` y
`language not parseable: python`. En ese mismo montaje sin red, el cargador real
`tree_sitter_language_pack.get_language("python")` lanza `DownloadError`: intenta
obtener el manifiesto de parsers de la release v1.22.1 y no puede resolver la red.

`ken.structure.get_parser` captura esa excepción y guarda `None`; `supports`
devuelve falso y `ken.codeflow` produce el resultado observado. El worker monta
modelos de embeddings preparados, pero fija una caché temporal distinta y no
provisiona gramáticas de tree-sitter. Es una omisión comprobada de preparación,
no una prueba de que Python sea incompatible. Versiones instaladas:
Ken0.18.0, tree-sitter0.25.2 y language-pack1.22.1.

La documentación del proveedor contempla [descargar parsers antes del uso sin
red](https://docs.tree-sitter-language-pack.xberg.io/getting-started/quickstart/)
y [configurar su caché](https://github.com/xberg-io/tree-sitter-language-pack/blob/main/docs-site/src/content/docs/reference/api-python.md).
Esas páginas pueden cambiar; la causa anterior se acredita con la versión instalada
y su excepción real, no con la documentación de main.

## Alcance, ensayos conservados y siguiente trabajo

Se copia el archivo sintético y meta.json, y se hace un backup SQLite del índice;
`worker_process` monta esa copia con el aislamiento existente. No se abre otro
turno nativo ni se reinscribe la instalación original. Los procesos diagnósticos
originales terminan; no son una prueba de una reparación en el producto instalado.
El primer auxiliar olvidó meta.json: MCP rechazó la copia antes de inicializarse.
Ese fallo del auxiliar se conserva y no se cuenta como fallo del producto.

**Reparación pendiente:** preparar gramáticas verificadas fuera de la ejecución,
montarlas de sólo lectura y comprobar análisis real con red deshabilitada. Añadir
preflight para impedir que una instalación con capacidad estructural ausente pase
por lista. No habilitar red al peer ni parchear la librería hermana para resolverlo.
Separar la orientación de argumentos del arreglo de preparación; pruebas mixtas
de código y llamadores, no sólo `supports=True`.

Este diagnóstico no acepta Proyectos ni resuelve AuthorityBusy/U08/C10.
Se mantienen **3/12 páginas y41/43 escenarios amplios**.
[Recibo](ken-capability-diagnosis-results.json),
[MCP original](ken-capability-mcp-diagnosis.json),
[excepción del cargador](ken-capability-parser-diagnosis.json),
[plan de reparación](../superpowers/plans/2026-11-08-ken-offline-capabilities.md).
