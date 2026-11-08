# Repositorios: aceptación técnica y visual

`/repositories` completa la aceptación técnica y visual delegada del explorador y
la preparación explícita ya implementados. Se conserva el concepto elegido; no
cambian el renderer, el backend ni el wheel. Son **3 de 12 páginas** junto con
Documentos y Archivos. Bloque 02:02:43–02:22:16 UTC: **19 min 33 s hasta verificar**;
documentación y checkpoint posteriores no incluidos, base `941dc5f`.

Pasan 15 estados principales y 5 complementarios con HTTP, SQLite, filesystem y
Git reales: creación vacía, adopción conservando HEAD/configuración/nota local,
clonado autenticado con TLS verificado, árbol/código/Markdown y cambio de rama.
Un trigger SQLite rechaza el registro después de crear Git; observar recupera la
fuente sin otra revisión inicial. Una copia se detiene durante el intercambio TLS
y se repara mediante otra autorización, conservando una nota local añadida a la
carpeta parcial. La comprobación independiente confirma dos HEAD clonados exactos,
dos creaciones con un solo commit, originales intactos y credenciales fuera de
Git y de la historia de operaciones.

Se crea un remoto vacío privado en la organización elegida mediante una fixture
Forgejo controlada. El transporte TLS y los clientes del producto son reales;
la respuesta del proveedor es un modelo de contrato, no una cuenta real. Hay una
sola creación REST y cero escrituras Git al servidor desde el producto. La carga
inicial del bare Git es preparación local de la fixture, no publicación probada.

El ensayo complementario vuelve a abrir el host cerrado y registra carpetas
existentes. Tras perder una respuesta ya confirmada, recargar y recuperar devuelve
el mismo registro. Una carpeta sin Git muestra el límite de lectura, sin heredar
el repositorio padre. Fuentes homónimas entre proyectos conservan contenidos
distintos. Una respuesta posterior a A→B→A termina su recibo sin cambiar la fuente
seleccionada en la nueva visita. Se espera además la eliminación del paquete
original del navegador, evidencia de que su callback terminó. Las seis operaciones
originales de preparación permanecen idénticas; quedan ocho registros en total.

Pasan **54 casos backend instalados**, **16 contratos frontend** y **2 pruebas de
identidad en la interfaz**, sin omisiones. El mismo paquete coincide con 676 fuentes
y sus imports proceden del entorno instalado. Once definiciones Python nuevas
tienen docstrings en inglés; módulos y helpers del navegador tienen JSDoc.

Se conservan cuatro fallos previos del ensayo: selector de label con opciones,
espera insuficiente al reabrir el formulario, Stop con fence anterior y lectura
del estado detenido anterior antes de admitir una reparación. En el tercero,
el servidor rechazó correctamente una parada desactualizada; no se atribuye ese
rechazo a un fallo del motor. El cuarto interrumpió su fixture al cerrar el ensayo:
se conserva esa copia detenida y su autorización, sin reintentarla. El recorrido
final espera respuesta HTTP de cada gesto antes de interpretar el resultado.
No se suman las repeticiones como casos nuevos.

Cero runs, despachos o inferencias. Cierre de las seis preparaciones actuales y
de sus peers comprobado; servicios y servidores de pruebas cerrados. La contención
nativa anterior no se reprodujo en estas operaciones Git y sigue sin solución;
no se deduce su corrección de estos resultados. U08/C10 siguen abiertos, al igual
que comprensión humana, evaluación científica pendiente y cierre global.

DD128 recoge densidad de rutas/historia, actividad observada que requiere refresco
y dos avisos PLW1510 de los nuevos coordinadores; Ruff no se declara verde. Los
ajustes secundarios quedan para después de las capacidades mayores. No se afirma
zoom nativo ni accesibilidad exhaustiva. [Auditoría visual](../design/audits/2026-11-08-repositories-acceptance/report.md),
[resultados](repositories-page-results.json), [paquete](repositories-page-packaging.json),
[docstrings](repositories-page-docstrings.json), [reproducción](../../evals/operation/README.md).
