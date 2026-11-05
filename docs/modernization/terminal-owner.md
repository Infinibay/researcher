# Usar la terminal con el runtime nativo

Inicia la API con la base ya inicializada y el perfil nativo configurado. La
inicialización y autoridad del host están en [bootstrap](bootstrap.md). CLI y TUI
se conectan a ese mismo servicio; no inicializan otra base ni otro equipo.

La API anuncia el fichero privado de emparejamiento al arrancar. Usa esa ruta
actual, el proyecto registrado y su origen local:

```bash
researcher --server http://127.0.0.1:8000 --project-id 101 \
  --owner-key-file /ruta/privada/owner-servidor.key
```

Añade `--no-tui` para consola clásica. `--state-dir` selecciona estado privado
fuera de los workspaces; por defecto usa `$XDG_STATE_HOME/researcher/terminal` o
`~/.local/state/researcher/terminal`. No pases el contenido de la clave en argv.
Variables equivalentes: `RESEARCHER_OWNER_URL`, `RESEARCHER_PROJECT_ID` y
`RESEARCHER_OWNER_KEY_FILE`.

Un inicio no interactivo devuelve la tarea/run de planificación:

```bash
researcher --project-id 101 --owner-key-file /ruta/privada/owner-servidor.key \
  --prompt 'Investigar el parser y proponer un cambio respaldado'
```

Después usa `--command '/proposal RUN'`, `/accept-plan RUN`, `/execution RUN` y
`/execute-plan RUN` como decisiones separadas. La propuesta debe consultarse antes
de aceptarla. Un ejemplo en consola:

```text
/plan Investigar el comportamiento antes de cambiarlo
/proposal IDENTIDAD_DEL_RUN
/accept-plan IDENTIDAD_DEL_RUN
/execution IDENTIDAD_DEL_RUN
/execute-plan IDENTIDAD_DEL_RUN
```

Los resultados de tareas se consultan por sus propios runs. `/help` muestra los
controles de investigación, desarrollo, revisión y aceptación. `/pause-plan RUN`
usa la ejecución previamente consultada; su recibo solicita detención. Consulta
los intentos para comprobar cierre. Reanudar sólo continúa trabajo aún no emitido.

Si se pierde una respuesta, conserva el mismo directorio de estado y usa `/retry`.
No rehagas el comando con otra clave. Un servidor que cambió de DB se rechaza
aunque conserve URL e IDs. Al reiniciar la API, usa su fichero actual de
emparejamiento; no cambia el contenido de tu solicitud pendiente.

El modelo lo configura el host en el campo `model` de `INFINIBAY_RUNTIME_CONFIG`.
`/task ID` muestra la configuración disponible y `/input RUN` el modelo registrado
para ese intento. El antiguo `--model` se rechaza con esta indicación; cambiar
`LLM_MODEL` o un proveedor Ollama no configura el runtime nativo.

La terminal antigua ejecutaba y mezclaba resultados automáticamente. Ese flujo
se reemplazó por estas decisiones sobre el journal común. Historial previo y
configuración antigua se conservan; snapshots del LoopEngine no se cargan como
sesiones nativas. [Contrato y pendientes](../architecture/terminal-owner-client.md).
