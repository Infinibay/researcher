# Autenticación de suscripción gestionada por el host

El transporte nuevo no necesita montar el hogar administrado ni enviar refresh
tokens al ejecutor. `ManagedTokenFile` lee una instantánea privada existente y
`ExternalChatGPTAuth` entrega sólo access token, cuenta y metadato opcional de plan
mediante el RPC experimental del App Server. No admite login por API key ni cambia
de proveedor cuando la suscripción falla.

## Contrato implementado

- La fuente abre sin crear ni seguir el symlink final, comprueba propietario,
  permisos privados, fichero regular sin hardlinks y tamaño máximo de 1 MiB.
  Comprueba identidad/modificación al terminar; rechaza JSON o modo inválido con
  mensajes que no copian el contenido. El objeto de credenciales tiene repr redactado.
- La primera instantánea fija la cuenta de esa conexión. Las renovaciones deben
  conservarla, respetar la retirada de autoridad antes y después de la lectura y
  entregar un token distinto. Hay un máximo predeterminado de dos renovaciones y
  un plazo de ocho segundos. Un error nunca elige otra cuenta ni reenvía un turno.
- La fuente es un puerto asíncrono del host. El adaptador de fichero puede pedir
  renovación a un hook gestionado por éste; sin hook sólo relee estado que otro
  proveedor haya rotado. Releer el mismo token se rechaza: **no implementa OAuth
  ni demuestra renovación por sí solo**.
- `CodexSession(subscription_auth=...)` instala la autenticación después de
  initialize y antes de comprobar la cuenta o crear el hilo. Las conexiones
  actuales sin ese argumento conservan su contrato mientras se migra la fábrica.

```python
source = ManagedTokenFile(host_auth_path, renew=host_owned_renewal)
auth = ExternalChatGPTAuth(source.tokens, active=attempt_is_active)
native = CodexSession(
    rpc, workspace=admitted_workspace, model=selected_model,
    limits=limits, subscription_auth=auth,
)
```

El ejemplo requiere que el host suministre renovación y retiro reales. No es una
instrucción para copiar auth.json al workspace ni para usar una clave de pago.

## Renovación fuera del canal del agente

El SDK puede pedir `account/chatgptAuthTokens/refresh` antes de devolver una llamada
pendiente y sin threadId. El filtrado por hilo no puede atender ese control.
`JsonRpcClient.register_private_request` instala manejadores explícitos antes de
abrir la conexión. Atiende esas peticiones en tareas separadas, con un máximo de
cuatro, sin introducirlas en la cola pública ni contar su respuesta como progreso.
Una notificación malformada de ese método falla como protocolo, sin llegar al agente.

Un fallo del proveedor se redacta y retira la conexión. El cierre físico del
endpoint precede al drenaje/cancelación de los manejadores; Stop no espera a que
termine una lectura o renovación para retirar al ejecutor. Los detalles sensibles
de excepciones no se propagan como causa pública. La sesión conserva sólo un
código acotado de diagnóstico y suelta las referencias a la cuenta al cerrar.

La decisión de enviar también se revalida después de adquirir el lock de escritura,
inmediatamente antes de entregar el frame. Retirar autoridad impide así enviar un
token cuya respuesta ya estuviera esperando en esa cola. La misma comprobación se
aplica al login inicial; cancelar la sesión retira la autorización de renovación.

Las pruebas con un peer determinista verifican renovación durante thread/start y
turn/start pendientes, una sola llamada de turno, cuenta equivocada, token sin
cambios, presupuesto, retirada durante lectura, errores redactados, saturación y
cancelación. Ese peer prueba el protocolo, no una suscripción real.

## Evidencia del SDK real y límite actual

El Codex **0.166.0 real**, dentro del broker y de un namespace de red privado,
aceptó por RPC credenciales **ficticias** y no creó auth.json en su hogar privado.
Después, account/read falló con `workspace routing discovery failed`: necesita
descubrimiento de cuenta a través de la red. Se conserva ese ensayo como negativo
de falta de conectividad; no se convierte en prueba de acceso o entitlement.
No se enviaron turnos ni credenciales reales en estos ensayos.

La [documentación oficial](https://learn.chatgpt.com/docs/app-server) describe el
modo experimental de tokens externos y el callback del host. El esquema generado
por el binario instalado contiene esos campos, pero también una descripción
«internal/unstable». La compatibilidad queda fijada a la versión probada; no se
infiere que otras versiones o rutas OAuth admitan el mismo contrato.

Siguen pendientes el proveedor de renovación real y compartido por cuenta, estado
nativo persistente aislado, TLS/DNS/egress, Ken y negocio en el perfil nuevo,
ensayo real por suscripción y adopción en CodexRuntime/RuntimeService. La composición
administrada y la inscripción del dominio completo de actores también siguen
pendientes. La aceptación de un login local, una cuenta leída y un turno completado
son evidencias distintas; ninguna acepta por sí sola una tarea del producto.
