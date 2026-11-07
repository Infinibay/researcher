# Continuación explícita de cálculos locales

Bloque principal de recuperación dentro del plan del31octubre; no sustituye su
alcance ni declara E08 completo. Inicio registrado:17:08:08UTC; lectura previa
sin inicio medido. Base:f65ed71.

- [x] Registrar dueño y trabajador antes de entregar datos; registrar cierre
  físico. Reutilizar pidfd, boot_id, observer_namespace y start_ticks. Una
  identidad de namespace-init no sirve para estos trabajadores ordinarios.
- [x] Diagnóstico de sólo lectura y autorización explícita, idempotente, del
  siguiente cálculo idéntico. Conservar consumo anterior, volver a comprobar
  autoridad/presupuesto al ejecutar y no iniciar trabajo desde la autorización.
- [x] Integrar control web, recibo recuperable tras perder respuesta y alcance
  por proyecto. Explicar con un ejemplo la reserva anterior y la nueva.
- [x] Verificar procesos reales, competencia, permisos, respuesta perdida,
  migración y producto instalado; documentar límites y checkpoint.

Contrato: cada autorización nombra la operación original exacta. Sólo una
sucesora puede consumirla. No guardar el documento para repetirlo desde el
control: la próxima solicitud debe aportar el mismo contenido y productor.
Resultados completos se recuperan sin nueva autorización. Registro histórico
sin identidad, cambio de kernel/namespace y muerte durante el intervalo de
creación sin identidad del hijo conservan incertidumbre: no son prueba de
cierre. Estos límites se muestran y se mantienen abiertos, sin un bypass.

Interfaz compartida: el transporte registra creación/cierre; el ledger reserva
y conserva resultados; la decisión del propietario sólo habilita una sucesora.
No introducir otro proceso dueño ni autorizar una repetición automática del
intento nativo. Detalles de presentación se anotan para el final.

Validado:136casos instalados,12DOM,2contratos y recorrido web real de3estados/1autorización. Ver [resultados y límites](../../modernization/auxiliary-continuation-review.md). El plan completo y E08 siguen abiertos; los casos sin prueba de cierre no se reclasifican como detalles.
