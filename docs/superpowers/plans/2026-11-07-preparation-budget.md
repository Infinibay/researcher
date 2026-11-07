# Admisión antes de preparar Ken y la sesión

Parte de E08 del plan completo; base fe3da17. Inicio de auditoría: 17:53:04 UTC.

La reserva actual ocurre después de abrir el runtime. Un proyecto sin cupo aún
puede preparar Ken y una sesión nativa. Criterio de salida: ninguna preparación
sin admisión persistida, y una solicitud contabilizada una sola vez al despachar.

- [x] Reserva inmutable por intento antes de runtime.open, con la misma política
  de proyecto, control de concurrencia y rechazo de repetición.
- [x] Conversión contable sin duplicación: el input exacto se congela después de
  obtener catálogo/modelo reales. Preparación sin dispatch conserva capacidad.
- [x] Historia/API/web distinguen preparación y consumo observado; migración
  preserva dispatches antiguos y permite inversa sólo sin reservas nuevas.
- [x] Pruebas dirigidas: rechazo antes de open, fallo/reinicio, carrera por último
  cupo, dispatch con reserva previa, cambios de política y paquete instalado.

No mide CPU de Ken en tokens ni afirma conocer facturación. Los límites físicos
existentes siguen acotando cada preparación; esta reserva limita cuántos intentos
pueden prepararse. No cerrar E08 sin contrastar sus otros requisitos. Detalles
secundarios van a la cola final, sin ampliar este bloque.

Validado:163casos instalados,10DOM y build;13min57s hasta validación.
[Resultados y límites](../../modernization/preparation-budget-review.md). E08 y el plan completo permanecen abiertos.
