# Recuperar una búsqueda o extracción local interrumpida

En Tareas, abre **Presupuesto de trabajo → Revisar cálculos locales**. Consulta
el diagnóstico de la operación original antes de pedir otra:

| Diagnóstico | Acción disponible |
| --- | --- |
| Resultado guardado | Solicita la misma búsqueda o vista previa; se recupera sin otro cálculo. |
| Dueño o trabajador activo | Espera su resultado o usa el control existente de detención. Un tiempo agotado no prueba cierre. |
| Cierre comprobado sin resultado | Autoriza un nuevo cálculo. Guardar no lo ejecuta; la próxima solicitud idéntica usa otra reserva. |
| Historial restaurado | Puedes autorizar un cálculo nuevo en esta instalación. No se afirma que el host original terminó. |
| Identidad ausente o cierre incierto | Conserva el registro. La pantalla no ofrece una repetición que suponga el cierre. Usa recuperación de instalación si necesitas seguir sobre una copia. |

Por ejemplo: un cálculo dejó3000ms desconocidos. Autorizar su sucesora no borra
esa reserva. Si la nueva ejecución mide25ms, se contabilizan3025ms; si no hay
capacidad, se rechaza antes de iniciar el proceso. Un permiso retirado tampoco
se restaura al guardar esta decisión.

## Recuperación de instalación

Usa la instalación administrada y los comandos existentes, conservando siempre
el original. Los destinos y el witness deben ser nuevos. Las rutas siguientes
son marcadores; el archivo de assets contiene la configuración explícita de la
instalación nueva, sin pegar credenciales en comandos o documentos.

```sh
python -m backend.cli.bootstrap backup-host --directory /ruta/original --destination /ruta/backup-nuevo
python -m backend.cli.bootstrap verify-backup --backup /ruta/backup-nuevo
python -m backend.cli.bootstrap restore-host --backup /ruta/backup-nuevo --destination /ruta/restauracion-nueva
python -m backend.cli.bootstrap enroll-restored-host --directory /ruta/restauracion-nueva --witness-dir /ruta/witness-nuevo --assets /ruta/assets.json
```

El backup exige las comprobaciones de propiedad y consistencia existentes. Si
hubo un reinicio real del kernel, `backup-host --after-reboot` permite el archivo
explícito de autoridad anterior y valida su evidencia. No uses esa opción para
suponer que terminó un proceso ni para eludir una denegación de acceso. Un
rechazo conserva el original y requiere inspeccionar la causa indicada.

La restauración preserva datos del snapshot y evidencia de autoridad anterior;
la inscripción crea autoridad y acceso nuevos. Vuelve a emparejarte con esa
instalación. El historial local identifica los cálculos copiados y exige una
decisión actual para los que no tienen resultado. Los permisos pendientes
copiados no se consumen automáticamente. El runtime tampoco reanuda intentos,
grants o planes anteriores por esta autorización local.

Si se pierde la respuesta de una autorización, usa **Consultar autorización
original**. Un recibo de otra instalación se presenta como histórico. Revisa el
cálculo y guarda una nueva decisión sólo si quieres realizarlo en la copia.

La copia no contiene escrituras posteriores al snapshot, no deshace efectos
externos y no demuestra que el original haya dejado de existir. Sus presupuestos
representan la historia copiada y el trabajo nuevo de esa instalación, no una
cuota global compartida entre varias copias ni la facturación del proveedor.

Después de actualizar a63, las decisiones nuevas tienen origen verificable.
Las decisiones62 conservan su recibo pero no disponen de esa prueba: si no
ejecutaron una sucesora, requieren autorización actual. Un resultado existente
se mantiene recuperable y su consumo no se reinicia.
