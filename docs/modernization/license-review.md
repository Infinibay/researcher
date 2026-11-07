# Licencias: inventario y avisos de los paquetes

Bloque del 7 de noviembre de 2026, **10:16:47–10:30:25 UTC**, **13 min 38 s** hasta
el corte de validación. Base `3cbffff`. Se resuelven las 139 declaraciones ausentes
del inventario previo; no se declara aprobada toda la distribución.

| Evidencia | Resultado |
| --- | --- |
| Python | 164 versiones: 162 declaraciones y 2 revisiones de archivos exactos |
| npm | 415 entradas: 278 declaraciones del lock y 137 recuperadas de archivos verificados |
| Ausencias/errores/revisiones pendientes del inventario | 0/0/0 |
| Pruebas del auditor | 12 aprobadas, 0 fallidas, 0 omitidas |
| Web | Build correcto; 93 entradas de avisos, 91 con texto y 2 pendientes |
| Wheel/sdist | Licencia y documento de avisos incluidos y comparados con la fuente |
| Instalación aislada del wheel | Metadata AGPL-3.0-or-later y ambos archivos verificados |

La licencia original y su copyright permanecen byte por byte iguales. README
aclara los nombres Researcher/Infinibay; Python y npm declaran la licencia existente.
El mínimo de setuptools pasa a 77.0.3 para soportar la metadata indicada por la
[guía oficial de empaquetado](https://packaging.python.org/en/latest/guides/writing-pyproject-toml/#license-and-license-files).
Los 608 archivos Python/SQL del backend coinciden con el wheel anterior. No se
reinstala el entorno productivo ni se modifica su lógica.

## Evidencia frente a inferencia

La ausencia en el lock no significaba ausencia de licencia. Para npm se descarga
el archivo fijado, se comprueba su integridad y la identidad nombre/versión y se
lee el manifiesto sin instalarlo, extraer rutas ni ejecutar código. Para Python
se conservan los textos de las distribuciones fuente, su SHA256 y una revisión
expresa también ligada al hash del archivo de licencia:
`py-rust-stemmers 0.1.8` contiene MIT; `sentencepiece 0.2.1` contiene Apache 2.0.
Esas revisiones no certifican cada componente nativo ni cada wheel de plataforma.

El auditor falla ante datos ausentes, inaccesibles o sin revisar. Se añade
`--licenses-only` para comprobar licencias sin repetir los escaneos de avisos.
El workflow existente ya usa `--licenses` y recibirá el mismo comportamiento
cuando se integre; no se ejecutó GitHub Actions.

El [colector incorporado de Vite](https://vite.dev/config/build-options#build-license)
genera `assets/THIRD_PARTY_LICENSES.md`; la compilación conserva además la licencia
original en `assets/PROJECT_LICENSE.txt`. Ambas rutas retornan 200 y los bytes
esperados mediante ASGI TestClient, sin iniciar almacenamiento, modelos ni el
ciclo de vida del servidor. No se presenta ese ensayo como navegación o servidor
real. Se documenta la advertencia existente de Starlette/httpx.

## Límites y detalles posteriores

Dos paquetes MIT, `rehype-katex 7.0.1` y `remark-math 6.0.0`, no incluyen el texto
en su archivo npm. El colector genera sus entradas con declaración pero sin texto.
Se registra la incorporación de los textos oficiales para después de las tareas
gruesas, antes de distribuir: DD091. Cuatro avisos Ruff quedan en DD090.
No se amplía ahora el bloque con un recolector legal propio.

Las obligaciones de la distribución concreta —componentes nativos, fuentes
tipográficas, modelos, fuentes correspondientes y alternativas de licencia—
siguen descritas en [los avisos](../../THIRD_PARTY_NOTICES.md). Una lista de
declaraciones no demuestra compatibilidad. No se cambian pins, avisos de seguridad
ni límites de recursos de Ken/Chroma; no hubo nuevas inferencias, suite global,
push, merge o despliegue.

Se conservan los resultados iniciales: cuatro casos nuevos fallaron antes del
lector; nueve entradas `@types` no usaban la raíz de tar `package/`, defecto
reproducido y corregido; el primer verificador instalado resolvió el egg-info de
la fuente por su cwd y pasó al usar Python aislado. No se ocultan esos intentos.
16 definiciones Python y ambos módulos tienen docstrings; el hook de Vite tiene
JSDoc. [Resultados](license-results.json), [inventario](license-inventory.json),
[revisiones exactas](license-artifact-reviews.json), [estilo](license-lint.json).

Siguiente tarea principal: entrega de planificación dentro de su presupuesto
anterior. Siguen 43 escenarios amplios abiertos y 0/12 páginas totalmente aceptadas.
