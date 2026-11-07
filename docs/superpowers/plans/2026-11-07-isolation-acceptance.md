# D10–D12 — acceso y aislamiento del recorrido actual

Inicio: **2026-11-07 22:06:26 UTC**. Base `dd1be91`.
Continuación del plan principal: primero las capacidades gruesas y después los
detalles. El bloque anterior dejó 31/43 escenarios comprobados.

## Contrato y evidencia disponible

- D10: la credencial de herramienta fija proyecto, tarea, actor, intento y
  capacidades en el servidor. No se convierte en sesión humana, SQL interno o
  suscripción WS; una corrección, retirada o DB reemplazada invalida el acceso.
- D11: homónimos, IDs de otro proyecto y enlaces externos no exponen adjuntos,
  informes ni fuentes ajenos. Los peers sólo reciben las vistas admitidas; los
  lectores del host también comprueban alcance e identidad.
- D12: toda ejecución de código, incluida CI, queda dentro de su perfil real.
  No recibe credenciales del host o salida de red general. La inferencia usa su
  canal de autenticación y egress propios, sin entregar esos permisos al código.

El contraste inicial encontró implementación y pruebas en `local_access.py`,
`research_dependencies.py`, `SQLiteResearchStore._check_scope`, `owned_runtime.py`,
`check_capsule.py`, perfiles del broker, proveedor de suscripción y proxy. Los
documentos antiguos describen etapas intermedias: no se toman sus pendientes ni
sus afirmaciones de seguridad como estado actual sin leer el código.

## Pasos y criterio de salida

- [x] Contrastar emisión y uso real de permisos con las rutas y modelos actuales;
  comprobar retirada de las entradas internas y launchers históricos.
- [x] Añadir una aceptación integrada con la fábrica actual y un intento real
  registrado: credencial A, adjunto/informe homónimo de B, intentos de sustituir
  alcance, acceso humano/SQL y retirada. Los rechazos no persisten efectos ni
  entregan bytes ajenos; el acceso permitido a A debe seguir funcionando.
- [x] Reforzar el ensayo de CI real con credenciales ficticias en archivos y
  entorno del host, DB y contenido de otro ámbito; comprobar que no se leen ni
  se modifica el origen, y que la red exterior permanece denegada. No usar
  secretos reales ni enviar peticiones a servicios externos.
- [x] Corregir sólo brechas funcionales demostradas, si aparecen. Una prueba de
  aceptación que ya pasa valida implementación existente; no exige inventar
  cambios ni retirar controles para producir artificialmente un fallo.
- [x] Ejecutar la selección instalada de middleware, permisos/recursos, fábrica,
  desarrollo/análisis/CI, Ken, credenciales, egress y retirada antigua. Conservar
  los límites y resultados fallidos; comprobar que no hubo omisiones.
- [x] Actualizar matriz, docstrings, estado y tiempo; commit local. Aceptación
  completa de páginas y comprensión humana siguen en sus propios bloques.

La inferencia y las identidades serán controladas. Las pruebas de kernel, Codex
sin generación, almacenamiento y transportes locales son reales cuando así lo
declara cada caso. Los ensayos históricos de suscripción/Ken mantienen su alcance;
no se repiten sin un cambio relevante en esas fronteras.

Verificación final: 2026-11-07 22:36:15 UTC; 29 min 49 s hasta verificar.
232/232 casos instalados pasan, sin omisiones; 674 fuentes coincidentes,
360 de producto sin cambios, tres definiciones documentadas. Ver
[matriz y límites](../../modernization/isolation-acceptance-review.md).
