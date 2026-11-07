# Acceso y aislamiento actuales: D10–D12

Inicio **2026-11-07 22:06:26 UTC**, base `dd1be91`.
La selección instalada está en [el recibo](isolation-acceptance-packaging.json);
el cierre y duración se registran en [resultados](isolation-acceptance-results.json).

Verificado **2026-11-07 22:36:15 UTC**, **29 min 49 s** desde el inicio
hasta verificar, sin documentación/checkpoint posteriores. **232 casos instalados
pasan, cero fallos y cero omisiones**, en 288,637 segundos. Los 674 archivos
Python/SQL coinciden entre fuente, rueda e instalación; los 279 módulos backend
importados proceden del paquete instalado. Se cierran D10–D12 con el alcance
de esta matriz: **34/43 escenarios comprobados, nueve abiertos**.

Esta entrega contrasta los tres escenarios contra la arquitectura actual y
refuerza su aceptación. **No añade otro motor o capa de aislamiento**: los
[360 archivos de producto Python/SQL](isolation-acceptance-artifact-comparison.json)
coinciden exactamente con el artefacto verificado de D08. Cambian tres pruebas y
la evidencia. Los pendientes descritos por documentos de etapas antiguas no se
convierten automáticamente en cambios necesarios de la arquitectura vigente.

## Fronteras y escenarios

| Escenario | Recorrido actual y comprobación |
| --- | --- |
| D10: herramienta que intenta actuar como dueño | `OwnerAccessMiddleware` separa cookie/CSRF de bearer. Las rutas de herramientas usan `ResearchContext`; el servidor deriva alcance del grant, sin aceptar proyecto/tarea/actor del modelo. La prueba recorre todas las rutas de producto registradas y comprueba rechazo de HTTP/WS con bearer de herramienta. El SQL interno y las otras rutas históricas no existen ni para el dueño autenticado. |
| D10: usar autoridad vieja o copiada | `SQLiteResearchStore._check_scope` verifica grant, permisos, versión de contexto, lease, fence e intento vigente dentro de la transacción. La fábrica fija la DB y comprueba su identidad física mediante la autoridad del controlador. La prueba de reemplazo por copia con los mismos datos rechaza la credencial; la retirada viva también impide leer o repetir un recibo anterior. |
| D11: IDs o nombres homónimos | La aceptación nueva usa un intento registrado en la fábrica configurada, sin cookie humana. A puede leer su informe y capturar su adjunto; no puede leer el informe ni capturar el adjunto homónimo de B. Sustituir alcance por query/body se rechaza. Los intentos rechazados no crean fuentes; la captura legítima deja una única fuente. |
| D11: enlaces, rutas o contexto ajeno | Los lectores del host resuelven IDs registrados dentro del proyecto; `BoundedReferenceReader` y la importación de archivos fijan directorios y rechazan escapes/symlinks. Los perfiles del broker sólo reciben la vista de fuente/copia admitida, sin el árbol completo de uploads o la DB. Los casos prueban enlaces de archivo/directorio, traversal, repositorio ajeno y preservación del contenido externo. |
| D12: código de desarrollo o CI que busca secretos | Los comandos de desarrollo operan en la copia privada; análisis y Ken mantienen sus vistas restringidas. `CheckCapsule` ejecuta CI en otra copia, con metadata Git y dependencias elegidas en lectura. El ensayo reforzado crea credenciales ficticias, datos ajenos y un archivo de origen existentes, y pasa una API key ficticia al entorno host: el hijo no puede leer esas rutas ni la DB, heredar la key o escribir metadata/origen. |
| D12: exfiltración o uso del canal de inferencia | Código/CI no obtiene sockets de Internet. El perfil nativo usa namespace de red propio, el proxy del host y destinos admitidos; las pruebas verifican denegación de acceso directo al host, sockets/control de peers y descriptores heredados. La credencial de negocio queda en el host y fuera del catálogo. El proveedor de suscripción mantiene su canal privado, rotación acotada, cancelación y errores sin secretos; esos permisos no se transfieren al comando de código. |

El flujo concreto es propietario → coordinador → intento/grant → perfil del
broker. La inferencia conserva su propio transporte. Una llamada de negocio
vuelve a la **misma aplicación ASGI** y a su DB fijada; una llamada de código va
al peer de comandos del broker. CI selecciona una receta del host y otra vista
de trabajo. El argumento de una herramienta no elige un perfil más permisivo.

