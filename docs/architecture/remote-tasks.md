# Decisiones de publicación remota en Tareas

Después de comprobar una publicación local, Tareas permite observar el servidor
registrado y pedir **por separado** push, creación de PR e incorporación de la
versión aceptada. Aceptar código o crear un PR no autoriza el merge.

La interfaz sigue el piloto visual elegido para Tareas: tipografía, superficies,
contraste y controles existentes, sin una página nueva ni otra dirección visual.
El diagrama de tres pasos muestra qué requiere decisión y qué ocurrió realmente.

## Observar antes de preparar una escritura

«Comprobar destino registrado» consulta identidad numérica del repositorio y SHA
de las ramas mediante HTTP acotado del host. El propietario sólo elige las ramas;
no introduce IDs internos, URL arbitraria ni credenciales. El origen HTTPS procede
de la configuración del operador y la URL de clone del registro del repositorio.
Se comprueba la aceptación/origen antes y después de la lectura. La consulta no
crea un run, no usa inferencia y no concede permisos de publicación.

Si la rama de la versión contiene un SHA distinto de la base o head aceptados,
se pide elegir otra rama. Si la rama de destino del PR cambió respecto a la base
revisada, se explica que hace falta revisar esa base; no se incorporan cambios
nuevos por suposición. La ejecución vuelve a comprobar sus precondiciones reales.

## Solicitudes originales y recuperación

Antes del POST se guarda el cuerpo completo con su clave, publicación local,
predecesor, contexto y head exactos en sessionStorage. Una respuesta debe coincidir
con todos esos datos para cerrar la solicitud local. Una respuesta perdida o una
recarga conserva el paquete; reenviarlo recupera el run original. El historial
guardado también puede resolver una admisión que coincida exactamente.

Una escritura incierta muestra un ejemplo concreto: el servidor pudo aplicar el
efecto antes de perderse la respuesta. «Comprobar qué ocurrió» guarda otro comando,
con intento y fence originales, para un observador nuevo de sólo lectura. Perder su
respuesta conserva ese mismo comando. No se ofrece el control genérico de
recuperación de inferencia para publicaciones del host.

Los estados distinguen solicitud en cola, operación en curso, recibo comprobado,
incertidumbre y efecto histórico después de retirada. Un merge con Git aplicado
y registro del PR desconocido se presenta como tal. La UI no aprueba otra versión
ni habilita la repetición de esa etapa. [Contrato de recuperación](remote-recovery.md).

## Fronteras HTTP

- `POST /api/projects/{project}/code-publications/{local}/remote-preview`:
  cuerpo estricto `target_ref`, `base_ref`, pairing/CSRF; sólo lectura remota.
- `GET /api/projects/{project}/code-publications/{local}/remote-publications`:
  historial guardado de esa publicación, sin conexión remota ni reintentos.
- El workspace expone `runtime.remote_publication` sólo si el adaptador configurado
  declara esa capacidad. Un runtime ausente conserva lectura del historial.
- Las acciones y la recuperación usan las rutas estrictas del
  [runtime remoto](remote-runtime.md). Credenciales, paths, actores y pruebas de
  cierre se derivan del host.

El historial muestra las últimas100 operaciones y declara truncación. En ese caso
se bloquean decisiones nuevas; no se toma una lista incompleta como ausencia.
La paginación integral y la selección de cadenas antiguas quedan registradas.

## Verificación y trabajo restante

[Resultados](../modernization/remote-tasks-results.json),
[wheel](../modernization/remote-tasks-packaging.json),
[Python](../modernization/remote-tasks-docstrings.json),
[TypeScript](../modernization/remote-tasks-jsdoc.json) y
[auditoría visual](../design/audits/2026-11-05-remote-publications/report.md).
Pasan92 pruebas backend,92 del wheel y80 del frontend/build. Nueve estados de
navegador cubren escritorio/móvil y pérdida de respuesta/recarga de publicación
y recuperación. Sus efectos y pruebas físicas son sintéticos explícitos;
la integración TLS anterior es evidencia separada de Git/HTTP reales.

La capacidad central de Tareas está conectada. Se pasa a coordinación y cutover
legacy sin ampliar ahora el pulido de este panel. Siguen en alcance adopción tras
retirada, continuidad explícita de etapas no emitidas, instancia real de Forgejo,
crashes ampliados, migraciones/restore y aceptación completa de todas las páginas.
