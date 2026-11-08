# Aceptación principal de Conversación

Inicio de preflight09:41:48UTC, base6be94e2. Plan global activo,9/12páginas y
41/43escenarios. Reutilizar el concepto existente y TaskRunWorkspace; no otra
ronda de imágenes ni generación por defecto. Detalles DD142y anteriores al final.

## Evidencia leída y límites

- frontend/src/components/pages/ChatPage.tsx separa índice/preguntas, conversación
  de tarea y archivo del proyecto. TaskConversation selecciona conversación desde
  el run observado o la respuesta original; TaskRunWorkspace conserva identidad
  de solicitud/corrección y ya pasó recuperación Tareas→Conversación→Tareas.
- ConversationTimeline muestra procedencia de intervención, contexto, observaciones
  y suposiciones de pares y límites de recepción/comprensión. Su timestamp ya
  interpreta SQLite naive como UTC; no confundirlo con el helper de notas DD142.
- ProjectConversation/ProjectArchive muestran mensajes de vacío a partir de
  data.length===0sin exigir lectura exitosa. Es una hipótesis de falso vacío sobre
  datos cacheados si falla refetch; reproducir con DOM/consulta real antes de editar.
- QuestionInbox evita vacío con isSuccess, pero el contador total cacheado carece
  de etiqueta de antigüedad al fallar. Revisar en conjunto, sin inventar pendientes
  ni considerar un error como lista actual. Las respuestas usan QuestionCard:
  leer productor/contrato y sus pruebas antes de suponer cómo guardan el paquete.
- No hay formulario de nota libre del propietario en el módulo leído. Revisar el
  contrato del producto/servicios antes de afirmar falta de capacidad o añadirlo.
  Diferenciar una nota advisory de instrucción que admite trabajo y respuesta que
  cambia contexto; no reutilizar el formulario de instrucción como si fuesen iguales.
- Ken sigue conectado al checkout original; encontró ChatPage como ubicación, pero
  la fuente actual se verificó en este worktree. No atribuir al índice validación
  de los componentes modernos ni repetir búsquedas si ya está nombrado el archivo.

## Trabajo principal siguiente

1. Revisar QuestionCard/hooks/API y el contrato de notas/hilos, sus consumidores y
   pruebas existentes. Elegir fixture de pregunta nativa cerrada por dominio sin
   iniciar modelo. No inventar id/version/body o afirmar cierre físico por fixture.
2. REDpara errores cacheados demostrables. Corregir lectura/desconocido/reintento
   y scopes; docstrings/JSDoc de módulos/componentes/helpers relevantes modificados.
3. Navegador instalado: selección/búsqueda/proyecto ajeno, conversación original,
   lectura de archivo/hilo, error/reintento, pregunta/recibo/respuesta y corrección
   con identidad retenida. Usar las APIs y registros reales; selección no inicia
   inferencia.1440/390, teclado y Axe regional, registrar límites.
4. Revisar capturas del concepto, actualizar coverage/tablero y avanzar a Ejecución.
   No elevar41/43por una captura ni convertir fixture sintético en ciencia o
   comprensión humana. Detalles visuales al final.
