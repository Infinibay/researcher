# Comunicación durante desarrollo: un par real

Dos turnos nuevos con la suscripción de OpenAI, `gpt-6.1-sol/low` y Ken publicado.
Ambos implementaron un candidato CSV en su copia privada y entregaron explicación
en español. No hubo aceptación, publicación ni modificación del original.
[Recibos](development-communication-live.json),
[verificación](development-communication-results.json),
[respuestas completas](development-communication-responses.json).

## Registro y controles

Se congelaron petición, ejemplo de entrada/salida, seis pruebas, fuente inicial,
políticas y cuatro archivos del evaluador antes de generar respuestas. El
[registro original](development-communication-evidence/registration.json) y sus
inputs se conservan; la base del repositorio era `e1ec84b`, y los hashes del
evaluador identifican los cambios aún no comprometidos al registrarlo.

Es desarrollo real: capacidad `development`, tarea `code`, repositorio Git
sintético con base idéntica, edición privada y captura productiva del candidato.
La inyección de política rechaza cualquier otra capacidad. El comparador verificó
entrada sustantiva, catálogo y selección de modelo/esfuerzo iguales. Cada brazo
recibió un turno, 180 segundos, 20 herramientas y 350000 tokens observados como
techos; no se aumentaron límites del operador ni se repitió un intento.

| Brazo | Resultado | Tokens observados | Tiempo del brazo |
| --- | --- | ---: | ---: |
| Política histórica | Candidato y explicación entregados | 231480 | 81,104 s |
| Política actual, catálogo9 | Candidato y explicación entregados | 205048 | 77,039 s |

Total: **436528 tokens observados y 158,143 segundos**. Preparación, análisis y
documentación quedan fuera del tiempo de los brazos. No es facturación ni cuota
restante. Ambos consumos quedaron asentados; no prueba superioridad del catálogo.

## Lectura del resultado

La revisión del implementador, **sin cegamiento**, encuentra apoyo para los cuatro
criterios registrados en ambos brazos:

- Implementan columnas, orden, cabecera vacía, quoting y errores por claves ausentes.
  El AST de `list_observations`, los tests suministrados y el original se conservan.
- Hay recibos completos de los seis tests nombrados y `OK`, con cierre físico.
  No se infiere cobertura de un código cero. El candidato usó un comando compuesto:
  su salida global no acredita por sí sola cada subcomando. Los tests tienen su
  transcript separado. No había comprobaciones independientes del host configuradas.
- Explican el propósito, el vínculo entre registros y filas/columnas y cómo una
  coma puede permanecer dentro de una celda. Ambas respuestas son corregibles e
  inspeccionables; eso no demuestra que una persona las comprenda.
- No convierten la nota histórica de publicación en una fecha acordada. Ambos
  runs quedan `needs_review`, la tarea `in_progress`, sin aceptación/publicación.

Se verificaron los diffs binarios exactos y las fuentes finales, conservados en
[evidencia](development-communication-evidence/). Los candidatos incluyen bytecode
incidental; se anota DD151 y se preserva en el diff, sin limpiar ni regenerar los
resultados. Las definiciones nuevas del código entregado tienen docstrings ingleses.
Los 67 y 65 peers registrados están cerrados; cero grants activos y servicios -15.

## Validación del evaluador y pendientes

Tres casos fallaron por faltar la selección explícita de capacidad y dos por no
existir todavía registro/fixture de desarrollo. Después pasan **32 comprobaciones
dirigidas**, sin omisiones. Una primera colección chocó entre dos módulos llamados
`test_protocol`: no ejecutó pruebas; `--import-mode=importlib` resuelve la invocación.
El registro rechaza cambios de inputs y un brazo iniciado bloquea replay.
Ruff deja seis avisos I001 de orden de imports en archivos previos y ninguno en
el módulo nuevo. Se anotan para pulido DD151; no se declara lint limpio.

Se reutiliza la instalación vigente del producto: sólo cambió el evaluador, no
el backend instalado ni su catálogo. No se reconstruyó un wheel ni se ejecutó la
suite global. No se afirma superioridad estadística o causal, representatividad
ni aceptación humana. El contrato explícito de entrada/salida también puede
explicar similitudes; este par compara políticas completas, no una frase aislada.

Quedan comparaciones de `code_review` y `finding_review`, recorridos UI de espera/
fallo recuperable/parcial y observación humana/adaptación. U08 sigue abierto.
