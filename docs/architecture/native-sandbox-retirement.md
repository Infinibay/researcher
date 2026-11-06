# Un único launcher nativo y retirada de los pods históricos

El producto exige `runtime_profile: "owned-codex-v1"`. Una configuración sin
perfil, con `legacy-codex` o con un perfil desconocido falla antes de acceder a
credenciales, bases o procesos. Sin `INFINIBAY_RUNTIME_CONFIG` sigue disponible
la inspección del producto; iniciar trabajo requiere configurar el runtime.

Se retiran `backend/security/`, `Containerfile.sandbox`, el helper de archivos
de pods y `CodexRuntime`. El módulo `native_inference` conserva únicamente la
sesión compartida y la validación de directorios privados que consume el runtime
con propietario. No se inicia un contenedor por agente ni un limpiador periódico
basado en el estado del roster. Esta retirada no borra directorios de trabajo,
adjuntos, contenedores existentes, sesiones de Codex ni registros históricos.

## Capacidades conservadas

| Necesidad | Implementación vigente | Comprobación relevante |
| --- | --- | --- |
| Fuente de trabajo e identidad | `WorkspaceRegistry`, vista fijada de fuente y copia privada de desarrollo | `test_ken_worker.py`, `test_owned_factory.py` |
| Ejecución, memoria y procesos | `OwnedCodexRuntime`, `PeerBroker`, `ExecutionDomain`; límites explícitos del host | `test_broker_native.py`, `test_execution_domain.py`, `test_peer_broker.py` |
| Ken obligatorio | instalación de `ken-rank` y worker gestionado por el broker antes de abrir el turno | `test_broker_ken.py`, `test_broker_inference.py` |
| Herramientas y resultados | catálogo tipado de negocio y análisis; recibos durables | `test_owned_factory.py`, `test_broker_inference.py` |
| Autenticación de suscripción | token administrado fuera de las fuentes y mediación del host | `test_broker_native.py`, `test_codex_session.py` |
| Stop, pérdida del dueño y cierre | revocación de autoridad y cierre físico observado | `test_execution_domain.py`, `test_peer_broker.py`, `test_codex_session.py` |
| Adjuntos persistentes | `backend/api/config.py`, con `INFINIBAY_UPLOAD_BASE_DIR` conservado | `test_api_paths.py`; ensayo previo de imagen web/API |

La imagen web/API y Forgejo siguen teniendo sus propias funciones de despliegue.
Retirar la imagen de pods no aprovisiona las herramientas del host nativo ni
demuestra todavía su admisión dentro del contenedor web/API.

## Migrar una configuración anterior

1. Conservar las fuentes y datos existentes. No convertir carpetas de agentes
   automáticamente en repositorios autorizados ni reanudar intentos anteriores.
2. Preparar un JSON a partir de [la plantilla vigente](../modernization/runtime-owned.example.json).
   No basta con añadir el nombre del perfil: se necesitan el code-mode host,
   `token_file`, instalación Ken, caché pública, raíz de fuentes, directorio de
   control, padre cgroup delegado y autoridad inicializada explícitamente.
3. Seguir la [inicialización de almacenamiento](../modernization/bootstrap.md)
   y el [contrato del host](owned-product-runtime.md). Conservar el testigo de
   autoridad separado; nunca regenerarlo para ocultar un estado perdido.
4. Guardar el JSON fuera de las fuentes y seleccionar su ruta mediante
   `INFINIBAY_RUNTIME_CONFIG`. Los parámetros antiguos `managed_home`,
   `business_script`, `uv_binary`, `uv_cache` y `api_url` no configuran esta fábrica.
   La composición usa la aplicación que recibe la solicitud y sus grants.
5. Conservar `INFINIBAY_UPLOAD_BASE_DIR` si los adjuntos ya tienen una ubicación.
   Los antiguos `INFINIBAY_SANDBOX_*`, `ALLOWED_BASE_DIRS`, `ALLOWED_COMMANDS`,
   `WORKSPACE_BASE_DIR` y `CLEANUP_INTERVAL_SECONDS` ya no controlan la ejecución.
   Los valores históricos guardados no se eliminan ni trasladan como autoridad.

Los scripts `run_native_boundary.py`, `run_ken_identity.py` y
`run_crash_recovery.py` dependían del launcher retirado y también se retiran.
Sus recibos publicados son evidencia histórica de aquella implementación.
Las pruebas actuales de la tabla cubren el reemplazo con generación controlada
o metadatos nativos sin inferencia; no convierten esos recibos antiguos en una
evaluación real del nuevo despliegue. Las 38 funciones de prueba retiradas
incluyen tres casos de pods antes omitidos: ninguna se cuenta como reparada.

El aprovisionamiento del host, la admisión integral, restore/handoff y la
evaluación real/humana del conjunto siguen pendientes del plan. Véanse los
[resultados de esta retirada](../modernization/sandbox-retirement-results.json).
