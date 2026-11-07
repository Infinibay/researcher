# Panel de conservación en Repositorios

Se inspeccionaron visualmente [escritorio](desktop.png), [recuperación](recovered.png)
y [móvil](mobile.png). Viewports: 1440×1100 y 390×844. El panel mantiene la tipografía,
paleta y estructura del piloto existente; esta entrega añade el recorrido funcional.

El propietario elige el plazo y reconoce la cuarentena antes de archivar; después
solicita una recuperación independiente. El destino nuevo aparece en el historial
con la explicación de que sólo recupera datos. Los dos POST observados conservaron
proyecto/intento, clave de operación y CSRF del transporte de dueño.

El [recibo](evidence.json) registra cero errores de página, desbordamiento horizontal
o violaciones Axe en el panel inspeccionado. Se verificaron el texto, los controles
y el ajuste móvil en las capturas; los tests DOM cubren además respuesta perdida,
recarga y consulta del recibo sin reenvío automático.

El navegador ejecutó React y el transporte reales con respuestas HTTP controladas.
La integración del backend y el cierre físico se prueban separadamente en
`test_owned_retention.py`; no se presenta esta combinación como una prueba E2E
única. No acepta la página completa de Repositorios ni demuestra comprensión
de usuarios reales. Dos fallos del harness se corrigieron antes de las capturas:
una ruta que interceptaba módulos fuente y un contexto de navegador requerido por Axe.

Detalles aplazados DD118: concordancia singular/plural y densidad del formulario
de nuevo archivo/historial en móvil. No bloquean archivar o recuperar.
