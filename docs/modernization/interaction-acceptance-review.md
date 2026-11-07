# Continuidad, preguntas y acceso por terminal

U04, U05 y U07 quedan comprobados para el artefacto actual. U08 continúa abierto:
el usuario rechazó expresamente el primer ejemplo por no permitirle interpretar
nada. Renderizar correctamente una explicación no demuestra que resulte útil.

## Cambios que resuelven brechas funcionales

- Las opciones admiten `{id, label}`. Seleccionar «Kilogramos» guarda
  `{option_id: "mass_kg"}`; escribir `mass_kg` conserva texto libre, sin atribuir
  una selección. HTTP, MCP, SQLite, contexto, hilo y formulario preservan esa
  distinción. Las preguntas antiguas con opciones de texto conservan su forma.
- La bandeja presenta todas las solicitudes paginadas, cantidad de preguntas,
  estado de respuesta y prioridad observada de la tarea. Esa prioridad no se
  presenta como una urgencia inferida de la pregunta.
- El formulario conserva una copia profunda del envío para repetir la misma
  intención tras perder el recibo. Cambiar de proyecto remonta el formulario;
  una respuesta anterior no se convierte en entrada del proyecto nuevo.
- Markdown admite Mermaid bajo configuración propia restrictiva, sin montar el
  SVG del autor como HTML activo. Se requiere descripción textual; quedan a la
  vista tanto la explicación como el error y el original si falla el dibujo.
- El catálogo nativo 9 explica opciones estables, diagramas con `accTitle` y
  `accDescr`, límites y ejemplos concretos. Después de la crítica humana se
  añade el criterio de no usar números sin situación ni diagramas decorativos.
  Las versiones 2–8 conservan su identidad histórica y hash.

Mermaid 12.3.0 se carga bajo demanda. Se comprobaron su
[API de renderizado](https://mermaid.js.org/config/usage.html),
[accesibilidad](https://mermaid.js.org/config/accessibility) y
[política de seguridad](https://mermaid.js.org/config/schema-docs/config-properties-securitylevel.html).
Los límites de12.000 caracteres/100 aristas no son un plazo duro de CPU del navegador.

## Evidencia y alcance

La selección instalada inicial pasó88 casos y falló al buscar `start.sh` dentro
de `site-packages`: ese test depende del checkout. Se conserva el fallo; no se
modificó el producto ni se omitió el test. La continuación instalada pasó28 casos
distintos; los dos archivos del lanzador pasaron6 casos desde el checkout.
Los116 casos instalados incluyen preguntas/HTTP/SQLite, hilo, correcciones,
snapshot de entrada, política enviada al protocolo nativo controlado y TUI real.
No es una nueva suite global verde. Recibos:
[inicial](interaction-acceptance-packaging.json),
[continuación](interaction-continuation-packaging.json),
[resultado del bloque](interaction-acceptance-results.json).

Pasan26 contratos frontend,13 casos DOM y la compilación. Los contratos intercalan
historial/eventos, reconexión y A→B→A. Se reutiliza D13 con
[comparación exacta de los módulos listados](interaction-event-comparison.json).
La auditoría documenta35 definiciones Python nuevas/modificadas con docstring,
además del JSDoc de los componentes y contratos nuevos.

El recorrido de navegador usa servidor instalado, base nueva y formularios reales:
dos proyectos, tareas/dependencia, corrección persistida, recarga y aislamiento.
Los documentos guardados dibujan flujo y secuencia; un bloque inválido conserva
explicación/original. Se rechazan configuración y recursos externos; una etiqueta
HTML queda inerte. Cero solicitudes al destino externo de prueba, errores de
página o incidencias Axe en el documento; escritorio y móvil sin desbordamiento.
El servicio termina por SIGTERM observado 143. Cero inferencias o API simuladas.
[Auditoría visual y límites](../design/audits/2026-11-07-interaction/report.md).

## Corrección recibida del usuario

Respuesta literal sobre el primer ejemplo: «Que el ejemplo utilizado en la imagen
es malo y no me deja capturar o interpretar nada».

Observación: la explicación no fue útil para esa persona. Interpretación del
agente: números sin una situación reconocible y un dibujo redundante no ayudan
a decidir. No se presenta esta interpretación como una causa demostrada.

Se reemplaza por una decisión concreta: pedir PostgreSQL y corregir a SQLite
mientras el agente trabaja. Explica qué intento pierde autoridad, cuándo se usa
la corrección y qué debe hacer el usuario para continuar, sin prometer deshacer
efectos anteriores. Se conserva el ensayo inicial y se comprueba de nuevo el
documento revisado. La nueva versión **no tiene aceptación humana**. El ejemplo
escrito por el agente de implementación tampoco sustituye una evaluación de
explicaciones generadas y adaptación real bajo la política final.

## Compatibilidad y trabajo restante

La compatibilidad comprobada cubre datos históricos de preguntas y cliente/backend
actuales. Un navegador con un bundle antiguo no queda declarado compatible con
las nuevas opciones estructuradas; la distribución debe resolver la actualización
conjunta. No hay nueva migración SQL ni promesa de downgrade a código anterior.

Continúan U08, C10, datos históricos, evaluaciones,12 páginas completas,
dependencias/distribución y cierre global. Los detalles visuales/rendimiento
quedan al final en DD121. Las113 entradas npm nuevas tienen declaraciones y una
revisión del archivo MIT de `khroma`; consolidar avisos de distribución sigue
pendiente. El audit de dependencias de producción no encontró avisos conocidos
en esta ejecución; eso no constituye una garantía general de seguridad.
