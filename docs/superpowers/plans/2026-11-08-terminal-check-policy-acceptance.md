# Aceptación de código desde terminal y política observada

La integración de terminal llegó a una revisión confirmada y comprobaciones
válidas, pero su fixture no eligió política de comprobaciones. Ese bloqueo es
correcto. La observación durable de `/code` conserva `check_policy_unset` como
único impedimento; no se infiere la causa a partir del teardown.

Además, el consumidor CLI omite `check_policy_revision` al aceptar código. La API
y `CodeAcceptances.accept` ya exigen esa revisión. Corregir solo la fixture dejaría
la terminal incompatible con ese contrato.

## Cambio acotado

1. Añadir una regresión del transporte CLI: enviar la política observada y
   conservar una petición incierta si el recibo declara otra revisión.
2. Pasar esa revisión desde el estado guardado por `/code`, sin refrescarla
   automáticamente. Exigir la misma revisión en el recibo esperado.
3. En la integración, configurar por HTTP propietario una decisión explícita
   `allow_missing`, con recibo y sin inferencia. La comprobación existente es un
   comando de aserción; no se reclasifica como una suite de tests. La aceptación
   mantiene su reconocimiento explícito de límites.
4. Ejecutar las pruebas de terminal, cliente, política y el recorrido HTTP real
   con generación controlada. Conservar los fallos anteriores y distinguir el
   presupuesto de prueba de los límites del producto.

No cambia el contrato de la API, sus guardas, los recibos históricos ni la
política elegida por proyectos reales. La terminal sigue siendo un cliente del
servidor. La prueba configura el proyecto mediante el mismo endpoint propietario
que usa la web; añadir un editor CLI de política queda fuera de esta corrección.

Consumidores inspeccionados: `ProjectOrchestrator._accept_result`,
`OwnerClient.post/_send`, `AcceptCodeResult` y `CodeAcceptances.accept`. Ken devuelve
el índice del checkout original; se verificaron estas rutas en el worktree activo.
