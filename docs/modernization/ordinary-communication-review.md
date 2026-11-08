# Explicación real entregada bajo la configuración ordinaria

El producto generó una explicación final de **295 palabras** y un informe
propuesto sobre la configuración de modelos. El turno terminó `completed` y el
run quedó `needs_review`, sin cambiar ajustes ni aceptar trabajo. **Comprensión,
corrección útil y aceptación humana siguen pendientes.**

[Explicación para leer](ordinary-communication-explanation.md),
[salida literal](ordinary-communication-original.md),
[resultados](ordinary-communication-results.json),
[registro previo](ordinary-communication-evidence/registration.json),
[resultado original del runtime](ordinary-communication-evidence/native-result.json),
[revisión del contenido](ordinary-communication-evidence/manual-review.json).

## Qué se midió

La condición nueva usa los límites del operador: **350 000 tokens observados,
25 herramientas, un turno, 180 s**. La condición de desarrollo 120k/20 continúa
como predeterminada del evaluador y ambos ensayos anteriores siguen fallidos.
El modo nuevo es explícito, sólo se elige al registrar y se limita además por la
configuración del operador/proyecto. La combinación inválida de elegir límites
al ejecutar se rechaza antes de admitir un run.

Se conservaron pregunta, fuentes, criterios, modelo/esfuerzo y cuerpo de política
11; sólo cambia el presupuesto efectivo del nuevo registro. **No se inyectó la
receta controlada ni un informe preparado.** Esta observación responde si existe
una explicación útil bajo configuración ordinaria. No demuestra eficiencia,
causalidad, ajuste a 120k ni que la política nueva haya mejorado el resultado.

## Resultado observado

- Una admisión y un turno de modelo, **nueve rondas** y ocho `exec`; 14 herramientas.
- **285 862 tokens observados**, incluidos tokens de entrada cacheados. Son datos
  del runtime, no una estimación de facturación o rendimiento general.
- **98,669 s** de observación. Cinco peers cerrados, cero grants sin revocar y
  servicio terminado. Sin reintento automático ni sustitución de proveedor.
- Ken devuelve las **118 líneas completas**, verificadas contra la copia y el
  original; hashes de fuente y todas las citas guardadas comprobados.
- Dos hallazgos provisionales, un informe draft y una propuesta explícita. Cero
  aceptaciones y cero filas de configuración de modelos. La tarea no se marca done.

El contenido explica la pareja modelo/esfuerzo, ámbitos, herencia, entradas/salidas
y elección inmutable por intento. El ejemplo se declara ficticio y no afirma que
esos modelos estén disponibles. Distingue ajustes de modelo de la tarea/evidencias
que recibirá y declara lo que el módulo no permite saber. El siguiente paso es
inspeccionar el valor efectivo en Modelos, sin pedir un cuestionario de comprensión.

La comprobación de criterios es del implementador, sobre esta salida y sus fuentes.
No equivale a aceptación del propietario. Se presentó la explicación con una
pregunta opcional sobre qué necesita aclarar para usar la configuración; no se
recibió todavía una respuesta ni se bloquea por ello el trabajo independiente.

## Límites conservados

El intento auxiliar `command_read` volvió a fallar validación; el modelo no lo usó
como evidencia. `ken_related` devolvió transporte exitoso con análisis `ok:false`;
el informe conserva el límite de llamadores no verificados. No se ejecutaron
pruebas del comportamiento analizado ni se verificó disponibilidad actual de la
cuenta: la explicación misma sí fue generada por el modelo mediante suscripción.

Los enlaces nativos a archivos usan `/run/researcher-source`, que pertenece al
entorno del ensayo. La proyección para leer adapta sólo esos dos destinos al
mismo archivo real del repositorio y conserva el texto restante; la salida exacta
se guarda por separado. El informe tipado tiene encabezados canónicos ingleses
con cuerpo español. Se anotan esos problemas de presentación para la fase final.

El coste de nueve rondas y los fallos120k siguen visibles. La composición ejecutable
probada no fue suministrada a este modelo ni se atribuye a ella esta entrega.
Siguen pendientes respuesta/corrección humana, eficiencia, Ken/ONNX, documentación,
accesibilidad y cierre integrado. No hay nueva suite global ni una aceptación de U08.
