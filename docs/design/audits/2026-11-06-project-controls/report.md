# Controles generales — actividad nativa y solicitudes originales

Alcance comprobado: controles de la cabecera compartida. El engine completo y
la aceptación integral de las doce páginas siguen pendientes.

La cabecera consulta `projectWorkspace`, compartiendo la observación con el
expediente. Una etiqueta `completed` ya no oculta una detención real; `executing`
sin intentos registrados ya no inventa actividad. Una consulta fallida muestra
incertidumbre y bloquea nuevas decisiones basadas en ella. El dato sigue siendo
un registro consultado, no una prueba de proceso vivo ni de cierre físico.

La detención usa el transporte existente: guarda proyecto, clave y alcance antes
de enviar. Recuperar el recibo conserva exactamente la solicitud original, incluso
si comenzó trabajo nuevo. El recibo confirma intención y explica que falta
comprobar el cierre. Sólo un rechazo explícito habilita descartar esa solicitud.
El controlador anterior conserva su cierre en Proyectos; la cabecera enlaza allí
y no usa el POST antiguo sin cuerpo. El inicio de planificación conserva su
solicitud y sólo navega al resultado si todavía está seleccionado ese proyecto.

## Verificación

La prueba de navegador inicial falló: el proyecto `completed` con trabajo nativo
mostraba únicamente planificación deshabilitada. El recorrido final pasa con
siete capturas a 1440/390 px y cero incidencias Axe en cabecera, errores JavaScript
o desbordamientos de ancho. [Evidencia](evidence.json).

- Metadatos `completed` con trabajo nativo y `executing` sin trabajo.
- Respuesta503 de detención, recarga y recuperación con idéntica clave y cuerpo;
  el trabajo nuevo conserva un alcance distinto.
- Planificación pendiente de Beta, selección de Atlas y respuesta tardía de Beta;
  Atlas y la página elegida se conservan.
- Error de consulta distinto de ausencia de trabajo; recuperación manual.
- Controlador anterior visible y planificación deshabilitada hasta su revisión.
- Un rechazo anterior no habilita descartar otra solicitud pendiente guardada
  después desde el expediente; se comprueba la identidad original antes de retirar.

Cuatro POST explícitos: dos de la misma detención, uno de planificación y otra
detención rechazada con 409. Ninguna
mutación automática por consultar o recargar. Fixtures HTTP controlados, cero
modelos, procesos nativos o datos reales del usuario. No se declara una prueba
nueva de terminación física ni de recuperación backend.

**123 pruebas frontend pasan en 1,808 s; TypeScript/Vite compila en 3,96 s.**
Cuatro módulos y 18 funciones nombradas revisadas tienen JSDoc en inglés
([auditoría](jsdoc.json)). Se inspeccionaron las capturas desktop y móvil.
No se repitieron backend, wheel, suite global ni evaluaciones humanas.

La altura móvil y el tratamiento visual de controles quedan en DD045, después
de todas las tareas principales. Las advertencias existentes de bundle grande
siguen registradas. Esta entrega no cambia los 48 conceptos ni convierte los
doce pilotos en páginas integralmente aceptadas.
