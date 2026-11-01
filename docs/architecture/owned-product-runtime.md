# Runtime con procesos propios conectado al producto

El perfil explícito `owned-codex-v1` conecta `RuntimeService` y las rutas que usa
la web con `OwnedCodexRuntime`. Reutiliza sus solicitudes, preguntas, correcciones,
leases, entrada congelada, presupuestos y recibos. Codex conserva el loop de
inferencia. El host prepara herramientas y controla su autoridad y ciclo de vida.

```mermaid
sequenceDiagram
    participant U as Propietario / web
    participant S as RuntimeService
    participant O as Fábrica y broker
    participant K as Ken propio
    participant N as Codex propio
    participant A as Mismo API / SQLite
    U->>S: Solicitud explícita con versión de contexto
    S->>O: Intento, workspace, grant y límites
    O->>O: Abrir autoridad existente y dominio nuevo
    O->>K: Preparación, cierre y catálogo obligatorio
    O->>N: Estado propio, autenticación externa y readiness
    S->>S: Congelar entrada y reservar presupuesto
    S->>N: Un turno solicitado
    N->>O: Herramientas dinámicas
    O->>A: Mismas rutas y permisos, mediante ASGI
    U->>S: Stop o corrección
    S->>O: Retirar autoridad
    O->>O: Cerrar dominio, canales y herramientas
    O->>S: Cierre observado después de salir de los scopes
    S->>S: Conservar propuesta/recibos; nunca autoaceptar
```

## Controlador y origen de negocio

La configuración recibe la aplicación real desde su lifespan. Sólo acepta su
misma instancia `LiveGrants`; el store de investigación queda fijado a la DB
seleccionada al arrancar. Las herramientas llaman a esa aplicación mediante
`httpx.ASGITransport`, sin abrir otro servidor de negocio ni elegir un puerto.
Conservan los modelos, límites, autorización y transacciones de las rutas actuales.
El bearer de herramientas queda en el host; no se entrega a Codex ni al análisis.

Cambiar después `INFINIBAY_DB` no redirige esas herramientas. El callback de
autoridad comprueba además dispositivo/inodo del archivo original: una DB copiada
con los mismos tokens vinculados al intento no conserva la autorización viva del controlador. Esto no
certifica restore en sitio, handoff, protección de todas las APIs heredadas ni
inscripción de cada hilo/actor del host; siguen pendientes en el plan.

Cancelar HTTP no deshace una transacción ya confirmada. Se retira el grant vivo
antes del drenaje y se conservan claves/recibos para reconciliar efectos inciertos.
El API sigue sirviendo al propietario cuando se detiene el dominio de trabajo.

## Preparación y Stop

Cada intento usa un dominio nuevo dentro del padre cgroup seleccionado por el
operador y el journal previamente aprovisionado. `NativeState` conserva sus datos
fuera de la fuente. Se prepara Ken bajo el broker, se exige exit0 y cierre antes
de abrir su MCP, y se comprueban las cinco herramientas obligatorias. No se abre
el thread si faltan Ken, el helper o los controles de configuración.

Un supervisor observa pérdida de autoridad también durante la preparación, antes
de que exista una sesión devuelta a `RuntimeService`. Stop/corrección retiran el
grant y cierran el broker completo; no esperan a un `turn/interrupt` que puede no
responder. La cancelación incluye Ken y los comandos, además de la inferencia.

El servicio recibe la prueba de cierre sólo después de abandonar los contextos:
broker retirado y dominio eliminado, negocio/análisis cerrados. También puede
consumirla cuando el arranque terminó por excepción antes de devolver una sesión.
Ese acuse local no es autoridad nueva ni sustituye los recibos globales/source;
perderlo mantiene incertidumbre hasta reconciliar, sin repetir trabajo.

## Análisis con el mismo controlador de comandos

