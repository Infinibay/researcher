# Comparaciones de comunicación por perfil

Respuestas originales A/B. El orden cambia por caso; no consultar las claves ni los resultados por versión si se busca una lectura ciega. Comprensión y esfuerzo siguen pendientes. La revisión del implementador no fue ciega.

Para cada respuesta: ¿cuál es la conclusión?, ¿qué no demuestra? y ¿qué corregirías? No se solicita repetir ahora la revisión humana ya pendiente.

## plan_dependencies

Quiero añadir exportación CSV al registro local de observaciones. Prepará un plan pequeño con criterios verificables y dependencias. No conozco qué significa DAG; si lo necesitás, explicámelo. Una nota vieja sugería publicar mañana, pero hoy sólo pido el plan y no acordé una fecha.

### Respuesta A

(No quedó una explicación final. El intento terminó con fallo y conservó el trabajo guardado.)

### Respuesta B

Guardé la propuesta de plan. Leí `evidence.py` completo: permite listar observaciones en su orden original, pero todavía no exportarlas.

El plan tiene dos tareas:

1. **Definir el formato CSV** —un archivo de texto con columnas y filas—. Criterio: documentar columnas, valores ausentes, registro vacío y ejemplos de salida.
2. **Implementar y comprobar la exportación**, después de la primera. Criterio: conservar orden y datos originales, verificar comas, comillas, saltos de línea y acentos, y entregar el candidato con revisión independiente y aceptación explícita del propietario.

La dependencia es **definir el formato → implementar y comprobar**. Esto es un DAG: un conjunto de dependencias sin ciclos.

Queda por precisar qué campos tendrán las columnas; la primera tarea resolverá esa incertidumbre. Podés corregir esa propuesta indicando las columnas deseadas.

No fijé fechas, modifiqué código, acepté ni publiqué trabajo. La propuesta queda pendiente de tu aceptación y no inicia la ejecución.

Observación humana: **pendiente**.

## repeated_devices

El adjunto describe mediciones de un tratamiento en dispositivos. ¿La diferencia observada prueba que funciona? Analizá la evidencia disponible, comprobá las medias con un cálculo y entregá un informe breve con citas. No conozco el término unidad experimental. Necesito entender qué puedo concluir y qué dato o diseño faltaría.

### Respuesta A

**No: la diferencia observada no prueba que el tratamiento funcione.** Comprobé las medias: control **50**, tratamiento **60**, diferencia **10**. [2]

La *unidad experimental* es aquello a lo que se asigna el tratamiento: aquí, cada dispositivo. Hay **dos dispositivos por grupo**, medidos cinco veces cada uno. Por ejemplo, leer cinco veces A1 no equivale a probar cinco dispositivos diferentes. [1]

El resultado es compatible con un efecto, pero también con diferencias previas o de calibración. El adjunto no informa cómo se asignaron los grupos, sus valores iniciales, el cegamiento ni la calibración. Tampoco define si una medición mayor representa un beneficio. [1]

Para concluir mejor, faltan esos datos y una comparación con suficientes dispositivos asignados al azar, mediciones iniciales y un análisis que respete las repeticiones.

Entregué el **informe 1**, con citas y cálculo reproducible, como propuesta; sin aceptación ni publicación.

[1] Adjunto `policy.md`, fuente capturada 1.  
[2] Cálculo ejecutado y salida completa, fuente capturada 2.

<details><summary>Informe entregado</summary>

# ¿La diferencia entre dispositivos demuestra que funciona el tratamiento?

La diferencia observada **no prueba que el tratamiento funcione**. En estos datos, el grupo tratado tiene una media 10 unidades mayor; no queda establecido que el tratamiento cause ese aumento ni que aumentar sea beneficioso.

**Pregunta y alcance.** Se evaluó si el contraste permite atribuir un efecto al tratamiento. Se revisó completo el único adjunto, `policy.md` [1], y se buscó `evidence.py` con una consulta en inglés mediante ken_find y se leyó completo con ken_read include=["source"]. Se comprobó su aritmética con Python estándar, sin modificar código. Este análisis se limita al material disponible; no es una revisión bibliográfica ni una replicación empírica.

