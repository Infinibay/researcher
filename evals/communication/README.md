# Comunicación: recorridos y evidencia

Este directorio es la entrada común del §7.7. Reutiliza conversaciones registradas
y ejecutores productivos; no añade otro loop ni una capa de inferencia para
reformular estados.

| Recorrido | Material y ejecutor | Alcance |
| --- | --- | --- |
| Pregunta sencilla, explicación, analogía engañosa y corrección | `../context_alignment/`, `../prompts/cases.json` | Comparaciones históricas acotadas; conservar originales y catálogos. |
| Comparación e incertidumbre | `../profile_communication/`, `../current_scientific/` | Casos sintéticos y resumen primario; no representatividad o validez causal general. |
| Pregunta material y corrección durante trabajo | `../communication_flow/` | Turnos reales y respuestas guionadas; no observación humana. |
| Resultado guardado, fallo de lectura y recuperación | `retained.py`, `../../frontend/tests/communication-baseline.mjs` | API y datos reales de ensayos previos, corte de red inducido; cero nuevos turnos. |
| Espera larga de herramienta activa | `live_wait.py`, `wait_worker.py`, `../../frontend/tests/communication-wait.mjs` | Comando realmente activo bajo el coordinador instalado; transporte nativo controlado sin generación. Los recibos determinan el resultado de cada ensayo. |
| Encuadre de propósito, datos y entrada/salida | `purpose_framing.py` | Pregunta histórica reconocible y fuente real del repo; un turno de catálogo10 falló por presupuesto antes de entregar explicación. No aceptación humana. |

Para leer los dos casos retenidos, usar Python del producto instalado y Node24:

```bash
python -I evals/communication/retained.py --host /ruta/dentro/de/.researcher/evaluations/instalacion \
  --output /ruta/nueva/dentro/de/.researcher/evaluations/salida \
  --kind code_review --node /ruta/absoluta/node
```

El otro modo es `--kind partial`. Rechaza fuentes con peers/grants abiertos o
intentos activos, conserva filas/campos anteriores y registra adiciones de esquema.
El navegador permite sólo GET y emparejamiento. Una interrupción de GET comprueba
recuperación de lectura; no demuestra recuperación del backend o de una herramienta.

Para la espera, usar una salida privada nueva, el mismo Python instalado y Node24:

```bash
python -I evals/communication/live_wait.py --assets /ruta/privada/recursos.json \
  --output /ruta/nueva/dentro/de/.researcher/evaluations/espera --node /ruta/absoluta/node
```

El navegador envía una única instrucción real. Un comando conserva una puerta
acotada en su copia privada hasta que el navegador consulte el mismo recibo en
escritorio/móvil durante al menos diez segundos. Después se libera ese comando,
se observa su salida y se espera la propuesta antes de cerrar el servicio original.
No hay modelo generativo: la reserva nativa controlada y su consumo desconocido
se registran aparte. El transporte corto reutilizado se amplía a90s sólo en su
copia; el comando sigue limitado a80s y la puerta a60s. Recursos originales intactos.
Se fijan copias verificadas de DNS/certificados públicos fuera de las fuentes,
conservando la verificación productiva de identidad y el Ken real.

La infracción conocida de nombres accesibles de cuatro botones deshabilitados se
retiene como DD155 y se identifica exactamente; cualquier otro hallazgo falla.
Un recorrido funcional con esa excepción no es accesibilidad limpia. Conservar
también intentos fallidos y no volver a enviar sus instrucciones inciertas.

## Rúbrica común

Evaluar con evidencia y límites: claridad, fidelidad, utilidad del ejemplo,
saltos injustificados, carga de lectura y posibilidad de corregir. Distinguir
afirmación del usuario, ejemplo, observación, interpretación y suposición. Una
analogía debe conservar la relación pertinente; una tabla o un párrafo pueden
explicar mejor que un diagrama decorativo. No puntuar por cantidad de mensajes,
diagramas o frases breves. Se conserva cada rúbrica registrada y sus resultados;
esta guía no modifica puntuaciones históricas.

Las medidas humanas siguen desconocidas hasta observarlas. Enmarcar objetivo,
datos, relaciones y entradas/salidas antes de pedir una decisión útil. Observar si
la persona identifica conclusión/límite, elige un paso y corrige una interpretación,
y si el sistema adapta el trabajo. Respuestas guionadas, capturas y comprobaciones
automáticas no sustituyen esa evidencia. No repetir cuestionarios abstractos.
