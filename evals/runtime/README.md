# Evaluaciones de runtime: estado actual e historia

El producto exige `owned-codex-v1`. Un script conservado y un recibo histórico
no prueban el comportamiento de la instalación actual. Esta carpeta contiene
escenarios anteriores cuya migración completa sigue pendiente; no ejecutarlos
como una suite de aceptación vigente.

## Comprobaciones vigentes

Desde el Python instalado del proyecto, con sus dependencias bloqueadas:

```sh
python evals/runtime/check_business_catalog.py
python evals/security/run_local_access.py --live
```

El primero abre el MCP real y compara sus 45 herramientas con el contrato actual
`RESEARCH_NAMES`, además de comprobar preguntas, hallazgos e informes. No concede
una autoridad real ni llama al modelo o al backend.

El segundo inicia un backend instalado con datos sintéticos, comprueba separación
entre acceso anónimo, propietario y herramientas, CSRF, origen/Host, WebSocket y
revocación al cerrar sesión. Cierra su servidor original. Su `--live` habilita
HTTP local: este recorrido envía cero turnos de modelo.

El helper HTTP compartido usa `sys.executable -I`, requiere que el paquete esté
instalado y configura adjuntos/web mediante variables explícitas. Ya no depende
de `.venv/bin/python`, no inserta el checkout en el proceso hijo y no activa
flags de CrewAI/sandbox/LLM retirados. Sin configuración de runtime no configura
inferencia. Un perfil antiguo se rechaza antes de crear DB, credenciales o servidor.
Una configuración nativa sigue necesitando autoridad, recursos y workspace
válidos: el helper no los inventa ni migra instalaciones por sí mismo.

Para investigación nativa con Ken, la ruta comprobada de instalación y reinicio
está en [host nativo](../../docs/architecture/native-host-installation.md) y
[contenedor nativo](../../docs/architecture/native-container-operation.md).
`evals/operation/host_smoke.py` y `native_container.py` requieren una instalación
sintética nueva; el turno por suscripción es explícito y acotado con `--live`.
Estos recorridos no sustituyen la evaluación completa de los escenarios de abajo.

## Escenarios nativos y pendientes

### Instalaciones nuevas para investigación e interacción

Estos seis runners usan `native_trial.py` y el launcher instalado. Aceptan
`--assets` con el mismo formato de recursos que `researcher-bootstrap init-host`,
incluidos modelo, cuenta por suscripción, Ken publicado, caché y cgroup delegado.
No aceptan una configuración de runtime anterior ni un workspace del operador.

```sh
python evals/runtime/run_product.py --live --assets /ruta/host-assets.json
python evals/runtime/run_conversation.py --live --assets /ruta/host-assets.json
python evals/runtime/run_questions.py --live --assets /ruta/host-assets.json
python evals/runtime/run_product_stop.py --live --assets /ruta/host-assets.json
python evals/runtime/run_input_continuity.py --live --assets /ruta/host-assets.json
python evals/runtime/run_analysis_inference.py --live --assets /ruta/host-assets.json
```

Ejecutarlos en serie, cada uno sobre una instalación sintética nueva. El archivo
de recursos debe permitir dos turnos para `run_product.py`, `run_questions.py`
y `run_input_continuity.py`; los otros tres admiten uno. El runner reduce los límites a su escenario y nunca
aumenta un límite de tiempo, herramientas o tokens del archivo del operador.
No cambia el modelo ni copia tokens. Un límite de turnos de proyecto insuficiente
se rechaza antes de preparar la instalación.

Cada directorio privado de `.researcher/evaluations/` conserva instalación,
testigo separado, código y adjuntos sintéticos, preparación, resultado y cierre
del servidor original. Un fallo conserva su evidencia; no se reinicia un turno
incierto. Las comprobaciones numéricas y de entrega no prueban comprensión humana.
El estado de los ensayos está en
[resultados de la migración](../../docs/modernization/native-evaluation-runners-results.json).

El escenario de análisis comprueba además el cálculo observado, el catálogo MCP
actual, todos sus peers cerrados y la lectura de código devuelta por Ken en la
traza del turno original. `run_analysis_inference.py --verify-root /ruta/ensayo`
permite inspeccionar los artefactos de ese mismo ensayo sin arrancar otro turno;
conserva el resultado original, incluso si el harness había fallado. También
reconoce el formato histórico para inspeccionar recibos anteriores.

