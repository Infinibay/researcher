# Frontera común para documentos y búsqueda semántica

PDF/HTML/DOCX/CSV/JSON/XML y el encoder local comparten un único cupo por proceso
supervisor. Se conserva hasta reapear el proceso original, también ante timeout,
cancelación y fallo de IPC. Una solicitud concurrente recibe ocupado; no se crea
otro trabajador ni una cola oculta.

Cada trabajador instala restricciones obligatorias antes de importar parsers o
el encoder y antes de leer el documento. Conserva CPU, espacio virtual, plazo,
FDs, tamaño de archivo, entrada/salida y muerte con el padre. No hay dependencias
nuevas ni cambios a los límites por documento o consulta.

## Filesystem, procesos y red

Landlock permite sólo lectura de intérprete, librerías, backend, dependencias y
archivos públicos concretos. Los pesos semánticos siguen llegando por FDs de
sólo lectura verificados. No permite escribir archivos, crear directorios ni leer
contenido privado fuera de esas raíces. Las raíces de código/dependencias son
recursos de confianza del operador: no deben contener credenciales.

Seccomp reutiliza la validación de arquitectura y denegaciones del broker. Añade
bloqueo de fork/clone/threads, exec, señales/controles de otros procesos, IPC del
host, io_uring, ioctl y cambios de permisos/propietario/xattrs/timestamps. Estas
operaciones de metadatos necesitan una barrera propia porque Landlock no cubre
esas familias, según la [documentación del kernel](https://docs.kernel.org/userspace-api/landlock.html).

Se exige Linux x86_64, usuario sin privilegios y Landlock ABI3 o superior; el host
ensayado expone ABI7. Una barrera ausente o fallida termina el bootstrap, sin
fallback. `init-host`/`check-host` consultan esa capacidad sin restringir al
supervisor. La procedencia de extracción/consulta incluye la política del trabajador.
No son namespaces: algunos metadatos del filesystem siguen observables. Es una
política para programas fijos, no una interfaz para ejecutar código arbitrario.

## Comunicación y control

`WorkerBusy` distingue capacidad ocupada de documento inválido: HTTP429 y
`processing_busy`; semántica conserva `retrieval_busy`. La explicación indica que
no se inició otro proceso y que se puede volver a intentar cuando termine el
actual. No hay reintento automático. Stop/corrección conserva la operación
registrada, el pidfd original y la espera física del hijo, independientemente de SQL.

## Evidencia

Bloque **12:02:31–12:21:47 UTC:19min16s**, hasta el corte de validación.

- Primera validación de sandbox/límites:12pruebas aprobadas. Formatos, encoder
  real y host:66aprobadas. Consumidores HTTP/herramientas/hallazgos:30aprobadas.
- Se añadieron rechazo sin fallback y estado HTTP ocupado. Un test consultó
  inicialmente `error` como código; el contrato existente usa `code` y pone la
  explicación en `error`/`detail`. Se corrigió el test sin cambiar ese contrato.
  El corte final reúne **98casos distintos de fuente**, aprobados sin omisiones;
  se conserva la corrida intermedia con ese fallo de expectativa.
- Primer wheel:43pruebas instaladas aprobadas. Wheel final con estado ocupado:
  **44pruebas instaladas aprobadas**, sin omisiones y fuera del checkout.
-614archivos Python/SQL coinciden entre fuente, wheel e instalación.35definiciones
  cambiadas documentadas.83decisiones de prompts vigentes tras revalidar un
  consumidor; catálogo6 y texto de instrucciones sin cambios.

Las pruebas del kernel intentan leer un secreto sintético accesible al UID, crear
un directorio, cambiar permisos, abrir un socket, hacer fork y ejecutar otro
programa después del bootstrap. Todas se deniegan. También se agotan CPU/memoria/
salida, retira autoridad y mata al supervisor, comprobando cierre físico. El encoder
real conserva recuperación con offsets/texto exactos. No hubo turnos de modelo
generativo ni llamadas a la suscripción; sí se ejecutó el encoder local preparado.

Los fixtures antiguos escribían un marcador desde la dependencia. Esa escritura
ahora se prohíbe: el marcador se crea en el bootstrap de prueba antes de aplicar
restricciones. Acredita nacimiento, no entrada al parser. Las pruebas de denegación
se ejecutan después de las barreras reales.

[Corridas](aux-workers-results.json), [paquete](aux-workers-packaging.json),
[docstrings](aux-workers-docstrings.json), [estilo diferido](aux-workers-lint.json).

## Pendientes principales

El cupo es por proceso, no entre instalaciones. RLIMIT_AS limita espacio virtual;
no se convierte en una cuota cgroup de RSS de todo el servicio. Bytes/estructuras
preparados o validados en el padre, títulos HTML extraídos antes del worker,
exportación Chroma, backups/restore, tareas administrativas y recursos remotos
requieren completar su propia frontera. No se declara resuelta la seguridad de
versiones Ken/ONNX/Chroma mediante este aislamiento.

Siguen recursos restantes del supervisor, migración/recuperación de hosts acotados,
comunicación humana/otros perfiles, datos históricos y aceptación de12páginas.
Los43escenarios amplios siguen abiertos; no hay nueva suite global verde.
DD098 conserva estilo/imports para después de las capacidades principales.
No hubo push ni despliegue.
