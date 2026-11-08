# Espera de un comando activo y consulta de su recibo original

Un comando realmente activo se mantuvo esperando mientras el navegador consultó
su recibo en escritorio y móvil. **Se envió una sola instrucción, se ejecutó un
solo comando de trabajo y se recuperó su mismo identificador al terminar.** La
propuesta quedó guardada sin aceptar. El transporte nativo fue controlado, sin
generación de modelo: no se presenta como una nueva respuesta de la suscripción
ni como observación de comprensión humana.

[Resultados y registro](live-wait-communication-results.json),
[capturas revisadas](../design/audits/2026-11-08-live-wait/report.md).
Se reutiliza el coordinador del producto instalado, con su autoridad, concesiones,
copia privada de desarrollo, comandos y Ken. Sólo se sustituye el ejecutable de
transporte dentro del proceso de evaluación; no se añade otro engine o API.

## Resultado observado

- Navegación real a Tareas, emparejamiento local y una instrucción desde el
  formulario. Se abre la salida del comando y se acciona «Consultar recibo» con
  foco y Enter. Consultar no inicia otro comando.
- La puerta del comando queda activa **11,336s** desde que el padre anuncia su
  identidad; el navegador observa al menos **10,366s** de espera. Dos capturas
  muestran ejecución activa y dos el resultado terminal, a1440/390píxeles.
- El recibo explica que la salida puede estar vacía mientras trabaja, que
  consultarla no repite el comando y que código de salida/cierre/aceptación son
  hechos distintos. El mismo job termina con salida0 y cierre local registrado,
  conservando106bytes de salida estándar y cero de errores.
- Un run termina needs_review, un candidato ready, una reserva nativa controlada
  queda settled/completed con consumo **desconocido**, no cero inventado. Todos
  los peers y grants quedan cerrados; servidor original termina-15. El archivo
  original `evidence.py` mantiene su hash. No se comprobaron aquí todos los archivos.
- Las cuatro capturas se inspeccionaron manualmente. Cero overflow, errores de
  página o escrituras prohibidas. **Accesibilidad regional no limpia**: las cuatro
  vistas conservan la misma infracción de nombres accesibles en cuatro botones
  deshabilitados, DD155. El recorrido funcional no cierra ese detalle.

El comando no realiza una investigación lenta real: espera en una puerta acotada
del ensayo. Eso demuestra observación y control de una herramienta viva, sin
demostrar calidad del razonamiento, progreso autónomo útil o una espera externa
de duración arbitraria. La prueba de Stop y la recuperación física conservan su
evidencia propia; aquí no se añaden ensayos nuevos de parada.

## Montaje y fallos que se conservan

El ejecutor es [live_wait.py](../../evals/communication/live_wait.py), el servicio
aislado [wait_worker.py](../../evals/communication/wait_worker.py) y el recorrido
[Playwright](../../frontend/tests/communication-wait.mjs). El registro congela
hashes de fuente, candidato, transporte y evaluadores antes de admitir. Recursos
originales intactos; DNS y certificados públicos se copian y verifican fuera de
las fuentes, sin quitar la comprobación de identidad productiva. Puerta60s,
comando80s, transporte de prueba90s; límites del proyecto no ampliados.

Se conservan cinco ensayos anteriores, cada uno con instalación/identidad nueva;
ninguna instrucción incierta se vuelve a enviar al mismo intento. Los seis ensayos
contienen **cero turnos generativos**. Sus reservas controladas y consumo desconocido
se atribuyen individualmente en los resultados, sin llamarlos gasto de la cuenta.

1. La preparación rechaza una identidad de archivo público de red antes de
   reservar inferencia. El registro identifica la frontera; no demuestra cuál
   archivo cambió. Todos los procesos cerrados. Las copias verificadas aíslan
   posteriores ensayos del reemplazo de archivos del sistema.
2. Primer recibo activo capturado; falla axe por los nombres de botones. La
   limpieza cierra el intento. Se declara DD155 antes de la excepción exacta;
   cualquier infracción distinta continúa fallando el recorrido.
3. Dos capturas activas, pero el transporte heredado corta `command/exec` a8s.
   Su `subprocess.run(timeout=8)` explica la desconexión frente a una puerta de
   más de10s. Se cambia sólo esa constante en la copia de transporte usada por
   el ensayo; el producto conserva su límite de comando.
4. El mismo comando termina0. El evaluador falla al esperar una propuesta en5s;
   la preparación posterior del candidato aún seguía. El cierre del servicio
   cancela el intento. Se amplía a45s esa espera específica.
5. El comando termina0 y su recibo se recupera, pero una aserción de cierre
   agota5s. Se conserva ese fallo; el ciclo de consulta y cierre no es instantáneo.
6. Recorrido completo observado: comando activo→mismo recibo cerrado→propuesta
   guardada→servicio cerrado. **70,613s** de ejecución del lector, sin preparación
   inicial ni análisis/documentación. Las aserciones mantienen sus límites reales:
   la llamada `expect.configure` no reasigna la instancia y se anota en DD156;
   no atribuir a ella el éxito ni afirmar que toda aserción tenía45s.

Este montaje necesitó más correcciones de las deseadas: reutilizaba un transporte
pensado para comandos cortos y confundía el cierre de un comando con el tiempo
necesario para guardar el candidato. El recibo real permitió localizar cada
frontera. No se convierten los fallos previos en éxito ni se ocultan sus estados
unknown/cancelled. La próxima vez conviene fijar estos límites antes del primer
recorrido y observar condiciones registradas, conservando los presupuestos.

Bloque **16:41:54–16:57:03UTC:15min9s** hasta inspeccionar el resultado final;
documentación y checkpoint posteriores aparte. Esto completa el alcance técnico
de espera/UI junto a [lectura recuperable y plan parcial](execution-communication-review.md).
U08, adaptación a una corrección humana, revisión independiente final, paquete y
suite global siguen abiertos. No se modificó producto/prompts en este bloque.
