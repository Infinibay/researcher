# Cadena de migraciones y recuperación de una interrupción

El arranque conserva los manejadores anteriores a la versión18 y aplica las
versiones18–59 en un único [catálogo](../../backend/db/migration_catalog.py).
El esquema SQL inicial sigue siendo la base histórica17. La versión actual es59:
57 conserva procedencia de procesos archivados,58 la de fragmentos importados
y59 el punto de continuidad perdido por borrados de eventos.

`ensure_migrations(database, existing_only=True)` sigue exigiendo una base
inicializada y avanza hasta la versión actual. El argumento opcional
`target_version` permite detener un avance en una versión concreta entre17 y59
para ensayos históricos o una actualización por etapas. No se expone como modo
de funcionamiento de la web: el runtime actual necesita el esquema actual.

El migrador rechaza un destino inválido antes de crear almacenamiento, una base
más nueva que la instalación, huecos en el historial moderno y un destino menor
que la versión existente. Conserva las peculiaridades de los marcadores antiguos
anteriores a18. Cada paso usa su implementación transaccional original y debe
dejar registrado su marcador de finalización. No se modificaron sus recursos SQL.

Por ejemplo, una base en49 que falla al migrar a50 debe conservar los paquetes
de entrega originales. Al abrirla otra vez se continúa desde49; no se declara50
por haber empezado el trabajo. Una base en56 no puede volver a49 indicando un
destino menor: hacen falta una inversa validada que preserve los datos o una
restauración explícita. El historial utilizado no se elimina para permitirla.

Se comprobó cada frontera18–59 terminando abruptamente un proceso hijo justo
antes de insertar el marcador de versión. En los42 casos se conservaron esquema,
historial, proyectos y tareas anteriores, y se pudo continuar sobre la misma
base. También pasan comprobaciones de integridad y claves foráneas. Este ensayo
abarca un punto de interrupción por versión; no demuestra tolerancia a corte de
energía, cada instrucción intermedia ni migradores concurrentes.

Las pruebas históricas construyen ahora prefijos completos del catálogo. Las
pruebas de versiones antiguas preparan directamente sus registros SQL: usar la
API actual para escribir una base antigua requería tablas que todavía no
existían. Estos registros comprueban conservación y rechazo de borrados, sin
afirmar que hubo inferencia, procesos de agentes o una aceptación real del
propietario. Las pruebas de las operaciones actuales permanecen separadas.

El checkpoint original18–56 conserva208 pruebas de fuente y127 del paquete no editable, ejecutadas
fuera del checkout. Los577 archivos Python/SQL empaquetados coinciden con fuente
e instalación;308 son productivos. Dos pruebas del launcher shell sólo se
ejecutan desde fuente porque necesitan `start.sh`. Los39 contratos Python nuevos
o modificados y los22 módulos afectados tienen docstrings.
[Resultados y fallos anteriores](../modernization/migration-chain-results.json),
[verificación instalada](../modernization/migration-chain-packaging.json).

La comprobación anterior18–58 forma parte de139 pruebas dirigidas de fuente y139
instaladas, con593 archivos Python/SQL coincidentes; no es una suite global.
[Recibo anterior](../modernization/legacy-import-packaging.json).
La cadena18–59 pasa dentro de116 pruebas de fuente y116 instaladas.
[Recibo actual de eventos](../modernization/durable-events-packaging.json).
La [restauración administrada](installation-backup.md), la recuperación tras
reboot controlado y la [importación histórica](legacy-import.md) tienen evidencia
separada. La [política de recuperación](migration-recovery-policy.md) distingue
inversas administrativas condicionadas, versiones sin downgrade publicado y
restauración después de nuevas escrituras. Siguen pendientes el inventario y
migración de los datos reales y la aceptación integral de recuperación.
Ninguna base del propietario fue migrada en estos ensayos. El pulido DD071 y
posteriores permanece para después de las capacidades principales.


La cadena forward18–70 y sus interrupciones de escritor pasan en la selección de
133pruebas instaladas del [recibo de tareas](../modernization/task-creation-packaging.json).
Migración70 conserva recibos de grupos/hitos y permite creación exacta de tareas;
su inversa local rechaza recibos usados y versiones posteriores. No sustituye el
ensayo global pendiente de todas las inversas hasta70. El usuario confirmó que no
hay historial suyo que migrar; no volver a buscar una base de usuario por defecto.
