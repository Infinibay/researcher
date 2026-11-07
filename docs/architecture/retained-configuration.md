# Configuración retenida y runners de evaluación

6 de noviembre de 2026. Cambio sobre `38c08eb`. El objeto `Settings` pasa de
85 opciones a las diez con consumidores productivos observados. Se retiran
75 opciones, la derivación de embeddings desde el proveedor LLM y el cargador
de `.researcher/settings.json`, sin consumidores productivos. No se borran
archivos de configuración, datos, historiales ni preferencias del usuario.

| Configuración retenida | Consumidor y propósito |
| --- | --- |
| `DB_PATH`, `MAX_RETRIES`, `RETRY_BASE_DELAY` | Conexión SQLite y reintentos ante bloqueo; se conservan aliases y resolución de rutas |
| `FORGEJO_API_URL`, `FORGEJO_TOKEN`, `FORGEJO_OWNER`, `WEB_TIMEOUT` | Cliente y vistas de Git del propietario que todavía los consumen |
| `RETRIEVAL_ASSET_DIR` | Recuperación semántica con recursos locales explícitos |
| `WEB_RPM_LIMIT`, `WEB_ROBOTS_CACHE_TTL` | Política existente de acceso a fuentes web |

Las opciones LLM, embeddings derivados, loop, autonomía, TUI y herramientas
retiradas no seleccionan el runtime actual. `Settings(...)` rechaza esos campos
como argumentos; variables antiguas del entorno no se leen como configuración
productiva. Los secretos Spider/Context7 siguen sus lectores nativos separados.

Modelo, esfuerzo, límites de ejecución, recursos y autoridad permanecen en
la configuración explícita `owned-codex-v1` y en las preferencias versionadas
globales/proyecto/agente. Las pruebas conservan selección por intento y control
de revisión concurrente. [Configuración de modelos](model-configuration.md),
[preparación del host](native-host-installation.md).

Los valores Forgejo retenidos atienden consumidores concretos de la API de Git;
no conceden autoridad de publicación al agente. La publicación nativa mantiene
su origen, cuenta, credencial de archivo y CA explícitos en `remote_publication`.
No se unifican credenciales ni se deriva autorización de una variable antigua.

## Migración de una instalación existente

1. Conservar el archivo histórico y la base. Este cambio no realiza una
   restauración ni importa valores desde `settings.json`.
2. Declarar los diez ajustes retenidos que necesite el servicio mediante el
   entorno `INFINIBAY_`; los aliases de base siguen vigentes.
3. Configurar la ejecución mediante el perfil nativo y elegir el modelo en su
   superficie actual. No trasladar `LLM_API_KEY`, defaults Ollama ni flags del
   loop anterior. La inferencia sigue usando la suscripción autorizada.
4. Comprobar la instalación con las herramientas de diagnóstico vigentes.
   Re-enrollment tras reboot y restauración sobre datos reales siguen pendientes.

## Runners y evidencia

El chequeo del MCP dejaba de avanzar porque exigía once herramientas. Ahora
comprueba el contrato de capacidades y los esquemas relevantes: el proceso
real expone 45 herramientas, sin llamar a un modelo ni conceder autoridad real.

El helper HTTP compartido usa el Python instalado que lo invoca, aislado con
`-I`; no impone `.venv/bin/python` ni cambia globals de configuración en el hijo.
Los paths de adjuntos y web se pasan por su contrato actual. No hereda una
configuración de runtime incidental; exige un perfil nativo explícito antes de
crear el almacenamiento del ensayo. No aprovisiona recursos o autoridad por
suposición. La prueba real de acceso local pasa con cero turnos: comprueba HTTP,
Host/origen, CSRF, WebSocket, separación de grants y cierre de sesión/servidor.

**La migración de todos los runners continúa abierta.** Los escenarios de
turnos, Stop, preguntas, continuidad, pérdida del padre e inspección de un
ensayo previo necesitan llevarse a fixtures nativos vigentes. Su código y sus
recibos históricos se conservan; la guía ya no los presenta como comandos de
aceptación actuales. [Inventario y rutas vigentes](../../evals/runtime/README.md).

[Resultado de configuración, paquete y pruebas](../modernization/configuration-retirement-results.json).
Se retiran diez funciones de test dedicadas al escritor global eliminado; no se
cuentan como fallos reparados. La fixture de flows deja de parchear autonomía
retirada. Los avisos de estilo se conservan en DD067, después de las capacidades
principales. No hay suite global nueva, nuevos turnos de modelo, migración de
datos ni aceptación de las doce páginas en este corte.
