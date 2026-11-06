# Resumen: cuaderno de situación

Base: f527215. Usuario: propietario de un proyecto que necesita decidir dónde
continuar sin recorrer todos los paneles. Resultado: abrir una pregunta, propuesta
o tarea con su contexto original y consultar fuentes/decisiones registradas.

Tres conceptos independientes, herramienta Imagegen integrada, más adaptación
móvil de la selección. Referencia: captura del producto de Repositorios, 6 noviembre.
La selección está delegada explícitamente por el usuario. No se pide confirmación.

Se elige **Cuaderno de situación**: columna principal de atención/trabajo y margen
de contexto/fuentes/decisiones. Mesa de decisiones reduce el espacio explicativo;
Ruta de trabajo introduce fases ilustrativas que podrían confundirse con el plan
real. Se conservan los tokens de papel/tinta/verde y la navegación existente.

Contrato: consultas existentes de workspace, tareas y preguntas. Ninguna mutación
al abrir el resumen. Preguntas con paginación y estado propio; propuestas con run
original; tareas y navegación del proyecto seleccionado; cambio de proyecto elimina
el contenido anterior. Error de consulta nunca equivale a cero pendientes. Estados
guardados no prueban proceso vivo. Tareas done no equivalen a aceptación del proyecto.

Ruling: se reutiliza QuestionInbox para no duplicar su protocolo de preguntas.
El contenido real requiere subtítulos y estados adicionales respecto al concepto;
se preserva la jerarquía principal. No se reproducen estados de fuente inventados
por Imagegen como estados de tareas. No se añaden gráficos sin datos ni imágenes
decorativas. Las imágenes son referencias, nunca controles rasterizados.

Validación: navegador con fixtures explícitos (preguntas/paginación/navegación,
proyecto vacío, error parcial y recuperación, todas las tareas done, cambio de
proyecto), capturas 1440/390, Axe en región nueva, suite frontend y compilación.
Fixtures prueban interfaz, no backend ni comprensión humana. Las pruebas reales
integrales y aceptación de doce páginas siguen abiertas. Pulido secundario al final.
