# Dominio de ejecución Linux: nacimiento y retirada implementados

El debate con `review_workspace_ownership_design` después de `45d560d` identificó
el siguiente hueco: registrar un PID después de crear el proceso deja un intervalo
en que una caída pierde esa identidad. Marcarlo `prepared` no prueba vacío. Este
incremento implementa una **primitiva de dominio real**, con un ensayo de recuperación
de ese intervalo; todavía no es el broker productivo ni aprovisionamiento del host.

## Decisiones y responsabilidades

`execution_domain.py` abre un cgroup v2 existente y fija dispositivo/inode, boot ID,
namespace PID y namespace cgroup del observador. La comprobación nativa del tipo de
filesystem impide que archivos llamados `cgroup.events` simulen un cgroup.
No crea un dominio por ausencia de estado y rechaza el cgroup del controlador y
sus ancestros antes de cualquier escritura de control. Su identidad debe quedar
en el registro durable externo, independiente de la DB del proyecto.

`_domain_spawn.c` usa `clone3(CLONE_INTO_CGROUP | CLONE_PIDFD)` con SIGCHLD.
El proceso nace en el dominio; no hay fork seguido de migración ni fallback ante
ENOSYS/EPERM. La API es para código de confianza del host, no una herramienta del
modelo. [Semántica de clone3](https://man7.org/linux/man-pages/man2/clone.2.html).

Antes del clone se copian argv/env y se duplican todos los FDs permitidos por encima
de sus destinos. El hijo sólo remapea descriptores, normaliza señales y ejecuta
`execve`: no llama a CPython, allocators ni logging. La espera nativa libera el GIL.
El canal de error de exec tiene CLOEXEC. EOF de ese canal no confirma inicio del
payload ni aceptación de trabajo. Se cierra en exec todo FD no declarado; no se
hereda el entorno del padre. Las pruebas verifican ciclos de remapeo, conservación
de FDs del padre, ausencia de un FD secreto sintético y restauración de señales.

Los FDs que un intérprete abre por sí mismo **después** de exec son distintos de
los heredados: se observó uno propio del runtime de Python para transparent
hugepages. Se corrigió esa suposición del test, no se amplió la herencia del proceso.

## Retirada y arranque concurrente

`retire` retira primero la admisión viva y escribe en el `cgroup.kill` del objeto
fijado, antes de esperar el lock de arranque. Mientras drena constructores repite
el cierre si un nacimiento pudo competir con la primera observación vacía.
Un constructor retirado no entrega transporte al cliente.

Tras drenar, espera `populated=0` y elimina el dominio. Si no puede eliminarlo,
vence el plazo, aparecen descendientes de cgroup o falta visibilidad, no devuelve
un recibo de retirada. No borra recursivamente un árbol desconocido ni considera
un timeout como cierre. Un FD retenido del cgroup eliminado no permite crear un
actor tardío en él. [Contrato de cgroup v2](https://docs.kernel.org/admin-guide/cgroup-v2.html).

La prueba de arranque congelado crea el proceso ya detenido por el kernel antes de
exec. Reprodujo el bloqueo de Stop detrás del lock; ahora la retirada termina sin
descongelar el dominio y el programa de prueba no ejecuta su marcador. Los plazos
NaN, infinitos, negativos y booleanos se rechazan antes de escribir controles.

Cerrar los handles del módulo no certifica retirada. La salida de un proceso
tampoco certifica retirada del dominio. Los resultados y presupuestos desconocidos
deben conservarse por separado en la futura autoridad semántica.

## Ensayo decisivo realizado

El test usa un cgroup privado temporal creado bajo la delegación del propio test,
una DB de proyecto sintética real y el registro testificado externo:

```mermaid
sequenceDiagram
    participant T as Test host
    participant J as Registro testificado
    participant D as Dominio kernel
    participant R as Recuperador separado
    T->>J: Guardar dominio e intención starting
    T->>D: Crear constructor directamente dentro
    Note over D: Hijo setsid sigue escribiendo heartbeat
    Note over T: SIGKILL antes de publicar identidades; DB original eliminada
    R->>J: Leer identidad del dominio, sin PIDs publicados
    R->>D: Retirar y eliminar dominio
    R->>J: Conservar tombstone retired
```

Se comprueba que el hijo sigue vivo después de morir el lanzador y justo antes
de recuperar. El recuperador sólo recibe las rutas del registro global; no recibe
la DB original ni el PID del constructor. Después del cierre no aparece el efecto
tardío. El constructor es una fixture de confianza, sin modelo, diseñada para
ejercitar el intervalo anterior a publicación; **no implementa el gate productivo**.

Los demás casos reales comprueban nacimiento dentro del cgroup, hijo desacoplado,
rechazo de directorio normal, dominio retirado con FD viejo, fallo de exec sin
proceso restante, capacidad de FDs y recuperación desde una identidad esperada.
Resultados: [evidencia](../modernization/execution-domain-evidence.json).

## Instalación y portabilidad

El paquete ahora construye una extensión C Linux y una wheel por plataforma/ABI.
La construcción desde fuentes requiere compilador, headers de Python y Linux,
y setuptools compatible con `ext-modules`. No requiere sudo en ejecución si el
dominio ya está delegado. El host de ensayo tiene Linux 6.18.55, glibc 2.44,
GCC 16.2.1 y delegación writable; se usaron únicamente hijos privados del test,
sin mover al controlador ni modificar otros cgroups, cuentas o servicios.

Prerrequisitos de kernel: cgroup v2, CLONE_INTO_CGROUP, close_range(CLOEXEC) y
cgroup.kill. La versión mínima conjunta es Linux 5.14; también pueden impedirlo
la delegación, seccomp o la visibilidad del despliegue. Esta verificación es de
Linux x86_64/CPython 3.12; otros targets y CI siguen pendientes de aceptación.

## Obligaciones que no resuelve esta primitiva

- **Confinamiento contra migración:** un payload con acceso a cgroupfs o al
  administrador por D-Bus puede escapar. `Delegate=no`, permisos observados o
  esconder una sola ruta no demuestran esa frontera. La primitiva no es sandbox;
  el broker debe imponer y probar el perfil de todos sus ejecutores.
- **Origen y cobertura completa:** un cgroup nuevo vacío no prueba que no haya
  escritores anteriores fuera. Hace falta inscripción externa y dominio completo
  de actores desde el origen o migración comprobada de los anteriores.
- **Broker único dueño de G:** `run_peer` debe ocultar intención, nacimiento,
  publicación global, bind local verificado y apertura del gate. Revocación y G
  tienen que serializarse; el cliente nunca debe conservar el extremo que abre G.
- **Autoridad semántica:** concesión global, generaciones, autenticación,
  reconciliación de respuesta perdida, tombstones y liberación durable. Un
  `DomainClosure` no es por sí solo permiso para otra concesión.
- **Integración:** PeerRegistry, todos los constructores/escritores heredados,
  presupuestos, restauración/handoff y herramientas mutables productivas.

El incremento cierra un hueco de nacimiento/recuperación del dominio de ensayo.
Conserva pendientes las obligaciones completas del plan y no habilita edición.
