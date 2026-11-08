Sí. **Researcher permite elegir una pareja de modelo y esfuerzo de razonamiento** para futuros intentos. Leí completo [evidence.py](/run/researcher-source/evidence.py:1), de 118 líneas, mediante Ken, y el adjunto `policy.md`, que identifica su procedencia documental.

La elección sirve para indicar con qué modelo y esfuerzo se solicitará ejecutar el trabajo. Según la documentación, se configura desde **Modelos**. Sus entradas son:

- El ámbito: global, proyecto o agente dentro de un proyecto.
- El identificador del modelo y su esfuerzo de razonamiento.
- La revisión esperada, para evitar sobrescribir un cambio simultáneo.

Al guardar, devuelve el ajuste con una nueva revisión. Al consultar, muestra también la pareja efectiva y de dónde proviene. La prioridad es **agente → proyecto → global → host**. Se hereda la pareja completa; restablecer ambos campos permite usar el nivel siguiente. Esto está implementado en [la resolución y actualización](/run/researcher-source/evidence.py:48).

**Ilustración con valores ficticios:** el ámbito global tiene `modelo-A/low` y el proyecto tiene `modelo-B/high`. Un agente de ese proyecto que hereda obtiene `modelo-B/high`, con procedencia del proyecto. Estos nombres no representan modelos disponibles.

Cada intento conserva su primera elección: cambiar después la configuración no modifica esa selección. Antes de iniciar el turno, se comprueba que la pareja figure en el catálogo nativo; si falta, se rechaza sin sustituirla automáticamente. Guardar tampoco inicia una investigación ni cambia permisos o credenciales.

Respecto a **qué datos recibe el modelo**, este módulo solo permite explicar los ajustes, los metadatos del intento y el catálogo. No contiene el armado de la tarea, mensajes o evidencias enviados para investigar. Tampoco demuestra cuánto cambia la calidad, rapidez o consumo.

Dejé el informe 1 propuesto, sin aceptar ni publicar. El paso útil siguiente es consultar en **Modelos** el valor efectivo y su procedencia, sin guardar cambios, para identificar qué pareja correspondería al próximo intento.