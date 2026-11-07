# Comprobación visual de la migración de dependencias

6 de noviembre de2026. Chromium156.0.8078.4, Playwright1.64.1, axe4.14.0.
Se sirven los archivos compilados con Vite8 y se intercepta HTTP con datos
sintéticos. No hay backend ni modelo en estos recorridos.

- Resumen:5estados antes y5después, todos pasan. Composición revisada a1440px
  y390px, navegación original, aislamiento al cambiar proyecto y error parcial.
- Ejecución:10estados pasan. El selector de error se acotó a su región porque
  una alerta independiente de la cabecera hacía ambiguo el selector global.
- Acceso:3capturas; desktop/móvil pasan Axe. El foco permanece visible con
  colores forzados, pero el runner termina1 porque Axe informa un contraste que
  no coincide con la captura. Conservar para diagnóstico final, sin declarar
  ese recorrido completamente aceptado.

Son18estados posteriores,17sin violaciones Axe y1con el hallazgo de contraste;
las5capturas anteriores son comparación, no aceptación adicional. No se observaron
excepciones JavaScript. No prueba comprensión humana, toda la aplicación,
WebSocket ni versiones mínimas de otros navegadores. Siguen0/12páginas aceptadas
integralmente. [Recibo completo](../../../modernization/frontend-dependencies-results.json).

Comparación de Resumen:

- [Antes, escritorio](before-home/01-desktop.png) y [después](home/01-desktop.png).
- [Antes, móvil](before-home/02-mobile.png) y [después](home/02-mobile.png).
- [Recibo anterior](before-home/evidence.json), [recibo actualizado](home/evidence.json).

Ejecución y acceso:

- [Inspector de Ejecución](flow/01-desktop-inspector.png), [recibo](flow/evidence.json).
- [Acceso móvil](access/mobile-focus.png), [colores forzados](access/mobile-forced-colors.png),
  [recibo con el fallo conservado](access/evidence.json).
