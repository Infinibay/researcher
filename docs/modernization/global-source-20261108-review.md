# Suite completa y contaminación de entorno en una prueba

La suite común actual termina con **2576 aprobadas y dos fallos**, sin omisiones
ni errores de fixture, en **2121,12 s (35 min 21 s)**. Los dos fallos comparten una
contaminación de entorno reproducida y corregida en una prueba del lanzador.
La selección ampliada posterior pasa sus **22 casos**. **No se declara todavía
una nueva ejecución completa verde.**

[Resultados](global-source-20261108-results.json), [JUnit completo](global-recheck-evidence/global.xml),
[log completo](global-recheck-evidence/global.log),
[registro y cierre](global-recheck-evidence/global-exit.json).

## Alcance de la ejecución completa

Base `cb4da17`; los mismos bytes backend permanecen en el checkpoint documental
`353dbf9`. Inicio 20:32:30 UTC, cierre 21:07:52 UTC del 8 de noviembre. Son
**2578 casos** de fuente con el entorno Python instalado, no una suite completa
de wheel aislado. `live` queda excluido; se suministran los activos offline reales
de Ken y recuperación semántica. No se pidieron turnos de suscripción reales.
Default pytest de 20 s y marcas particulares existentes conservados.

Los **703 archivos Python/SQL/C** quedaron congelados durante la ejecución;
hashes y pertenencia se comprobaron. La advertencia de Starlette/httpx se conserva.
La referencia anterior de 2210 casos y 31 fallos/1 error continúa como histórica;
sus 32 selectores ya habían pasado como 33 casos actuales antes de esta ejecución.

## Causa comprobada

`test_prepared_semantic_assets_reach_reopened_host_and_launcher` llama al CLI
real con `run_services` controlado. El CLI exporta correctamente la configuración
de la instalación al entorno. La prueba sólo retiraba la variable de activos
semánticos y no registraba las demás variables para restaurarlas al terminar.
Dejaba, entre otras, `INFINIBAY_RUNTIME_CONFIG` apuntando a su instalación sintética.

Dos pruebas posteriores asumían un servicio de lectura sin runtime configurado:

- El historial se archivaba correctamente, pero salir del lifespan de ese runtime
  inesperado revocaba grants. El envío posterior encontraba `ResearchForbidden`
  antes de poder comprobar el rechazo por conversación cerrada.
- La consulta de fuentes e historial devolvía `runtime.configured=true`, aunque
  el escenario pretendía comprobar la consulta sin configuración de runtime.

La secuencia productor → ambos consumidores reproduce exactamente **1 aprobada y
2 fallos en 4,24 s**. El fallo no se atribuye a archivar mensajes, a los controles
de revocación ni a la consulta de fuentes. No se cambió código productivo.

## Corrección y comprobación

La prueba del lanzador ahora registra y retira **cada clave exportada** mediante
`monkeypatch` antes de llamar al CLI, igual que su prueba vecina ya hacía. Así el
escenario empieza realmente sin esas variables y teardown restaura sus valores
anteriores o su ausencia. Se comprueba además todo el mapa exportado, conservando
la aserción del activo semántico y todas las aserciones de los consumidores.

- Misma secuencia: **3 aprobadas, 3,82 s**.
- Archivos completos de instalación, historial y consulta: **22 aprobadas,
  16,34 s**, sin omisiones. [JUnit](global-recheck-evidence/environment-expanded.xml).
- Evidencia RED [original](global-recheck-evidence/environment-red.xml) y
  GREEN [dirigida](global-recheck-evidence/environment-green.xml) conservadas.

Esto muestra por qué cada prueba debe establecer su contexto en vez de dar por
compartida una condición ambiental. La corrección no convierte el resultado
completo anterior en verde. Documentación pendiente en copias, paquete final,
suite final, revisión independiente, U08 humano y distribución Ken/ONNX conservan
sus propios gates. No hay push, merge ni despliegue por este bloque.

Logs y JUnit se conservan literalmente: 20 diagnósticos de espacios en evidencia
original; fuera de esos archivos, `git diff --check` pasa.
