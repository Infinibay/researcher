# Recursos de backup, restauración e importación

Los comandos `backup-host`, `verify-backup`, `restore-host` y `stage-legacy-host`
ejecutan la operación en un proceso de confianza separado. El padre transmite
su salida sin acumularla en memoria, controla el plazo y espera el cierre real
del hijo original. No inicia otro intento ni borra copias parciales.

Antes de importar las dependencias, el hijo instala límites de espacio virtual
(1 GiB), CPU (el `--timeout` solicitado), tamaño por archivo (`--max-bytes`),
descriptores (512), procesos del UID (0 nuevos) y core dumps (0). Conserva cualquier
límite duro heredado que sea menor. El plazo del padre tiene además un fusible
de alarma y el hijo recibe SIGKILL si muere su padre. No se heredan las variables
de cuenta del entorno; las rutas de datos siguen siendo argumentos explícitos.

Las respuestas satisfactorias incluyen `execution_limits` observado en el hijo.
La ayuda permanece sin inicializar datos. Los formatos de backup, recibos
persistentes y barrera `pending_enrollment` no cambian. Un timeout o la pérdida
de la respuesta no prueban que no se haya alcanzado a escribir el marcador final:
el mensaje pide conservar rutas y examinar los recibos antes de decidir qué hacer.

El inventario común ahora aplica el presupuesto mientras lee el directorio,
antes de acumular u ordenar todas sus entradas. La verificación también rechaza
objetos adicionales mientras recorre la carpeta, sin construir primero un conjunto
de tamaño ilimitado. Se mantiene la detección de cambios y el tratamiento de
sidecars SQLite; los datos no se truncan para cumplir un límite.

## Evidencia y alcance

Base `68f6b20`. Bloque **12:29:30–12:41:58 UTC: 12 min 28 s**, hasta validación.

- Una prueba reprodujo el inventario que consumía entradas adicionales antes
  de rechazar el presupuesto. Ahora se detiene en la primera entrada que lo excede.
- Un hijo real rechaza reservar 2 GiB bajo el límite de 1 GiB. Una operación
  bloqueada termina al vencer el plazo; el padre la recoge antes de devolver el
  control y el archivo parcial conserva sus bytes. Matar al padre también termina
  su hijo dormido; no se repite la operación.
- Primera comprobación: 27 pruebas aprobadas. Conjunto ampliado: 85 aprobadas y
  4 fallos de expectativas históricas de migración, ya presentes en
  `current-global-results.json`. Conjunto final administrativo: 28 aprobadas.
  La unión final es **86 aprobadas y 4 fallos conocidos**, sin omisiones.
- Paquete instalado: 47 aprobadas y 1 fallo de preparación del ensayo. El fixture
  coloca credenciales temporales bajo `/tmp`; usar `/tmp` como workspace hace
  que se rechacen correctamente. Un intento con variable de entorno no lo cambió
  porque el fixture la sobrescribe. La corrección fue usar un cwd separado,
  fuera del checkout y distinto del padre de esas credenciales. Pasaron ese caso
  y el comando instalado de importación: **49 casos distintos aprobados** en total.
  No se modificó el producto ni se ocultaron las corridas anteriores.
- 616 archivos Python/SQL coinciden entre fuente, wheel e instalación; 327 son
  productivos. La semilla de desarrollo `db/seeds/dev_data.sql` conserva su exclusión
  previa de la regla de empaquetado `db/*.sql`. No falta una migración productiva.
- 20 definiciones cambiadas documentadas. 83 revisiones de prompts vigentes;
  sólo se revalidó la ayuda humana del CLI. Sin llamadas a modelos ni suscripción.

[Corridas](admin-resources-results.json), [paquete](admin-resources-packaging.json),
[docstrings](admin-resources-docstrings.json), [estilo](admin-resources-lint.json).
DD099 difiere 18 avisos Ruff hasta después de las capacidades principales.

## Lo que continúa pendiente

Son límites de una operación del CLI, no de todas las invocaciones simultáneas,
del servidor web ni de llamadas directas a las funciones Python. El proceso es
de confianza y necesita acceso a sus datos: esta frontera no es un sandbox para
ejecutar código ajeno. RLIMIT_AS limita espacio virtual, no una cuota agregada de
RSS o de caché del kernel para todo el host.

`--max-bytes` y el límite por archivo no equivalen a una cuota de filesystem:
metadatos, journaling y temporales necesitan su propia capacidad agregada.
Siguen como trabajo principal la cuota del exportador separado de Chroma,
recursos del supervisor, migración/recuperación bajo volúmenes acotados, seguridad
de dependencias, evaluación humana, datos históricos y aceptación de las12páginas.
Los43escenarios amplios permanecen abiertos. No hubo suite global nueva, push
ni despliegue.
