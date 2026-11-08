# Aceptación completa de Planificación

Inicio real **2026-11-08 04:27:54 UTC**, base `4607e8e`.
Concepto existente: `docs/design/concepts/planning/tree-detail.png`, selección en
su manifest.json. No generar otras variantes ni rehacer controles por pulido.

## Contrato observado y brecha reproducida

EpicsPage permite crear grupos e hitos, eliminar grupos, consultar dependencias
y revisar bases/suposiciones de una propuesta, enlazando la decisión a Tareas.
El piloto usó HTTP controlado; no acreditó persistencia ni recuperación real.
Las rutas de grupos/hitos siguen creando un registro por llamada, sin identidad
de solicitud. La UI conserva un borrador y advierte incertidumbre; no es idempotencia.

`backend/tests/api/test_planning_commands.py` repite la misma solicitud, incluida
una operation_key que los modelos actuales no declaran. Ambos POST responden201,
pero devuelven IDs2y3: sucede para grupos y para hitos. **Dos tests RED reales**,
`planning-commands-red.log`; cero turnos generativos. No es todavía una simulación
de pérdida de respuesta de red ni una reparación. El patrón reutilizable de
Proyectos está en `ProjectWorkspace.create` y projectPackets.

## Ejecución

1. Unificar las escrituras pertinentes en un servicio de planificación con una
   transacción inmediata: validar alcance, recuperar intención exacta o escribir
   recurso/recibo juntos. Misma clave y contenido devuelve identidad original;
   misma clave con otra intención se rechaza sin nuevo efecto. Una recuperación
   nunca recrea un recurso eliminado posteriormente.
2. Reusar infraestructura de recibos/transacciones donde sus contratos encajen.
   Para historial1:N, evitar reescribir todo metadata_json del proyecto en cada
   creación. Si hace falta tabla dedicada, registrar migración forward/inversa y
   verificar rollback/restore; no dar por reutilizable una tabla de otro dominio.
3. La web debe capturar y conservar la solicitud antes del envío; persistirla por
   proyecto, tipo y grupo cuando corresponda. Tras incertidumbre o recarga,
   recuperar la solicitud original explícitamente. Cambiar de proyecto o editar
   otro borrador no puede retargetearla ni borrar una petición más reciente.
   Reusar los patrones existentes en projectPackets antes de duplicarlos.
4. Decidir la compatibilidad de clientes existentes al leer consumidores reales.
   Todos los envíos de la web nueva llevan clave. No atribuir recuperación estable
   a una llamada antigua que no proporcionó identidad. Evitar introducir otro
   motor o un servicio de generación para estas acciones de metadatos.
5. Comprobar borrado real y su transacción: conservar tareas, dependencias y fuentes;
   verificar protección de historia nativa/planes y carreras con admisión. No
   asumir que el estado manual in_progress representa toda actividad o historia.
   Basarse en contratos actuales de planificación/ejecución antes de imponer una
   prohibición nueva. No relajar el control de historia para hacer pasar la UI.
6. Verde backend: repeticiones, conflicto de clave/intención, ámbitos distintos,
   rollback y recurso retirado. Documentar módulos/clases/métodos relevantes en
   inglés. Después comprobar el mismo código desde el paquete instalado limpio.
7. Navegador real: entrada/vacío, crear grupo/hito, dependencias y enlace original,
   propuesta/aceptación histórica, recarga, A→B→A, respuesta perdida/tardía real,
   errores parciales, sesión y conservación de datos. Datos sintéticos, cero
   turnos generativos; no repetir el plan aceptado ni los proyectos fallidos.
8. Inspeccionar capturas desktop/móvil contra tree-detail; teclado/foco y estados.
   Registrar evidencia de la ruta completa y lo que no demuestra. Pulido de
   densidad, etiquetas y demás detalles al registro final, sin desviarse del flujo.

**Estado inicial conservado:** diagnóstico y dos RED, antes de implementar. No se
incrementan3/12páginas ni41/43escenarios. Ken offline queda en4607e8e, verificado;
la contención original/U08/C10 siguen abiertos. No hay inferencia nueva, push o despliegue.


## Avance de la primera fase

2026-11-08,05:25:17UTC: creación recuperable y protección nativa verificadas.
Migración69 añade recibos1:N; legado sin clave mantiene llamadas simples, web nueva
siempre usa clave estable. Respuesta original identificada, no estado actual;
no se recrea un recurso retirado. Archivo de instalación usa sessionStorage.
124casos instalados,148contratos/51UI, tipos/build y pérdida real de respuesta tras
commit pasan.42definiciones documentadas; estilo pendiente, DD132.0turnos generativos.
57min23s desde inicio original hasta inspección/evidencia de esta fase, no cierre
de la página. [Resultado y límites](../../modernization/planning-commands-review.md).

Siguiente: completar pasos7–8 con propuestas/historia, diálogo de borrado,
errores/escala/teclado/móvil reales. Sólo cuatro capturas actuales son de esta página;
no extrapolar todo el recorrido compartido.3/12páginas y41/43escenarios permanecen.
