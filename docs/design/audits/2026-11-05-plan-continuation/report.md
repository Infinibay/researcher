# Tareas: continuación explícita de una entrega

Se conserva la referencia visual del piloto de Tareas. El nuevo control separa
consultar cierre/efectos, autorizar una sucesora y reanudar despacho. Ofrece un
ejemplo concreto: una fuente guardada antes de detenerse permanece registrada.

Se inspeccionaron visualmente las capturas01 y02, en1440×1100 y390×844.

| Estado | Captura |
| --- | --- |
| Evidencia del intento cerrado en escritorio | [01](01-desktop-original-closed-evidence.png) |
| Evidencia y decisión en móvil | [02](02-mobile-original-closed-evidence.png) |
| Respuesta perdida | [03](03-mobile-response-lost.png) |
| Recarga conserva el paquete original | [04](04-mobile-reload-original-permission.png) |
| Recibo recuperado en móvil | [05](05-mobile-original-receipt.png) |
| Recibo recuperado en escritorio | [06](06-desktop-original-receipt.png) |

[Evidencia](evidence.json): dos POST idénticos después de perder respuesta y
recargar dejan una sola sucesora. El plan sigue pausado; sólo existe el run
anterior. Sin errores de página, desbordamiento horizontal ni infracciones Axe
en el panel examinado. React, owner HTTP y SQLite reales; witnesses de cierre y
generación explícitamente sintéticos. El ensayo físico del runtime se registra
por separado. No hay inferencia real ni evaluación representativa de comprensión.

Localización de estados secundarios y selección por títulos quedan enDD015.
Persisten0/12páginas totalmente aceptadas y los requisitos visuales del plan completo.
