# Publicación remota desde Tareas — 2026-11-05

El panel continúa la dirección visual seleccionada de Tareas; no constituye otra
página ni aceptación completa de `/tasks`. Se inspeccionaron las capturas de
entrada escritorio/móvil, respuesta perdida, recuperación, PR y resultado final.

El recorrido usa owner HTTP, discovery policy, scheduler, SQLite y React reales.
El servidor Forgejo y los testigos de efectos/cierre físico son **sintéticos
explícitos**. No se consume inferencia ni se escribe en un servidor del usuario.
La integración HTTPS con Git real sigue documentada por separado en
[remote-recovery-results.json](../../../modernization/remote-recovery-results.json).

Se verificaron nueve estados en1440×1100 y390×844: cero errores de página, cero
desbordamiento horizontal y cero incidencias Axe en el panel nuevo. Las entradas
conservan etiquetas, la secuencia se apila en móvil y las decisiones quedan
separadas. Se explica versión exacta, cambio de base e incertidumbre con ejemplos.

La publicación perdió su respuesta después de admisión; se bloqueó temporalmente
la lectura del historial para verificar conservación del paquete tras recarga.
Dos POST idénticos recuperaron el mismo run y un efecto. La consulta de recuperación
perdió también su respuesta después de completarse; tras recargar, dos comandos
idénticos devolvieron un recibo y conservaron un único observador. PR y merge
requirieron acciones posteriores distintas. Contadores del fixture:
`push=1`, `pull=1`, `merge_git=1`, `merge_record=1`, `observers=1`.

[Escritorio inicial](01-desktop-initial.png), [móvil inicial](02-mobile-initial.png),
[destino observado](03-destination-observed.png), [respuesta de push perdida](04-push-response-lost.png),
[recarga original](05-push-reload-original.png), [respuesta de consulta perdida](06-recovery-response-lost.png),
[PR y decisión de merge](07-pr-created-separate-merge.png),
[resultado móvil](08-mobile-completed.png), [resultado escritorio](09-desktop-completed.png).
Hashes, cuerpos originales, tamaños y límites están en [evidence.json](evidence.json).

No acredita compatibilidad con Forgejo real, comprensión humana representativa,
lector de pantalla, zoom ni toda la aceptación de doce páginas. La paginación de
historial y textos secundarios quedan para la pasada de detalles; no se amplía
esta entrega con otra auditoría o rediseño del panel.
