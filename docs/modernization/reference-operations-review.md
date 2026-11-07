# Artefactos recuperables: D05

Base `adf04f6`. Inicio real: **2026-11-07 20:15:44 UTC**.
Verificado a las **20:41:51 UTC**: **26 min 07 s** hasta validar, sin incluir
documentación/checkpoint posteriores. D05 queda comprobado con el alcance de esta
matriz. No se aceptan D06–D09 ni la página completa de Archivos.

Se reprodujo una pérdida real: el borrado quitaba los bytes antes de confirmar
la eliminación de su referencia en SQLite. Una transacción rechazada dejaba una
fila descargable cuyo archivo ya no existía. Ahora el commit de la intención y
la retirada del catálogo precede al borrado físico; una interrupción conserva
una operación que se puede consultar y recuperar.

| Frontera | Comportamiento y comprobación |
| --- | --- |
| Informe canónico | El texto completo, sus relaciones y su recibo ya se guardan en una transacción SQLite; la ruta de exportación no es la fuente canónica. Nuevos fallos inducidos al insertar artefacto, informe o recibo revierten el conjunto. El mismo intento confirma después un único informe legible. |
| Carga | La migración 66 registra proyecto, clave, intención exacta, tamaño, SHA-256 y ubicación relativa antes de crear el archivo. La referencia se publica sólo después de verificar los bytes y confirmar su durabilidad. |
| Respuesta perdida | La misma clave y cuerpo recuperan el recibo original sin volver a escribir. Un cuerpo diferente o una clave de borrado se rechazan. Repetir una carga ya eliminada devuelve su recibo histórico y no recrea el adjunto. La web conserva la clave al fallar el envío. |
| Disco lleno, fsync y DB | El fallo no devuelve éxito ni crea una referencia válida. Los restos de una carga registrada se conservan. Una carga incompleta no se publica; el propietario puede cerrar su intento sin borrar los restos ni habilitar una publicación posterior. |
| Proceso interrumpido | Dos hijos reales terminan después de guardar bytes o de hacer unlink. La misma operación queda pendiente; HTTP la reconcilia una sola vez. Los hijos comprueban la huella del módulo ejecutado. |
| Borrado | La retirada del catálogo y su intención se confirman juntas. Un fallo previo conserva fila y bytes. La recuperación sólo elimina la revisión originalmente observada; si cambió, preserva el archivo y deja la operación pendiente. Confirmar ausencia sincroniza el directorio del archivo; un almacenamiento inaccesible no equivale a borrado confirmado. |
| Concurrencia y alcance | Cerrar una carga mientras acaba su escritura impide publicar bytes tardíos. Las claves se resuelven dentro del proyecto, con sesión del propietario y CSRF; consultar el historial no ejecuta recuperación. El borrado de proyecto conserva esta historia. |
| Migración y restauración | La cadena hasta 66 conserva datos y se recupera tras interrupciones. La inversa 66 sólo admite un esquema sin operaciones. Una copia completa conserva cargas pendientes y restos; restaurarlas en otra ruta permite publicar sus bytes verificados. Una intención antigua de borrar no adquiere autoridad sobre el nuevo inode restaurado: se conserva pendiente para revisión. |

La web incorpora «Cargas y borrados», historial paginado, recuperación explícita
y cierre de cargas incompletas. Distingue un recibo histórico de la disponibilidad
actual del adjunto y explica la consecuencia de cada acción. Guardar, consultar o
recuperar archivos no inicia inferencia. Se mantienen los lectores de referencias,
previas, capturas, importación Chroma y archivos de revisión.

## Validación y límites

La reproducción original falló por pérdida de bytes. Tras corregirla pasan 20 casos
iniciales y 103 de fuente ampliados; no se suman porque se solapan. La primera
selección instalada dio 291 pases y 1 fallo histórico: la prueba de inversa 58 se
intentaba sobre un esquema posterior. Se conserva la protección y se comprueba
la importación tanto sobre el prefijo real 58 como sobre el esquema actual.
Los seis casos finales de fuente pasan, incluidos tres fallos de informe y el
rechazo de clave vacía. Tres interacciones DOM, cinco contratos de Archivos y la
compilación frontend pasan. El paquete final pasa **296 casos instalados**, cero fallos y cero omisiones,
en 122,769 s. Los 661 archivos Python/SQL coinciden entre fuente, wheel e
instalación no editable; 351 son de producto. Los 274 módulos backend observados
se importaron desde la instalación, fuera del checkout. No se suman los resultados
de paquetes o selecciones solapadas. SHA-256 del wheel final:
`0e47594bd19ee5e635203253957cfc79af418e9f1061138aab9375db54c58325`.

53 definiciones Python nuevas o modificadas tienen docstrings; los módulos y
funciones frontend relevantes tienen JSDoc en inglés. Inventario: 307 archivos,
85 candidatos revisados, cero pendientes. Tres candidatos cuyo AST no cambió se
revalidaron: el único consumidor afectado añade la conservación del historial de
archivos al borrar un proyecto; no cambia instrucciones ni autoridad del agente.

Alcance: datos sintéticos, SQLite y sistema de archivos reales, API y DOM.
No se ensayó un apagado físico del equipo ni hardware de almacenamiento adverso.
No se promete eliminar archivos cambiados por un escritor externo ni restos de
identidad incierta. Su conservación y una futura política explícita de retención
siguen dentro de D08/D13; no se rebasa automáticamente una intención antigua.
Los huérfanos previos al journal y los datos históricos reales requieren su propia
reconciliación de importación. La presentación integral de Archivos sigue abierta.
Cero turnos reales de modelo; ninguna nueva suite global ni aceptación de página.

[Paquete inicial](reference-operations-packaging.json),
[paquete final](reference-operations-final-packaging.json),
[docstrings](reference-operations-docstrings.json).
