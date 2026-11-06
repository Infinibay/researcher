# Resumen — validación del piloto

Resultado: **piloto funcional verificado; aceptación integral pendiente**.
Se eligió Cuaderno de situación entre tres imágenes independientes y se generó
su adaptación móvil. [Brief y selección](../../concepts/home/brief.md),
[manifest y prompts](../../concepts/home/manifest.json).

La captura anterior muestra el problema reproducido: porcentaje de tareas como
cierre del proyecto. La prueba roja esperaba el área de atención, ausente antes.
El primer intento del verificador interceptó también módulos `/src/api/` y se
corrigió para interceptar sólo endpoints `/api/`; no fue un fallo del producto.

La página usa workspace/tareas/preguntas existentes. Ofrece enlaces originales,
registra la cantidad de tareas sin inferir aceptación y permite refrescar consultas.
Errores parciales, proyecto vacío y ausencia de selección tienen mensajes propios.
Navegar no envía mutaciones. No se añaden endpoints ni una segunda interpretación LLM.

Prueba de navegador reproducible desde frontend:
`node tests/home.browser.mjs` con Vite en 127.0.0.1:5179; usa fixtures controlados.
Cinco capturas 1440/390, cero incidencias Axe dentro de la región nueva, cero errores
JS y cero escrituras. Verifica preguntas paginadas y su enlace original, error parcial
con recuperación, tareas todas done sin declarar aceptación, cambio a proyecto vacío
y entrada sin selección. [Evidencia](evidence.json). Suite frontend:123/123; build4.04s.
La prueba no acredita API/SQLite, procesos reales, comprensión humana ni evaluación científica.

Comparación visual: referencia de escritorio1487×1058 frente a viewport1440×1024
(densidad1); referencia móvil852×1846 frente a viewport390×1024, captura superior y
captura desplazada al contexto. Son referencias generadas con resolución distinta;
se compararon composición y legibilidad, no equivalencia píxel a píxel. Ambos pares
se abrieron juntos en la entrada de comparación. No se confunde fullPage con capturar
todo el scroll interno; la segunda captura móvil verifica la zona inferior.

- Tipografía: Georgia para títulos y sans de producto para lectura, cuerpo14–18px;
  jerarquía principal conservada. Se restituyó el peso de títulos tras la primera comparación.
- Espacio: columna principal y margen lateral; en móvil una columna. Preguntas con
  contexto/paginación ocupan más espacio que el mock, por contrato real. Densidad y
  margen oscuro móvil se difierenDD041; no impiden controles ni lectura.
- Color: tokens existentes papel/tinta/verde; contraste probado por Axe en región.
- Imágenes: los conceptos no requieren fotos/avatares. Controles son HTML funcional;
  no se incorporan capturas como UI. Navegación compartida se conserva.
- Contenido: fuentes disponibles no prueban estado Git; actividad registrada no prueba
  proceso vivo; informes remiten al contexto original con vigencia sin revalidar.
  Los estados inventados por Imagegen y sus fechas no se usan como datos del producto.

Axe detectó un nombre accesible que omitía la pregunta visible en QuestionInbox.
Se eliminó el aria-label sustitutorio, conservando el nombre derivado del contenido;
la prueba completa posterior pasa. Se añadió el acceso primario a la primera tarea
señalada. La aceptación visual global sigue parcial por los detalles diferidos y
las pruebas integrales/humanas abiertas. No se presenta como diseño final aprobado.
