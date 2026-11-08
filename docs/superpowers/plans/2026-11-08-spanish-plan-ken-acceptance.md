# Plan en español y consultas Ken observadas

Inicio: 2026-11-08 03:18:47 UTC, base `3d8b33a`. La causa de la contención original
sigue abierta; el diagnóstico seguro del productor ya está verificado e instalado.

Ruling: adelantar una comprobación independiente de idioma y Ken en una instalación
sintética nueva. Las seis preparaciones sin generación no reprodujeron la contención;
otro ensayo equivalente no verificaría la salida. Se usa la autorización previa
del usuario para su suscripción, con un turno máximo y límites inferiores o iguales
a los del operador. Si falla, conservar el intento y su traza; no reintentar.
El resultado positivo tampoco declara corregida la fiabilidad intermitente.

1. Modelo configurado: `gpt-6.1-sol`; máximo 180 s, 90 s sin progreso, 25 llamadas
   y 350000 tokens observados. Un turno por sesión/proyecto; presupuesto agregado
   del proyecto 350000. Conservar límites menores si están configurados.
2. Mantener los prompts de producción. Registrar las llamadas y respuestas reales
   de `ProjectTools.call`, siguiendo el patrón del evaluador de contexto existente.
   El observador no sustituye respuestas ni cambia la autoridad de herramientas.
3. Crear desde la web una propuesta CSV pequeña y explícita, con `ken_find` en
   inglés y `ken_read` con código fuente. Verificar respuestas exitosas y contenido
   del archivo, no sólo nombres genéricos de herramientas ni afirmaciones del modelo.
4. Inspeccionar explicación, títulos y criterios en español; contrastar la propuesta
   guardada y su aceptación exacta. La aceptación crea hijas pendientes sin
   ejecutarlas. Conservar código original y toda historia anterior de otros ensayos.
5. Contar envíos, cierre, tokens observados y resultados guardados por separado.
   No inferir facturación ni comprensión humana de esos contadores. U08/C10 y la
   causa del fallo anterior continúan independientes de este caso.

## Resultado

Verificado 03:51:45 UTC,32min58s desde el inicio. Un plan español aceptado,
lectura y búsqueda Ken con código real; dos consultas avanzadas sin análisis válido.
No se repite el modelo. Cierres y fuente comprobados; contención original abierta.
La respuesta humana pide más contexto de objetivo/entradas/salidas: U08 no aceptado.
[Recibo y límites](../../modernization/spanish-plan-ken-review.md).
