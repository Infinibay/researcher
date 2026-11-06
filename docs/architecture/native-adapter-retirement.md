# Retirada de adaptadores de ejecución y documentos

Se eliminan 23 módulos de `backend/tools/shell`, `git`, `rag` y `data`, además de
`web/code_docs_search.py` y su configuración CrewAI. El único consumidor productivo
fuera del conjunto era el export de documentación del paquete web, ya retirado.
El [inventario](../modernization/native-adapters-retirement.json) conserva rutas,
hashes anteriores, imports externos y pruebas antiguas retiradas.

## Destino y cambios de contrato

| Capacidad | Destino nativo y límite relevante |
| --- | --- |
| Comandos y Python | Jobs con dueño mediante `researcher_command_start/python/read/cancel`; argumentos acotados, claves de operación, salida recuperable y cierre físico. El intérprete estándar no hereda paquetes ni credenciales. No se conserva el fallback que ejecutaba directamente en el host si faltaba el sandbox. |
| Git status/diff | Lecturas dentro del workspace admitido y vistas del candidato identificado; no «último diff» global ni repositorio inferido por cwd del servidor. |
| Branch/commit | La copia de desarrollo y el capturador del candidato conservan base/HEAD/contexto. El host publica el candidato aceptado sobre el ref elegido; un comando privado no acepta la tarea. |
| Push/PR/merge | Publicación del host con aceptación vigente sobre SHA exacto, identidad remota y reconciliación del recibo. Los modelos no reciben los wrappers ni credenciales de publicación. Se conservan las vistas históricas de Git. |
| PDF, CSV, DOCX, JSON y XML | Captura canónica de fuentes/adjuntos, parser acotado, estructura y locators, búsqueda literal o semántica local y cita exacta. El documento fuente y sus límites permanecen visibles. |
| Búsqueda semántica de directorios | Ken para código/documentos del workspace; para evidencias, listar y capturar las fuentes seleccionadas y consultar cada snapshot. No se promete una consulta única sobre una carpeta arbitraria no capturada ni cobertura de archivos omitidos. |
| Documentación de bibliotecas | Context7 opcional con coste separado y documentación externa capturada; búsqueda semántica sobre el snapshot local. No se conserva la generación/embedding ocultos de CrewAI ni su fallback de `default` a OpenAI. |
| SQL genérico del modelo | Retirado deliberadamente. Las lecturas del producto usan contratos tipados por alcance; el agente no puede consultar `env_vars` u otras tablas mediante un SELECT arbitrario. Los operadores conservan sus herramientas administrativas fuera del catálogo del modelo. |

Los contratos vigentes están en [comandos](host-analysis-tools.md),
[operaciones de código](native-code-operations.md), [publicación](code-publication.md),
[publicación remota](remote-publication.md), [documentos estructurados](structured-sources.md),
[artículos](paper-capture.md), [recuperación semántica](semantic-source-retrieval.md)
y [Context7](context7-sources.md). La compatibilidad conserva capacidades mediante
esos recorridos; no conserva imports, schemas o condiciones inseguras de los
wrappers eliminados.

## Evidencia y datos conservados

Las pruebas nativas existentes se ejecutan con los adaptadores retirados: salida
y cancelación de jobs, refactor en copia privada, publicación exacta después de
revisión/aceptación, Git remoto y recibos PR/merge, parsers de formatos, recuperación
semántica multilingüe con assets locales y captura/citas de documentación.
La prueba nueva verifica las ubicaciones importables en fuente y paquete instalado.
Los modelos y servicios remotos se controlan donde lo indica cada ensayo; esto no
demuestra calidad de investigación o disponibilidad de un proveedor real.

Se retiran cinco archivos con 46 funciones de prueba específicas de wrappers.
No se contabilizan como fallos arreglados. Se conservan las pruebas del runtime y
los servicios actuales, incluidas las denegaciones de efectos Git antiguos.

No se cambian bases de datos, referencias, documentos, informes, registros Git,
assets ni carpetas Chroma existentes. Las colecciones antiguas no se adoptan como
fuentes verificadas ni se borran. Su exportación/migración —incluido un caso donde
sólo quede el caché y falte el documento original— sigue siendo parte principal
del bloque de migraciones/restore; no se declara resuelta mediante esta retirada.

## Trabajo principal que continúa

La familia web restante conserva el control antiguo de `robots.txt` y frecuencia;
esas políticas todavía deben integrarse en el transporte nativo antes de cerrar
su retirada. No son un detalle de estilo. Continúan también los adaptadores de
tareas, comunicación, proyecto y conocimiento, la persistencia/contexto compartidos
y las cinco dependencias explícitas del extra `legacy`. La evaluación humana y
científica y los escenarios integrales permanecen abiertos.

## Resultado de esta verificación

[Fuente](../modernization/native-adapters-results.json):132pruebas pasan y una
falla;[wheel instalado](../modernization/native-adapters-packaging.json):107pasan
y la misma falla, sin omisiones. Es la aserción de versión54 frente a55 en el
arranque de publicación; las comprobaciones previas de intención inmutable y
estado original pasan. No se cambian test ni migraciones en esta entrega.
La auditoría separada verifica730fuentes del wheel y211imports del entorno,
sin librerías legacy instaladas. Su alcance no equivale al mapa dinámico completo
de imports durante las pruebas; el informe explica la recuperación de evidencia.
[Docstrings](../modernization/native-adapters-docstrings.json): una función nueva
y los dos módulos afectados documentados. Los dos avisos de estilo del export web
siguen enDD048. Ningún ensayo nuevo realiza llamadas a modelos/proveedores reales.
