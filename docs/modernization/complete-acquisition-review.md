# Adquisición ejecutable de evidencia y entrega comprobadas

La [receta JavaScript](../../evals/communication/acquire_evidence.js) demuestra
una adquisición en un `exec`: Ken real, documento adjunto, inicio del comando,
observación acotada hasta cierre, captura por recibo y lectura de la fuente
canónica. Otro `exec` encadena hallazgo → resumen → propuesta con los IDs reales.
**Son programas y contenido de control escritos para la prueba; no una explicación
generada ni la solución completa de U08.**

[Resultados](complete-acquisition-results.json),
[prueba](../../backend/tests/runtime/test_investigation_acquisition_cell.py),
[evidencia del caso completo](complete-acquisition-evidence/complete/acquisition.json).

## Qué se comprobó

- Code host fijado real, Ken publicado 0.18.0 con modelos/gramáticas preparados
  explícitamente y sin descargas; esquemas, mediación, API y SQLite reales.
- Nueve llamadas de adquisición en un `exec`, incluida lectura de las 118 líneas
  Ken verificadas contra el módulo original. Dos fuentes canónicas completas,
  hashes/contenido/cobertura comprobados. El comando conserva stdout exacto.
- `command_read` usa ventanas de **un byte** para observar estado y asentar el
  cierre. La captura posterior lee los bytes persistidos por `job_id`; la salida
  emitida incluye fuentes interpretables, no otra copia base64 del comando.
- Tres llamadas dependientes de entrega en el segundo `exec`. El informe se lee
  por la API autenticada del propietario y no se acepta automáticamente la tarea.
- Se detiene sin informe/propuesta al truncar salida, retirar el grant real de API
  antes de capturar o recibir un hash esperado distinto. La comparación de hash
  es una prueba de discrepancia, no una carrera de modificación concurrente.

**Cinco casos pasan**, sin omisiones, en **77,57 s**. El caso completo tarda
4,528 s dentro del code host para adquirir y 0,064 s para entregar; preparación,
setup y observación nativa quedan fuera de esos dos valores. Son 12 llamadas
antes de una eventual ronda generativa final, no 12 rondas de modelo. La emisión
canónica completa mide 25 447 bytes UTF-8 JSON; bytes no son ahorro de tokens probado.

Ruff pasa, las funciones nuevas tienen docstrings y la receta tiene JSDoc. Los dos
primeros ensayos detectaron que el adjunto de prueba estaba fuera del directorio
`uploads/101/uploads` exigido por la API. Se corrigió el fixture, manteniendo el
rechazo del producto y los logs originales. El fixture usa lease explícita de
120 s para cubrir preparación offline; no cambia límites operativos ni de inferencia.

## Alcance y límites

Los programas y el breve informe sobre la pareja modelo/esfuerzo son fixtures.
La prueba demuestra composición e integridad del transporte, no que el modelo
los escriba ni que produzca la explicación completa que pidió el propietario.
El número de líneas y hash esperado son descriptores fiables del fixture; no
se supone que el input genérico del producto los proporcione. No hay una API nueva
de adquisición automática, otra política nativa ni una intervención del host
instalada a partir de este ejemplo.

Los procesos Ken/code host son reales. El servidor de comandos y recibos iniciales
de native/business usan los fixtures existentes: no se certifica aquí toda la
contención del broker. El cierre/final nativo se declara sintéticamente para
inspeccionar el candidato; no se usa como prueba de finalización generada. Quedan
sin inyectar por separado algunos fallos de transporte/resultado desconocido.

Cero turnos generativos o solicitudes de inferencia por suscripción. Los 371
archivos de producto siguen coincidiendo con el wheel anterior; los tests y esta
receta cambian sólo en el repositorio y tendrán su corte final de paquete. Sin
nueva suite global, aceptación humana ni evidencia de cabida en 120 000 tokens.

**19:38:13–19:54:27 UTC: 16 min 14 s** hasta comprobación, incluidas diagnóstico y
pruebas; informe/checkpoint después. DD157 permanece diferido.

## Siguiente observación y alcance del presupuesto

La revisión con contexto limpio contrastó el límite del evaluador con la
configuración operativa: **120 000/20 herramientas** era una condición de desarrollo,
frente a **350 000/25 herramientas** configurados por el operador, un turno y 180 s.
El [plan](../superpowers/plans/2026-10-31-actualizacion-proyecto.md) exige comunicación
comprensible y medición honesta, sin fijar aquel umbral de 120 000.

Se decide una observación **separada y preregistrada** de comunicación bajo esos
límites ordinarios, misma pregunta/fuentes/Ken/política 11 y criterio de final.
No se cambia el resultado ni la condición de los dos ensayos anteriores: ambos
siguen fallidos. La hipótesis nueva es entrega/claridad en configuración ordinaria,
no eficiencia, causalidad o ajuste a 120k. Un solo intento, sin rescate automático
ni informe precocinado. Comprensión/aceptación siguen desconocidas hasta observar
al propietario. Esta decisión evita anteponer otra API a la explicación pendiente.
