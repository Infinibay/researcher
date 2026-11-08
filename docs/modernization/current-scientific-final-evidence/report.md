# Cálculos renales: diferencia observada y límites de la conclusión causal

La afirmación «el segundo tratamiento causa mejores resultados» **no está justificada con este material**. Sí se observó una mayor proporción de éxitos en el segundo grupo.

La pregunta es si esa diferencia entre dos grupos permite atribuir el resultado al tratamiento. La unidad contada es el paciente; el desenlace transcrito es eliminación de cálculos o reducción a menos de 2 mm a los tres meses. [1]

| Grupo | Éxitos / pacientes | Tasa de éxito |
|---|---:|---:|
| Cirugía abierta | 273 / 350 | 78,00 % |
| Nefrolitotomía percutánea | 289 / 350 | 82,57 % |

La diferencia calculada es **82,57 − 78,00 = 4,57 puntos porcentuales**, con 16 éxitos más entre dos grupos del mismo tamaño. El porcentaje expresa la proporción dentro de cada grupo: 78 % significa 78 de cada 100. Los puntos porcentuales expresan la resta entre dos porcentajes. Aquí equivale, al expresar las tasas por cada 100 pacientes, a unos 4,57 éxitos observados más por cada 100 en el segundo grupo; no significa que cambiar de tratamiento produzca ese beneficio en una persona. Tampoco debe llamarse «4,57 % de mejora relativa». [2]

Una diferencia causada por el tratamiento es una explicación posible. También podrían contribuir diferencias previas entre pacientes, la selección de tratamiento o la variación aleatoria. El fragmento no permite distinguirlas. Para hacerlo faltarían detalles sobre cómo se asignó el tratamiento, comparabilidad y factores pronósticos iniciales —por ejemplo, tamaño del cálculo—, seguimiento y pérdidas, evaluación uniforme del desenlace y un análisis de incertidumbre apropiado al diseño. No afirmamos que hubiera desequilibrios ni que esos métodos se omitieran: simplemente no están descritos en lo suministrado. [1; interpretación del evaluador]

Alcance y comprobación: se capturó y leyó íntegramente policy.md y se buscó evidence.py mediante una consulta en inglés con ken_find, leyéndolo completo con ken_read include=["source"]. Sus cinco líneas concuerdan con los conteos. Python estándar, con fracciones exactas, calculó las dos tasas y su diferencia; la ejecución terminó con código 0, cierre físico confirmado y salida completa sin errores. Es una comprobación aritmética, no una nueva medición del estudio. No hubo cambios de código, búsquedas externas ni revisión del artículo completo. [1–2]

El adjunto es una transcripción de hechos seleccionados del resumen atribuido a Charig et al. (1986), no una nueva cohorte: el estudio incluyó 1052 pacientes en cuatro grupos y aquí solo se describen dos. No se verificaron métodos completos ni subgrupos por tamaño del cálculo, ni se realizó una evaluación formal de certeza. El código y el cálculo no son evidencia clínica independiente: sin la transcripción, esta evaluación carece de una fuente clínica independiente. La conclusión queda limitada a esos conteos y ese desenlace histórico; no se hacen recomendaciones clínicas actuales. [1]

La formulación respaldada es: **«En los grupos transcritos, la tasa de éxito fue 78,00 % frente a 82,57 %, una diferencia observada de 4,57 puntos porcentuales; estos datos por sí solos no demuestran una ventaja causal del segundo tratamiento».**

Referencias del material examinado:

[1] policy.md, fuente capturada 1, reference:1, SHA-256 7f8595fc3377bfd55af0a7b9bce05fa5b50cf01fca1d61d9a52244c3ca05a381. Citas exactas: “Open surgery: 350 patients; 273 classified as successful.”; “Percutaneous nephrolithotomy: 350 patients; 289 classified as successful.”; “This excerpt does not describe group assignment, baseline comparability or uncertainty estimates.” El DOI 10.1136/bmj.292.6524.879 es una atribución del adjunto; no se consultó su destino.

[2] Salida capturada de Python, fuente 2, job 4fade0c3-6e96-4bd4-835e-856923555305, SHA-256 690fe6d021bc24fca7227c3a6c3aa21bd30cfa88922a983a4569f6c00e599d23. Cita exacta: “difference second minus first: 8/175 = 4.5714285714 percentage points”.
