# Continuar una preparación Git interrumpida

Desde la preparación de fuentes, el propietario puede **Autorizar reparación de
etapas faltantes** después de detener o revisar una operación local. Es una nueva
autorización vinculada a la operación y al intento observado. No repite un clone
sobre su destino ni borra la carpeta para comenzar de cero.

La web explica el alcance antes de ese gesto. Ejemplo: si el usuario añadió
`notas.txt` después de detener, la reparación conserva ese archivo. Una creación
puede obtener su primera revisión vacía; una clonación incompleta puede recuperar
archivos que faltan. Registrar la fuente no incorpora los cambios locales a un
commit ni los da por aceptados. El resultado muestra esa distinción.

## Intención, identidad y reenvío

`POST /api/projects/{project}/source-operations/{key}/repair` recibe únicamente
`repair_key`, `operation_id` y `fence`; hereda el acceso owner y CSRF. No recibe
comandos, credenciales, rutas nuevas ni pruebas de cierre aportadas por el cliente.
`prepare_repair` guarda el alcance antes de programar su worker. Se conservan como
máximo ocho autorizaciones y ocho observaciones previas, dentro del presupuesto
completo existente de metadata; no se borra historia para hacer lugar.

Un reenvío idéntico devuelve el estado y la autorización conservada, incluso si su
worker sigue activo. La misma clave con otro fence es conflicto. La autorización
se liga a un nuevo lease administrativo real, con su intento/fence, y a la
asignación privada original. No se inventa una tarea, un turno de modelo o un
registro de repositorio para conseguir autoridad de escritura.

El navegador guarda `SourceRepairPacket` antes del POST. Una respuesta tardía debe
contener la autorización original; no basta con recibir un resultado de otra
fuente o de otro fence. Recargar sólo consulta. Una autorización anterior sólo se
reemplaza mediante otro gesto explícito cuando el usuario ya puede observar su
reconocimiento y cierre local. El historial entre navegadores todavía requiere
su propio recorrido de selección y recuperación.

## Tres clases de evidencia de cierre

| Estado original | Evidencia utilizada | Qué no se supone |
| --- | --- | --- |
| Hubo comandos admitidos | Concesión y comandos originales en el journal testificado; recuperación/retirada física y proyección de sus identidades | Un PID cualquiera o un proceso principal terminado no certifica sus descendientes |
| Se abrió un dominio pero nunca se reservó una concesión | `DomainClosure` real del broker original, constructor drenado y retirada; testigo `source:unused-domain:<id>` sellado con alcance/base/intento/dominio originales | La mera ausencia de una concesión o carpeta no certifica cierre |
| No se entró en un dominio | Recibo del control de flujo original drenado; dueño/fence/base coincidentes, sin dominio ni peers. Si ni siquiera se admitió dueño, se conserva `never_claimed` sin inventar un intento original | No se marca `domain_removed=true` para un dominio inexistente |

`_source_lease` conserva el resultado real si una cancelación interrumpe la entrega
del hilo SQLite. El helper genérico `_settled` drena ese hilo, pero no devuelve el
lease al llamador cancelado. Perder ese dato dejaba una preparación sin manera de
probar su alcance previo al dominio. La entrega específica ahora drena y registra
el alcance que realmente se creó.

`source_executor` conserva el dominio dentro de su scope, incluida una cancelación
al publicar su identidad antes del primer G. Si el broker nunca reservó, registra
la retirada física original en el journal antes de proyectarla en SQLite. Ese
testigo no es una concesión nueva ni libera la concesión activa de otro dominio.
Las pruebas existentes de Stop antes de SQLite y de recibos antiguos se mantienen.

Un registro viejo que perdió su dominio y carece de una prueba testificada válida
sigue sin cerrarse por suposición. Copiar/restaurar una base tampoco transfiere
sus identidades. Resolver esa historia retenida requiere el trabajo de migración/
restore del plan completo.

## Inspección y ejecución permitidas

La observación sigue siendo de sólo lectura. Puede examinar una carpeta detenida,
pero **un checkout incompleto no se registra como si fueran archivos que el usuario
hubiera eliminado**. Una copia sucia necesita recibos de etapas completas o una
reparación explícita. Una copia limpia y completamente observada puede reconocerse
sin repetir sus escrituras. La prueba reproduce el antiguo falso positivo y
comprueba que permanece pendiente antes de reparar.

`begin_observation(..., repair_key=...)` archiva el intento original y conserva su
asignación privada para la continuación. Una observación previa monta esa carpeta
readonly; no pierde la referencia al destino privado que una reparación posterior
necesita verificar. Los campos locales anteriores a `remote_server` se normalizan
sólo después de comprobar el cierre original, para que un grant antiguo se compare
con el alcance con el que fue emitido.

