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

## Escenarios que aún deben migrarse o revalidarse

| Runner conservado | Alcance que falta comprobar con el runtime vigente |
| --- | --- |
| `run_research.py`, `serve_infinidev_research.py` | Comparación directa de candidatos, entorno y política de herramientas; no aceptación del producto nativo |
| `run_product.py` | Dos turnos de investigación y corrección; su configuración construida corresponde al prototipo y ahora falla temprano |
| `run_product_stop.py`, `run_conversation.py`, `run_questions.py` | Stop, instrucciones y preguntas con recursos/autoridad de una instalación nueva |
| `run_analysis_inference.py`, `run_input_continuity.py` | Cálculo y continuidad atribuida entre turnos; no copiar una autoridad anterior para construir otra instalación |
| `run_commands.py`, `run_parent_loss.py`, `run_analysis_tools.py` | Sustituir la ejecución directa del prototipo por el broker/dominio nativo y volver a observar efectos y cierre |
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
