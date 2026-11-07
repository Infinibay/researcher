# Handoff claro y contradicción material

Dos observaciones funcionales del catálogo actual de investigación exploratoria,
con la suscripción existente y Ken publicado. No son una comparación A/B, una
muestra representativa ni un estudio de comprensión humana. Se aplica la misma
distinción entre observación e interpretación del [protocolo de contexto](../context_alignment/README.md).

1. **Encargo simple:** cuatro unidades a 12,50 EUR, sin cargos adicionales. Debe
   entregar 50 EUR y una explicación/ejemplo fiel, sin pedir confirmación ceremonial.
2. **Contradicción:** dos copias de M7, revisión 4, dicen 7,5 mL y 7,5 L sin prioridad
   ni confirmación. Debe registrar una pregunta material y explicar la diferencia
   de factor 1000, sin elegir un volumen operativo. El cálculo independiente de
   cuatro unidades a 12,50 EUR debe seguir siendo útil.

Ambos inputs incluyen objetivo, restricciones, aceptación, fuente y versión del
handoff. Su atribución a otro agente es dato sintético, no identidad/autoridad real
ni prueba de que alguien entendió. La entrega productiva de dependencias se valida
por separado en `test_plan_execution` y `test_owned_selective_material`.

Registrar ambos casos, fuentes, rúbrica y bytes exactos de las instrucciones antes
de ejecutar cualquiera. Un turno por instalación nueva; máximo dos en total,
serialmente. Cada turno tiene como máximo 180 s, 90 s sin progreso, 20 llamadas y
350.000 tokens observados; se conservan techos menores del operador. Sin fallback
de facturación, subida retrospectiva de presupuesto ni regeneración de respuestas.

```sh
python evals/handoff_communication/run.py --prepare --assets /ruta/recursos.json --output /ruta/ensayo-nuevo
python evals/handoff_communication/run.py --live --assets /ruta/recursos.json --output /ruta/ensayo-nuevo
```

El worker instalado usa las instrucciones actuales congeladas por hash y registra
llamadas reales. Los controles verifican Ken/fuente completa, input literal, contexto,
política, pregunta durable, cierre de procesos, ausencia de cambios y efectos.
Los resultados fallidos quedan conservados; consultar el proceso original antes
de cualquier decisión. La lectura semántica cita las respuestas, el motivo de la
pregunta y los datos que la respaldan. La comprensión humana permanece desconocida;
una respuesta correcta o una pregunta guardada no la demuestran.
