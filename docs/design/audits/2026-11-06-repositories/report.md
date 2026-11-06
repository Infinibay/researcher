# Repositorios: exploración verificada, ciclo de alta pendiente

Resultado de este alcance: passed para exploración/registro existente; aceptación
completa de la página y del producto pendiente. Tres alternativas desktop y una
móvil generadas/inspeccionadas; se seleccionó la primera por delegación del usuario.
[Prompts, procedencia y selección](../../concepts/repositories/manifest.json).
[Comparación conjunta](comparison-desktop.png): referencia1487×1058 y captura
real1440×1024, ambas normalizadas a900px sin alterar su proporción. Se revisaron
lectura, tipografía, ritmo, colores, calidad y copia. Se preservan registro lateral,
árbol/documento, papel/tinta/verde y acciones explícitas. Diferencias justificadas:
datos reales, controles de registro existente, raíz y límites desplegables y
texto literal del código; números de línea/sintaxis y densidad de rutas quedan
como pulido. No se copian los éxitos ficticios ni enlaces remotos inventados.

[Evidencia](evidence.json):15capturas funcionales, escritorio1440 y móvil390,
0errores JS/axe en cabecera+explorador/overflow horizontal. API owner/SQLite,
React y Git temporal son reales; origen histórico de PR es metadata sintética.
No se invocaron modelos/Ken ni un servicio remoto. Se comprobó registro con
respuesta perdida→recarga→mismo paquete/una fuente; rama avanzando137→200 mientras
la lectura inicial sigue137; actualizar explícitamente carga200; rama alternativa
retiene137. Foco/regreso móvil, PR con enlace exacto a su tarea, fuente sin Git,
blob ajeno rechazado y lista vacía mediante respuesta GET controlada. La nueva
fuente conserva origin/config y árbol limpio; no se declara clonado o publicación.

Los ensayos se continuaron sobre la misma fixture, sin reiniciar trabajo nativo.
Primero el lector devolvía SHA abreviado. Después, la carpeta sin Git descubría
ramas del repositorio padre: regresión reproducida y corregida. Dos servidores
anteriores terminaron143 por sus handles antes de cargar la corrección siguiente.
El verificador también buscaba una etiqueta select exacta cuyo texto incluía
opciones: se corrigió el selector. La primera fixture omitió campos NOT NULL de
historia; se completaron sobre la fuente ya creada, sin recrearla.

La primera comparación móvil mostró código fuera del pantallazo: se replegó
metadata y se llevó el foco al panel después de confirmar su carga. Una aserción
reprodujo el fallo; la evidencia final13–15 comprueba texto visible, Markdown/texto
original y el explorador final. Son capturas de varias revisiones locales con sus
límites: no se presenta el recorrido como una única sesión de la revisión final.
Las acciones de lectura están cubiertas además por22contratos instalados.

P3 diferidos: rutas muy largas en el registro, números de línea/resaltado y aviso
más visible de desplazamiento horizontal. No reabrir la implementación por ese
pulido. Crear/adoptar Git/clonar/remoto/reparar es capacidad principal pendiente;
no se engloba en esos P3. Faltan lector de pantalla/zoom/otros motores/comprensión
humana, setup completo y aceptación de todas las rutas. Total24/36desktop,
8/12móvil,8pilotos,4rutas aún sin conceptos/código y0/12aceptadas completamente.
