# Retirada de inferencia auxiliar antigua

Los caminos antiguos ya no construyen clientes ni generan texto fuera del runtime
nativo admitido. `config.llm.get_llm/get_litellm_params`, validación de function
calling, `probe_model/_run_probes` y `engine.llm_client.call_llm` rechazan la
operación antes de importar o llamar al proveedor. No hay sondeos sintéticos,
reintentos del cliente antiguo ni traducción de API keys a un proveedor alternativo.
Los hooks antiguos de entorno y parches se conservan sin efectos.

La selección del modelo, autenticación de suscripción y capacidades reales siguen
en el runtime configurado y su protocolo original. Los campos históricos
`ModelCapabilities` comienzan desconocidos (`None`, `probed=False`); no describen
el soporte del modelo nativo ni convierten un sondeo fallido en éxito. Los ajustes
LLM antiguos tampoco cambian el modelo nativo; su interfaz/configuración heredada
sigue pendiente de migración. Las vistas de ejecución muestran el modelo real.

## Conversación y evidencia

El lector histórico conserva las preguntas/respuestas y mensajes originales como
texto atribuido. No genera un resumen ni sustituye la fuente por una interpretación
cacheada. Muestra hasta diez mensajes recuperados, con extractos de300caracteres,
identifica cuántos se muestran y declara el historial no examinado. Los empates de
fecha usan el ID durable para conservar los mensajes más recientes en orden.

Un nombre de remitente, respuesta vieja o extracto no demuestra instrucción actual,
aprobación ni comprensión compartida. Los mensajes originales siguen en SQLite.
El protocolo nativo de entrada congelada, conversación, preguntas y correcciones
conserva su alcance/versionado; este lector de compatibilidad no lo reemplaza.

## Investigación profunda

`DeepWebResearchTool` devuelve una referencia al propietario de su proyecto antes
de búsqueda, descarga o síntesis, tanto en la entrada síncrona como asíncrona.
No afirma haber investigado. La investigación real se realiza dentro de la sesión
nativa admitida: descubrimiento nativo, captura explícita de fuentes, citas exactas,
hallazgos provisionales y selección de informes. Entrega, revisión y aceptación
siguen siendo operaciones distintas.

## Importación sin inicialización implícita

Importar `backend.tools.base.db` antes cargaba el catálogo entero y terminaba en
un ciclo con `event_listeners`/`ask_user`. El catálogo histórico ahora vive en
`backend.tools._legacy_catalog` y se carga por una exportación conocida solicitada
explícitamente. La exportación del BaseTool antiguo también es lazy. La API puede
importarse y construirse en un proceso limpio sin CrewAI/LiteLLM, sin abrir la base
ni arrancar mantenimiento. Los lectores de metadata de roles aún resuelven sus
nombres y schemas; no se confunden con el catálogo MCP nativo de negocio.

Esto prepara la retirada de dependencias, pero no la declara hecha: el catálogo,
constructores y herramientas antiguos aún existen y sus dependencias siguen en
el paquete. Falta contrastar y retirar esos consumidores, migrar MCP/Git/instalación
y probar una instalación nativa limpia. No se afirma que un proceso antiguo o
trabajador no registrado haya terminado por devolver un handoff.

[Resultados](../modernization/auxiliary-results.json) y
[paquete](../modernization/auxiliary-packaging.json) delimitan las pruebas, incluida
investigación nativa controlada con kernel/broker/SQLite y comprobaciones reales
del protocolo de búsqueda. No son una evaluación de calidad de un modelo real,
de ranking Ken ni de comprensión humana.
