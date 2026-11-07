# Presupuesto local: recorrido web real

Interfaz compilada contra API del propietario y SQLite sintética, sin runtime
generativo configurado. Tres estados funcionales, dos escrituras explícitas y
seis comprobaciones. Se pierde intencionalmente la primera respuesta después
del commit; recargar y consultar el recibo recupera la misma decisión sin POST.

La segunda decisión reduce CPU local de6000a2000ms. Se conservan3000ms de consumo
desconocido y queda capacidad cero. La DB conserva exactamente una operación
local y el run/dispatch generativo previamente sembrados; ninguna escritura de
presupuesto crea trabajo. Dos recibos, revisión2 e integridad SQLite correcta.

Se inspeccionaron las capturas de escritorio y la captura móvil. Las dos de
escritorio muestran el panel completo. La móvil conserva recorte inferior por
scroll interno, comoDD108: verifica operaciones mediante el harness, pero no
prueba inspección visual de todos los controles ni aceptación de la página.
Axe del componente y desbordamiento exterior pasan en los tres estados. La
altura de viewport fue1600px y no sustituye la matriz responsive del producto.

La primera captura del tercer estado ocurrió antes del refetch: todavía mostraba
6000ms. El assertion usaba una coincidencia parcial de `0`, que también aceptaba
`3000`. Se corrigió a texto exacto del valor y se volvió a consultar **el mismo
servidor y estado**, sin repetir escrituras. La captura final muestra3000de2000
y restante0; se conserva la anterior como `03-before-refetch.png`.

[Recorrido y corrección](browser-evidence.json), [DB](database-evidence.json).
El script reproducible está en `frontend/tests/auxiliary-budget.browser.mjs`;
el servidor sintético y logs, en el directorio scratch del plan. Su cierre se
observó con salida0. Comprensión humana y aceptación integral siguen pendientes.
