# Política por proyecto y resultados de CI — E11

Bloque iniciado el **2026-11-07 18:39:36 UTC**, desde `ff1e70f`.
**E11 queda comprobado** con el alcance de esta matriz. Validación final:
**19:02:40 UTC**, **23 min 04 s** desde el inicio; documentación/checkpoint
posteriores excluidos. E09, E10, E12 y el resto del plan permanecen abiertos.

El contraste E09–E12 encontró una brecha en E11: se distinguían los resultados,
pero todos los proyectos compartían la regla de aceptar pruebas ausentes/omitidas
con reconocimiento. Se implementó la elección explícita por proyecto, con revisión,
recibo y control del propietario. [Contrato](../architecture/project-check-policy.md).

| Requisito E11 | Evidencia comprobada |
| --- | --- |
| Diferenciar `passed`, `failed`, `no_tests`, `skipped` e infraestructura | Clasificación y ejecución de pytest real bajo perfil poseído; `test_check_results`, `test_check_execution`. El comando genérico no inventa cantidad de pruebas. |
| Repositorio ausente y comando roto no equivalen a cero pruebas | Nuevo caso de Git real: quitar el candidato rechaza preparación sin crear copia. Ejecutable inexistente se rechaza antes del lanzamiento; comando real con módulo inexistente produce `infrastructure_error`, no `no_tests`. |
| Política explícita por proyecto | Nuevos casos `test_project_check_policy`: sin elección no se acepta; política estricta bloquea ausencia/omisiones; modo flexible exige reconocimiento; ninguno permite fallos. |
| No continuar como aprobado tras agotar arreglos | El cierre nativo no acepta; `CodeAcceptances` mantiene bloqueos por check/revisión y publicación requiere aceptación vigente. Se reutiliza la aceptación E07 de turno acotado/rechazo sin rework automático. |
| Decisión observada, historial y recuperación | Revisión vieja rechazada, recibo original recuperable, rollback atómico, alcance por proyecto y API propietario/CSRF. Política posterior no reescribe una aceptación anterior. Base con esquema 64 anterior creada con el paquete previo para comprobar la migración real. |

Los ensayos nuevos tuvieron tres correcciones de expectativas/datos: longitud de
clave de emparejamiento, ruta de fixture en formato cadena y rechazo del ejecutable
inexistente **antes** del lanzamiento. No se modificó producto para omitir esas
protecciones. Los resultados intermedios permanecen en el directorio de trabajo.

Se conserva el límite de evidencia: generación y proveedor HTTP controlados en
integraciones, testigos sintéticos en ensayos de almacenamiento, Git/SQLite/kernel
reales donde se indica. No hay evaluación de calidad de modelo, comprensión humana,
aceptación de páginas completas, cuenta externa ni nueva suite global.

## Resultados y compatibilidad

Primera selección instalada: **215 pasan, 0 fallos, 0 omisiones**, en 242,618 s.
Después se actualizó un ensayo de revisión que necesitaba expresar la nueva
política del propietario. Sus **3 variantes pasan** desde el paquete final, en
52,693 s. Son **218 casos distintos**, no una suite global. Se compararon ambos
artefactos: los 347 fuentes Python/SQL de producto son idénticos; la diferencia
nativa de recompilación desaparece retirando únicamente debug/build-id. La otra
diferencia es ese ensayo. El paquete final coincide con 653 archivos Python/SQL
del árbol y todos los imports de backend observados proceden de la instalación.

La migración se comprobó sobre una base creada con el **paquete anterior**, en
esquema 64, con aceptación ya guardada. Al pasar a 65, elegir una política estricta
y recuperar la solicitud original, el recibo y su huella siguen idénticos byte a
byte. No se inventó una elección para el proyecto. Integridad y claves foráneas
correctas. Esto usa datos sintéticos, no una base histórica del usuario.

Frontend: **3 pruebas DOM, 4 de contratos y compilación correctas**. Recuperación
tras respuesta perdida conserva el cuerpo y consulta mediante GET; un cambio de
revisión mientras se edita no se adopta silenciosamente. Fallo de almacenamiento
local impide el envío. Se conservan las solicitudes antiguas de aceptación.

**45 definiciones Python** nuevas/modificadas tienen docstrings; los módulos y
helpers frontend relevantes tienen JSDoc. Inventario de prompts: **304 archivos,
85 revisados, 0 pendientes**. Se revalidó el consumidor estático de feedback:
la política importa canonical JSON; no cambia las instrucciones de agentes.
**Cero turnos reales de modelo**. DD113 conserva el pulido de presentación para
la pasada final; no se acepta por esto ninguna página completa.

[Ejecución amplia](project-check-policy-packaging.json),
[verificación final](project-check-policy-final-packaging.json),
[artefactos](project-check-policy-artifact-comparison.json),
[migración anterior](project-check-policy-legacy.json),
[resultados](project-check-policy-results.json),
[docstrings](project-check-policy-docstrings.json).
