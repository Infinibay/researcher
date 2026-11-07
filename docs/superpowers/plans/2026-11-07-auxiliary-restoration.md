# Cálculos locales tras restaurar una instalación

Parte del plan del31octubre. Base3a07b11; inicio17:27:42UTC.

Hallazgo: la inscripción restaurada pausa graphs, retira grants y conserva
ejecuciones históricas, pero una autorización local pendiente también se copia.
La comprobación de kernel/namespace impide inferir muerte del original: restore
debe ofrecer una nueva autoridad sobre la copia, no inventar cierre.

- [x] Vincular cada autorización nueva a la identidad de su base, reutilizando
  PeerRegistry. Conservar recibos viejos, pero una autorización de otra base o
  sin origen registrado no admite automáticamente un trabajador.
- [x] Archivar los cálculos copiados dentro de la transacción de enrollment
  verificado. Preservar reservas/resultados, diferenciar el historial restaurado
  y permitir una nueva decisión explícita sobre cálculos sin resultado.
- [x] Corregir diagnóstico/recibo y comunicación web para que una autorización
  histórica recuperada no se presente como permiso actual. No transferir grants.
- [x] Verificar backup/restore/enrollment reales, permiso copiado, identidad
  ausente/kernel distinto/creación incompleta, reinstalación y paquete instalado.

Contrato compartido: el transporte sigue dueño del cierre físico normal.
Restore nunca lo certifica. La nueva instalación puede efectuar un cálculo
local puro con permiso explícito actual mientras preserva la historia de origen.
Las autorizaciones previas y sus recibos no se reescriben. La versión63 migra
autorizaciones62 sin inventar origen: requieren nueva decisión si no ejecutaron
su sucesora; resultados existentes siguen recuperables.

Esta ruta usa backup/restore/inscripción existentes; no introduce un botón para
suponer el cierre de procesos desconocidos en la instalación original. Explicar
esa distinción y los pasos de recuperación en la documentación de operación.

Validado:182casos instalados,13DOM,2contratos;4estados web/1autorización y barrera de cambio de instalación preservada. [Resultados y límites](../../modernization/auxiliary-restoration-review.md). La recuperación se realiza sobre una copia con autoridad nueva; no se transforma evidencia histórica en prueba de cierre global. E08 y el plan completo siguen abiertos.
