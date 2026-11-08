# Documentos: aceptación técnica y visual

La ruta `/wiki` completa su aceptación sobre el producto instalado actual. Es la
primera de12páginas aceptadas. Se conserva el concepto elegido **Cuaderno con
alcance**; este bloque agrega un recorrido reproducible y su evidencia, sin
rediseñar el piloto ni cambiar el renderer del producto.

Bloque2026-11-08 01:08:25–01:27:09UTC: **18min44s hasta verificar**, base`a8e1e8b`.
Documentación/checkpoint posteriores no incluidos. La contención nativa continúa
como trabajo principal abierto; la biblioteca funciona sin iniciar inferencia.

El comando `evals/operation/web_workspace.py --journey wiki` crea otro host privado,
usando una cuenta sintética, y recorre la página con Chromium y HTTP/SQLite reales.
El coordinador comprueba por separado los efectos guardados:58páginas actuales,
25revisiones del documento principal, ámbito ajeno intacto y versión de una página
eliminada conservada fuera del índice actual. El borrado no restaura ni reutiliza
una identidad antigua. No se simulan respuestas de negocio; sólo se controlan
retraso/pérdida de respuestas reales y errores de transporte expresamente probados.

El recorrido canónico pasa25estados y10grupos de operaciones: conflictos,
comparación y sobrescritura elegida; recibo perdido y reintento idéntico; recibo
posterior a otra selección; borradores entre proyectos, cancelación de recarga y
renovación real de sesión; ámbito global explícito; creación/HTML literal;
borrado con teclado y texto retenido; índice de55documentos, búsqueda lexical,
historia de25versiones y lectura de110674bytes a320px. Una revisión complementaria
comprueba biblioteca vacía real y muestra completos comparación/texto retenido.
La lectura a720px ocupa su ancho disponible. [Recorrido y capturas](../design/audits/2026-11-08-wiki-acceptance/report.md).

Pasan **18casos backend instalados** y **8contratos frontend**, sin omisiones. El
mismo wheel limpio anterior coincide con676fuentes; los imports backend provienen
del entorno instalado. Dos funciones Python nuevas/modificadas y los módulos y
helpers del recorrido tienen documentación en inglés. El renderer y los fuentes
backend del producto no cambiaron, por lo que no se reconstruye otro artefacto.

El primer wrapper integrado falló porque esperaba `evidence.json` y el navegador
había escrito `interaction-evidence.json`; el navegador y la comprobación SQLite
independiente sí pasaron. Se conserva ese fallo. Se corrigió el nombre canónico y
el comando completo pasó en otro host nuevo. No se suman las repeticiones como
casos distintos ni como una comparación estadística.

La exploración CSS200% pasó el checker geométrico pero produjo un lector estrecho:
la inspección visual rechazó esa captura como prueba de zoom/accesibilidad. Los
atajos no cambiaron viewport/DPR en este Chromium headless. No se afirma zoom
nativo ni lector de pantalla completos;720px/320px son observaciones separadas.
Axe no detectó infracciones en las regiones de Documentos comprobadas; el acceso
bloqueado se observó aparte, sin atribuirle una auditoría Axe que no se hizo.

DD125 conserva avisos de guardado persistentes, etiqueta `owner`, altura de cabecera
y verificaciones manuales de accesibilidad. DD126 recoge el I001 ya existente en
los imports del evaluador; el estilo no se declara verde. Los ajustes secundarios
se resuelven después de las capacidades mayores, como pidió el usuario.

No hay inferencias, despachos ni runs en la aceptación. Servidores y peers cerraron;
el guardián registra `closed` y `domain_removed=true`. No se migró historial del
propietario. Esta aceptación técnica/visual delegada no acepta U08 ni demuestra
comprensión humana. Siguen41/43escenarios y once páginas restantes, además de la
contención, plan español/Ken, C10, evaluaciones, dependencias/distribución y cierre.

[Resultados](wiki-page-results.json), [paquete](wiki-page-packaging.json),
[docstrings](wiki-page-docstrings.json), [instrucciones](../../evals/operation/README.md).