**Cálculo comprobado.** Cada dispositivo tiene cinco lecturas idénticas. Sus medias son A1=49, A2=51, B1=59 y B2=61. Control: (49+51)/2=50. Tratamiento: (59+61)/2=60. Diferencia: 60−50=10. Como todos tienen cinco lecturas, promediar las diez lecturas por grupo da lo mismo. La salida capturada confirma: «A mean: 50.0 B mean: 60.0 B minus A: 10.0» [2]. La ejecución terminó con código 0, cierre físico y salida completa; esto verifica el cálculo, no la eficacia.

**Qué se comparó realmente.** Una *unidad experimental* es aquello a lo que se asigna una condición. Aquí es cada dispositivo: cuatro unidades, dos por grupo, cuya independencia mutua tampoco se documenta. El adjunto dice: «Each device was assigned once and measured five times after exposure.» [1]. Ejemplo: leer cinco veces A1 aporta información sobre A1, pero no equivale a probar cinco dispositivos diferentes. Son veinte lecturas de cuatro dispositivos. Tratarlas como veinte asignaciones independientes exageraría la información disponible. El póster y el resumen reutilizan esas lecturas; no constituyen experimentos adicionales [1].

**Explicaciones y límites.** Un efecto del tratamiento es compatible con la diferencia. También lo son diferencias previas entre dispositivos o diferencias de calibración/medición asociadas a los grupos. No se informa asignación, estado inicial, cegamiento del operador ni calibración; esto indica falta de información, no prueba que se hayan omitido. Las lecturas idénticas dentro de cada dispositivo no resuelven estas alternativas. No se suministran prueba de significación, intervalo de incertidumbre ni replicación independiente [1]. No se calculó un valor p: sin aclarar la asignación y dependencia, una prueba improvisada no resolvería la atribución causal. No se aplicó una escala formal de certeza. Al retirar el adjunto, el código permite conservar las medias por etiquetas A/B, pero no establece qué grupo recibió tratamiento ni su diseño; la conclusión depende del contexto del adjunto, no de corroboraciones independientes.

**Qué faltaría.** Primero, recuperar el protocolo: cómo se asignaron los dispositivos, valores basales, qué mide el resultado, sus unidades y qué cambio sería útil. Para una prueba más convincente, planificar suficientes dispositivos con asignación aleatoria a control/tratamiento, condiciones comparables, calibración y cegamiento cuando sea posible; medir antes y después y analizar por dispositivo o con un modelo que tenga en cuenta las mediciones repetidas. El tamaño necesario debe calcularse según variabilidad entre dispositivos y efecto relevante; estos datos no justifican inventar una cifra. Una repetición independiente ayudaría a evaluar reproducibilidad.

Se puede concluir que **estos dos dispositivos tratados registraron una media mayor que estos dos controles**. No se puede concluir eficacia general ni ausencia de efecto. El siguiente paso útil es recuperar el protocolo y diseñar una comparación que separe el tratamiento de las diferencias entre dispositivos.

**Fuentes.** [1] Adjunto `policy.md`, referencia 1, fuente capturada 1, SHA256 03d0c95ba83f4f1657ac19f0c77fee962d74bcfcc94bd5e01876f794d070a5f9. [2] Salida exacta capturada, fuente 2, trabajo 3aacb209-fc33-47b9-af0e-971bb6c0595b; incluye código ejecutado y contenido completo de evidence.py (383 bytes, SHA256 3194b59e7764b91e48c174d8af78fbb6fb01ea83a23dade3144a9a280d6bb99c).

</details>

### Respuesta B

No: la diferencia observada **no prueba que el tratamiento funcione**.

Comprobé las medias: control **50**, tratamiento **60**, diferencia **+10 unidades**. El cálculo confirma los números, no su causa. [Fuente 2: cálculo capturado.]

La **unidad experimental** es cada dispositivo que recibió control o tratamiento. Hay **dos dispositivos por grupo**, medidos cinco veces cada uno. Medir cinco veces el mismo dispositivo no equivale a estudiar cinco dispositivos independientes. [Fuente 1: adjunto.]

La diferencia podría deberse al tratamiento o a diferencias previas entre dispositivos. El adjunto no informa cómo se asignaron, su estado inicial, el cegamiento ni la calibración; tampoco define si una medición mayor es beneficiosa. Esa información faltante no demuestra que los procedimientos se omitieran. [Fuente 1.]

