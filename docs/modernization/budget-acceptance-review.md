# Aceptación de E08: trabajo observable y presupuesto compartido

**E08 queda comprobado**, conservando los límites de observación que exige el
propio plan. Base0587a5a; bloque **2026-11-07 18:09:42–18:17:59 UTC**,
**8 min 17 s hasta validar**. Documentación/checkpoint posteriores excluidos.
No se declara completado el plan ni otro escenario por esta aceptación.

El requisito original es presupuesto por operación, intento y proyecto; incluir
las llamadas observables; un dueño para concurrencia/retry; consumo desconocido
explícito; ninguna alternativa de proveedor por cuota agotada. Su origen concreto
era inferencia auxiliar en resúmenes/guardrails fuera del presupuesto. La fase2
permite medición ausente si se declara y se mantienen límites verificables de
tiempo y trabajo. No convierte esos límites en facturación física garantizada.

| Requisito | Implementación contrastada y evidencia |
| --- | --- |
| Operación, intento y proyecto | CodexSession aplica plazo, no-progreso, turno, herramientas y tokens observados. SQLiteRunStore reserva preparación antes de Ken/runtime y congela después la entrada exacta sin contar doble. AuxiliaryBudget reserva operación/CPU por proyecto e intento antes de parser/encoder. Pruebas preparation_budget, aggregate_execution_budget y auxiliary_budget. |
| Resúmenes y validaciones incluidos | Las rutas generativas antiguas fueron retiradas. Investigación, planificación, desarrollo y revisiones pasan por RuntimeService y el único turn/start estático. Las revisiones requieren nueva solicitud/cupo. Los builders de entrada no invocan un resumidor. Inventario AST297módulos, pruebas de retirada/revisión y evidencia previa deE07. |
| Ken y herramientas observables | Ken es herramienta dinámica del host: CodexSession reserva identidad antes del callback; BrokerInferenceSession valida/refresca catálogo y ProjectTools despacha KenTools/DevelopmentKen. Preparación inicial ya tiene reserva del proyecto. Comandos/checks usan operación original, límites y dominio del intento. La unión de solicitudes/avisos no cuenta duplicados ni permite repetir efectos. Pruebas host_tool_budget/owned_tool_budget y presupuesto de preparación. |
| Un dueño de concurrencia y retry | Admission lock y dueño de host limitan trabajos por proyecto/host. Broker rechaza otra concesión global activa; workers locales retienen su plaza hasta cierre. Dos pruebas nuevas comprueban rechazo antes de preparar, dentro del mismo proyecto y entre proyectos. Terminar el primero no activa silenciosamente el rechazado. HostSubscription comparte un refresco acotado entre conexiones. |
| Desconocido distinto de cero | Tokens ausentes siguen None y conservan techo; observaciones menores no devuelven cupo. Auxiliares sin CPU medida mantienen reserva; resultados completos se recuperan sin repetir. Historial original, continuación explícita y permisos de copia restaurada preservan consumo. Web distingue preparación/envío, CPU local, cuota desconocida y CPU global no consolidada. |
| Cuota agotada sin proveedor alternativo | Ensayo nuevo con runtime/procesos/broker/SQLite reales y generación controlada: el hijo devuelve failed por cuota, se conserva un intento/un turno/modelo original y1000tokens retenidos sin medición. Reenviar la misma solicitud recupera la original, no ejecuta. No hay otra sesión/proveedor, herramientas ni grants vivos. Autenticación exige cuenta de suscripción y la sesión exige proveedor OpenAI. |

## Evidencia actual y reutilizada

- Tres casos nuevos desde fuente pasan. El fixture añade exclusivamente una rama
  controlada de cuota; no cambia el backend de producto ni usa una cuenta real.
- **64casos instalados,0fallos,0omisiones**, en41,696s.647archivos Python/SQL
  coinciden con wheel/instalación;344de producto;237módulos sólo desde el paquete.
  Incluye los casos nuevos y las fronteras de preparación, herramientas,
  autenticación/refresco, presupuesto local e historial.
- Se compararon los **344archivos Python/SQL productivos** con el paquete anterior:
  son idénticos. Sus163pases siguen como evidencia de recuperación/restauración,
  migraciones, input y coordinador para esos mismos fuentes. No se suman ambos
  conjuntos como si fueran pruebas distintas.
- Cinco pruebas DOM y build pasan para la explicación ampliada. Se reutiliza la
  evidencia previa de API/historia; no se repitió navegador ni aceptación de página.
- Inventario AST actual:297módulos, un literal ejecutable turn/start; sin imports
  de las seis familias retiradas ni llamadas de los patrones generativos buscados.
  El stub warmup sigue inerte. Distribuciones antiguas/SDK de pago ausentes en el
  entorno inspeccionado. La búsqueda estática tiene su alcance exacto registrado.
- Dos nuevas definiciones Python tienen docstring inglés. Inventario de prompts
  sin cambios:302archivos,85candidatos revisados,0pendientes. Cero turnos reales.

[Paquete](budget-acceptance-packaging.json), [inventario](budget-acceptance-inventory.json),
[resultados](budget-acceptance-results.json), [docstrings](budget-acceptance-docstrings.json),
[preparación](preparation-budget-review.md), [presupuesto local](auxiliary-budget-review.md),
[continuación](auxiliary-continuation-review.md), [restauración](auxiliary-restoration-review.md).

## Límites conservados y criterio de alcance

La CPU de cada dominio puede quedar en el journal del broker y aparece en errores
de agotamiento; el panel no ofrece un total completo de CPU de Ken/runtime/servidor.
Ahora lo dice expresamente. Contar solicitudes y herramientas, con plazos y límites
físicos, no equivale a sumar esa CPU ni a garantizar una factura. La administración
confiable de instalación/backup tiene sus propios controles; no es inferencia de
agentes por fuera del proyecto. La medición universal de CPU era una mejora
inferida durante la auditoría, no un nuevo criterio explícito de E08. Mantener las
obligaciones de observabilidad, operación y evaluación del plan en sus escenarios.

Los avisos de herramientas nativas pueden llegar después del efecto. Las llamadas
internas del proveedor sólo son observables cuando el runtime las informa; no se
promete controlar o medir lo oculto. El ensayo de cuota demuestra la reacción del
host al fallo recibido, no fuerza un agotamiento real ni estudia reintentos internos
del proveedor. Tampoco demuestra calidad de modelos, comprensión humana, facturación
ni cuota global entre copias. No se convierte ninguno de esos casos en prueba aprobada.

La explicación genérica de ciertos errores nativos se anota enDD112 para mejorar
al final, sin repetir ahora el rediseño de errores ni el ensayo de cuotas. El estado
failed y la reserva conservada sí están comprobados. La última suite global con
fallos sigue siendo la referencia histórica; no hay nueva suite global verde.
