# U04/U05/U07/U08 — continuidad y comunicación con el usuario

Preparado durante U01–U03. Inicio real **2026-11-07 23:08:57 UTC**, base `4eb15e8`.
Mantener la lista actualizada con tiempos medidos en cada transición.

## Contratos del plan principal

- U04: historial y eventos vivos conservan IDs y cursores; callbacks de una
  conexión anterior no mezclan A→B→A ni desconectan su reemplazo.
- U05: la bandeja conserva todas las preguntas, IDs de opciones, prioridad,
  estado y correlación con solicitud/hilo. Responder o corregir no reutiliza
  silenciosamente el contexto del proyecto anterior.
- U07: CLI/TUI y web usan los mismos casos de uso vigentes y migraciones.
  Instalar en un directorio nuevo y trabajar en un proyecto cuyo ID no sea1
  funciona sin motores antiguos ni una inferencia implícita de pago.
- U08: conclusiones, evidencia, límites y suposiciones se distinguen; las fuentes
  se pueden abrir y la corrección queda asociada al intento. Diagramas tienen
  alternativa textual. Errores o desconexiones visibles conservan el contenido
  y no anuncian un éxito que no se observó.

## Aceptación

- [x] Contrastar cada recorrido actual con pruebas y evidencia ya válidas;
  reutilizar D13 para eventos sin repetirlo por documentación.
- [x] Verificar intercalado de eventos/proyectos, múltiples preguntas y opciones
  con valor distinto de su etiqueta, corrección/hilo y acceso por terminal.
- [x] Comprobar renderer válido/dañado, alternativa textual, error de herramienta
  y desconexión hasta la presentación y la corrección del usuario. Corregir sólo
  brechas funcionales, con docstrings/JSDoc en las definiciones afectadas.
- [x] Preparar un ejemplo concreto y revisable para la comprobación humana de
  U08: identificar conclusión, límite y dato supuesto; efectuar una corrección.
  Pedir respuesta sobre ese resultado, sin preguntas repetidas de confirmación.
  Automatización o juicio del agente no sustituyen esta evidencia humana.
- [x] Registrar alcance realmente probado, pendientes, duración y checkpoint;
  mantener U08 abierto si falta su evaluación humana, y continuar con trabajo
  independiente mientras se espera esa respuesta.

Después siguen datos históricos, evaluaciones pendientes, aceptación integral
de las doce páginas, dependencias y distribución. Los detalles aplazados se
resuelven al terminar lo grueso; DD120 debe corregirse y ejecutarse antes de
declarar verde la suite global. C10 conserva la brecha funcional de entrega
independiente; revisión global e independiente cierran el plan completo.


Resultado: U04/U05/U07 comprobados. U08 permanece abierto: el usuario rechazó
el primer ejemplo por no permitir interpretar nada. La revisión usa una corrección
PostgreSQL→SQLite durante una tarea y se comprobó en navegador, sin aceptación
humana nueva ni atribuir la explicación a una generación real. Registro completo
en `docs/modernization/interaction-acceptance-review.md`.