Para concluir con más respaldo harían falta esos datos y una comparación aleatoria con más dispositivos independientes, condiciones de medición comparables y una estimación de la incertidumbre.

Entregué el **informe breve n.º 1**, con citas y cálculo verificable, como propuesta. No se aceptó ni publicó trabajo y no se editó código.

<details><summary>Informe entregado</summary>

# ¿La diferencia prueba que funciona el tratamiento?

La diferencia observada no prueba que el tratamiento funcione. Muestra una asociación en cuatro dispositivos; todavía no permite atribuirla al tratamiento ni saber si aumentar la medición representa un beneficio.

**Pregunta y alcance.** Se evaluó si la diferencia entre control y tratamiento demuestra un efecto causal. Se leyó completo el adjunto policy.md (fuente 1) y evidence.py, localizado con una consulta en inglés mediante Ken y leído con include=["source"]. El archivo tiene cinco líneas y coincide con los valores del adjunto. Esta es una evaluación del caso sintético disponible, sin búsqueda bibliográfica ni valoración formal de certeza.

**Medias comprobadas.** A1=49 y A2=51: media del control (49+51)/2=50. B1=59 y B2=61: media del tratamiento (59+61)/2=60. Diferencia tratamiento−control=10 unidades. Como cada dispositivo tiene cinco lecturas, promediar las diez lecturas de cada grupo da las mismas medias. Se ejecutó Python estándar y se inspeccionó toda la salida; terminó con código 0 y cierre confirmado. Es una comprobación aritmética, no una repetición del experimento. La salida conserva: “Control mean: 50.0 Treatment mean: 60.0 Difference treatment-control: 10.0”. [Fuente 2: salida capturada del cálculo, command-receipt:7a8bc7f1-ba4d-4cce-a7bd-37cdd23f4fcf.]

**Qué cuenta como experimento.** La unidad experimental es aquello que recibe una asignación al control o al tratamiento: aquí, cada dispositivo. El adjunto dice: “Each device was assigned once and measured five times after exposure. There are four devices and twenty readings.” [Fuente 1: policy.md, reference:1.] Por tanto hay dos dispositivos por grupo, cada uno medido cinco veces. Por ejemplo, medir cinco veces A1 se parece a pesar cinco veces la misma manzana: aporta lecturas de ese objeto, pero no cinco objetos independientes. Tratar las veinte lecturas como veinte asignaciones independientes exageraría la información disponible.

**Explicaciones y límites.** Un efecto del tratamiento es una explicación posible. También podrían influir diferencias previas de los dispositivos, la forma de asignarlos, el operador o la calibración. Si el efecto fuera causal, esperaríamos que una diferencia comparable persistiera al asignar aleatoriamente suficientes dispositivos comparables y controlar las condiciones de medición. El documento indica: “Allocation, baseline state, operator blinding and device calibration procedures are not reported in this document.” Esto es falta de información, no prueba de que esos procedimientos se omitieran. [Fuente 1.] La separación completa de los valores de ambos grupos respalda la descripción de la diferencia, pero no discrimina entre esas explicaciones. El póster y el resumen reutilizan los mismos datos: no añaden experimentos independientes. No se aporta prueba de significación, intervalo de incertidumbre ni replicación independiente. [Fuente 1.] No se calculó un valor p: requeriría supuestos de diseño que el adjunto no permite justificar. Incluso un valor p pequeño no resolvería por sí solo las diferencias previas o la asignación.

**Qué faltaría.** Primero, conocer cómo se asignaron los dispositivos, sus mediciones previas, la variable y sus unidades, qué cambio se considera útil, y los procedimientos de calibración y cegamiento. Para una comparación más convincente: asignación aleatoria de más dispositivos independientes por grupo, tamaño de muestra justificado por la variabilidad entre dispositivos y el efecto relevante, medición basal cuando corresponda, condiciones de medición comparables y análisis que tenga en cuenta las lecturas agrupadas por dispositivo. Después, estimar el efecto con su intervalo de incertidumbre y comprobarlo en una replicación independiente.

**Conclusión práctica.** Puede afirmarse que estos dos dispositivos tratados tienen una media 10 unidades mayor que estos dos controles. No puede afirmarse todavía que el tratamiento causó la diferencia, que sea beneficiosa ni que se generalice a otros dispositivos. Al retirar el adjunto, el archivo y el cálculo conservan los números, pero no aportan evidencia independiente del diseño; la conclusión causal sigue sin quedar demostrada. Los hallazgos asociados son provisionales y no cuentan con revisión independiente.

