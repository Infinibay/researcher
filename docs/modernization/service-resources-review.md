# Recursos del servicio principal

El lanzador nativo aplica un presupuesto de CPU, memoria y procesos/hilos al API
y sus descendientes antes de ejecutarlos. La configuración `service_limits`
predeterminada es 2 GiB, 128 procesos/hilos y CPU equivalente a dos núcleos.
El guardián conserva el bloqueo de propiedad y retira el grupo original aunque
el lanzador muera; el recibo guarda identidad, eliminación y contadores reales.
Un cierre pendiente impide otro arranque. No se reutilizan PID numéricos.

El servicio y los actores nativos tienen dominios separados. Cerrar el servicio
no certifica cierre de agentes, aceptación de resultados ni resolución de efectos
remotos. Launcher y guardián quedan fuera del presupuesto para poder observar
y cerrar el grupo. No se presenta esto como sandbox: ejecutan código del host.

Backup adquiere el mismo bloqueo y conserva la exclusión durante la copia.
Restore archiva los dos archivos de control del servicio junto al historial
original; el host nuevo adquiere su propia propiedad. Un recibo pendiente sólo
puede archivarse tras reinicio si coincide con la evidencia de kernel/observador
verificada por el flujo existente; eso no prueba muerte en otro equipo.

## Evidencia

- 56 pruebas dirigidas de fuente y 55 del paquete instalado pasan. La diferencia
  es la prueba de `start.sh`, archivo del checkout que no pertenece al wheel.
  [Corridas y fallos iniciales](service-resources-results.json).
- Los casos de kernel fuerzan OOM real con descendientes, salida de un servicio
  mientras otro espera y SIGKILL del lanzador con un descendiente que hizo
  `setsid()`. Se observa eliminación del grupo y se conserva un proceso ajeno.
- El ensayo instalado usa recursos locales reales y credenciales sintéticas,
  sin inferencia. Original y restore responden por HTTP; el grupo vivo tiene
  memoria de 2 GiB, 128 procesos/hilos y CPU de medio núcleo. Backup en vivo se
  rechaza; después de Stop se copia, restaura, reinscribe y arranca otro grupo.
  Ambos lanzadores salen con 143; bases íntegras y cero dispatches.
  [Resultado](service-resources-host.json).
- 618 miembros Python/SQL coinciden entre fuente, wheel e instalación;
  [paquete](service-resources-packaging.json). Las 34 definiciones nuevas o
  modificadas tienen docstrings; [comprobación](service-resources-docstrings.json).
  Las 83 decisiones del inventario de prompts quedan vigentes: el texto de
  ayuda del launcher no cambió y el consumidor de instrucciones sólo añade la
  política del servicio. Esto no constituye evaluación nueva de prompting.

El primer ensayo de HTTP consultó una ruta inexistente en el script de prueba;
el servicio sí arrancó y se confirmó su cierre físico antes de un ensayo nuevo.
Se corrigió el script para usar `/api/tasks?project_id=101`. El primer ensayo de
cierre ordenado también descubrió una función de Python ausente: se sustituyó
por el binding libc que utiliza el proyecto. Se conservan ambos fallos como
evidencia; no se cuentan como validaciones satisfactorias.

## Alcance restante

Arranques directos de uvicorn y el modo sin runtime nativo no adquieren estos
límites. Las operaciones administrativas externas tampoco comparten su cuota.
Los límites del launcher/guardián, la cuota durable de auxiliares y la recuperación
con disco lleno, pérdida de energía o inodos agotados siguen pendientes principales.
Un guardián que no puede escribir su recibo puede dejar cierre sin confirmar;
no se elimina ese registro ni se inventa una recuperación automática. No se
demuestra aquí el caso de muerte simultánea del launcher y del guardián.

DD101 conserva los 26 avisos de Ruff en los archivos revisados. Son detalles
posteriores a todas las tareas principales. Siguen abiertos 43 escenarios amplios,
0/12 páginas completamente aceptadas y la validación global del plan.

Bloque: **2026-11-07 13:06:07–13:23:38 UTC**, **17 min 31 s** hasta validación.
La preparación del informe y commit queda fuera de ese tramo medido.
