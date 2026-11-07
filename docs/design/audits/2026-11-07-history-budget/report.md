# Historial de intentos y presupuesto

Se conserva el piloto seleccionado de Agentes. La ampliación muestra el
presupuesto del proyecto y permite consultar intentos anteriores con su propio
modelo, resultado y medición. Tareas incorpora historial paginado independiente
del resumen que gobierna los controles actuales.

El navegador comprobó10 estados a1440 y390px: presupuesto, intentos anteriores,
Stop incierto/solicitado, consumo desconocido, cambio de proyecto y fallo de
lectura. Sin errores JavaScript, desbordamiento horizontal ni violaciones Axe
en la región de Agentes. Se inspeccionaron visualmente las capturas de presupuesto
y detalle en escritorio/móvil. [Evidencia](evidence.json).

El primer ensayo carecía de la respuesta actual de `/projects/{id}/workspace`;
la alerta de la cabecera volvió ambiguo un selector global. Se corrigió el
fixture sin cambiar el producto ni relajar la aserción.
[Intento anterior](evidence-before-fixture-fix.json).

Son respuestas HTTP controladas, no ejecuciones reales ni datos del propietario.
Los dos POST Stop del ensayo fueron interceptados. La paginación de Tareas y
las respuestas tardías A→B→A tienen pruebas DOM; estas capturas no aceptan por
completo Tareas ni Agentes. Siguen0/12 páginas integralmente aceptadas.

Pulido diferido DD078: singular/plural de contadores, menor repetición de las
explicaciones y jerarquía más compacta del presupuesto en móvil. La capacidad
principal queda disponible; no se repiten pruebas por ese pulido.