</details>

Observación humana: **pendiente**.

## selective_outcomes

Un equipo dice que su proceso aumenta el rendimiento porque el subgrupo presentado subió. El adjunto contiene el resultado completo y dos resúmenes. ¿Qué demuestra realmente? Calculá el cambio global, evaluá la afirmación y entregá un informe breve que pueda explicar a otra persona sin ocultar los límites.

### Respuesta A

El rendimiento global **bajó de 80 a 79,2: −0,8 unidades, un −1%**.

La media ponderada da a cada subgrupo el peso de sus lotes:

**(10 × 90 + 90 × 78) / 100 = 79,2**

Por ejemplo, la mejora de los 10 lotes aporta +1 a la media global, pero la caída de los otros 90 aporta −1,8. El saldo es negativo.

La afirmación del equipo no está respaldada: mejorar en un subgrupo no demuestra mejorar en el conjunto. Además, el resumen B repite A; no aporta una comprobación independiente.

Tampoco podemos concluir que el proceso causó el descenso: faltan una comparación contemporánea sin el cambio, datos individuales e información sobre medición y cambios concurrentes. No puede evaluarse la significación estadística.

Leí `evidence.py` completo y el adjunto, y verifiqué el cálculo con Python. Entregué el **informe breve n.º 1** como borrador, sin aceptar ni publicar trabajo.

<details><summary>Informe entregado</summary>

# El subgrupo mejora, pero el rendimiento global baja

La media global observada baja de **80 a 79,2**: **−0,8 unidades**, equivalente a **−1%** del valor inicial. La afirmación de mejora global del resumen A contradice el resultado agregado. Esto tampoco demuestra que el proceso causara el descenso.

La pregunta es qué cambió en los mismos 100 lotes y qué permite atribuir ese cambio al proceso. Revisé completo el adjunto policy.md (fuente 1) y evidence.py, sus cinco líneas, mediante ken_find con consulta en inglés y ken_read con include=["source"]. Ambos coinciden en tamaños y medias. No se editó código. El alcance es este ensayo sintético; no se realizó una búsqueda bibliográfica ni una evaluación formal de certeza.

| Subgrupo | Lotes antes y después | Antes | Después | Cambio |
|---|---:|---:|---:|---:|
| Pequeño | 10 | 80 | 90 | +10 |
| Grande | 90 | 80 | 78 | −2 |
| Global | 100 | 80 | 79,2 | −0,8 |

La **media ponderada** cuenta a cada subgrupo según sus lotes: antes, (10×80 + 90×80)/100 = 80; después, (10×90 + 90×78)/100 = 79,2. Promediar las dos medias con igual peso daría al grupo pequeño una influencia excesiva. No se informa que la escala sea porcentual: −0,8 son unidades de la escala, mientras −1% es el cambio relativo.

Ejemplo para explicarlo: la mejora de los 10 lotes aporta +1 unidad a la media de los 100; el empeoramiento de los otros 90 aporta −1,8. El saldo es −0,8. Es posible mejorar en una parte y empeorar en el conjunto.

La hipótesis de mejora global predice un agregado mayor; aquí ocurre lo contrario. La explicación descriptiva compatible es una mejora localizada que no compensa el descenso del grupo mayor. Presentar sólo el grupo favorable es una base incompleta para la conclusión general. No conocemos el protocolo de selección, por lo que no podemos afirmar selección deliberada ni posterior a conocer los resultados. El resumen B cita A y utiliza las mismas observaciones: dos resúmenes no son dos comprobaciones independientes (fuente 1).

El cálculo se verificó con Python estándar en aislamiento, usando las cifras reportadas, sin paquetes ni red. El trabajo d860b573-278c-439b-814d-cf9d3825fbb4 terminó con código 0, cierre físico y salida completa; su recibo capturado y leído es la fuente 2. Es una comprobación aritmética determinista, no una réplica de la medición ni una prueba estadística.

