# Avisos de ONNX y Chroma: rutas utilizadas y límites

Revisión independiente de solo lectura sobre `d278653`, contrastada con fuentes
primarias. El [plan](../superpowers/plans/2026-10-31-actualizacion-proyecto.md)
requiere evaluar cada aviso contra el uso real; no exige demostrar riesgo cero.
Una mitigación documentada tampoco equivale a una corrección ni a aceptación del
riesgo por el propietario.

Los informes actuales contienen **19 entradas y 12 IDs de ONNX**, y **5 entradas
y 4 IDs de Chroma**. Hay entradas repetidas: no se suman como vulnerabilidades
independientes. [Informe ONNX](dependencies-final-evidence/ken-after-lock.json),
[resumen de auditoría](dependencies-final-evidence/initial-summary.json).

## ONNX 1.20.1 en Ken publicado

El sdist verificado de Ken usa `onnx.load`, `check_model` y `save` durante la
preparación del reranker. La dependencia tiene consumidores reales. Los modelos
están fijados y se verifican tamaño y hash antes de montarlos en lectura; el
proyecto no elige esos bytes. Esto restringe la procedencia de las entradas, sin
demostrar que sus metadatos sean seguros.

| IDs del informe | Disparador y evidencia de alcance | Disposición actual |
| --- | --- | --- |
| PYSEC-2026-104, PYSEC-2026-2239, PYSEC-2026-2241 | Lectura de datos externos siguiendo enlaces simbólicos o duros. `onnx.load` sí se ejecuta y carga datos externos por defecto. [Aviso de enlace simbólico](https://github.com/onnx/onnx/security/advisories/GHSA-p433-9wv8-28xj), [segundo caso](https://github.com/onnx/onnx/security/advisories/GHSA-3r9x-f23j-gc73), [enlace duro](https://github.com/onnx/onnx/security/advisories/GHSA-cmw6-hcpp-c6jp). | Procedencia fijada y archivos montados por FD mitigan sustitución por el proyecto. No se inspeccionaron todos los descriptores externos del grafo oficial. Corrección de ONNX pendiente. |
| PYSEC-2026-2240 | `ExternalDataInfo` acepta atributos arbitrarios durante carga externa. [Aviso](https://github.com/onnx/onnx/security/advisories/GHSA-538c-55jv-c5g9). | Hashes y límites del trabajador son mitigaciones; el hash no valida seguridad semántica. Corrección pendiente. |
| PYSEC-2026-103 | `onnx.hub.load(..., silent=True)` evita advertencias de confianza. [Aviso](https://github.com/onnx/onnx/security/advisories/GHSA-hqmj-h5c6-369m). No se encontró esa API en los 361 archivos Python de Ken verificados; la ruta observada usa HuggingFace fijado y trabajador offline. | API no observada en ese recorrido. Revalidar al cambiar preparación o consumidores; no afirmar ausencia global. |
| PYSEC-2026-2689, PYSEC-2026-3587 | Conversión de versiones con modelos malformados. [Adapters](https://github.com/onnx/onnx/security/advisories/GHSA-hwpq-hmq9-wj77), [Gemm](https://github.com/onnx/onnx/security/advisories/GHSA-p893-rvq9-2xf9). Ken compone sobre opset 18; no se encontró conversión en sus fuentes verificadas. | API específica no observada; cobertura transitiva no exhaustiva. Mantener seguimiento de la actualización. |
| CVE-2026-115919, CVE-2026-115920, CVE-2026-115921 | Inferencia de shapes de [RNN/GRU/LSTM](https://github.com/onnx/onnx/security/advisories/GHSA-48m4-24cq-37qf), [ConvTranspose](https://github.com/onnx/onnx/security/advisories/GHSA-6pwm-x34p-fvj2) y [Scan](https://github.com/onnx/onnx/security/advisories/GHSA-m4pr-6v3c-6fgr). Ken llama `check_model` sin `full_check`; ONNX 1.20.1 usa `False` y solo invoca `InferShapes` con ese flag verdadero. [Implementación](https://github.com/onnx/onnx/blob/v1.20.1/onnx/checker.cc). | Distinguir checker e inferencia de shapes. No se encontró `infer_shapes` directo; no es una prueba exhaustiva de dependencias transitivas ni de ONNX Runtime. |
| CVE-2026-115922 | Materialización sub-byte mediante `numpy_helper.to_array` o `ReferenceEvaluator` con dimensiones desproporcionadas. [Aviso](https://github.com/onnx/onnx/security/advisories/GHSA-q69g-f4f5-v8m7). Ken usa `from_array` para pesos FP32; no se encontraron las APIs indicadas. | API específica no observada. Cargar o comprobar por sí solo no reproduce ese disparador. |
| PYSEC-2026-3876 | Escritura externa con carrera de enlaces. [Aviso](https://github.com/onnx/onnx/security/advisories/GHSA-q56x-g2fj-4rj6). Ken guarda en staging nuevo y privado; usa `save_as_external_data=False`. La carga normal materializa y elimina los descriptores externos. [Implementación](https://github.com/onnx/onnx/blob/v1.20.1/onnx/external_data_helper.py). | Revisar carga, composición y guardado como un flujo. El argumento predeterminado por sí solo no excluye tensores todavía marcados como externos. Corrección pendiente. |

La [variante coherente con ONNX 1.23.2](ken-onnx-candidate-review.md) ya tiene
comprobaciones funcionales y auditoría. Esa evidencia se conserva y no se repitió.
El producto todavía admite Ken publicado 0.18.0: esta revisión no adopta la
variante. Las alternativas concretas son una distribución publicada compatible o
integrar deliberadamente la distribución local fijada y su mantenimiento. Ninguna
requiere modificar el checkout hermano ni publicar ahora. Mantener el pin actual
con mitigaciones deja una decisión de riesgo abierta.

## Chroma 1.5.9 en el exportador local

El informe detallado retenido está en
`.researcher/evaluations/dependencies-final-20261108/export_legacy_chroma-py-lock.stdout`.
Chroma está separado del servicio principal. El exportador no inicia un servidor
HTTP; trabaja con una copia elegida por el operador.

| IDs del informe | Disparador y evidencia de alcance | Disposición actual |
| --- | --- | --- |
| PYSEC-2026-311, PYSEC-2026-3814 | Modelo malicioso con `trust_remote_code=true` mediante endpoints de [creación](https://github.com/advisories/GHSA-f4j7-r4q5-qw2c) o [actualización](https://github.com/advisories/GHSA-36p7-vc44-83pf). El exportador neutraliza descriptores de embeddings en una copia desechable antes de importar Chroma y utiliza `embedding_function=None`. La [fuente 1.5.9](https://github.com/chroma-core/chroma/blob/1.5.9/chromadb/api/collection_configuration.py) confirma el constructor y la excepción del descriptor `legacy`. | Mitigación para este formato y lector local. No certifica otros formatos o todos los lectores nativos, ni se aplica a un servidor Chroma. |
| PYSEC-2026-3813, PYSEC-2026-3815 | Alcance de autorización entre [tenants](https://github.com/advisories/GHSA-2wm9-hf6c-p5cr) y [RBAC](https://github.com/advisories/GHSA-xph7-9rjv-w5fr). El lector local no utiliza esos endpoints ni ese proveedor RBAC para separar usuarios remotos. | Función de servidor no utilizada en el recorrido inspeccionado. Tenant/database siguen determinando el contenido exportado; su selección no autoriza la importación posterior. |

Persisten dos límites propios, separados de esos cuatro avisos:

- `snapshot` interpreta SQLite en el padre antes del sandbox. No se ha demostrado
  una explotación; tampoco puede afirmarse que toda interpretación esté aislada.
- El lector tiene tmpfs, plazo y RLIMITs por proceso, pero carece de una frontera
  agregada de memoria/procesos. Afirmar contención frente a ejecución arbitraria
  comprometida requiere esa frontera; los avisos por sí solos no demuestran tal
  compromiso.

Esta revisión deja explícitos uso, mitigaciones y desconocidos. No declara una
auditoría verde, una migración de datos del propietario ni la aceptación de riesgo
en su nombre. La actualización coherente de Ken y las decisiones sobre el lector
siguen abiertas.


## Alcance del hardening del lector

Una segunda revisión del plan distingue requisitos explícitos de mejoras futuras.
D05 protege publicación/persistencia recuperable; D13 limita clientes/broadcast y
exige restore consistente. D12 cubre ejecución de agente/CI. Ninguno prescribe
una nueva cuota agregada para este exportador administrativo opcional, separado
del servidor, ni mover su snapshot SQLite al sandbox. Es una mejora futura DD149,
condicionada a nuevo uso servido, almacenamiento hostil explícito o defecto
concreto. Se conservan todos los límites ya declarados y avisos conocidos. La
confirmación de que no hay historial real elimina una migración del propietario
pendiente; no demuestra seguridad general del lector.

## Comprobación posterior de la publicación

A las 19:00 UTC del 8 de noviembre se consultaron de nuevo los
[metadatos públicos de PyPI](https://pypi.org/pypi/ken-rank/json): la versión sigue
siendo **0.18.0**, con **`onnx==1.20.1`**. El
[recibo acotado](ken-published-recheck-20261108.json) conserva versión, requisito
y hashes de los artefactos anunciados. Esta comprobación no repite instalación,
auditoría ni pruebas de la variante y no adopta ninguna distribución. La elección
anterior sigue pendiente; la publicación no aporta una alternativa nueva que
permita resolverla automáticamente.
