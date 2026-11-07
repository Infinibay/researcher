# Contraste completo de E08

Base0587a5a; inicio18:09:42UTC. Alcance original: presupuestos por operación,
intento/proyecto, todas las llamadas observables, un dueño para concurrencia/retry,
consumo ausente explícito y ninguna alternativa de proveedor por cuota agotada.

- [x] Contrastar productores y rutas actuales, reusando las pruebas válidas;
  renovar el inventario estático con sus límites reales, sin llamarlo prueba de
  ausencia universal de llamadas dinámicas o internas del proveedor.
- [x] Verificar rechazo de cuota recibido por el host sin segundo turno/proveedor
  ni devolución de reserva, y capacidad compartida antes de otra preparación.
- [x] Explicar en la web qué cuenta el cupo y qué CPU/consumo interno no está
  consolidado. No prometer una medición física completa que no existe.
- [x] Comprobar paquete/contratos afectados, matriz de requisitos y decidir E08
  con evidencias por requisito. Mantener separados los escenarios aún abiertos.

El requisito habla de admisión de trabajo observable; no exige inventar cuota
interna del proveedor ni convertir CPU de tareas distintas en tokens. La auditoría
no elimina obligaciones funcionales reales ni convierte dudas en aceptación.

E08 comprobado con alcance/límites explícitos;8min17s hasta validar.
[Resultados](../../modernization/budget-acceptance-review.md). El plan completo sigue activo.
