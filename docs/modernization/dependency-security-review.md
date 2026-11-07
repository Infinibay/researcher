# Seguridad y dependencias: revisión del 7 de noviembre de 2026

Se corrigieron cuatro dependencias y se comprobaron sus consumidores. La auditoría
del producto principal queda sin avisos conocidos en este corte. **La seguridad
integral sigue abierta:** Ken/ONNX, el exportador histórico Chroma, la revisión de
licencias y los demás escenarios de aislamiento no están aceptados por esta entrega.
Base de trabajo: `77d79c0`; sin push, merge, despliegue ni llamadas al modelo.

## Cambios y evidencia

| Dependencia | Antes → ahora | Motivo y comprobación |
| --- | --- | --- |
| KaTeX | 0.16.47 → 0.19.1 | Reproducción con `Object.prototype.trust` ya contaminado: aparecía una imagen externa; ahora se rechaza y la fórmula válida sigue renderizando. |
| minimatch | 10.2.6 → 11.0.5 | Corrección del aviso de amplificación de patrones; árbol npm, ejecución de ESLint y build comprobados. |
| postcss-selector-parser | 6.0.10 → 6.1.5 | Actualización limitada al consumidor `@tailwindcss/typography`; conserva la rama mayor6 y el build funciona. |
| filelock | 3.32.7 → 4.2.9 | La prueba con `huggingface_hub.utils.WeakFileLock` truncaba un archivo existente; ahora conserva bytes/permisos. También se comprueban exclusión entre procesos y liberación posterior. |