`broker_command_executor` reutiliza `AnalysisTools` y `OwnedCommandExecutor`:
reservas, salida paginada, correlación, deadlines, cancelación y no replay siguen
en el código existente. Cambia el transporte a un peer `command` nativo del mismo
broker, con hogar efímero sin cuenta, fuente readonly y sockets externos bloqueados.
No se conecta ese peer a una suscripción ni inicia un thread de modelo.

`command/exec` usa `externalSandbox` sólo desde el host porque el aislamiento de
kernel ya está aplicado y no puede retirarse por RPC. Los argumentos del modelo
no eligen el perfil ni permisos. No hay fallback de sandbox anidado. El cierre
del transporte proyecta la prueba original broker→source, sin otra señal paralela.

## Configuración y límites actuales

La [plantilla de configuración](../modernization/runtime-owned.example.json)
describe los campos y debe guardarse fuera de los repositorios administrados.
`INFINIBAY_RUNTIME_CONFIG` selecciona ese JSON. No se crea un journal perdido ni se
adopta una DB como autoridad. El aprovisionamiento inicial y la instalación completa
del host todavía requieren el trabajo explícito pendiente del plan.

- `runtime_profile: "owned-codex-v1"` selecciona esta fábrica. Un error no cambia
  al launcher anterior ni a una API facturada por uso.
- La configuración sin ese perfil conserva temporalmente el camino heredado para
  migrar capacidades; retirarlo sigue siendo obligatorio, no está terminado.
- Una autoridad admite una concesión activa; este perfil exige `max_concurrent:1`.
  Esto no completa coordinación entre agentes ni concurrencia multiproyecto.
- La memoria/PIDs son política explícita del host. El ejemplo2GiB responde al OOM
  observado de Ken a512MiB; no es una garantía de capacidad para cualquier proyecto.
- `token_file` aporta snapshots de la sesión CLI administrada. La fábrica sólo
  relee rotaciones externas; token vencido/sin cambio se rechaza. No implementa ni
  demuestra renovación OAuth, coexistencia de cuentas o WebSocket del proveedor.
- El modelo se sigue eligiendo por JSON global con reinicio; faltan selectores web,
  por proyecto/agente y la migración de las demás capacidades del producto.

## Evidencia

La prueba del lifespan real inicia una solicitud por HTTP con sesión de propietario
y CSRF, usa la fábrica configurada y deja `needs_review`. Las rutas de negocio y
SQLite son reales: un finding provisional, un informe draft, un cálculo200 con
recibo de comando y todos los peers cerrados. La generación y Ken de ese fixture
son protocolos controlados; no demuestra inferencia real del nuevo entry point.

Otra prueba usa Codex0.166 real, sin cuenta/modelo, para ejecutar un comando bajo
el perfil nuevo: resultado200, sockets denegados, fuente readonly, credenciales
ausentes y prueba original de cierre. Stop durante preparación y durante turno,
DB copiada/token conservado y configuración sin autoridad también están cubiertos.
El ensayo generativo conjunto anterior sigue siendo evidencia de la composición,
no se vuelve a etiquetar como prueba de este entry point.

El [ensayo posterior por la entrada productiva](../modernization/owned-product-live.json)
usó la suscripción, Codex y Ken publicados reales: un turno, 12 llamadas exitosas,
cálculo200 e informe persistido leído íntegramente. El monitor abortó por contención
de autoridad; los datos y recibos conservados demostraron el resultado y cierre,
y una inspección HTTP posterior, sin runtime configurado, devolvió200/needs_review.
No se repitió inferencia ni se reconstruyeron los picos de memoria/PIDs perdidos.

Faltan bootstrap/operación y restore,
OAuth administrado, recuperación de todo el servicio, migración de71 herramientas,
engine/loops/roles/flows, prompts y comunicación humana, web completa y cierre final.

Evidencia: [contratos](../modernization/owned-factory-evidence.json),
[resultados](../modernization/owned-factory-results.json),
[paquete](../modernization/owned-factory-packaging.json).