## Evidencia nueva y reutilizada

Las dos pruebas dirigidas pasan. La primera ejecución conservó un fallo del
fixture: faltaba `artifacts.file_path`, obligatorio incluso para contenido
canónico retenido. Se completó el registro histórico de ensayo; no se relajó el
esquema ni se cambió el backend. La prueba CI exige que sus rutas de prueba
existan antes de ejecutar: la ausencia de un archivo de fixture no demuestra
aislamiento. Sólo se usan canarios ficticios.

El primer ensayo instalado conservó82casos correctos y un fallo del ensayo de
memoria por `FileNotFoundError` sin nombre de archivo. El caso aislado y los94
casos de su mismo prefijo pasan sin cambios. Una segunda selección conservó106
casos correctos y un fallo cuya traza identifica `cpu.max` ausente durante la
configuración del dominio. El padre del entorno perdió el controlador CPU;
60muestras consecutivas confirmaron `memory pids` sin `cpu`. El comportamiento
fue rechazo antes de ejecutar sin límite, no un permiso degradado.

La validación final corrió bajo `systemd-run --user --scope
--property=CPUQuota=800%`, con unidad temporal que retiene la disponibilidad del
controlador y desaparece al terminar. No se modifica el producto ni la
configuración persistente del host. El recibo registra CPU, memoria y PIDs disponibles antes/después.
El requisito de CPU ya pertenece al contrato de instalación. El primer fallo
podría compartir causa, pero no se demostró; DD119 conserva esa incertidumbre y
la precondición para la suite global. Se mantienen los recibos
[inicial](isolation-acceptance-initial-packaging.json) y
[anterior al ámbito estable](isolation-acceptance-before-cpu-scope-packaging.json).

Con CPU estable,116casos pasan antes de que el verificador corte a30segundos
una integración completa de preparación, captura y dos comprobaciones de CI.
El diagnóstico aislado muestra avance cada5segundos y termina correctamente en
31,12segundos. Se asigna a ese único test un plazo de120segundos que abarca el
recorrido completo; no se modifica ningún límite de producto. El
[recibo anterior](isolation-acceptance-before-check-diagnosis-packaging.json)
conserva el timeout y sus116casos correctos. La selección final incluye y supera la
misma integración con el plazo declarado, sin omitirla.

La selección instalada cubre 24 familias/casos de middleware, API histórica,
permisos y recursos, adquisición, parser, fábrica, comandos, Ken, desarrollo,
CI, red/proxy, proveedor/sesión privada, imports de archivos y exploración de
repositorios. Los hashes permiten distinguir evidencia de producto sin cambios
de las nuevas pruebas de aceptación. Las selecciones solapadas no se suman.

Las [tres definiciones nuevas o modificadas](isolation-acceptance-docstrings.json)
tienen docstrings en inglés y sus módulos ya están documentados. No se modifican
prompts, dependencias ni frontend; el inventario estático anterior no se convierte
en una nueva evaluación de eficacia. Los ensayos previos de suscripción/Ken
conservan su alcance histórico; no se gastó otra generación para repetirlos.

## Límites

Estos escenarios comprueban las fronteras declaradas, no certifican seguridad
frente a todo adversario. Kernel, filesystem, Git y transportes locales son reales
en los casos que los ejercen; la generación, el protocolo Ken, las cuentas y los secretos son
controlados. La prueba nueva de grant usa el intento/DB/controlador reales, sin
abrir un turno generativo; las ejecuciones nativas se comprueban en las demás
familias. No se usa la suscripción ni se llama a cuentas externas.

El operador y los assets/recetas admitidos del host son confiados. Un archivo que
el propietario incluya deliberadamente dentro de la fuente autorizada es entrada
del proyecto; esto no promete detectar todos sus secretos. Los sistemas externos
de CI no quedan bajo este kernel: la ejecución que realiza Researcher se controla
por su perfil propio. No se presenta la bandera del runtime como aislamiento por
sí sola ni se atribuye autoridad a una etiqueta de estado.

La selección no sustituye la suite global, la migración de datos históricos,
aceptación visual integral o comprensión humana. No hubo cambios visuales que
justifiquen generar conceptos o repetir la compilación web en este bloque.
Sigue D13, con backpressure y recuperación/restauración; los detalles quedan al final.