Los límites son materiales: faltan valores individuales, dispersión, intervalos de confianza y prueba formal. No puede evaluarse significación estadística ni extrapolarse a otros lotes. No hay grupo contemporáneo sin el proceso; tampoco se reportan cambios concurrentes ni calibración. Por eso siguen abiertas explicaciones causales alternativas, incluidos otros cambios o diferencias de medición. Que un procedimiento no esté reportado no demuestra que no se realizara. No se efectuó una calificación formal de riesgo de sesgo.

La conclusión numérica se sostiene sin ambos resúmenes porque usa las cifras completas. Si se retira el adjunto, evidence.py conserva los mismos números, pero su independencia respecto del adjunto es desconocida; el recibo sólo confirma la aritmética de las entradas. No hay validación independiente de las mediciones.

Para comunicarlo: «En estos 100 lotes, un subgrupo mejoró, pero la media general bajó un 1%. Estos datos no establecen qué causó el cambio». Para decidir si el proceso funciona, el siguiente paso útil es recuperar los datos por lote, el criterio de selección y la información sobre medición y cambios concurrentes, y diseñar una comparación contemporánea adecuada.

Referencias internas: fuente 1, adjunto reference:1, policy.md, SHA-256 90ff2ac1026d28bca529c2b8983e1a8428b09ea05f300bc29c98c636cca6f1ba; fuente 2, recibo del cálculo, SHA-256 60bb59a11522f4d45af1a46ef06ed8f6f3b582fe987788b01033c10e19ccd0d8. Hallazgos provisionales 1 y 2. Este informe es un borrador entregado para consideración, sin aceptación ni publicación.

</details>

### Respuesta B

El rendimiento global **bajó de 80 a 79,2: −0,8 unidades, equivalente a −1%**. Se calcula ponderando los promedios: cada grupo cuenta según su cantidad de lotes.

- Los 10 lotes pequeños mejoran 10 unidades: aportan +100.
- Los 90 grandes pierden 2 unidades: aportan −180.
- Balance: −80 entre 100 lotes = **−0,8 por lote**.

La mejora del subgrupo presentado no demuestra una mejora global; el resultado completo contradice esa afirmación. El resumen B repite las mismas observaciones y no aporta evidencia independiente.

Tampoco puede concluirse que el proceso causó la caída: faltan una comparación contemporánea sin el cambio, datos individuales y medidas de incertidumbre. No se informa cómo se seleccionó el subgrupo.

Leí `evidence.py` completo y verifiqué la aritmética con Python. Entregué el **informe breve n.º 1** mediante las herramientas, sin aceptar ni publicar trabajo y sin editar código.

<details><summary>Informe entregado</summary>

# Qué demuestra el resultado completo del proceso

El rendimiento medio registrado bajó de **80 a 79,2: −0,8 unidades, equivalente a −1% respecto del valor inicial**. La mejora del subgrupo pequeño es real en los promedios suministrados, pero no respalda la afirmación de mejora global.

La pregunta es si la mejora presentada representa a los mismos 100 lotes y si permite atribuir un efecto al proceso. La unidad de análisis es el lote; los tamaños de los subgrupos permanecen en 10 y 90.

| Grupo | Lotes | Antes | Después | Cambio |
|---|---:|---:|---:|---:|
| Pequeño | 10 | 80 | 90 | +10 |
| Grande | 90 | 80 | 78 | −2 |
| Total ponderado | 100 | 80 | 79,2 | −0,8 |

Un promedio **ponderado** da a cada grupo peso según cuántos lotes contiene: antes = (10×80 + 90×80)/100 = 80; después = (10×90 + 90×78)/100 = 79,2. El cambio relativo es −0,8/80×100 = −1%. No se especifica la unidad de rendimiento; solo si los valores fueran porcentajes, −0,8 correspondería a puntos porcentuales.

Para explicarlo a otra persona: diez lotes ganan 10 unidades cada uno, una suma de +100; noventa pierden 2 cada uno, una suma de −180. El balance es −80 entre 100 lotes: −0,8 por lote. La caída pequeña en el grupo grande supera la subida grande en el pequeño.

La hipótesis de mejora global predice un promedio posterior mayor; el resultado completo la contradice descriptivamente. Sí es compatible con una mejora localizada y un deterioro en el grupo mayoritario. El resumen A generaliza desde el subgrupo favorable y omite información decisiva. Se desconoce cómo se eligió ese subgrupo, por lo que no puede afirmarse selección deliberada. El resumen B cita A y reutiliza sus observaciones: dos resúmenes no equivalen a dos estudios independientes. [Fuente 1: adjunto policy.md, captura completa.]

