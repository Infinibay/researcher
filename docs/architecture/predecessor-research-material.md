# Informes aceptados como entrada de una tarea dependiente

Un resultado documental aceptado puede ocupar hasta2MiB. Incrustarlo en la
entrada del siguiente agente, cuyo límite completo es1MiB, impedía iniciar una
tarea válida. Desde el esquema4 se conservan identidades de tarea,
intento, contexto y aceptación, y describen los materiales mediante hash y tamaño.
Los informes y sus fuentes siguen guardados completos; no se resumen ni truncan.
El esquema5 incorpora [selección de evidencia y referencias al contexto histórico](selective-work-material.md).

`researcher_prerequisite_research` permite leer el paquete completo aceptado,
un informe incluido en él o la entrada original del autor. Cada ventana contiene
hasta16384bytes en base64, hash del material completo, tamaño y siguiente offset.
El último fragmento no afirma que los anteriores hayan sido leídos. Un informe
ajeno a la entrega se rechaza; una entrada original ausente se informa como desconocida.

La lectura reutiliza `PredecessorMaterials`, la entrega original y el lease
vigente. Comprueba proyecto, autor, intento, contexto, aceptación exacta y
vigencia de sus fuentes/revisión mediante `result_state`. Un revisor de código
recibe solamente las dependencias de su autor original. No hay otra cola,
base de datos, loop, permiso de publicación ni selección arbitraria de autores.

Ejemplo: A registra «137 unidades» y advierte al final «no inferir mediciones
individuales». B puede recuperar esos bytes y sus fuentes. Eso demuestra qué
material recibió; no que comprendió la limitación, repitió la medición o adquirió
permiso para actuar. La política común7 exige distinguir esas afirmaciones.
Se preservan las identidades de políticas2–6 y los bytes de entregas2/3 existentes.

## Alcance y límites

- Las pruebas reconstruyen tres informes que juntos superan1MiB, incluyendo su
  aclaración final; la entrada del sucesor queda por debajo de25000bytes.
- El recorrido nativo controlado usa kernel, broker, Git y SQLite reales. El
  desarrollador consulta el paquete aceptado antes de continuar; investigación,
  investigación exploratoria y método científico recorren1,2 y3ventanas.
- La generación y Ken del ensayo son dobles controlados. No se acredita calidad
  de un modelo real ni comprensión humana; no se consumen turnos de suscripción.
- El acceso por ventanas no garantiza que leer todo un paquete grande quepa en
  el presupuesto del intento. La selección de fuentes/limitaciones y referencias
  al contexto original/continuaciones se implementan en el esquema5; la suficiencia
  de cada selección sigue requiriendo evaluación. No se aumenta ningún presupuesto
  ni se declara cierre global deC04.
- Una entrega histórica grande conserva su identidad; no se reescribe en silencio.
  Puede seguir excediendo el límite hasta una nueva entrega explícitamente autorizada.

Las pruebas están en `test_predecessor_research_material.py`,
`test_plan_execution.py`, `test_owned_plan_execution.py` y
`test_prompt_catalog.py`. [Resultados y límites del bloque](../modernization/research-material-review.md).
