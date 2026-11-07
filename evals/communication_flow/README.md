# Recorridos de comunicación

Ejecuta como máximo cuatro turnos reales, en dos instalaciones nuevas, con Codex
por suscripción y Ken publicado. Requiere recursos del host, kernel/cgroups y el
wheel actual instalado en el intérprete usado. Conserva el archivo de recursos
original; cada escenario declara dos turnos y120000 tokens observados por turno
en un archivo privado. Estas medidas son límites del host, no facturación.

```sh
python evals/communication_flow/run.py --live --assets /ruta/recursos.json --output /ruta/nueva
```

`--only question_answer` o `--only active_correction` selecciona un escenario en
un directorio nuevo. Nunca reinicia una admisión incierta ni sobreescribe un ensayo.
Si falla un verificador después de cerrar procesos, conservar el resultado fallido
y reanalizar los recibos originales; no generar otra respuesta para ocultar el fallo.

- Pregunta: falta la unidad de una duración. El agente debe registrar la pregunta;
  la pausa exige cierre real. Una respuesta guionada cambia contexto sin admitir
  trabajo; una nueva instrucción explícita usa ese dato y el pedido original.
- Corrección: se retiene una respuesta real de Ken antes de entregarla al modelo,
  se registra la corrección durante el intento activo y se comprueba su invalidación.
  El siguiente intento recibe el pedido original completo como historia y el
  contexto corregido como vigente.

Se registran política/casos antes de inferir, inputs y catálogos entregados,
herramientas, preguntas, estados, consumo observado y cierre de procesos/permisos.
El worker de observación utiliza el texto exacto del catálogo actual y verifica
su hash; sólo instrumenta este perfil de investigación. No cambia el API productivo.

Son regresiones funcionales nuevas con respuestas del propietario guionadas.
No son casos reservados del experimento anterior, una comparación causal de
prompts, una evaluación de todos los perfiles ni una observación de comprensión
humana. Una pregunta clara no demuestra que una persona haya podido responderla.
