# Capacidad Ken estructural disponible sin red

Base de diagnóstico: `dac2b4e`; [causas y recibos](../../modernization/ken-capability-diagnosis.md).
Autorizado dentro de la modernización, sin nueva generación para verificarlo.

1. Seguir `KenInstallation.inspect`, `worker_process`, bootstrap/host preflight y
   sus consumidores reales antes de cambiar el contrato compartido. Ken no indexa
   el runtime moderno: contrastar sus resultados con imports del checkout b09e.
2. Definir un conjunto explícito de gramáticas soportadas/preparadas y su versión,
   procedencia, tamaños y hashes. Prepararlas como recursos públicos fuera del
   peer. Reusar la provisión existente si cubre ese contrato; evitar otro sistema
   de configuración si no aporta capacidad necesaria.
3. RED: un análisis Python real con llamador conocido falla bajo el worker offline
   actual. Verificar además que instalación incompleta o recurso alterado se rechaza
   antes de inferir. Conservar presupuestos, montajes de fuente y aislamiento.
4. Implementar preflight y montaje de sólo lectura de recursos fijados; comprobar
   compatibilidad del loader instalado. No descargar dentro de Ken ni aceptar una
   caché arbitraria modificable desde la fuente. Docstrings en inglés.
5. GREEN: mismo análisis con árbol/llamador correctos y un caso negativo, MCP real
   sin red, cero modelos. Distinguir éxito de transporte y contenido. Comprobar
   originales intactos y terminación de los procesos; no contar generaciones.
6. Orientar el uso de `ken_find`: compact para files/symbols; tests con argumentos
   admitidos. Mantener errores originales, sin éxito inventado ni reintento de
   efectos. Verificar la política enviada al actor y su revisión estática; su
   eficacia generativa se evalúa después, sin repetir el plan aceptado.
7. Construir sdist→wheel limpio, instalar y ejecutar selección de consumidores;
   verificar inventario y docstrings. Actualizar matrices sin cerrar AuthorityBusy,
   Proyectos o comprensión humana por esta reparación. Detalles visuales al final.
