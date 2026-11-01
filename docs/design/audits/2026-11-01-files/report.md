# Archivos: punto de partida del rediseño

Base de frontend:312dd7b, sin cambios posteriores en FilesPage. Backend del corte:
7a72fe9. Chromium156 con sandbox, app/API reales y sesión de propietario sintética.
Copia del ensayo de producto retenido más un PDF generado de dos páginas; ninguna
base del usuario, captura nueva de fuente ni inferencia. Se consultó solamente la
lista: no se pulsaron upload, descarga, borrado ni inicio de proyecto.

![Escritorio anterior](before-desktop.png)

![Móvil anterior](before-mobile.png)

La captura de escritorio1440×1024 muestra mezcla de navegación española con Files,
Filename, Download/Delete y fechas relativas futuras. El listado conserva
el archivo, tamaño, MIME y descripción, pero no explica la diferencia entre subir
un adjunto, extraer su texto y usarlo como evidencia en una investigación.

En390×844 la tabla mide631px: el nombre queda partido, el tipo técnico ocupa varias
líneas y las acciones quedan fuera de la zona visible. No hay una composición móvil
con acciones por archivo. La descripción del upload sólo aparece como placeholder;
los estados de teclado/formulario/error todavía necesitan evaluación específica.
No se atribuye comprensión, accesibilidad o fallo de una operación a estas dos
capturas. No hubo errores JavaScript no controlados.

El PDF está subido pero no capturado por un agente. No se puede mostrar «leído»,
«analizado» o «listo para citar» a partir de su nombre/MIME. El contador durable de
inferencia permaneció1 y el informe anterior conservó su cuerpo. El servidor de
fixture se cerró con PID/cmdline/cwd verificados; sesión46831 terminó0.

[Evidencia y hashes](before-evidence.json). El [brief](../../concepts/files/brief.md)
guía las alternativas pendientes. Estas capturas no son conceptos generados, piloto
implementado ni aceptación de la ruta. Inventario visual permanece3 pilotos,
9/36 conceptos de escritorio,3/12 móviles y0/12 rutas aceptadas completamente.
