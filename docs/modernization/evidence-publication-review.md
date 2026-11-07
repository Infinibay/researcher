# Evidencia vigente y publicación exacta — E09, E10 y E12

**Los tres escenarios quedan comprobados con el alcance de esta matriz.**
Bloque desde `dc429b7`, **7 noviembre 2026, 19:05:11–19:20:31 UTC**:
**15 min 20 s hasta verificar**. Documentación y checkpoint posteriores excluidos.
No fue necesario cambiar el producto: se añadieron tres casos y se amplió el
recorrido de dos tareas para cubrir huecos de evidencia.

| Requisito | Evidencia comprobada |
| --- | --- |
| E09: recuperar contraevidencia final sin confundir una ventana con la fuente completa | `test_code_review_files` recupera la contradicción final y conserva hash del archivo entero, offsets y cobertura. `test_predecessor_research_material` reconstruye informes grandes; `test_work_material` conserva referencias a contexto histórico y restricciones finales. `test_owned_selective_material` ejerce esas herramientas mediante kernel/broker reales y generación controlada. |
| E09: detectar cambio externo y no reutilizar la cita anterior | El nuevo caso cambia la cabecera dejando intactas las palabras citadas: la huella completa cambia y la cita antigua se rechaza. Un ensayo separado con el modelo real recupera el final de un archivo de 65.987 caracteres y observa otro archivo pasar de 137 a 200 con huellas diferentes. |
| E10: CI y revisión pertenecen al candidato observado | `test_check_results` invalida cambios de repositorio, base, head, contexto o intento; `test_check_workspace` exige candidato exacto. Se reutiliza la ejecución instalada de E11 sobre producto idéntico. `test_code_review_state`, `test_code_review_git` y `test_code_candidate` pasan nuevamente: contexto, diff completo, identidad de origen y árbol limpio forman parte de la comprobación. |
| E10: independencia real del reviewer | La admisión rechaza actor/origen relacionados y exige hilo distinto del autor; una etiqueta de rol no concede independencia. El montaje del reviewer permite leer sólo el candidato. Las pruebas de almacenamiento usan testigos sintéticos; el recorrido integrado conserva autores, revisores y procesos distintos con generación controlada. |
| E10: aprobar A no permite publicar B | Nuevo caso de Git real: un commit limpio B en el mismo directorio no puede usar la vista observada de A; no se crea ninguna referencia ni recibo. Publicación local, remota y merge comprueban aceptación, repositorio, head y base exactos; carreras de refs se rechazan mediante actualización condicional. Proveedor HTTP controlado, sin publicar en una cuenta externa. |
| E12: dos tareas más una edición por shell permanecen en el diff | El recorrido integrado amplía dos tareas dependientes con `task-one.txt`, `task-two.txt` y `shell-added.txt`. Comprueba contenido y diff completo del segundo candidato, ausencia de cambios posteriores en el primero y head exacto recibido por la segunda revisión. Git, SQLite, shell, kernel y broker son reales; generación y Ken son controlados en este recorrido. |
| E12: finalizar normalmente no equivale a aceptar/publicar | Nuevo caso: revisión confirmada `needs_revision`, turno nativo `completed`, aceptación ausente y publicación denegada incluso con clave inventada. Se conserva también la prueba integrada de revisión rechazada de E11, sobre producto idéntico. No hay rework ni aceptación automáticos. |

## Ensayo con suscripción

Un reviewer real, `gpt-6.1-sol`, usó la suscripción y Ken publicado 0.18.0, sin
web ni fallback a clave API. Leyó las ventanas de evidencia, encontró el fallo
final y detectó el cambio externo. Explicó en español que observar `200` no
demuestra que las pruebas pasaran; distinguió lo leído de lo no comprobado y
no atribuyó quién cambió el archivo.

La propuesta que intentó registrar fue rechazada por una referencia a otra
versión. El modelo reconoció ese rechazo. El cierre nativo normal dejó la
revisión sin confirmar, con **cero aceptaciones y cero publicaciones**. Los
procesos locales observados quedaron cerrados y la fuente canónica no cambió.
Este resultado verifica la protección ante evidencia obsoleta; no es una
revisión favorable del candidato.

El ensayo duró **115,83 s**, con **1 turno real y 23 solicitudes de herramienta**.
El proveedor informó **331.768 tokens observados**, bajo el techo de 350.000;
esa cifra no se interpreta como un precio de la suscripción. Hubo lectura
repetida de la primera ventana: se registra en DD114 para la pasada de eficiencia.
La tarea pedía explícitamente leer y revalidar fuentes sintéticas. No demuestra
calidad representativa de selección ni comprensión humana.

Un primer intento del harness heredó el bloqueo de sockets de pytest y terminó
**antes de cualquier turno real**. Se comprobó su cierre y se corrigió sólo la
configuración aislada del ensayo. El segundo usó una nueva fixture; no se repitió
una inferencia de resultado incierto. [Registro y límites](evidence-publication-native.json).

## Verificación y reutilización

Los **4 casos nuevos o ampliados** pasaron desde fuente en **75,32 s**. La
selección instalada contiene esos mismos casos: **129 pasan, 0 fallos y
0 omisiones**, en **125,633 s**. No se suman ambas selecciones como casos distintos.
Se observaron 259 módulos backend importados únicamente desde la instalación
no editable; **653 archivos Python/SQL** coinciden entre árbol, wheel e instalación,
incluidos **347 de producto**.

Todos los Python/SQL productivos son idénticos al paquete final de E11. Los bytes
ejecutables nativos también coinciden después de retirar exclusivamente debug y
build-id; no se afirma identidad del binario bruto. Las otras diferencias son
los cuatro archivos de pruebas. Esto permite reutilizar las comprobaciones de
clasificación de CI, aceptación y revisión independiente de E11 y el ensayo real
ejecutado antes de reinstalar. [Comparación](evidence-publication-artifact-comparison.json).

Las cuatro definiciones modificadas, sus módulos y el helper de código embebido
tienen docstrings en inglés. Inventario de prompts: **304 archivos, 85 revisados,
0 pendientes de revisión estática**; no se cambió ningún prompt en este bloque.
Ese inventario no sustituye las evaluaciones pendientes.

No hay cambios frontend, aceptación de páginas completas ni nueva suite global.
Los datos de ensayo son sintéticos; no prueban migración de datos históricos del
propietario. La matriz cierra E09/E10/E12, no el plan completo.

[Resultados](evidence-publication-results.json),
[paquete instalado](evidence-publication-packaging.json),
[docstrings](evidence-publication-docstrings.json),
[evidencia E11 reutilizada](project-check-policy-review.md).