### Comandos y recuperación sin modelos

Estos tres runners usan `kernel_trial.py`, almacenamiento sintético nuevo y el
broker/dominio actual. Requieren el ejecutable Codex compatible y un cgroup v2
delegado con los controladores `memory` y `pids`. No abren una cuenta ni llaman
a un modelo. Ejecutarlos en serie:

```sh
python evals/runtime/run_analysis_tools.py --codex-binary /ruta/codex --cgroup-parent /sys/fs/cgroup/ruta/delegada
python evals/runtime/run_commands.py --live --peer-loss --db-contention --codex-binary /ruta/codex --cgroup-parent /sys/fs/cgroup/ruta/delegada
python evals/runtime/run_parent_loss.py --live --codex-binary /ruta/codex --cgroup-parent /sys/fs/cgroup/ruta/delegada
```

`--live` habilita procesos locales reales, incluida la muerte del proceso hijo
original en el escenario de pérdida del padre. La preparación no reutiliza una
autoridad ni un workspace anterior. El código del evaluador y del backend se
carga desde el checkout con las dependencias y extensión nativa instaladas.

Análisis comprueba cálculo, lectura, rechazo de escritura, acceso a otra fuente,
escape por symlink, red y credenciales. Comandos comprueba Stop de descendientes,
otro propietario que sigue trabajando, cierre físico con SQLite bloqueado y
pérdida del canal RPC con revocación. Los propietarios tienen autoridades
independientes: esto no demuestra concurrencia dentro de una única instalación.
La prueba de contención usa un intento propio, porque un resultado incierto
invalida la autorización para despachar más comandos.

Pérdida del padre comprueba retiro global aun con el escritor de la base local
bloqueado, proyección posterior y reconciliación repetible sin repetir el trabajo.
Los resultados sin recibo de salida permanecen `unknown`, con `exit_code=null`;
haber cerrado los procesos no convierte el trabajo en exitoso. La preparación
se observa mediante stdout original; el cierre mediante pidfd y estado del
cgroup. [Resultados e intentos fallidos](../../docs/modernization/kernel-evaluation-runners-results.json).

### Escenarios restantes

| Runner conservado | Alcance que falta comprobar con el runtime vigente |
| --- | --- |
| `run_research.py`, `serve_infinidev_research.py` | Comparación directa de candidatos, entorno y política de herramientas; no aceptación del producto nativo |
| `../security/run_ken_isolation.py` | Revalidar Ken publicado y aislamiento en la composición vigente |
| `run_owner_command_inspection.py`, `../ui/run_owner_capture.py` | Lectura de recibos y navegación sobre fixture sintético actual, portable y reproducible; hoy dependen de un ensayo anterior específico |

Las pruebas ordinarias del producto cubren contratos de estas capacidades,
pero no se cuentan como ejecución de estos runners ni como comprensión humana.
Las pruebas de procesos/cgroups se ejecutan en serie. La configuración y los
resultados de esta revisión están en [retirada de configuración](../../docs/architecture/retained-configuration.md).

## Evidencia y fixtures históricos

`manifest.json` y `research_manifest.json` conservan versiones, prompts, límites
y restricciones del experimento original. `fixture/invoice.py` tiene un defecto
intencional y sus dos pruebas deben fallar antes de la corrección. Es material
sintético; no es código productivo ni una política financiera.

Los resultados anteriores están en `docs/modernization/*-evidence.json` y en
[runtime-evaluation.md](../../docs/modernization/runtime-evaluation.md). Se
conservan también los intentos fallidos. No trasladar sus aprobaciones al estado
actual ni interpretar tamaño de texto como calidad de prompts o consumo facturado.

Las pruebas comunes no requieren login, red ni suscripción. Una evaluación real
usa la suscripción autorizada, nunca una API facturada como fallback, con Ken
publicado, directorio nuevo, límites y comprobación independiente de artefactos.
No repetir una admisión incierta por un timeout de observación: volver al mismo
proceso/recibo y resolver su estado antes de una decisión posterior.
