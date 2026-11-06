# Retirada de bibliotecas del backend antiguo

Se eliminan CrewAI, crewai-tools, LiteLLM, Ollama y Chroma del manifiesto y del
lock, después de retirar sus herramientas y verificar los consumidores restantes.
La instalación conserva el runtime nativo, la base de datos compartida y las
interfaces de investigación, tareas, comunicación y proyecto ya migradas.

## Cambios y límites

- Se retira el extra `legacy`, junto con sus filtros de warnings de pytest.
- Se eliminan cinco módulos sin consumidores: `_legacy_access`, `base_tool`,
  `dedup`, `embeddings` y `permissions`. También desaparece la exportación
  diferida de `InfinibayBaseTool`; los exports de DB/contexto se conservan.
- Se eliminan las dos fixtures que desactivaban la persistencia de CrewAI. No
  se eliminan casos de integración ni se cuentan esas retiradas como fallos resueltos.
- El lock pasa de 177 a 86 paquetes: 91 retirados, ninguno añadido y ninguna
  versión retenida modificada. `requirements.txt` queda idéntico al anterior.
- No se modifica ningún dato, esquema, vector, índice o archivo histórico.
  Recuperar material que sólo existe en archivos o colecciones antiguas sigue
  siendo trabajo principal de migración/restauración. Quitar Chroma no demuestra
  que esos datos ya estén recuperados ni permite eliminar sus copias.

El análisis AST revisa 642 archivos de `backend` y `scripts`, incluidos tests,
sin encontrar imports estáticos de las bibliotecas, auxiliares o familias de
herramientas retirados. Se corrige la resolución relativa de `__init__.py` en el
auditor: representa su paquete, no un módulo adicional. La exportación diferida
de la clase base era un consumidor que el atajo anterior podía omitir; ahora se
retira y comprueba expresamente. Este análisis no cubre consumidores externos
ni imports construidos dinámicamente.

## Comprobación

| Alcance | Pasan | Fallan | Omitidos |
| --- | ---: | ---: | ---: |
| Pruebas afectadas desde fuente | 129 | 7 | 3 |
| Pruebas desde el wheel instalado, fuera del checkout | 124 | 7 | 3 |
| Auditor de prompts | 2 | 0 | 0 |

Cinco casos de manifiestos y `start.sh` se ejecutan sólo desde fuente: esos
artefactos pertenecen al checkout. El paquete instalado comprueba por separado
sus metadatos y la ausencia del extra y requisitos antiguos. Coinciden los 676
archivos Python/SQL empaquetados; los 256 módulos backend importados proceden del
entorno instalado. Hay 83 distribuciones compatibles y ninguna de las cinco
bibliotecas retiradas. El lock se valida sin red.

Los siete fallos se reproducen en el código anterior `e78d752`, usando el entorno
histórico porque sus fixtures todavía importan CrewAI. Esa comparación usa un
entorno de dependencias distinto: demuestra que los fallos ya eran reproducibles,
no equivalencia completa de entornos. Los mensajes coinciden tras normalizar
únicamente direcciones de memoria en dos de ellos. Corresponden a listeners,
transiciones de tareas y el router de finalización del flujo antiguo; quedan
para la tarea principal de servicios/flows heredados. Los tres casos omitidos
dependen de la imagen de pod antigua. No se declara una suite global verde.

Las tres definiciones de tests nuevas/modificadas tienen docstrings en inglés.
El inventario conserva 234 candidatos de prompts en 365 archivos y 364 entradas
archivadas, sin revisión estática pendiente ni cambio semántico de prompts en
este corte. Su eficacia con modelos y comprensión humana siguen pendientes.
No se hicieron llamadas a modelos o proveedores de pago.

La evidencia está en [resultados](../modernization/legacy-dependencies-results.json),
[paquete](../modernization/legacy-dependencies-packaging.json) y
[imports](../modernization/legacy-dependencies-imports.json).
El siguiente bloque principal son los servicios, lectores, rutas internas y CLI
heredados restantes. Los cuatro avisos de estilo quedan en DD056 para después
de todas las capacidades principales.
