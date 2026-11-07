# Interpretación de un resumen científico real

Un caso de desarrollo con la política actual. Reutiliza el runtime instalado,
Codex por suscripción, Ken publicado y `context_alignment.run.run_arm`.
No hay comparador A/B ni un nuevo loop de agentes.

La fuente es una transcripción factual seleccionada del
[resumen primario de Charig et al. (1986)](https://pmc.ncbi.nlm.nih.gov/articles/PMC1339981/).
El PDF del editor respondió 403; no se verificaron métodos completos ni cifras por
tamaño de cálculo. La tarea pide interpretar evidencia histórica, no recomendar
tratamientos actuales. Una transcripción no se presenta como el artículo completo.

Usar un Python con el producto instalado. El preimport de `backend` antes de
incorporar el checkout mantiene el driver y sus workers ligados a esa instalación:

```bash
"$EVAL_PYTHON" -I -c 'import backend,sys; sys.path.insert(0,sys.argv.pop(1)); from evals.current_scientific.run import main; main()' \
  "$EVAL_REPO" --prepare --assets "$EVAL_ASSETS" --output "$EVAL_OUTPUT"
"$EVAL_PYTHON" -I -c 'import backend,sys; sys.path.insert(0,sys.argv.pop(1)); from evals.current_scientific.run import main; main()' \
  "$EVAL_REPO" --live --assets "$EVAL_ASSETS" --output "$EVAL_OUTPUT"
```

`--prepare` no llama al modelo. Congela caso, evidencia, rúbrica, política con
límites efectivos y hash de recursos. `--live` admite un único intento; una
carpeta de brazo existente impide repetirlo incluso si no quedó recibo final.
Cambios de evidencia o recursos requieren otra inscripción, nunca una edición
silenciosa del caso iniciado. Las pruebas del protocolo no necesitan cuenta.

## Primera observación conservada

El primer registro fijó 120000 tokens observados, por debajo del techo del operador.
El intento acumuló 140692 tras siete solicitudes de herramientas y terminó sin
informe. Se conserva como fallo: una fuente capturada y un cálculo correcto
no son una explicación entregada. El consumo remoto final sigue desconocido.

La configuración del evaluador usa ahora el techo 350000 ya empleado por el harness
general, conservando límites menores del operador. Este cambio sólo afecta
inscripciones futuras. El registro original sigue en 120000; no se volvió a
generar su respuesta ni se elevó su presupuesto retrospectivamente.

[Resultado, cálculo original y cierre](../../docs/modernization/current-scientific-results.json).
Una observación no demuestra calidad general, comprensión humana ni superioridad
de la política. Los criterios sin explicación final quedan sin evaluar.
