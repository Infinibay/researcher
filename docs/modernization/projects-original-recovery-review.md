# Aceptación acotada de Proyectos sobre su intento original

**Proyectos completa su aceptación técnica y visual delegada.** La continuación
instalada vuelve al intento español fallido original desde su expediente, lo
recarga y regresa al mismo proyecto. Preserva mensaje, tarea, run, fuente y
presupuesto. No admite trabajo ni envía otra inferencia. [Recibo](projects-original-recovery-results.json),
[capturas y pasos](../design/audits/2026-11-08-projects-original-recovery/report.md).

La comprobación utiliza el wheel actual de la
[corrección CLI](regression-cli-packaging.json) y el frontend existente. La primera
ejecución actualizó explícitamente el host sintético de esquema 68 a 71: 162 tablas
conservan sus hashes de filas originales y cuatro tablas nuevas quedan vacías.
El historial conserva sus filas anteriores y añade 69–71. El fallo posterior de
ese verificador fue una consulta 401 antes de completar emparejamiento; permanece
guardado. La continuación se hace sobre el mismo host, ya en 71.

La lectura completa pasó en **9,229 s**, de 13:46:32 a 13:46:41 UTC; la inspección
y preparación anteriores no forman parte de ese cronómetro. Cuatro estados,
siete comprobaciones y cero infracciones regionales axe, overflow o errores JS.
Las tres fuentes conservan sus bytes; siguen cuatro ejecuciones, cuatro intentos
y un único dispatch anterior, con cero peers y grants abiertos. El servicio
actual terminó 143. Cierre del servicio y registros actuales de peers son hechos
distintos del mensaje histórico que decía no haber confirmado el cierre.

La evidencia se suma al recorrido español/Ken ya comprobado, al expediente y
recuperación de operaciones anteriores. Stop conserva su prueba UI de respuesta
perdida y su prueba instalada de kernel/broker por separado. No se presenta como
una sesión única ni como nueva generación del plan fallido.

La revisión del [gate correctivo](../superpowers/plans/2026-11-08-native-preparation-contention.md)
es explícita: exigir causa antes de modificar autoridad permanece; producir una
corrección causal no es condición para aceptar este alcance de recuperación.
**AuthorityBusy no está corregido ni explicado.** Su incidente permanece visible.

Con esta evidencia, 12/12 páginas tienen aceptación técnica/visual por alcance.
Siguen 42/43 escenarios: U08, comprensión humana, seguridad/distribución y controles
finales no se cierran con capturas. Densidad, etiquetas y encuadre se registran en
DD148 para después de las capacidades principales.
