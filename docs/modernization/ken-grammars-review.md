# Ken analiza llamadores sin descargar durante la ejecución

Desde `a6855c4`: **03:58:40–04:24:03 UTC, 25 min 23 s hasta verificar**.
Documentación/checkpoint posteriores excluidos. El worker publicado vuelve a
encontrar llamadores Python y pruebas con contenido `ok:true`, sin abrir su red
ni usar otro turno de la suscripción. **3/12 páginas y41/43 escenarios** sin cambios.

## Cambio y contrato

Una preparación explícita verifica el archivo público Linux x86_64 de
tree-sitter-language-pack1.22.1:23031807bytes, SHA-256
`4ad211e4a265be2106909ef9db4ccdc706e557436a446fbc10afbf23d668a2a5`.
Extrae372bibliotecas,521163488bytes, en `share/researcher-ken-cache` dentro de
la instalación confiable de Ken. No añade rutas al archivo de recursos del host.
El caché y su manifiesto pertenecen al mismo límite de confianza que el ejecutable;
no se acepta un manifiesto del código del proyecto. El wheel no incluye esos binarios.

`KenInstallation.inspect` exige la versión fijada del loader, verifica todos los
archivos declarados y conserva la huella del manifiesto. El lanzamiento comprueba
esa huella otra vez antes de crear estado de la fuente. Ken encuentra las gramáticas
por su caché dentro del montaje existente de herramientas, de sólo lectura; el
worker sigue sin red y sin credenciales. El broker registra huella y código del
nuevo helper; la admisión nativa exige la preparación cerrada con esa misma identidad.
Un recibo antiguo sin esa identidad no acredita la capacidad nueva ni se reescribe.

La preparación verifica el archivo antes de crear destino y conserva cualquier
destino existente inválido. No descarga, reemplaza ni repara de manera implícita.
El operador descarga el recurso público antes del comando explícito. El preflight
comprueba integridad de bytes, no comprensión del código ni corrección de372lenguajes.

Además, `KenTools` responde a tests+compact/evidence indicando cómo corregir los
argumentos. No envía esa combinación ni la sustituye por una llamada automática.
Los argumentos válidos y los resultados del servidor mantienen su tratamiento.
La eficacia de ese mensaje en otra generación no se declara probada.

## Evidencia que distingue resultados

- RED→GREEN del caché: el proceso intentaba leer `/tmp/cache/marker`; ahora lee el
  recurso confiable y una escritura se rechaza. Faltantes, corrupción del mismo
  tamaño, symlink, versión de manifiesto incorrecta y cambio coherente posterior a
  la inspección se rechazan antes de crear `.ken`. Las fixtures son inertes y no
  prueban que una biblioteca sintética analice código.
- Dos RED→GREEN de argumentos: compact/evidence para tests produce un error útil
  sin envío ni reintento. Una llamada posterior explícita con argumentos válidos
  se transmite una sola vez.
- **92 casos fuente y los mismos92instalados pasan**, cero omisiones;42,003s en
  el entorno no editable,238módulos backend importados exclusivamente desde él.
- Ken publicado real: preparación0; nueve loaders cargan dentro de otro namespace
  de red. MCP encuentra `summarize` y `test_order` como llamadores de
  `list_observations`; `unrelated` tiene cero llamadores y `test_observations.py`
  aparece por import y nombre. Son dos archivos sintéticos, no una auditoría de
  cualquier repositorio. El proceso original termina con SIGTERM observado(-15).
  Los archivos fuente conservan sus bytes.

Un segundo ensayo usa **el perfil real del broker**, con sus gates, seccomp y
cgroup de2GiB, y el Ken publicado instalado. Repite los resultados positivo,
negativo y de pruebas; ambos manifiestos conservan la misma huella de gramáticas
y el hash del helper nuevo. Pico observado1393745920bytes, cero OOM; ambos peers
Ken y sus operaciones cerrados, grant retirado y dominio eliminado. Usa génesis
sintética del formato de autoridad, no acredita inscripción de un host arbitrario.
Los placeholders nativo/negocio nunca se liberaron: después de comprobar cierre
físico se cerraron como `never_released`, y se canceló/retiró sólo ese contexto
sintético mediante APIs normales. Cero despachos/inicios nativos, cero peers abiertos;
no se tocó el proyecto fallido original. [Recibo del perfil](ken-grammars-broker-results.json).

La preparación real utiliza embeddings locales. **Cero turnos generativos** no
significa cero modelos cargados. No hubo cuenta nueva, hijas ejecutadas, cambio de
la fuente original del plan aceptado, push, merge ni despliegue.

## Fallos conservados y alcance restante

La primera preparación rechazó `libtree_sitter_TSQL.so`: el nombre real tiene
mayúsculas. No publicó destino; se ajustó la validación de basename y el archivo
fijado pasó. Al ampliar tests,14casos detectaron otro consumidor de la identidad:
`broker_inference._prepared` aún comparaba el recibo anterior. Se corrigió su
comparación, sin relajar el requisito de preparación, y los92casos pasan.

La primera comparación de contenido incluyó por error el seed opcional de desarrollo
`backend/db/seeds/dev_data.sql`, fuera del package_data declarado. El shell continuó
a la instalación pese a esa aserción. Se comprobó después el inventario declarado
completo y una verificación independiente instalada: **679Python/SQL**,362productivos,
coinciden. No se presenta aquella comprobación fallida como verde. `uv pip check`
pasa. Rueda limpia sdist→wheel, SHA en el recibo;26definiciones documentadas en inglés.

Ruff conserva11avisos en la selección, incluidos los heredados: DD131 y anteriores.
La comprobación de vigencia de prompts detecta **65revisiones desactualizadas de85**
en316archivos; no son65textos necesariamente defectuosos ni65fallos de modelo.
Hay20vigentes y0sin revisión previa. Las huellas anteriores no se renuevan a ciegas;
la revalidación estática sobre el árbol final sigue como gate pendiente. Este bloque
revisa explícitamente el nuevo mensaje correctivo y sus límites, sin atribuir
eficacia generativa a esa revisión. No hay nueva suite global verde.

La contención AuthorityBusy original continúa sin reproducir/corregir. Proyectos,
U08/C10, comprensión humana y las otras páginas mantienen sus propios pendientes.
Siguiente capacidad: continuar la aceptación integral de páginas; detalles secundarios
y gates globales después de las capacidades mayores.

[Resultados y límites](ken-grammars-results.json),
[paquete instalado](ken-grammars-packaging.json),
[MCP real](ken-grammars-mcp-evidence.json),
[loaders](ken-grammars-parser-evidence.json),
[docstrings](ken-grammars-docstrings.json),
[Ruff](ken-grammars-lint.json),
[preparación del host](../architecture/native-host-installation.md).
