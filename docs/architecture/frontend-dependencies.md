# Dependencias del frontend

Fecha: 6 de noviembre de 2026, hora de Argentina. Migración sobre `0c4e305`.
El frontend compila con el conjunto actualizado y conserva sus contratos de
interacción comprobados. Esto no acepta las doce páginas ni declara terminada
la modernización. [Resultados](../modernization/frontend-dependencies-results.json).

Actualización del7noviembre: KaTeX0.19.1, minimatch11.0.5 y selector-parser6.1.5
resuelven los tres avisos del corte inicial.136 contratos/10 DOM, build y árbol
pasan; auditoría npm sin avisos y9 errores de lint pendientes. Se probaron overrides
limitados y se conserva el alcance de cada comprobación en la
[revisión posterior](../modernization/dependency-security-review.md).

## Conjunto elegido

| Componente | Versión comprobada | Decisión |
| --- | --- | --- |
| Node / npm | 24.22.2 / 11.19.1 | Node >=24.15 y <25; lockfile e instalación explícita |
| React / React DOM | 19.3.1 | Misma versión; declaraciones 19.3.0 |
| TanStack Query / devtools | 5.107.1 | Misma versión; se conservan claves y controles originales |
| React Router / Zustand | 7.18.5 / 5.1.0 | Compatibilidad comprobada por los contratos y recorridos seleccionados |
| Vite / plugin React | 8.3.6 / 6.2.1 | Compilación Oxc/Rolldown, proxy local conservado |
| TypeScript | 6.0.3 | Se conserva `strict`; tipos Vite para imports CSS |
| Tailwind / plugin Vite / typography | 4.3.5 / 4.3.5 / 0.5.20 | Configuración CSS, colores propios y tipografía documental |
| React Markdown / KaTeX | 10.1.0 / 0.19.1 | Misma versión de KaTeX para CSS y renderizado de rehype |
| Vitest / jsdom | 5.1.0 / 31.0.0 | Nuevas pruebas DOM con Testing Library |
| ESLint / typescript-eslint | 10.14.0 / 8.72.1 | Configuración recomendada sin silenciar las incidencias existentes |
| Playwright / axe | 1.64.1 / 4.14.0 | Se conserva el conjunto de navegador ya utilizado |

