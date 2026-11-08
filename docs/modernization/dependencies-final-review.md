# Dependencias: instalación limpia y declaraciones actuales

Base14abcd2,11:35:21–11:54:49UTC,**19min28s hasta verificar**; documentación/
checkpoint posteriores excluidos. Revisión sobre árbol final de este corte;
no se confunde una instalación preparada con el lock que habría usado un host nuevo.

## Instalación de Ken corregida

El lock resolvía tree-sitter-language-pack1.25.0, mientras KenInstallation.inspect
exige1.22.1 para su pareja verificada wrapper/parsers. Una instalación nueva con
hashes reprodujo el rechazo aun con require_grammars=False. La instalación previa
que pasó92casos tenía la pareja preparada; esos resultados no demuestran que aquel
lock instalara un host utilizable.

requirements-ken.in declara ahora1.22.1. El lock regenerado conserva las otras71
versiones. Se sincronizó el entorno nuevoPython3.13.18con hashes:72paquetes
compatibles, admisión de preparación correcta y372recursos del archivo exacto
1.22.1verificados. Preparación offline0,9parsers reales, llamador positivo/
negativo ydescubrimiento de tests porMCP pasan. Fuente intacta;MCP-15cerrado,
0turnos generativos (sí recuperación local). No se amplió la admisión a wrappers
arbitrarios ni se cambió la versión publicada deKen.

## Seguridad: los avisos permanecen visibles

Auditoría pip-audit2.10.1/npm nueva ysin paquetes omitidos:

| Ámbito | Resultado |
| --- | --- |
| Producto uv.lock | 85versiones, sin avisos conocidos |
| Frontend actual | Sin avisos conocidos |
| Dos launchers MCP | 30versiones cada uno, sin avisos conocidos |
| Ken/ONNX1.20.1 | 19entradas/12IDs; también tras corregir el lock de grammars |
| ExportadorChroma1.5.9 | 5entradas/4IDs |

La auditoría inicial termina2por una licencia ausente, además de los avisos.
Tras corregir la declaración, el inventario de licencias termina0; el escaneo
focalizado deKen termina1por vulnerabilidades. **No auditoría global verde.**
Los demás recibos se reutilizan porque sus hashes de lock no cambiaron.

PyPI sigue publicandoKen0.18.0con ONNX==1.20.1; ONNXactual1.23.2 yChromaactual1.5.9.
[Ken](https://pypi.org/pypi/ken-rank/json), [ONNX](https://pypi.org/pypi/onnx/json),
[Chroma](https://pypi.org/pypi/chromadb/json). Se reutiliza la
[prueba previa de variante coherente](ken-onnx-candidate-review.md): no otra
instalación forzada incompatible, modificación del hermano o publicación.
Su adopción sigue pendiente.

Una revisión independiente verificó el sdist publicado porSHAy los consumidores
ONNXload/check/save: no es dependencia sin uso. Artefactos porFD/sha, caché offline,
red privada yfuente readonly restringen sustitución por el workspace; no cierran
los12IDs por sí solos. En Chroma la neutralización de constructores precede a la
importación yno se abren sus APIsHTTP. Siguen pendientes alcance por aviso,
límites agregados memoria/procesos del lector yla superficieSQLiteen el padre.
No se afirma explotación; tampoco seguridad universal por aislamiento.

## Licencias y límites de distribución

Inventario actual: **164versionesPython/528entradasfrontend**,0ausencias,
0errores y0revisiones pendientes. Son113entradas frontend más que el inventario
previo; sus resultados antiguos no se sobrescriben. Khroma2.1.0carece de campo
license, pero su archivo npm exacto contieneMITcompleto. Se verificó integridad,
identidad, SHA del archivo yde package/license, incluido copyright. El auditor
reutiliza la misma revisión explícita ligada a bytes que usabaPython; no infiere
compatibilidad de una cadena o un nombre.2RED→14pruebas pasan,0skip. El MITdeKhroma
ya está en el aviso del build actual; no se recompilófrontend para un inventario.

El código del producto/wheel no cambia. El enlace de avisos pasa al inventario
nuevo; verificar esos bytes en los artefactos finales sigue como gate de empaque.
No se repiten49backend/77UI/164contratos por cambios de locks/scripts/documentación.
Módulos yfunciones Python relevantes documentados. Python3.13aquí sólo acredita
Ken, no la matriz deResearcher; esa es la siguiente tarea principal de distribución.
Los textos pendientes del bundle, activos nativos/fuentes/modelos ycompatibilidad
legal concreta permanecen separados del inventario de declaraciones.

**42/43escenarios,11/12páginas.** No se cierraU08niProyectos/AuthorityBusy.
Después: adopción coherenteONNXyseguridad residual, matriz/distribución,
prompts/inversas71/global/revisiónfinal. Detalles al final.
[Resultados](dependencies-final-results.json),
[evidencia](dependencies-final-evidence/initial-summary.json),
[licencias actuales](dependencies-final-evidence/licenses.json).


## Revisión por aviso sobre el uso real

La [matriz independiente](dependency-advisory-dispositions-2026-11-08.md) contrasta
los 12 IDs únicos de ONNX y los cuatro de Chroma con fuentes primarias. Distingue
APIs utilizadas, APIs no observadas en las fuentes verificadas y mitigaciones
reales, con sus desconocidos. La actualización coherente de Ken o una decisión
explícita sobre el riesgo residual siguen pendientes. Esta revisión no cambia el
pin, no repite el candidato probado ni acepta el riesgo por el propietario.
