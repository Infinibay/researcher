# Inventario visual de la modernización

El requisito completo sigue siendo 36 imágenes independientes de escritorio,
12 adaptaciones móviles, selección y ejecución de las doce rutas. Los componentes
compartidos llevan cobertura adicional. Los números de esta tabla cuentan
archivos generados e inspeccionados, no pantallas aceptadas.

| Ruta | Escritorio / 3 | Móvil / 1 | Selección | Implementación | Aceptación visual |
| --- | ---: | ---: | --- | --- | --- |
| `/` | 0 | 0 | Pendiente | Pendiente | Pendiente |
| `/projects` | 0 | 0 | Pendiente | Pendiente | Pendiente |
| `/epics` | 0 | 0 | Pendiente | Pendiente | Pendiente |
| `/tasks` | 3 | 1 | Lista editorial con inspector | Piloto en código | Pendiente: navegador |
| `/agents` | 0 | 0 | Pendiente | Pendiente | Pendiente |
| `/chat` | 0 | 0 | Pendiente | Pendiente | Pendiente |
| `/wiki` | 0 | 0 | Pendiente | Pendiente | Pendiente |
| `/findings` | 0 | 0 | Pendiente | Pendiente | Pendiente |
| `/reports` | 0 | 0 | Pendiente | Pendiente | Pendiente |
| `/files` | 0 | 0 | Pendiente | Pendiente | Pendiente |
| `/repositories` | 0 | 0 | Pendiente | Pendiente | Pendiente |
| `/flow` | 0 | 0 | Pendiente | Pendiente | Pendiente |
| **Total** | **3 / 36** | **1 / 12** | **1 / 12** | **1 piloto** | **0 / 12** |

Los prompts, archivos, hashes, tamaños y procedencia del piloto están en
[concepts/tasks/manifest.json](concepts/tasks/manifest.json). Las tres alternativas
tienen composiciones distintas y se generaron mediante llamadas independientes
a la herramienta integrada. La variante móvil recibió la imagen elegida como
referencia; no se recortó una captura de escritorio para simularla.

Orden siguiente: comprobar el piloto y corregir densidad/navegación cuando exista
navegador; después continuar con Conversación y las otras diez rutas. Sin acceso
visual pueden prepararse otros briefs, prompts y trabajo del backend, pero no
se declarará la interfaz aprobada por build o por imágenes de concepto.