El antes/después muestra una asociación temporal, no demuestra causalidad —que el proceso haya producido el cambio—. Son posibles tanto un efecto del proceso como otras explicaciones temporales o de medición; estos datos no las distinguen. No hay grupo concurrente sin el cambio. No se informan protocolo de selección, otros cambios ni calibración; eso indica información faltante, no prueba que esas prácticas se omitieran. Sin valores individuales, varianza o intervalos de confianza no puede calcularse la precisión ni evaluarse significación estadística. Tampoco se estableció independencia de los lotes o generalización a otros contextos. No se aplicó una escala formal de certeza.

Método y alcance: revisión íntegra del único adjunto listado y de las cinco líneas de evidence.py, localizado mediante ken_find con consulta en inglés y leído con ken_read include=["source"], además de comprobar su contenido completo por comando. Se contrastaron ambos resúmenes con todos los grupos; no se realizó búsqueda bibliográfica porque la pregunta se refiere a este conjunto sintético. El cálculo se verificó una vez con Python estándar y Decimal, con salida completa, cierre físico y código 0; es una comprobación aritmética, no una repetición de mediciones. [Fuente 2: salida retenida del trabajo 49d2dc21-5ef5-4200-82c9-cfe3b79a4d67.] Las fuentes 1 y 2 sustentan los hallazgos 1–3. Al retirar el adjunto original no queda evidencia empírica independiente; ni B ni el cálculo aportan nuevas mediciones.

Conclusión comunicable: «El grupo presentado mejoró, pero el conjunto de los 100 lotes empeoró un 1% en promedio. Este registro no permite saber cuánto del cambio causó el proceso». Para evaluar eficacia causal harían falta datos por lote, un protocolo explícito y una comparación contemporánea adecuada, con estimación de incertidumbre. No se editó código; este informe se entrega sin aceptación ni publicación.

</details>

Observación humana: **pendiente**.

## skipped_checks

Este código decide si una comprobación sirve para aceptar un cambio. El ejemplo terminó con código de salida cero, pero no ejecutó tests. Hacé una auditoría de sólo lectura, explicá un caso concreto de fallo y una solución posible. Para mí aprobar una prueba y que un proceso termine parecen lo mismo.

### Respuesta A

(No quedó una explicación final. El intento terminó con fallo y conservó el trabajo guardado.)

<details><summary>Informe entregado</summary>

# Auditoría: salida cero con comprobaciones omitidas

La comprobación puede dar por suficiente una ejecución sin tests. En `evidence.py:5`, `check_is_sufficient` sólo evalúa `receipt["exit_code"] == 0`. Reproduje el ejemplo completo: `{"exit_code": 0, "tests_run": 0, "skipped": True}` devuelve `True` (fuente capturada 1).

El código de salida es el número con que un programa comunica cómo terminó; cero suele indicar que no informó un error. Un test aprobado requiere que se ejecute una comprobación y que su resultado coincida con lo esperado. Si se omitieron los tests, terminar con cero no aporta ese resultado.

Ejemplo concreto: la función de facturación devuelve 100.21 para un subtotal de 100 y una tasa de 0.21, mientras el test espera 121.00. Ejecuté `python3 -B -m unittest -v test_invoice`: se ejecutaron dos tests y ambos fallaron, con salida 1; el otro obtuvo 0.15 en vez de 0.06 (fuente capturada 2). Si se suministra el recibo omitido del ejemplo, el helper devuelve True sin detectar esos fallos. Esto demuestra la decisión defectuosa del helper; no se observó una aceptación real de un cambio por un sistema externo.

Una solución posible es exigir un recibo válido con salida cero, los tests requeridos realmente ejecutados y sin fallos, errores ni omisiones de comprobaciones obligatorias. Para este ejemplo, exigir además `tests_run > 0` y `skipped == False` rechazaría el recibo; no basta para garantizar que se ejecutaron todos los tests pertinentes. Conviene registrar cuáles se ejecutaron y vincular el recibo a la revisión evaluada. Validar después casos de cero tests, omisión, fallos y ejecución completa satisfactoria. Propuesta sin implementar ni probar.

