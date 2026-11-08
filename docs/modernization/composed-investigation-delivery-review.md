# Entrega de investigación compuesta en un exec

Una llamada `exec` ejecutada por el **code host real y fijado de Codex 0.166.0**
puede encadenar `researcher_finding_record` → `researcher_investigation_summary`
→ `researcher_result_propose`, utilizando los identificadores que devuelve cada
paso. Se verificó con JavaScript escrito como fixture, esquemas canónicos,
mediación, HTTP y SQLite reales. No se añadió una API ni otro loop de modelo.

[Prueba](../../backend/tests/runtime/test_investigation_delivery_cell.py),
[resultados](composed-investigation-delivery-results.json),
[revisión con contexto limpio](u08-delivery-proportionality-review.md).

El resultado conserva un hallazgo nuevo, un informe tipado y una selección
explícita del autor. Después de simular ausencia de finalización nativa y cerrar
los peers sintéticos de almacenamiento, el propietario puede leer el informe por
su API autenticada. La elegibilidad para aceptar sigue falsa y la tarea no se
marca terminada. No se necesita otro modelo para renderizar ese texto; tampoco se
simula una explicación generada como si proviniera de un usuario real.

**Prueba directa: 1 pasa en 1,68 s**, sin omisiones. Ampliación al contrato de
investigación y herramientas HTTP: **22 pasan, 4 se omiten, un aviso**, en 15,28 s.
Las cuatro omisiones son variantes opcionales de recuperación semántica que no
tenían su fixture local preparado; no se omitió la nueva prueba del code host.
Ruff pasa y las definiciones nuevas tienen docstrings de propósito y límites.
La primera ejecución falló porque el driver de prueba suponía que el frame
siguiente era la respuesta de cierre. Se corrigió siguiendo la correlación de
respuestas del preflight existente y se conserva ese log. No fue un cambio de
producto ni una corrección del fallo de generación original.

El proceso code host es real; el JavaScript es controlado y los peers del fixture
son sintéticos. Esto demuestra viabilidad de composición y lectura del draft,
no contención del runtime, cumplimiento del modelo, cabida en 120 000 tokens o
comprensión humana. Cero solicitudes de suscripción, sin nuevo wheel ni suite
global. La política nativa todavía no cambia en este bloque. El ensayo anterior
permanece fallido, U08 abierto y DD157 diferido.