TypeScript 7 se difiere porque el parser elegido admite versiones menores de
6.1. [Compatibilidad oficial](https://typescript-eslint.io/users/dependency-versions/).
Vite 8 cambia sus compiladores y su objetivo de navegadores;
se revisaron también los cambios desde Vite 6.
[Vite 8](https://vite.dev/guide/migration.html),
[Vite 7](https://v7.vite.dev/guide/migration.html).

Tailwind usa su plugin de Vite; se retiraron las configuraciones anteriores de
Tailwind/PostCSS y las dependencias directas de PostCSS/autoprefixer. Conserva
colores surface, cursores de botones, placeholders y centrado de diálogos.
`outline-hidden` mantiene la intención accesible del antiguo `outline-none`.
El objetivo de compilación es Chrome/Edge 111, Firefox 128 y Safari 16.4,
compatible con las necesidades CSS de Tailwind; **no acredita soporte integral
del producto en esas versiones**, incluidos popovers nativos.
[Guía de Tailwind](https://tailwindcss.com/docs/upgrade-guide).

Se retiró Recharts porque no tiene imports en `src` ni `tests`; los diagramas
existentes no lo consumen. El resto del stack Markdown conserva sus plugins
GFM, matemáticas y resaltado. Rehype KaTeX y micromark math requieren KaTeX
`^0.16.0`: subir sólo el CSS a0.19 mezclaría versiones. La revisión posterior
fija la misma0.19.1 para ambos mediante un override explícito, comprobando su
compatibilidad con el renderizador real. La migración inicial no utilizaba overrides.

## Verificación y límites de la migración inicial del6noviembre

- `npm ci --no-audit --no-fund`: 373 paquetes instalados; `npm ls` termina 0.
- `npm test`: 126 contratos existentes y 3 pruebas DOM pasan, antes y después
  de la instalación limpia. Las nuevas pruebas cubren enlaces accesibles,
  jerarquía de títulos, fórmulas, código, listas y rechazo de HTML/enlaces
  ejecutables. No prueban todas las posibilidades de entrada maliciosa.
- `npm run build`: pasa con TypeScript estricto. Se conserva el aviso por
  bundle grande; no se afirma una mejora de rendimiento global.
- Resumen: 5 estados con datos HTTP controlados, desktop/móvil, cambio de
  proyecto, error parcial y navegación a la pregunta original. Pasan antes y
  después de la migración. La comparación visual mantiene la composición.
- Ejecución: 10 estados, dependencias, historia, contexto cambiado, pausa
  incierta y recuperación de la misma decisión. El primer test usaba un
  selector ambiguo para dos alertas; se acotó a su región y pasó completo.
- Acceso local: el teclado mantiene el foco en desktop, móvil y colores
  forzados. Dos estados normales pasan Axe. En colores forzados la aserción de
  foco pasa, pero Axe informa un fallo de contraste: la captura muestra texto
  negro donde su recibo informa colores de autor. Se conserva el fallo y se
  difiere su diagnóstico, sin desactivar la regla ni declarar ese recorrido verde.
- En conjunto hay 18 capturas nuevas: 17 estados sin violaciones Axe y uno
  con el aviso anterior. Sin excepciones JavaScript observadas. Las pruebas
  usan Chromium y HTTP simulado; no validan backend, WebSocket, modelos,
  comprensión humana ni los navegadores mínimos. Los avisos de proxy WebSocket
  reflejan que estos fixtures no arrancan backend.

[Capturas y recibos](../design/audits/frontend-dependencies/report.md).
Los runners admiten `BROWSER_AUDIT_OUT` para conservar los ensayos anteriores.
`home.browser.mjs`, `flow.browser.mjs` y `access.browser.mjs` se ejecutan contra
`npm run preview -- --host 127.0.0.1 --port 5179 --strictPort`.

## Pendientes observados en el corte inicial (histórico)

Los tres avisos de dependencias descritos abajo se corrigieron el7noviembre;
no son el estado del lock actual. Se retiene el diagnóstico original y su
limitación sobre contaminación de prototipos. La seguridad integral del proyecto
y la aceptación de páginas siguen abiertas.

`npm run lint` termina 1 con los mismos 12 hallazgos del baseline: cinco usos de
`any`, dos bloques vacíos, dos regex de controles, dos variables/imports sin uso
y un `prefer-const`. No se aplicaron correcciones masivas ni excepciones al lint.
[DD066](../modernization/deferred-details.md#dd066--detalles-tras-actualizar-el-frontend).

`npm audit` termina 1: 16 paquetes afectados por tres avisos únicos, 12 entradas
moderadas y cuatro bajas, sin altas ni críticas. **La aceptación de seguridad
queda abierta**. Minimatch está dentro del lint; selector-parser dentro de
typography; KaTeX sí participa en renderizado. Los rangos exigidos por los
consumidores impiden sustituirlos automáticamente por sus versiones corregidas.

- [Minimatch](https://github.com/advisories/GHSA-g3hv-75wg-m249): la corrección
  requiere 11.0.1; los consumidores elegidos requieren 10.x.
- [Selector parser](https://github.com/advisories/GHSA-rj75-hqrm-r3gf): typography
  fija 6.0.10; la rama corregida comienza en 6.1.5.
- [KaTeX](https://github.com/KaTeX/KaTeX/security/advisories/GHSA-238p-pmpm-9mq7):
  corrección en 0.18.2. Requiere contaminación previa del prototipo o control
  sobre el prototipo de opciones; no se demostró esa condición en este producto.
  Las pruebas ordinarias de Markdown no prueban ausencia de esa condición.

Resolver compatibilidad y seguridad antes de aceptar una entrega del producto;
no ejecutar `npm audit fix --force`, que aquí propone incluso regresiones de
versión. El análisis de estos avisos queda separado de los detalles cosméticos.
No se reconstruyó el contenedor nativo: su recibo anterior conserva el frontend
anterior. La integración final deberá construir la imagen con este lockfile.
