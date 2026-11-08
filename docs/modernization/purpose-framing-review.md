# Encuadre de propósito, datos y resultado en las instrucciones reales

El catálogo10 incorpora el feedback del propietario en la política común: antes
de pedir una decisión, establecer propósito, datos disponibles y relaciones;
usar un ejemplo de entrada/salida cuando ayude; reconstruir el encuadre cuando
la explicación no se entiende, sin volver a un cuestionario de comprensión.
**La instrucción está conectada al runtime; el nuevo ensayo real no entregó una
explicación final.** No se acredita eficacia ni aceptación humana.

[Resultados](purpose-framing-results.json),
[registro previo a generar](purpose-framing-evidence/registration.json),
[resultado original, incluido el fallo](purpose-framing-evidence/native-result.json).

## Cambio y compatibilidad

Se añaden cuatro líneas a `COMMON_INSTRUCTIONS` en
[native.py](../../backend/prompts/native.py), compartidas una vez por los siete
perfiles del selector. El catálogo pasa9→10; `instruction_identity` conserva las
cabeceras históricas2–9 y sus hashes originales. No cambian selección de
capacidad, permisos, presupuesto, herramientas ni reglas de aceptación.

El consumidor real `OwnedCodexRuntime.open` compone la política y los límites
efectivos antes de abrir el thread. Se revisó esa llamada: su código no cambió.
Se contrastaron las seis fuentes de capacidades y la política de desarrollo:
permanecen byte a byte iguales. La instrucción de fuentes también conserva su AST;
su módulo cambia por la composición común. La entrada reference_research conserva
su uso de compatibilidad y no añade una ruta normal del selector.

Se revalidaron semánticamente doce decisiones: cinco candidatos de native.py y
siete de capacidades cuyo consumidor común cambió. Las otras73 permanecen
vigentes: **85candidatos en322archivos**, cero revisiones desactualizadas/sin revisar.
El inventario no demuestra exhaustividad de llamadas dinámicas ni eficacia.
El [recibo de revalidación](purpose-framing-evidence/revalidation.json) identifica
cada candidato. La medición de bytes/hashes tampoco es una medida de coste o calidad.

El cambio sigue el criterio ya aplicado de concentrar una política compartida y
conservar puntos concretos de corrección, sin otro loop. La documentación oficial
recomienda contexto relevante, objetivos claros y ejemplos para orientar el
resultado; no demuestra que estas cuatro líneas funcionen en este producto.
[OpenAI: model optimization](https://developers.openai.com/api/docs/guides/model-optimization#write-effective-prompts).

## Comprobaciones

- Se observó el RED de versión/composición en los siete perfiles. El primer
  comando no ejecutó pruebas por usar un flag de cobertura no instalado; se
  conserva en el log, separado del RED real.
- **42pruebas fuente pasan**: catálogo, inventario, evaluación de contexto y entrega
  atómica de planes. Incluyen envío por el runtime real con generación controlada,
  hash exacto de política y límites, reconocimiento de versiones previas y retiro
  de autoridad. No son pruebas de comprensión humana.
- Sdist→wheel e instalación no editable: **699archivos Python/SQL** coinciden con
  fuente, sdist, wheel e instalación;371son archivos de producto. Única exclusión:
  `backend/db/seeds/dev_data.sql`, semilla deliberadamente fuera de distribución.
  El primer control comparó700y detectó sólo esa exclusión; no faltan otros miembros.
- **31pruebas instaladas pasan** fuera del repositorio, con imports del prefix.
  El primer comando produjo28pass/3fallos por no activar asyncio auto fuera de la
  configuración del repo. La corrección del comando pasa los31sin tocar producto;
  conserva un aviso de ámbito del loop. [Paquete y hashes](purpose-framing-evidence/packaging.json).
- No se ejecuta otra suite global ni se vuelve a probar el frontend: este cambio
  no modifica UI. La suite frontend del checkpoint913e2f5 conserva su alcance.

## Ensayo real: resultado incompleto conservado

Se usó una pregunta reconocible del propietario —«Se puede configurar que modelo
usar o no?»— y su feedback histórico sobre claridad. La petición de evaluación
la redactó el implementador: se identifica como tal y no convierte las citas
históricas en nueva autorización, comprensión ni una preferencia de modelo.
Se capturaron el módulo real `backend/runtime/model_settings.py` y la documentación
del proyecto; no un algoritmo simplificado con números sin contexto.

Un turno real de suscripción/Ken con gpt-6.1-sol/low recibió el catálogo10 exacto.
Se verificaron lecturas completas del módulo, su hash intacto y un hallazgo parcial
con citas del adjunto. **147058tokens observados frente a120000de límite** detuvieron
el intento antes de la explicación final. Duración del ejecutor55,880s; cinco
peers cerrados, cero grants, servicio-15. El estado nativo/resultado final permanece
desconocido, no completed inventado. Tokens observados no son facturación ni cuota.

El agente añadió una captura `cat evidence.py` pese a tener el módulo leído.
Su lectura pidió max_bytes20000y fue rechazada por validación. No se usó esa
salida como evidencia. El hallazgo posterior se guardó, pero no equivale a una
explicación entregada. La entrega dentro de ese presupuesto continúa sin demostrar;
antes de otra validación debe revisarse esa exploración adicional y la proporcionalidad
del recorrido para una pregunta sencilla. No se repite ahora el caso ni se amplía
su presupuesto para convertir este resultado en éxito. El detalle del feedback
de parámetros se conserva en DD157.

El nuevo prompt no queda validado por estar presente. El ejemplo reconocible,
la corrección del propietario y la adaptación efectiva deben seguir observándose.
U08 continúa abierto, junto a Ken/ONNX, documentación/accesibilidad y cierre final.

Bloque iniciado17:01:34UTC; el tablero registra el corte final de comprobaciones
y separa documentación/checkpoint. Los segundos del ejecutor no representan todo
el bloque.
