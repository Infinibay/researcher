# Explorador de fuentes y revisiones

La ruta Repositorios implementa el explorador elegido entre tres conceptos y una
adaptación móvil. Cada proyecto tiene su registro; cambiar de proyecto desmonta
selección, borradores, lectura y revisión. Registrar una carpeta reutiliza el
paquete original de `ProjectWorkspace`, su comprobación de raíz y recuperación
tras respuesta perdida/recarga. No llama al alta genérica antigua ni envía una
solicitud a un rol retirado. Sólo registra una carpeta ya existente.

El explorador resuelve una rama a un commit completo y fija ese valor para árbol
y contenido. Consultar otra vez las ramas no cambia el archivo abierto: actualizar
su revisión es explícito. Respuestas de archivo cuyo path/blob no coinciden con
la entrada elegida rechazan antes de renderizar. Código es texto literal; Markdown
permite consultar su texto original. Carpetas implícitas se reconstruyen aunque
las entradas lleguen desordenadas. Los nombres se codifican en las URLs.

Los lectores Git locales devolvían SHA abreviado y ocultaban fallos como lista
vacía. Además, Git podía descubrir un repositorio padre desde una carpeta ordinaria.
Ahora exigen que `--show-toplevel` coincida con la fuente seleccionada, devuelven
SHA completo y diferencian error de referencias vacías. Se reutiliza la política
Git sin credenciales/configuración global, hooks, textconv, diffs externos o pager;
las llamadas tienen deadline15s. Árbol usa delimitación NUL para no transformar
nombres Unicode/saltos de línea; blob conserva SHA-1 o SHA-256 según el formato
real. Son consultas del propietario mediante el lector existente, no concesiones
para ejecutar código de un modelo ni prueba de aislamiento de todos los procesos.

La vista de revisiones conserva estado histórico, tarea, rama y copias registradas.
Comprueba el proyecto del enlace de origen y abre su tarea exacta; ninguna etiqueta
approved transfiere aceptación/publicación al motor nuevo. Anotaciones siguen el
hilo original; una respuesta incierta exige consultar el hilo y preparar otra
anotación explícita, sin reintento automático. No se afirma idempotencia remota.

En móvil alternan registro, árbol y archivo. Abrir un archivo espera su respuesta
o error antes de desplazar y enfocar el panel; no deja sólo la cabecera visible.
La identidad de fuente/revisión queda en el panel. Regresar restaura foco en la
fila elegida. Código desplaza sólo su propia región y conserva navegación teclado.

El alta completa sigue pendiente: crear local, clonar, crear remoto y reparar con
propiedad/recuperación reales. `RepositoryManager.init_repo` y su API antigua aún
pueden crear remoto/cambiar origin/forcepush; deben reemplazarse. El ejecutor nativo
actual necesita un intento de desarrollo y una fuente ya admitida: fabricar una
tarea para el setup sería autoridad falsa. Resolver esa frontera es el siguiente
bloque principal. También quedan presupuestos de lecturas grandes, concurrencia
del lector síncrono, metadatos especiales/submódulos y aceptación integral. No se
presentan como resueltos por este piloto.

[Resultados](../modernization/repositories-results.json),
[QA y comparación](../design/audits/2026-11-06-repositories/report.md).
