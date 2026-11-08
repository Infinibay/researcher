# Documentación del broker y los canales de proceso

Se añadieron **71 docstrings en inglés** en cuatro módulos. Se documentaron
propósito, efectos, límites y dueño de cada operación contra la implementación.
Son **254 definiciones documentadas en doce módulos** desde el inicio de esta
pasada; no se declara completa la documentación del proyecto.

| Módulo | Añadidos | Contratos documentados |
| --- | ---: | --- |
| [broker_profile.py](../../backend/runtime/broker_profile.py) | 23 | Preparación de cápsulas, assets verificados, perfiles de red, montajes y descriptores. |
| [broker_stdio.py](../../backend/runtime/broker_stdio.py) | 23 | Backpressure, constructores cancelados, canales y cierre bajo el broker original. |
| [broker_mcp.py](../../backend/runtime/broker_mcp.py) | 13 | Frames y concurrencia acotados, incertidumbre de entrega y cierre físico anterior al protocolo. |
| [peer_broker.py](../../backend/runtime/peer_broker.py) | 12 | Identidad de operaciones, concesión, lanzamiento, recibos y recuperación del dueño original. |

Preparar una cápsula o describir un endpoint no lanza un actor ni concede permiso.
El broker conserva el despacho y la liberación tras comprobar autoridad. Cerrar
los streams duplicados no acredita retirar el subárbol. Una respuesta de herramienta
con `isError` es un resultado de herramienta; un fallo de transporte tiene entrega
incierta y no autoriza repetir el efecto.

Los perfiles de red se describen según su código: el transporte nativo directo
comparte red del host; comandos y proxy tienen su namespace privado. La selección
de namespace y el filtro de syscalls no prueban por sí solos una restricción de
destinos. La documentación no modifica ni amplía esas capacidades.

Si se cancela el observador de un constructor que termina correctamente, los
handles que nadie puede recibir se cierran, y la retirada física permanece con el
broker original. El cierre por operación obtiene el recibo físico antes de
proyectarlo a SQL. La recuperación distingue PID original vivo, reutilizado y
visibilidad incierta; no mata un proceso nuevo por coincidir su número.

## Verificación

[Resultados](broker-docstrings-results.json),
[textos escritos por identidad](broker-docstrings-evidence/authored-docstrings.json),
[equivalencia de AST](broker-docstrings-evidence/ast-equivalence.json).

- Los cuatro módulos quedan sin clases o funciones sin docstring en el inventario
  sintáctico. El AST ejecutable coincide con `8850633` al retirar sólo docstrings;
  firmas, constantes, decoradores y sentencias permanecen iguales. Cambian `__doc__`
  y números de línea; no se certifica todo consumidor externo de introspección.
- Siete políticas nativas y las descripciones, esquemas y anotaciones de 48
  herramientas de negocio son idénticos a la captura previa.
- **63 pruebas fuente pasan**, sin fallos ni omisiones, en **52,69 segundos**:
  broker, fronteras, MCP/RPC, perfiles nativos/Ken, comandos y proxy. Cero turnos
  generativos nuevos; no se construye otro wheel para este lote.
- Inventario de prompts: **85 candidatos en 322 archivos**. Se revalidó un único
  consumidor cambiado de `read_feedback`: doce docstrings en `peer_broker.py`,
  fuente del candidato idéntica y llamadas/imports sin cambios. Las otras 84
  decisiones siguen vigentes. No se renuevan revisiones sin delta.

Quedan **367 definiciones sin docstring** fuera del alcance: presencia no equivale
a relevancia, calidad ni número de tareas. Continúan suscripción, estado nativo,
mediación y otras fronteras relevantes, además de JSDoc donde ayude a buscar y
usar el código. El MCP conectado al checkout original no se reindexó y no se
midió mejora de ranking. El paquete instalado conserva su propio corte anterior.
U08, Ken/ONNX, accesibilidad y cierre integrado permanecen abiertos.

Inicio 18:46:38 UTC; corte de verificación 18:55:14 UTC: **8 min 36 s**, incluida
la recuperación de contexto y la consulta de estado del usuario. Informe y
checkpoint posteriores aparte; los 52,69 segundos de pruebas no son todo el bloque.
