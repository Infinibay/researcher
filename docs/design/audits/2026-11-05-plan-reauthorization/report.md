# Tareas: revisar y adoptar condiciones corregidas

Se mantiene la referencia visual del piloto de Tareas. La revisión separa el plan
original, metadata observada, correcciones y una decisión nueva del propietario.
Muestra diferencias «Antes / Ahora», resultados vigentes retenidos y entregas que
faltan, con un ejemplo de corrección del tamaño de una muestra. Adoptar mantiene
el despacho pausado; reanudar identifica la revisión, incluso si el grafo no cambió.

Capturas01/02 inspeccionadas visualmente en1440×1100 y390×844.

| Estado | Captura |
| --- | --- |
| Condiciones y diferencias en escritorio | [01](01-desktop-corrected-premises.png) |
| Revisión en móvil | [02](02-mobile-corrected-premises.png) |
| Respuesta de adopción perdida | [03](03-mobile-response-lost.png) |
| Recarga conserva la decisión original | [04](04-mobile-reload-original-graph.png) |
| Recibo recuperado, revisión aún pausada | [05](05-mobile-adopted-paused.png) |
| Reanudar y pausar la revisión explícita | [06](06-desktop-explicit-revision-resume-and-stop.png) |

[Evidencia](evidence.json):2POST idénticos tras perder respuesta/recargar dejan una
revisión,2entregas nuevas y las anteriores como historia. Reanudar/pausar envían
revision1. Sin errores de página, desbordamiento horizontal ni infracciones Axe
en el panel examinado. No se afirma cierre físico a partir del recibo de pausa.

La prueba inicial detectó un fallo previo de historial: React intentaba renderizar
un objeto de contexto del proyecto como hijo. Una prueba SSR real lo reprodujo;
el historial ahora muestra JSON literal escapado, con booleans y estructura. Se
corrigió además el rol accesible del grupo de diferencias tras el fallo Axe.

Un fixture anterior ya contenía una revisión confirmada al volver a observarlo.
Se preservó su DB/recibo, se cerró su servidor y se preparó otro fixture en otra
ruta. La prueba final comprueba revisión0 antes de emitir la decisión y conserva
la solicitud original al recargar. No se reinició un proceso nativo incierto.

React/API/SQLite reales; generación y witnesses originales sintéticos. El recorrido
físico tiene evidencia separada. No se acredita inferencia real, comprensión
representativa ni toda la aplicación: siguen0/12páginas totalmente aceptadas.
Los ajustes secundarios de presentación quedan en la pasada diferida.
