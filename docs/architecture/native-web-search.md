# Búsqueda web nativa y evidencia capturada

El perfil `owned-codex-v1` utiliza la búsqueda del mismo Codex que ejecuta el
turno por suscripción. Conserva Ken publicado como requisito y el dueño durable
existente. No añade otro loop LLM ni un proveedor alternativo oculto.

## Configuración y admisión

En el JSON del operador, `web_search` admite `disabled`, `cached`, `indexed` y
`live`. El perfil de producto utiliza `live` cuando se omite. El modelo sigue
siendo el `model` configurado; este cambio no añade un selector web. Ejemplo:

```json
{"runtime_profile": "owned-codex-v1", "model": "gpt-6.1-sol", "web_search": "live"}
```

Es sólo el fragmento relevante; la configuración completa requiere los demás
campos de [runtime-owned.example.json](../modernization/runtime-owned.example.json).
Cambiarla requiere reiniciar el servicio. La política viaja hasta el proceso
nativo, queda en su manifiesto y se compara con `config/read` antes de abrir un
thread. Los peers de comandos y diagnóstico mantienen la búsqueda desactivada.
No se amplía su red ni se les entrega la cuenta.

Con búsqueda habilitada, `modelProvider/capabilities/read` debe declarar
`webSearch=true`. Una respuesta negativa impide abrir el thread: no se inicia un
turno ni se cambia de proveedor. Esa capacidad no prueba la autorización efectiva
de cada modelo/cuenta ni garantiza una consulta exitosa. Los errores posteriores
siguen siendo errores del turno original, sin reintento de inferencia automático.

El estado nativo congela también el modo junto al modelo, catálogo e instrucciones.
Cambiarlo no permite reanudar como si fuera el mismo intento. Un recibo antiguo
sin ese campo tampoco se completa mediante una suposición: requiere reconciliación,
sin recrear ni repetir la solicitud anterior.

## Qué se conserva y qué significa

`RuntimeService` conserva los eventos `webSearch` de inicio/finalización mediante
`SQLiteRunStore.observe_native`, con proyecto, tarea, intento, fence y versión del
contexto originales. Se recuperan por la paginación autenticada ya existente de
`GET /api/projects/{project_id}/runtime-events`. No hay una nueva base ni migración.

Cada observación incluye proveedor, modo, consulta, acción, identidades de thread,
turno e item, URL candidatas observadas, hash del item recibido y truncamiento.
Los resultados estructurados son opcionales: `not_supplied` significa desconocido,
no cero resultados. `supplied` tampoco certifica resultados completos o correctos.

La normalización hace como máximo 256 visitas recursivas y ocho niveles; conserva hasta
10 URL HTTP(S) diferentes de campos `url`, `link` o `href`, también de la acción.
Rechaza credenciales en la autoridad de la URL y URL cuya representación JSON supera 2048 bytes, contando escapes. Acota
consulta/consultas/patrón; omite campos arbitrarios, snippets y títulos. El parseo y el hash leen el item completo dentro del límite de mensaje del RPC. El registro
no conserva todo el JSON del proveedor ni ofrece páginas de resultados omitidos.
`truncated=true` declara esa pérdida; el hash identifica el item observado, sin
permitir reconstruirlo ni certificar su contenido. No se promete recuperar una
URL ausente del evento o fuera de ese límite.

Los datos siguen siendo contenido externo no confiable. Una observación tardía
se conserva en el contexto original sin restablecer permisos ni iniciar otra
captura. Stop cierra el dominio original; las búsquedas comparten el presupuesto
de items, tiempo, progreso y tokens de la sesión. Son fusibles observados: no
pueden deshacer una búsqueda ya enviada ni predecir consumo aún no informado.

## Del descubrimiento al borrador

```mermaid
flowchart LR
    Q[Consulta nativa observada] --> U[URL candidata recuperable]
    U --> C[Captura de fuente con permisos actuales]
    C --> R[Lectura de snapshot y límites]
    R --> F[Hallazgo provisional con cita exacta]
    F --> D[Informe borrador para revisar]
```

Buscar no crea fuentes ni hallazgos. La URL seleccionada pasa por
`researcher_capture_web` o `researcher_capture_paper`, con los controles y recibos
existentes. El texto guardado tiene su propio hash; las citas deben coincidir con
ese snapshot. Un marcador de cita nativo, una similitud o un resumen de búsqueda
no sustituyen la captura. La revisión independiente sigue pendiente.

El [ensayo real](../modernization/native-search-live.json) verificó una búsqueda y
una apertura, URL recuperable → captura → cita exacta → finding provisional →
informe draft, con la suscripción y Ken publicado. Conserva versión/modelo,
consumo observado y cierre; no demuestra todos los modos, modelos, cuentas,
recuperación en frío ni evaluación de comprensión humana. Tampoco añade una
vista web dedicada a las observaciones del buscador.

## Referencias de configuración

El esquema del Codex 0.166.0 instalado se comprobó localmente antes del ensayo.
La [referencia oficial de configuración](https://learn.chatgpt.com/docs/config-file/config-reference)
describe los modos de búsqueda. Sus filtros de dominio son distintos de las reglas
de red de comandos; este cambio no añade filtros de dominio configurables.
Las [limitaciones oficiales de autenticación por suscripción](https://developers.openai.com/siwc/token-sharing-open-source/preview-limitations)
indican que la búsqueda depende del modelo y de la política de cuenta/workspace.
La disponibilidad concreta aquí se sostiene con el ensayo, no sólo con esas páginas.
