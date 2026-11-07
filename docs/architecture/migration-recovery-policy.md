# Recuperación de migraciones y escrituras posteriores

La recuperación conserva las escrituras del snapshot elegido y mantiene el
original separado. Una copia anterior no contiene cambios posteriores: volver a
ella exige tratar esos cambios como material pendiente de recuperar, aunque la
aplicación vuelva a arrancar. Nunca se presenta ese procedimiento como una
inversa transparente del esquema.

Ejemplo: una copia contiene un informe A. Después de actualizar se corrige A y
se escribe B. Restaurar la primera copia devuelve A sin su corrección y no incluye
B. Para conservar ambos cambios, usar una copia posterior que los incluya o
reparar el original. No basta comprobar que el número de proyectos sigue igual.

## Qué camino existe para cada estado

| Estado observado | Camino admitido | Evidencia que se conserva |
| --- | --- | --- |
| Un paso18–59 se interrumpió antes de su marcador | Abrir de nuevo con la versión compatible; el paso transaccional vuelve a partir del esquema anterior | Misma base, relaciones y datos previos;42 fronteras de interrupción comprobadas |
| Base más nueva que el programa o historial moderno incompleto | Rechazo del arranque/migración; instalar código compatible o inspeccionar/restaurar evidencia | No se falsifican marcadores ni se acepta escritura sobre un esquema supuesto |
| Versiones18–32 y43–56 ya aplicadas | Reparación hacia adelante o restauración explícita de una copia compatible | No hay inversa general publicada; no borrar tablas/columnas para simular una vuelta atrás |
| Versión33, identidad wiki | Inversa sólo si33 es la última versión, su huella demuestra ausencia de escrituras posteriores y no hay colisiones | IDs, relaciones, secuencias y contenido anteriores |
| Versiones34–42, revisión/resultados/desarrollo | Inversas específicas, con el servicio detenido y sus condiciones de ausencia de uso/autoridad | Las admisiones, candidatos, comprobaciones, revisiones y decisiones utilizadas bloquean su eliminación |
| Versiones57–58, procedencia archivada/importada | Inversa sólo sin historial en la tabla correspondiente y sin esquemas posteriores | El historial utilizado exige reparación hacia adelante o restauración explícita |
| Se necesita recuperar una instalación después de nuevas escrituras | Copia actual verificada y restauración a una ruta nueva; reinscripción separada | Datos actuales, archivos, Git y evidencia de autoridad; sin adoptar procesos o repetir trabajo |
| Sólo existe una copia anterior | Restaurarla a otra ruta, con limitación explícita; conservar cualquier original o evidencia posterior disponible | Estado exacto de aquella copia; las escrituras posteriores siguen fuera de ella |

Las inversas de33–42 y57–58 son funciones administrativas con guardas, no un
comando de downgrade universal. Se aplican únicamente sobre su versión y bajo
sus precondiciones; las versiones posteriores deben tratarse explícitamente.
No se declara compatible un binario antiguo por conseguir que una operación SQL
termine. La aplicación actual requiere su esquema actual.

La versión59 conserva el punto de retención de eventos. No tiene una inversa
general publicada: eliminarlo permitiría ocultar pérdida de continuidad. Usar
reparación hacia adelante o una restauración compatible y explícita.

Las implementaciones están en `wiki_migration.py`, `review_migration.py`,
`result_migration.py`, `development_migration.py`, `peer_archive_migration.py` y
`reference_provenance_migration.py`. El catálogo de avance sigue siendo
[`migration_catalog.py`](../../backend/db/migration_catalog.py).
El alcance de cada prueba se conserva en los recibos; no se promete soportar
cualquier avería, combinación de versiones o pérdida física de almacenamiento.

## Recorrido operativo

1. Detener el servicio y conciliar los actores originales. Si cambió el kernel,
   usar el modo explícito de captura tras reboot descrito en la guía.
2. Conservar la instalación y, cuando sea recuperable, hacer una copia actual
   con `backup-host`; ejecutar `verify-backup`. Retener también la copia anterior
   y el paquete/configuración correspondiente hasta comprobar los recorridos.
3. Ejecutar `restore-host` hacia una carpeta nueva. Revisar `data_recovery`:
   identifica el snapshot, indica que las escrituras posteriores no están
   incluidas y distingue esa limitación de una comparación con el original,
que no se realiza automáticamente. Tampoco se supone que el host original siga
disponible: el comando conserva esa incertidumbre incluso si la ruta ya no existe.
4. Ejecutar `enroll-restored-host` con recursos y testigo nuevos. El mismo aviso
   permanece en el resultado y en `enrollment.json`. No se reenvían solicitudes
   antiguas ni se interpretan los procesos copiados como cerrados en otro host.
5. Verificar lectura de tareas, informes y adjuntos, relaciones y repositorios.
   Conservar el original mientras queden cambios posteriores por recuperar.

[Comandos completos y recuperación tras reboot](installation-backup.md).
Si los datos pertenecen al sistema anterior al runtime nativo, seguir primero
[la importación histórica](legacy-import.md), con asignaciones explícitas.

## Metadatos completos con activación acotada

Las nuevas restauraciones usan un recibo pequeño de formato2. Referencia
`details.json` en su mismo directorio por ruta, tamaño exacto y SHA-256; ese archivo
conserva todos los conteos y cambios de rutas, con límite explícito de128MiB.
La configuración y el recibo de activación mantienen su límite de64KiB.
El lector recorre padres y archivo sin seguir enlaces y verifica tamaño, hash
e identidad antes de crear autoridad. Un hash detecta cambios; no autentica a
un operador que controle todos los archivos.

Los recibos pequeños de formato1 siguen siendo compatibles. Si una restauración
antigua produjo un recibo mayor a64KiB, conservarla como evidencia y restaurar
la copia verificada a otra ruta con el productor actual. No editar su recibo para
ocultar datos. Un fallo entre `details.json` y el recibo conserva la carpeta
parcial sin marca de instalación terminada; la recuperación usa otra ruta nueva.

Se detectó y corrigió una inversa wiki que permitía borrar el marcador33 debajo
de34 o58, dejando incompleto el historial moderno aunque no hubiera ediciones
wiki. Dos regresiones exigen rechazo previo y conservación exacta de la base.

La comprobación actual incluye320 adjuntos adicionales, corrupción y enlaces
en metadatos, una salida abrupta real entre archivos, compatibilidad del recibo
anterior y una actualización43→58 con nuevas escrituras. La copia vieja y la
nueva se restauran separadamente y el original conserva los cambios recientes.
[Resultados y límites](../modernization/recovery-policy-results.json).

La ubicación de los datos del propietario continúa pendiente; estos ensayos
sintéticos no equivalen a migrarlos. La aceptación integral del sistema sigue
abierta, incluida la recuperación ante fallos más amplios y los recorridos web.