Las fuentes publicadas describen las condiciones y versiones corregidas:
[KaTeX](https://github.com/KaTeX/KaTeX/security/advisories/GHSA-238p-pmpm-9mq7),
[minimatch](https://github.com/advisories/GHSA-g3hv-75wg-m249),
[selector parser](https://github.com/advisories/GHSA-rj75-hqrm-r3gf),
[filelock](https://github.com/tox-dev/filelock/security/advisories/GHSA-69hj-f68j-2879).

La reproducción de KaTeX **no demuestra una vía de contaminación del prototipo
en Researcher**: prepara esa condición y comprueba el componente posterior.
El primer fixture no permitía escribir la propiedad y causaba un error de KaTeX;
ese primer resultado positivo no se cuenta como reproducción. Se conserva junto
al fallo válido posterior y al resultado corregido. El aviso de selector parser
concierne a selectores no confiables en determinadas condiciones; no se atribuye
automáticamente una exposición HTTP al compilador de estilos.

Los overrides de npm se limitan a estos consumidores; `npm ls --all` termina sin
errores. Rehype/micromark todavía declaran la familia0.16 de KaTeX: la compatibilidad
observada cubre el renderizador real y sus pruebas, no todos los usos posibles.
El mínimo `filelock>=4.2.1,<5` también se declara en el paquete, de modo que una
instalación sin `uv.lock` reciba esa restricción. Lock y requirements regenerados
son consistentes. El wheel nuevo fue instalado y su metadata comprobada.

## Auditorías y límites de los conteos

Antes: npm comunicaba16 entradas afectadas, correspondientes a3 avisos y sus
consumidores; el entorno Python principal comunicaba13 entradas de filelock.
Después se auditaron todos los locks comprometidos, incluidos paquetes opcionales
y variantes de plataforma, sin instalar esas dependencias para inspeccionarlas:

| Alcance | Paquetes/versiones examinados | Resultado |
| --- | ---: | --- |
| `uv.lock` | 85 | Sin avisos conocidos |
| `frontend/package-lock.json` | npm audit completo | Sin avisos conocidos |
| `requirements-ken.txt` | 72 | ONNX1.20.1:19 entradas,12 IDs distintos |
| Exportador Chroma aislado | 87 | Chroma1.5.9:5 entradas,4 IDs distintos |
| Launcher MCP Researcher | 30 | Sin avisos conocidos |
| Launcher MCP Infinibay | 30 | Sin avisos conocidos |

El proceso termina con **código1 por hallazgos**, no con éxito. No hay paquetes
omitidos en esta auditoría de locks. El sondeo anterior del entorno Ken instalado
incluía además el paquete local Researcher, que PyPI no pudo auditar; no se utiliza
ese sondeo para afirmar cobertura completa. Los IDs distintos no equivalen
necesariamente a vulnerabilidades independientes: pueden existir alias/duplicados.
[Resultados, hashes y alcance](dependency-audit-results.json).

**Ken:** la distribución publicada `ken-rank==0.18.0` exige `onnx==1.20.1`.
Actualizar ONNX por la fuerza dejaría de satisfacer esa metadata. La fuente local
de Ken utiliza `onnx.load`, `check_model` y `save` al preparar activos; por ello no
se descarta toda la familia de avisos como código sin uso. El aviso sobre
[datos externos y enlaces](https://github.com/onnx/onnx/security/advisories/GHSA-p433-9wv8-28xj)
ilustra una condición que requiere comprobar procedencia y límites del modelo.
Falta probar compatibilidad con una versión corregida y resolver el pin mediante
una distribución coherente de Ken, manteniendo esa revisión separada. No se
modificó el repositorio hermano, su entorno ni se publicó una versión.

**Chroma:** el exportador aislado utiliza `PersistentClient` sobre una copia y
`get_collection(..., embedding_function=None)`. No inicia un servidor HTTP ni
genera embeddings. Los cuatro avisos publicados describen rutas de servidor,
configuración de modelos y autorización; no ofrecen una versión corregida en
este corte ([ejemplo de configuración](https://github.com/advisories/GHSA-f4j7-r4q5-qw2c),
[actualización de colección](https://github.com/advisories/GHSA-36p7-vc44-83pf),
[tenant](https://github.com/advisories/GHSA-2wm9-hf6c-p5cr),
[RBAC](https://github.com/advisories/GHSA-xph7-9rjv-w5fr)).
Eso no prueba que el lector de almacenamiento quede fuera de alcance. Sigue
pendiente revisar la carga de configuración persistida y el aislamiento del
exportador antes de aceptar datos históricos reales. No se ignoran estos avisos.

## Comprobaciones ejecutadas

- 36 pruebas Python de dependencias, acceso local y ciclo de WebSocket pasan.
- 5 pruebas del auditor pasan, incluidas herramienta ausente, proceso fallido,
  paquete omitido, aviso conocido y respuesta de error del registro.
- 33 pruebas desde el wheel instalado, fuera del checkout, pasan;604 fuentes
  Python/SQL coinciden,324 productivas.202 módulos backend proceden de la
  instalación. [Recibo](security-packaging.json).
- 136 contratos frontend y10 pruebas DOM pasan; build y árbol de dependencias
  pasan. ESLint conserva9 errores; no se declara lint limpio.
- HTTP/WS real pasa: anónimo rechazado, Host/Origin controlados, bearer de
  herramientas sin acceso de propietario, CSRF requerido, cierre1008 al salir y
  cookie revocada. Se conserva la página de eventos recibida. Servicio original
  cerrado con salida-15 y cero inferencias. El primer intento del harness falló
  por esperar `pong` antes de la página inicial; se adaptó al contrato de eventos,
  sin debilitar las comprobaciones de acceso ni aceptar eventos de otro proyecto.
- 16 definiciones Python relevantes tienen docstrings. Ruff conserva3 avisos
  de estilo. [Inventario](dependency-security-docstrings.json).

Estos conjuntos se solapan: no se suman como casos únicos del producto. No se
repitió la suite global: sigue la referencia documentada con fallos abiertos.
No hay aceptación general de páginas, comunicación o seguridad a partir de estos
resultados. [Resumen verificable](dependency-security-results.json).

## Mantenimiento preparado

[`audit_dependencies.py`](../../scripts/audit_dependencies.py) conserva resultados
por alcance y termina con1 ante avisos,2 ante error/omisión. Ejecuta los demás
alcances aunque uno falle. No utiliza `--fix`, exclusiones de avisos ni credenciales
de la suscripción. Se puede repetir con un directorio de salida nuevo:

```sh
python3 scripts/audit_dependencies.py --output /tmp/researcher-dependencies-new --licenses
```

Requiere Python3.12+, uv y npm en PATH. `pip-audit` queda fijado a2.10.1.
El [workflow](../../.github/workflows/dependency-audit.yml) prepara ejecución semanal,
manual y para PRs de dependencias; conserva artefactos incluso al fallar, utiliza
permisos de lectura y acciones fijadas a commits de releases comprobados.
Dependabot separa familias de API, caché de modelos, React, Markdown, estilos y
herramientas; Ken y las acciones tienen sus propias entradas. Los scripts PEP723
se auditan, pero su actualización sigue siendo explícita con `uv lock --script`.
El soporte de gestores se contrastó con
[GitHub](https://docs.github.com/en/code-security/reference/supply-chain-security/supported-ecosystems-and-repositories).

YAML, pins, `uv lock --check` y exportación reproducible comprobados localmente.
No había actionlint disponible y no se ejecutó GitHub Actions. **La configuración
todavía no está publicada/activa**. [Validación](dependency-workflow-validation.json).

El inventario conserva164 versiones Python y415 entradas npm.139 entradas carecen
de declaración en las fuentes inspeccionadas (2 Python,137 npm); ninguna consulta
falló. Una declaración ausente no prueba ausencia de licencia, y una declaración
presente no demuestra compatibilidad. Falta revisar archivos LICENSE/distribuciones
y obligaciones del conjunto. [Inventario](dependency-license-inventory.json).
Las declaraciones largas se abrevian de forma explícita, conservando longitud,
hash y URL de procedencia; el recibo completo está en el directorio privado del ensayo.

Ken/ONNX, Chroma y licencias son pendientes principales. Los3 avisos Ruff y9 ESLint
se conservan en DD083 para después de las capacidades principales.
