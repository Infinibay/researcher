# Catálogo por rol y memoria CrewAI retirados

Después de retirar el motor, el único consumidor productivo del catálogo por rol
era el constructor antiguo de agentes. No quedaban llamadas de producto a esos
constructores. Se eliminan las nueve piezas de `backend.agents`, el catálogo
ejecutable `_legacy_catalog`, el puente de eventos CrewAI y sus dos adaptadores
de conocimiento/memoria. Los paquetes `tools` y `knowledge` dejan de resolver
exports que inicializaban esas integraciones.

El modelo recibe las herramientas del catálogo nativo admitido para su capacidad.
Un rol histórico no puede construir herramientas, seleccionar proveedores,
inyectar memoria automáticamente ni completar una ejecución.

## Datos y capacidades conservadas

- `roster`, `agent_runs`, memoria y etiquetas históricas permanecen en SQLite.
  La API de lectura antigua sigue devolviendo sus identidades originales; no
  crea intentos nativos ni interpreta esos registros como actividad comprobada.
- La página Agentes usa el registro nativo separado. Wiki mantiene página,
  proyecto/global y revisión; dos páginas con el mismo path no se confunden.
- Investigación, revisión, exploración y desarrollo conservan herramientas
  nativas para consultar hallazgos y el feedback real de sus revisiones.
- Los schemas antiguos permanecen como
  [snapshot documental](legacy-tool-schemas.json), sin instanciar sus clases.
  Las nuevas descripciones y nombres enviados al modelo siguen en el catálogo
  nativo compartido por el runtime y el MCP de negocio.

No se cambia el esquema ni se migra o borra contenido. Las antiguas APIs Python
de constructores/catálogo dejan de estar disponibles; una integración debe usar
la admisión y las lecturas del propietario correspondientes, no recrear agentes
por rol o adoptar su memoria como instrucciones actuales.

## Comprobación

El [inventario](../modernization/catalog-removal-inventory.json) conserva hashes
de trece módulos de producción y cinco archivos de pruebas retirados, con
37 funciones de prueba. Su retirada no cuenta como reparación de fallos antiguos.
Las comprobaciones vigentes cubren los contratos conservados en el nuevo recorrido.

- RED inicial: constructor todavía disponible; la lectura histórica ya pasaba.
- [Fuente](../modernization/catalog-removal-results.json): 47 pruebas pasan en
  12,30 s. Incluyen lectura histórica sin escritura, namespaces/revisiones wiki,
  catálogos nativos, MCP stdio real y control de trabajadores registrados.
- [Wheel instalado](../modernization/catalog-removal-packaging.json): 30 pasan,
  cero fallos/omisiones, 8,988 s; 797 fuentes coinciden y 234 módulos se cargan
  sólo desde el entorno instalado. El archivo construido desde una copia limpia
  no contiene los módulos retirados. Siguen 85 distribuciones sin frameworks
  legacy instalados.
- Un recorrido de investigación usa kernel/broker/SQLite reales con generación y
  Ken controlados. Cero modelos reales o efectos sobre datos del usuario.
- Cinco definiciones modificadas/nuevas llevan docstrings en inglés;
  Ruff no señala incidencias en el alcance modificado. El auditor de prompts y
  sus dos pruebas pasan: 553 candidatos en 487 archivos, siete entradas más
  archivadas y veinte revisiones revalidadas por retirada de consumidores.

La primera selección de pruebas colocó una comprobación nativa en un módulo que
importa herramientas individuales opt-in; se trasladó al módulo nativo. Una
aserción migrada de Wiki usaba `page_id` en vez del campo real `id`; se corrigió
en la prueba, sin cambiar producción. El primer build previo a esa corrección
fue sustituido por el build final. No se repitió la suite global ni el frontend.

## Trabajo principal que continúa

Las implementaciones individuales antiguas de herramientas todavía existen y
requieren el extra `legacy` si se importan directamente. Por eso esta entrega
**no declara retirada completa de CrewAI, Chroma o tree-sitter**.

Context7 y Spider aún necesitan adaptación o una decisión de compatibilidad
justificada y verificable. Capturar una página web normal no demuestra scraping
avanzado ni reemplaza la búsqueda documental de Context7. Esas capacidades,
consumidores/índices antiguos y dependencias siguen como trabajo principal.
Migraciones/restore, presupuestos, historial, CLI y aceptación integral permanecen
en el alcance completo; no se difieren como pulido.
