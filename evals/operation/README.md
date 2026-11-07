# Ensayos de operación

`restored_host.py` prepara una instalación sintética nueva, guarda una solicitud
pendiente, crea/verifica una copia y la restaura en otra ruta. Reinscribe esa copia
con autoridad y acceso nuevos; envía una sola solicitud nueva mediante HTTP,
comprueba Ken, cálculo, citas e informe y reinicia el servicio conservando sus
resultados. La instalación original y su solicitud no se ejecutan ni reemplazan.

```bash
/ruta/al/entorno/bin/python -I evals/operation/restored_host.py \
  --live \
  --assets /ruta/privada/recursos-host.json \
  --output /ruta/privada/ensayo-nuevo
```

El entorno debe tener el paquete instalado. `-I` mantiene sus imports fuera del
checkout; el harness carga sólo su auxiliar de operación desde este repo. Los
recursos tienen el formato de [preparación del host](../../docs/architecture/native-host-installation.md),
incluyendo la cuenta por suscripción, Ken publicado, sus modelos locales y un
cgroup delegado. Configurar `project_turn_limit:1` y `limits.max_turns:1`, además
de límites explícitos de tiempo, herramientas y tokens. El directorio de salida
debe ser nuevo y su padre debe existir. No pasar una instalación del propietario
como salida ni reemplazar recursos existentes.

La intención y su clave quedan en `result.json` antes del envío HTTP. Una pérdida
de respuesta o del observador no autoriza otro turno. Conservar el proceso/handle
original mientras siga vivo; después inspeccionar su base y recibo. El siguiente
comando sólo lee el resultado original y escribe `verification.json`; no arranca
servicios ni modelos:

```bash
/ruta/al/entorno/bin/python -I evals/operation/restored_host.py \
  --verify-root /ruta/privada/ensayo-original
```

La verificación exige el run original, un único dispatch completado, un cálculo
con salida200/exit0, cita literal contenida en su fuente, informe draft, procesos
registrados cerrados y la respuesta de `ken_read` correlacionada con el código
esperado. Un nombre de herramienta o una afirmación del modelo no bastan.
El chequeo del trace está limitado a esta fixture; no es un intérprete general de
JavaScript ni certifica atribución de resultados adversariales.

`host_smoke.py` conserva el ensayo de preparación/arranque nuevo y
`native_container.py` el ensayo rootless con el observador del host. Ninguno de
estos ensayos demuestra por sí solo un reboot del kernel, pérdida de energía,
migración de datos históricos del propietario, calidad científica o comprensión
humana. [Resultado actual del host restaurado](../../docs/modernization/restored-host-evaluation-results.json).
