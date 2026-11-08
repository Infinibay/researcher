# Comunicación de resultados guardados y recuperación de lectura

Se comprobó la consulta de dos resultados reales de ensayos anteriores, sin
generar nuevas respuestas: una revisión de código que pide cambios y un plan
guardado antes de alcanzar el límite de tokens. Se corrigieron mensajes que
presentaban como hechos una aprobación pendiente o una causa de bloqueo que
la pantalla no demostraba. **La espera de una herramienta activa y la comprensión
humana siguen pendientes.** U08 no se cierra con estas comprobaciones.

## Cambios y recorridos

1. Una revisión terminada se identifica como tal, aunque su decisión sea pedir
   cambios. Una propuesta guardada invita a revisar límites y comprobaciones,
   sin afirmar que sólo falta aceptarla. Cerrar un intento pendiente conserva
   lo guardado y no promete deshacer acciones. Se reutiliza el control existente.
2. Se interrumpe únicamente el GET del espacio de tarea. La interfaz muestra
   el fallo y «Volver a consultar»; al retirar el corte, foco y Enter recuperan
   el resultado original. No se reenvía una instrucción ni se ejecuta una herramienta.
3. El plan parcial muestra la causa registrada —límite de tokens— junto a su
   propuesta conservada, bases, supuestos y tres tareas. No ofrece aceptación.
   El mensaje de inelegibilidad ya no atribuye el bloqueo a cierre/contexto sin
   evidencia suficiente: pide revisar resultado y vigencia antes de continuar.

No se cambian contratos de aceptación, permisos, API ni prompts. El estado
registrado de la tarea y la actividad física siguen siendo conceptos distintos;
la densidad y su presentación más amplia permanecen en DD148.

## Procedencia y comprobaciones

[Resultados y huellas](execution-communication-results.json),
[capturas y alcance visual](../design/audits/2026-11-08-execution-communication/report.md).
El lector reproducible es [retained.py](../../evals/communication/retained.py), con
el recorrido [Playwright](../../frontend/tests/communication-baseline.mjs) y la
[entrada común de comunicación](../../evals/communication/README.md).

- Revisión: instalación del brazo actual de la [comparación de código](code-communication-review.md).
  Candidato controlado y explicación de revisor real, conservados sin modificaciones.
- Plan parcial: instalación del caso `plan_dependencies` de la
  [evaluación de presupuesto](delivery-budget-review.md), intento
  `25f7b6f7-8d96-4680-ac3d-a09ab93e8e68`, propuesta
  `8dac8b3b4f314fafb484fe1ea144314c`. Su fallo y su borrador son históricos reales
  del ensayo; no son un escenario exitoso inventado ni un historial del usuario.
- Dos recorridos finales, seis estados cada uno: **12 estados sin overflow ni
  infracciones axe en la región auditada**, cero errores de página y cero
  solicitudes de escritura prohibidas. Axe cubre `.task-execution` o, durante el
  fallo de lectura, `main [role="alert"]`; no certifica accesibilidad completa.
- Sólo GET y emparejamiento local. **Cero nuevas admisiones de modelo**. Todas
  las tablas/campos originales comparados mantienen sus hashes y cantidades;
  el registro de migraciones se trata por separado. En una lectura preliminar
  del plan se añadieron 16 tablas vacías al actualizar el esquema del host
  sintético, conservando los datos previos. Los recorridos finales no añaden
  tablas. No se han comprobado hashes de todos los archivos del repositorio.
- Los dos servidores pertenecen al lector y terminan con código143. Son lecturas
  de intentos cerrados, no prueba de espera actual ni de recuperación física.
- Verificación frontend posterior al último cambio: **165 contratos y77 pruebas
  UI pasan**,24 archivos Vitest; build correcto. Lint falla con15 errores en
  archivos que este bloque no modifica; se registran en DD154 junto al aviso de
  tamaño del bundle. No hay nueva suite global ni nuevo wheel en este bloque.

## Fallos conservados y límites

La comprobación inicial capturó un placeholder de carga: esas imágenes se
rechazaron y se exigió el título real antes de capturar. Otro lector falló al
buscar `.task-execution` cuando la rama de error lo desmonta; se corrigió el
alcance de la auditoría, conservando el resultado fallido. La prueba de copy
reprodujo el mensaje de aprobación anterior; otra comprobación negativa falló
con la atribución incorrecta de cierre/contexto del plan. Se conservan originales
y recibos; los recorridos finales pasan con las correcciones.

La lectura visual manual cubre las seis imágenes finales indicadas en el informe;
las otras seis sólo tienen comprobaciones automáticas. El texto completo del DOM
permite verificar copy que queda más abajo del viewport. No afirmar que cada
captura muestra íntegramente una tabla o una propuesta larga.

El corte de red es inducido, los resultados proceden de turnos reales anteriores
y el emparejamiento es local: cada fuente de evidencia tiene distinto alcance.
Estas pruebas no demuestran comprensión, menor esfuerzo humano, superioridad de
una política ni adaptación a una corrección humana. La respuesta del usuario pide
entender objetivo, datos, relaciones y entradas/salidas; debe orientar el próximo
recorrido útil, sin volver a un cuestionario abstracto.

Bloque iniciado **15:44:21UTC**. Recorridos finales desde16:31:56 y16:34:53UTC,
8,283s y9,380s respectivamente. Estos tiempos sólo miden lectores; preparación,
análisis, correcciones, build, inspección y documentación se contabilizan aparte
en el tablero. La siguiente capacidad es una espera viva de herramienta, usando
el coordinador productivo y conservando la identidad del mismo comando.
