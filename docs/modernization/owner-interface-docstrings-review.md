# Documentación de acceso y proyecciones del propietario

**43 docstrings nuevos en inglés**: local_access (12), rutas runs (22),
sqlite_questions (5) y views (4). Contratos revisados contra implementación:
credenciales locales separadas de OAuth/grants del modelo, sesión/CSRF y origen,
retiro de WebSockets expirados, lectura de recibos, recuperación sin replay y
respuesta humana que crea contexto para una ejecución posterior. La pasada
acumula **416 definiciones en 26 módulos**, con **205 faltantes por presencia**
fuera del alcance y distinta relevancia.

[Resultados](owner-interface-docstrings-results.json),
[textos por identidad](owner-interface-docstrings-evidence/authored-docstrings.json),
[delta OpenAPI](owner-interface-docstrings-evidence/openapi-delta.json).

Los cuatro archivos quedan sin clases/funciones sin docstring en el inventario
sintáctico. AST ejecutable idéntico a `3f1e19d` sin documentación; cambian `__doc__`
y líneas. **Se añaden 14 descripciones OpenAPI** de rutas/modelos del propietario;
se comparó el esquema generado en procesos separados: rutas, métodos, campos,
referencias, límites y demás valores iguales. Esto no altera las siete políticas
nativas ni las 48 descripciones/esquemas/anotaciones de herramientas de negocio.

**55 pruebas fuente pasan**, sin omisiones, en **29,83 s**: acceso local,
preguntas, salida de comandos e inbox. Un aviso existente de deprecación de
`httpx` en TestClient se conserva en el log. Inventario de prompts **85/322 vigente**:
dos consumidores de `run_inputs` revalidados por cuatro docstrings en views,
fuentes de candidatos y llamadas intactas; las otras 83 decisiones no se renuevan.

No se declara accesibilidad, comprensión humana, ranking Ken ni documentación
global completos. No se reindexa el MCP original ni se construye otro paquete;
el wheel anterior conserva sus bytes. Continúan interfaces/JSDoc relevantes,
U08, Ken/ONNX, accesibilidad y cierre integrado.
**19:08:56–19:11:47 UTC: 2 min 51 s** hasta verificación; informe/checkpoint después.
