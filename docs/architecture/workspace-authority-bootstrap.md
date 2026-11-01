# Bootstrap y restauración de la autoridad de workspaces

Revisión de diseño con `review_workspace_ownership_design`, continuada desde su
revisión independiente con contexto limpio. Es una **propuesta de contrato**, no
una autoridad global, broker o mecanismo de restore ya implementados.

## Separar dos problemas

La [vista fijada del peer](pinned-peer-workspace.md) impide que un rename cambie
su directorio admitido. La [autoridad global](workspace-authority-design.md) debe
decidir quién puede actuar, conservar esa decisión tras una caída y cerrar actores
aunque falte su DB original. Resolver el primero no demuestra el segundo.

La autoridad propuesta tiene una concesión mutable única por cuenta/host y un
journal separado de las DB de proyectos. Es una serialización explícita con coste
de concurrencia. Las lecturas del propietario continúan disponibles. Otro
observador no crea una autoridad independiente: debe acceder al mismo servicio
o recibir incompatibilidad, para evitar dos autoridades sobre los mismos archivos.

## Origen verificable

Dos paths vacíos no prueban que sea una instalación nueva. Un segundo archivo de
estado tampoco prueba que no existan procesos anteriores. La inicialización
necesita una frontera externa que controle todos los nacimientos y pueda conservar
cerrado ese gate mientras demuestra vacío su dominio completo de actores.

Una opción es un broker administrado por el host con un subtree de ejecutores
de cgroup v2. Debe controlar todos sus lanzadores y evitar que los ejecutores
salgan del dominio. Una cuenta de servicio dedicada desde su creación es una
posible forma de establecer esa frontera; no se creó ni se instaló una aquí.
Otro adaptador puede servir si aporta las mismas pruebas. Un subtree nuevo vacío
no demuestra que una cuenta interactiva existente no conserve escritores heredados
fuera de él.

El kernel expone si un cgroup y sus descendientes contienen procesos vivos y
ofrece cierre del subtree que trata forks concurrentes. Es útil sólo junto con
el gate y el dominio completo; no concilia efectos remotos.
[Contrato de cgroup v2](https://docs.kernel.org/admin-guide/cgroup-v2.html).

La condición de génesis propuesta es: instalación/host/observador provisionados;
gate de nacimientos cerrado; dominio completo vacío; ninguna inscripción anterior
sustituida por archivos ausentes. Se inscribe primero una génesis durable y única,
y se completan SQLite y testigo antes de abrir el gate. Una caída deja inscripción
pendiente recuperable, no permiso para inventar otra instalación.

En este host se observaron cgroup v2 y permisos de control en el subtree de usuario; **no se demostró un
dominio que abarque a todos los actores de Researcher**. No se trasladaron procesos,
se escribió cgroup.kill ni se instalaron servicios. Enumerar `/proc` por nombres,
argv o paths no sustituye esa prueba. Tampoco se pide al usuario que afirme cierre.

## Testigo anterior al efecto

El testigo vive fuera del dominio de restauración tanto de las DB de proyectos
como de la SQLite de autoridad. No basta colocarlo en otra carpeta del mismo
snapshot. Su estado propuesto incluye:

```text
COMMIT(authority_id, generation, sequence, state_hash)
PREPARE(next_sequence, previous_hash, deterministic_delta, next_state_hash)
```

El hash cubre el estado real canónico: concesión, generaciones, identidades de
peers, fences y tombstones. Bajo el mutex se verifica SQL contra COMMIT, se escribe
y sincroniza PREPARE, se aplica la transacción SQL durable, y se escribe/sincroniza
COMMIT. Sólo después se autoriza el efecto, especialmente G. La creación de los
archivos y sus directorios también necesita sincronización.

| Estado observado | Operación permitida |
| --- | --- |
| SQL coincide con COMMIT n | Continuar desde ese estado. |
| SQL n y PREPARE n+1 válido | Completar la delta hacia delante, sin ejecutar efectos. |
| SQL n+1 coincide con PREPARE n+1 | Completar COMMIT del testigo, sin reenviar G. |
| SQL anterior a COMMIT, adelantado sin PREPARE o hash distinto | Bloquear y conciliar; no adoptar el estado por tener un contador mayor. |
| Falta SQL o testigo después de inscripción | No reinicializar vacío. |

Así se detecta un restore de SQLite sobre el mismo inode. Si SQL y testigo vuelven
juntos al mismo prefijo válido, el software local no puede distinguirlo de aquel
histórico. Cubrir rollback completo del host/VM requiere una referencia monotónica
externa a ese rollback. La primera versión debe declarar este límite; no prometer
detección integral con dos archivos locales.

## Integración y pruebas que faltan

El módulo profundo de autoridad debe ocultar mutex, secuencias y orden de commits.
PeerRegistry publica la identidad completa globalmente antes de local/G. Revocar
impide nuevas publicaciones/efectos; el cierre usa la identidad global aun sin DB
original. Sólo se libera con pruebas de cierre de todos los actores. Un resultado,
presupuesto o efecto externo desconocido no desaparece por cerrar los procesos.

Se requieren pruebas de dos inicializadores; carrera vacío/spawn; escritor legado
fuera del dominio; observador/visibilidad incompatibles; restore SQL/testigo por
separado y en conjunto; caída en PREPARE/SQL/COMMIT/G; DB original perdida; `setsid`;
G tardío con revocación; testigo perdido; handoff repetido con respuesta perdida y
presupuestos conservados. Los tests de providers simulados sólo prueban el protocolo,
no una frontera de despliegue del host.

Las skills de sistemas de datos y diseño de módulos orientan dos decisiones:
representar explícitamente commit, efecto y conocimiento incierto, y mantener ese
protocolo dentro de una operación semántica de autoridad. El coordinador no debería
conocer ni reconstruir una transacción distribuida entre dos SQLite y un testigo.

Este contrato conserva el objetivo completo. El primer
[almacenamiento testificado](witnessed-authority-journal.md) ya está implementado
como núcleo de apertura de estado previamente aprovisionado, con pruebas de
crash/rewind y recuperación de namespaces independientes de la DB del proyecto.
No está integrado en el broker/PeerRegistry productivo. Aprovisionamiento, dominio
completo de actores, migración de escritores, restore y aceptación siguen pendientes.
Las herramientas mutables no se habilitan por este núcleo de almacenamiento.