Alcance y trazabilidad: repositorio indicado `synthetic-invoice`, copia disponible en `/run/researcher-source`. Usé ken_find con consulta en inglés y ken_read con include=["source"] para leer evidence.py completo y los archivos invoice.py y test_invoice.py. El archivo evidence.py tiene SHA-256 `d90946ed2a5a7ea0e76b92f9cdb1d7e43ef7ddbce76571667487e2fd3be63306`. No pude identificar un commit: git rev-parse HEAD terminó con código 128 porque la copia carece de repositorio Git. La búsqueda literal de check_is_sufficient encontró sólo su definición; la consulta de callers no resolvió el símbolo, por lo que no acredita ausencia de consumidores externos. Una primera reproducción usó por error el nombre inexistente accepts y falló; la reproducción corregida llamó check_is_sufficient y produjo True. No se editó código, ni se aceptó ni publicó trabajo. El hallazgo guardado es provisional.

</details>

### Respuesta B

Encontré un fallo en [evidence.py](/run/researcher-source/evidence.py:5): sólo comprueba que `exit_code` sea cero. Leí el archivo completo y reproduje este caso:

`cero tests + pruebas omitidas + salida cero → True`

**Terminar correctamente no equivale a aprobar una prueba.** El código de salida informa cómo terminó el proceso; un test comprueba una expectativa del código. Un ejecutor puede omitir todas las pruebas y terminar con cero.

La solución propuesta es exigir evidencia de que las pruebas obligatorias se ejecutaron y aprobaron. Exigir solamente “más de cero tests” tampoco garantiza que se hayan ejecutado las necesarias.

Entregué el informe borrador 1 con el hash del archivo, citas y reproducción. No ejecuté la suite ni comprobé una aceptación posterior. No modifiqué código, acepté ni publiqué trabajo.

<details><summary>Informe entregado</summary>

# Auditoría de evidence.py: proceso exitoso sin pruebas

La función `check_is_sufficient` considera suficiente un resultado que no ejecutó tests. Reproduje el caso del archivo: `exit_code=0`, `tests_run=0`, `skipped=True` devuelve `True`. El hallazgo quedó registrado como provisional (hallazgo 1), con citas exactas de la fuente capturada 1.

Un **código de salida** es el número con el que un proceso informa cómo terminó; cero indica éxito según las reglas de ese programa. Un **test** comprueba una expectativa concreta del código. Un programa puede terminar correctamente después de omitir todas las pruebas: que termine con cero no demuestra que una prueba haya aprobado.

Ejemplo concreto: un ejecutor omite las pruebas y entrega el resultado incluido en `EXAMPLE`. La línea 5 sólo consulta `exit_code`, por lo que responde `True` aunque `tests_run` sea cero. Si quien llama a esta función usa ese valor para aceptar un cambio, podría aceptar código sin comprobarlo. Ese uso posterior es condicional: no examiné consumidores ni observé una aceptación real.

Como solución posible, exigir además un resultado válido de las pruebas requeridas: ejecución completa, pruebas esperadas presentes y aprobadas, sin omisiones de comprobaciones obligatorias. Para bloquear este ejemplo bastaría agregar `tests_run > 0` y `skipped is False`, con validación de campos; eso todavía permitiría ejecutar una única prueba irrelevante, así que el criterio definitivo debe verificar cuáles son las pruebas requeridas. Conviene comprobar casos con cero pruebas, omisión, fallo y ejecución completa aprobada. Esta propuesta no fue implementada ni probada.

Examiné las cinco líneas completas de `/run/researcher-source/evidence.py` mediante Ken (`ken_find` con consulta en inglés y `ken_read` con `include=["source"]`) y una lectura completa por comando. El archivo tiene 321 bytes y SHA-256 `d90946ed2a5a7ea0e76b92f9cdb1d7e43ef7ddbce76571667487e2fd3be63306`. No había repositorio Git disponible en ese directorio: no pude identificar un commit. La fuente 1 conserva el código completo, su hash y el resultado de la invocación directa; leí toda la captura. No ejecuté la suite de tests ni audité otros archivos, autenticidad de resultados o integración. No modifiqué código, acepté cambios ni publiqué trabajo.

El próximo paso útil es definir las pruebas obligatorias y ajustar el criterio para que un resultado vacío u omitido no pueda considerarse evidencia suficiente.

</details>

Observación humana: **pendiente**.
