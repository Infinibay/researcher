# Repositorios: fuentes, revisión y preparación explícita

Se mantiene [Explorador con registro de fuentes](../../concepts/repositories/source-explorer.png).
La implementación conserva las columnas de fuente/árbol/lector, el papel claro,
tinta y acento verde. Usa controles separados para registrar una carpeta y preparar
Git; no copia los estados ficticios del concepto. En móvil, árbol y archivo son
vistas alternadas y el código desplaza su propia región. No hay cambios del renderer
en este bloque. La selección y la revisión visual están delegadas por el usuario.

Chromium utiliza el backend instalado. El navegador integrado no estaba disponible.
Los proyectos, credenciales y fallos son sintéticos; el Git/TLS es real y el REST
Forgejo es una fixture controlada. No se evaluó una cuenta remota del propietario.

- **Vacío real:** [escritorio](current/01-actual-empty.png) y
  [otro proyecto en móvil](current/15-independent-empty-mobile.png) muestran la
  ausencia confirmada de fuentes. No se usa una lista durante la carga como prueba.
- **Lectura:** [código](current/05-immutable-code.png) y
  [Markdown móvil](current/06-markdown-mobile.png) sitúan fuente, rama y revisión
  junto al contenido. La consulta usa SHA completo aunque la vista lo abrevie.
  Se conserva texto literal y se cambia de rama explícitamente. La revisión
  histórica y la disponibilidad de carpeta no se presentan como aceptación actual.
- **Preparación:** creación, adopción y clonado tienen elecciones diferentes.
  La [parada del trabajador](current/11-stopped-partial-clone.png)
  se explica como trabajador cerrado y carpeta todavía parcial; la captura deja
  el título parcialmente sobre el viewport, pero muestra completos estado y acciones.
  La [reparación terminada](current/12-explicit-repair-keeps-note.png) distingue
  registro de Git y cambios locales sin aceptar. La nota se comprueba desde disco.
- **Remoto vacío:** [resultado](current/13-controlled-remote-creation.png) conserva
  servidor, organización y visibilidad. Explica que no hay copia local ni código
  publicado. El resultado corresponde al contrato de la fixture, no a un proveedor
  real. La actividad global mostrada es una observación anterior; DD128 deja su
  contextualización/refresco para la pasada de detalle.
- **Historia con alcance:** [móvil](current/14-original-history-mobile.png) nombra
  la operación elegida y conserva otra solicitud del navegador separadamente.
  La captura prueba ese contexto; no pretende mostrar toda la operación larga.
- **Respuesta perdida:** [aviso y recuperación](review/01-lost-registration-receipt.png)
  conserva la selección original; esta captura sólo muestra el final del formulario.
  Tras recarga, [la carpeta sin Git](review/02-same-registration-without-git.png)
  es el mismo registro y no toma Git del repositorio padre.
- **Nueva visita:** [respuesta tardía](review/04-late-response-keeps-current-visit.png)
  conserva «original» y [lector móvil actual](review/05-current-code-mobile.png)
  permite continuar. La aserción espera que el callback resuelva su paquete antes
  de aceptar la selección, no sólo que el título anterior siga visible un instante.

Se comparan las capturas inspeccionadas con el concepto; otras quedan identificadas
como capturas programáticas en [image-review.json](image-review.json). Axe no
detecta infracciones en las regiones comprobadas. No equivale a comprensión humana,
zoom nativo ni prueba completa de lectores de pantalla. Densidad de rutas, altura
de cabecera e historia y avisos de estilo del evaluador quedan en DD128; las
capacidades mayores tienen prioridad.

Aceptación técnica/visual de la página actual: 15 estados principales y 5
complementarios, 54 casos instalados, 16 contratos y 2 pruebas de identidad.
Cero inferencias. [Alcance y fallos conservados](../../../modernization/repositories-page-review.md).
