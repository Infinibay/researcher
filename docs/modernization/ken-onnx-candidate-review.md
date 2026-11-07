# Compatibilidad de Ken con ONNX actualizado

Se comprobó una variante **local y separada** de Ken 0.18.0 con ONNX 1.23.2.
La preparación de modelos y las búsquedas MCP funcionan en dos proyectos nuevos.
Las 71 dependencias instaladas desde PyPI no presentan avisos conocidos en esta
auditoría. **La adopción en el producto sigue pendiente:** su instalación y sus
locks conservan Ken 0.18.0/ONNX 1.20.1. No se publicó ni modificó el repositorio
hermano. Base: `e150d7c`; bloque 13:55:32–14:03:54 UTC del 7 de noviembre,
**8 min 22 s hasta la validación funcional y auditoría**.

## Cambio comprobado

La fuente procede del [sdist publicado de Ken 0.18.0](https://files.pythonhosted.org/packages/0f/43/d9431865f60140629c706523142aeba7444dd54756a57ea2dec1fcf7b865/ken_rank-0.18.0.tar.gz),
SHA-256 `177490d5b3904a3b817fc21e64c088de7db9751ae3afb873f1062990328cc335`.
El [parche](../patches/ken-onnx-1.23.2.patch) cambia únicamente el pin de ONNX y
la versión de Ken a `0.18.0+researcher.1`. Se archiva el `PKG-INFO` generado del
sdist fuera de la copia de trabajo para regenerarlo al construir. Sin ese paso,
la primera compilación conservó metadata 0.18.0 aunque el módulo declaraba la
versión local; se retuvo como evidencia privada y nunca se instaló.

El wheel final, su módulo y su metadata coinciden. Sus **425 archivos de Ken**
coinciden byte a byte con la fuente y la instalación. El resolver mantiene las
otras **70 versiones**; `uv pip check` pasa para los 72 paquetes. No se forzó
ONNX mediante una instalación incompatible con la metadata del paquete.

## Evidencia y alcance

- Dos preparaciones desde estado nuevo, con modelos locales verificados y sin
  red dentro del trabajador. Cada una indexa un archivo y dos propietarios de
  código. El código de `prepare_best` ejecuta el reranker; la preparación desde
  cero pasa por `onnx.load`, `check_model` y `save`, y verifica el hash del grafo
  compuesto antes de ejecutar ONNX Runtime. Picos observados: aproximadamente
  1,42 y 1,43 GiB dentro de un límite de 4 GiB; sin eventos OOM.
- **12 comprobaciones MCP** pasan: lectura propia, búsqueda semántica, textual
  y estructural, aislamiento frente a rutas ajenas/enlaces y memoria separada.
  Las fuentes originales permanecen iguales; ambos grupos de procesos se
  retiran y todos los trabajadores registrados cierran.
- Auditoría de **71 dependencias de registro**, salida 0, sin avisos ni paquetes
  omitidos. La variante local de Ken no se presenta como auditada por PyPI;
  su revisión se limita al parche y a estas comprobaciones.
- Cero turnos generativos y ningún archivo de suscripción. Sí se ejecutan
  modelos locales de recuperación. El sdist no incluye la suite de tests de
  Ken: estas pruebas no equivalen a ejecutar toda su suite ni cubren otros SO,
  versiones de Python, GPU o todos los perfiles de recuperación.

[Resultados y hashes](ken-onnx-candidate-results.json),
[auditoría y versiones completas](ken-onnx-candidate-audit.json).
No se repitieron la suite global ni el empaquetado de Researcher: no cambió su
código productivo. El módulo y la función nuevos de evaluación tienen docstrings.

## Reproducir y adoptar

1. Descargar y verificar la fuente indicada; extraerla en una carpeta nueva.
   Aplicar el parche con `patch -p1` dentro de esa copia. Mover su `PKG-INFO`
   fuera de ella antes de compilar.
2. Construir sdist y wheel con `uv build --python <python-3.12.9> --out-dir
   <dist-nuevo> <fuente-parcheada>`. Verificar que nombre, metadata y módulo
   declaran `0.18.0+researcher.1` y que `Requires-Dist` exige ONNX 1.23.2.
3. Crear otro entorno con `uv venv`. Del `requirements-ken.txt` identificado
   por hash en el informe, extraer los pares `nombre==versión`, excluyendo
   `ken-rank` y `onnx`; conservar los otros 70 como constraints. Instalar el
   wheel con `uv pip install --python <entorno>/bin/python --constraint
   <constraints> <wheel>` y ejecutar `uv pip check` contra ese entorno.
4. Con los activos de modelos públicos ya preparados y un cgroup delegado,
   ejecutar desde Researcher:

   ```sh
   <python-del-producto> evals/security/run_ken_onnx_candidate.py --live \
     --ken-command <entorno-candidato>/bin/ken \
     --model-cache <cache-de-modelos> --codex-binary <codex> \
     --cgroup-parent <grupo-delegado> --memory-mib 4096
   ```

   El evaluador admite temporalmente esa versión exacta **en su propio proceso**
   para reutilizar la prueba de aislamiento. La admisión normal del producto
   continúa exigiendo la versión publicada; no se amplía a versiones arbitrarias.

La siguiente decisión de integración es trasladar el cambio a una versión
publicada y compatible de Ken, regenerar el lock de herramientas y verificar
la preparación de un host real con ella. Esta evidencia permite revisar ese
cambio, pero no lo reemplaza. Chroma, licencias y los demás escenarios de
seguridad siguen abiertos; no se cierra ninguno de los 43 escenarios globales
por este ensayo. Los detalles secundarios se retoman después de todas las
capacidades principales, como pidió el usuario.
