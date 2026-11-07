# U01–U03 — evidencia, recuperación y vigencia del conocimiento

Preparado durante la validación D13. Inicio real **2026-11-07 22:47:36 UTC**,
base `f6f0630`. Continuar el plan principal: capacidades
grandes primero, detalles al final; no volver a implementar componentes vigentes.

## Contratos del plan

- U01: consultar una fuente no equivale a guardarla. La persistencia usa el
  schema real y el ámbito correcto; los errores quedan visibles y no producen
  una confirmación ficticia de evidencia registrada.
- U02: una revisión nueva de fuente o un finding provisional/superseded conserva
  fecha, hash, extractos y procedencia. Recuperar por similitud no valida una
  afirmación ni elimina contraevidencia de la explicación.
- U03: modelo/dimensión y revisión de corpus identifican el índice utilizado.
  Reconstrucción, cobertura incompleta o antigüedad son observables; una consulta
  durante indexación no mezcla proyectos ni presenta un vacío como inexistencia
  demostrada. Ken publicado y su integración real forman parte del contraste.

## Recorrido de aceptación

- [x] Leer implementaciones, pruebas y recibos actuales de fuentes, findings,
  búsqueda/retrieval y Ken; distinguir evidencia vigente de pendientes históricos.
- [x] Contrastar persistencia fallida, fuente modificada, finding superseded,
  índices/corpus de revisiones distintas y consultas durante reconstrucción.
  Corregir brechas funcionales demostradas, con docstrings útiles para Ken.
- [x] Verificar la presentación de procedencia y límites hasta el consumidor
  humano; separar ese contrato de la aceptación visual integral de las páginas.
- [x] Reutilizar artefactos/pruebas válidos y ejecutar sólo las verificaciones
  afectadas. Si hace falta inferencia real, usar la suscripción autorizada y Ken;
  no repetir generación sin una pregunta de aceptación pendiente.
- [x] Registrar matriz, límites, resultados y tiempos; actualizar cobertura y
  tablero, guardar commit local y publicar lista al cambiar de tarea.

Después siguen U04/U05/U07/U08, datos históricos, evaluaciones y aceptación de
las doce páginas, dependencias/distribución y cierre global/independiente.
U08 exige comprensión/corrección humana: un test de renderer no la reemplaza.
Los detalles secundarios y C10/DD116 conservan su lugar al final de lo grueso.

Verificado **2026-11-07 23:04:16 UTC**, **16 min 40 s** hasta verificar.
La mejora de atribución semántica y los contratos U01–U03 están comprobados.
225 casos instalados correctos y un fallo histórico conservado en DD120; no se
declara suite global verde. Ken publicado verificó dos revisiones en el mismo
índice con cierre real. [Matriz y límites](../../modernization/knowledge-acceptance-review.md).