El nuevo stage fijo `repair` ejecuta `source_repair_program.py` bajo el mismo broker
y dominio de Git. El hash del programa queda en `SourceGitLaunch` y se revalida antes
del G. El broker comprueba también la clave de reparación contra el alcance owner
original. El programa tiene argumentos fijos derivados del request validado; no
ofrece shell ni comandos elegidos por el usuario o un modelo. Hooks/helpers y
configuraciones que puedan redirigir ejecución o transporte se rechazan o quedan
sujetos a la política Git fija. El driver conserva los límites del dominio; el
stage dura como máximo15s local o60s con red, con subcomandos de35s y salidas
completas limitadas. No se presenta como presupuesto total del flujo SQLite/red.

- **Crear:** si faltan metadatos, `init` conserva los archivos. Si falta HEAD y no
  hay contenido preparado en el índice, se crea un objeto de commit inicial vacío
  con el marcador original y se publica su ref mediante comparación con ref
  inexistente. No se añade un commit sobre una rama que apareció entre tanto.
  Si HEAD ya existe, la observación exige la revisión inicial original; no la
  reemplaza. Un índice con trabajo preparado detiene la creación inicial.
- **Clonar:** no se vuelve a ejecutar `clone`. Si falta un commit completo, se
  consulta la rama explícita o el HEAD simbólico del remoto original y se descargan
  sus objetos sin forzar refs existentes. Sólo se restaura un origin ausente;
  un origin distinto se conserva y detiene la reparación. Sólo se prepara un índice
  ausente. `checkout-index --stdin -z`, sin fuerza, recibe las rutas que faltan;
  archivos ya existentes, incluso modificados, se conservan. Un índice irresoluble,
  metadatos redirigidos, un padre symlink o submódulos detienen ese recorrido.
- **Adoptar:** continúa siendo observación de la carpeta existente. No inicializa
  ni descarga ni cambia origin como sustitución de una adopción fallida.

Las condiciones de creación de refs y checkout sin reemplazo se contrastaron con
los manuales oficiales de [update-ref](https://git-scm.com/docs/git-update-ref),
[checkout-index](https://git-scm.com/docs/git-checkout-index) y
[fetch](https://git-scm.com/docs/git-fetch). La evidencia de funcionamiento es Git
real bajo el aislamiento del proyecto; esos manuales por sí solos no prueban el
flujo completo.

Si la descarga original no dejó un commit, no se afirma conservar una versión
que nunca quedó demostrada. La nueva autorización observa la rama actual del
remoto y el recibo muestra el SHA obtenido; puede diferir del primer intento.
Un HEAD local ya existente se conserva.

## Qué pasaría si…

| Situación | Resultado observado |
| --- | --- |
| Stop antes de admitir un dueño | La continuación crea su primer dueño real; la historia anterior sigue sin dueño/attempt/dominio ficticios |
| Cancelación durante claim o allocate | Se drena la entrega original y conserva el recibo previo al dominio; luego puede continuar explícitamente |
| Stop antes del primer comando | El dominio vacío se cierra físicamente y su testigo permite continuar |
| Stop después de init y el usuario añade un archivo | Se completa la primera revisión vacía; el archivo queda fuera del commit, conservado y explicado |
| Clonación detenida antes de descargar o antes del checkout | La continuación obtiene la rama solicitada/predeterminada observada o hidrata sólo lo que falta; conserva archivo editado, config, índice y commit cuando ya existían |
| El usuario preparó contenido antes del commit inicial, cambió origin o redirigió `.git` | Se rechaza esa reparación sin modificar ese estado |
| Se pierde la respuesta HTTP de reparación | La web recupera el mismo resultado al recargar, con una única autorización enviada |
| Se intenta observar un checkout parcial como si estuviera listo | Sigue pendiente; no se fabrica un registro con borrados atribuidos al usuario |

## Evidencia y trabajo pendiente

[Resultados](../modernization/source-repair-results.json),
[paquete](../modernization/source-repair-packaging.json),
[docstrings](../modernization/source-repair-docstrings.json) y
[recorrido web](../design/audits/2026-11-06-source-repair/report.md).
Las capturas corresponden al caso de creación después de init; las variantes de
clonación y cierre temprano se comprueban por API/kernel. No equivalen a un ensayo
humano completo ni a aceptación de toda la página.

Siguen abiertos: selección de historia desde otro navegador; resolución explícita
de reservas/adopción cuando el usuario transformó la fuente fuera del alta inicial;
entrega interrumpida antes de programar un repair ya guardado; fuentes con formatos
especiales, reconstrucción de metadata para clones SHA256, submódulos y presupuestos
globales; restauración de historias antiguas sin prueba de cierre. El plan completo,
los43escenarios, las12páginas y la suite global siguen sin aceptación integral.
