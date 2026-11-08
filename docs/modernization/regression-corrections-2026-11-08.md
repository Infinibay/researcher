# Correcciones dirigidas de la regresión actual

La aceptación de código desde CLI ya envía la revisión de política que el
propietario observó con `/code` y exige esa misma revisión en el recibo. Era una
incompatibilidad real del consumidor con la API actual. Las guardas del backend
se conservan. [Resultados y recibos originales](regression-corrections-2026-11-08-results.json),
[cambio acotado](../superpowers/plans/2026-11-08-terminal-check-policy-acceptance.md).

La matriz dirigida reúne **220 casos distintos con resultado final aprobado**.
Conserva las ejecuciones anteriores, incluidos los fallos durante la investigación;
no suma los casos repetidos como progreso adicional. Los 26 fallos y el error de
fixture del corte global anterior tienen comprobación dirigida de sus contratos
corregidos. **Todavía falta una nueva suite global única** sobre el árbol final.

## Qué cambió y por qué

- **Política observada en CLI:** dos casos nuevos fallaron primero: faltaba el
  campo en la petición y se aceptaba un recibo con otra revisión. Ambos pasan
  después de enlazar petición y recibo al estado observado. Los paquetes pendientes
  anteriores se recuperan mediante `/retry` sin reconstruirlos.
- **Preparación del recorrido de terminal:** se importa su fixture de dependencia
  `schema_target`; la observación espera también `cancelling`. La prueba elige por
  HTTP propietario una política explícita `allow_missing`: su aserción ejecutada
  es un comando, sin presentarla como una suite de tests. Mantiene el reconocimiento
  de límites y comprueba cuatro turnos controlados, cierre y fuente sin publicar.
- **Presupuesto de pruebas:** los nueve timeouts originales pasan con código y
  fixtures intactos bajo un límite diagnóstico de 90 s, con duraciones de
  19,7–23,4 s. Se añadieron límites de 60 s exclusivamente a esos recorridos
  compuestos; los nueve vuelven a pasar usando los decoradores definitivos.
- **Inversas históricas:** los seis tests parten ahora de prefijos coherentes
  65 o 68 y remigran explícitamente hasta ellos. Conservan rechazo de historia
  utilizada y de esquemas posteriores. Pasan los seis casos iniciales y los
  143 de sus módulos, consumidores y cadena de migraciones.
- **Observación de SQLite:** los tests de contención instrumentan la transacción
  real de `SQLiteRunStore`, antes de su `BEGIN IMMEDIATE`. Los hijos de prueba
  terminan alrededor del commit mediante el `__exit__` que utiliza ese contexto;
  sobrescribir `commit` no observaba ese recorrido. Se conservan las exigencias
  de atomicidad de tarea/evento y respuesta de health, WebSocket y Stop.
- **Lecturas y fixtures:** se separa reconciliación al iniciar del efecto de una
  consulta o archivo de conversación. Se prueba reemplazo físico de la base,
  declarando explícitamente el host sin runtime, en lugar de suponer que todos
  los modos reaccionan igual a una variable de entorno. El emparejamiento del
  evaluador crea su archivo durante el inicio que pretende observar; el roster
  usa su contrato síncrono y la fixture de planificación espera la entrega actual.

La revisión independiente confirmó la causa del bloqueo de terminal en su
observación durable: revisión confirmada, comprobaciones válidas y política sin
elegir. No era una carrera deducida del teardown. Detectó además el campo omitido
por CLI; el bloqueo correcto y el defecto real se trataron por separado.

## Paquete instalado

El build limpio usa sdist y luego wheel, sin reutilizar un directorio de build
anterior. **43 casos instalados pasan**, sin fallos ni omisiones, en 54,034 s.
Los 262 módulos backend observados vienen del entorno instalado; las 698 fuentes
Python/SQL, incluidos 371 archivos de producto, coinciden con fuente, sdist,
wheel e instalación. Las 83 distribuciones instaladas son compatibles.

El wheel incluye la extensión CPython 3.12 y los avisos legales actuales, con
bytes idénticos a sus fuentes. [Recibo instalado](regression-cli-packaging.json).
No hubo turnos de suscripción: generación y Ken están controlados en estas
pruebas; HTTP, SQLite, Git y fronteras de procesos son reales. Es validación
Linux/CPython 3.12, no una nueva matriz universal ni aceptación humana.

Diagnóstico y corrección hasta la verificación fuente: **12:55:21–13:17:04 UTC,
21 min 43 s**. Documentación y empaquetado posteriores se registran por separado.
La observación histórica de CLI sin política necesita renovar `/code`; su mensaje
de recuperación queda en DD147, sin alterar paquetes pendientes antiguos.

Continúan recuperación de Proyectos, integración o decisión sustentada de
dependencias, comunicación humana, docstrings y demás detalles diferidos, y los
controles finales. Este bloque no modifica 42/43 escenarios ni 11/12 páginas.
