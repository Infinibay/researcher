# Repositorios: preparación explícita de fuentes

El diseño continúa el concepto de explorador ya seleccionado: papel/tinta/verde,
registro lateral y panel de trabajo. No se añadió una página ni una nueva ronda
de conceptos. Totales del proyecto:24/36desktop,8/12mobile,8pilotos y0/12páginas
completamente aceptadas.

Diez [capturas y observaciones](evidence.json) sobre React, API del propietario,
SQLite, Git temporal y cierre real del broker/kernel. Cero errores JavaScript,
cero violaciones axe en cabecera/Repositorios y cero overflow de la página en
1440×1024 y390×844. No prueba accesibilidad global, otros navegadores ni comprensión
humana evaluada. Configuración nativa controlada; ningún modelo, Ken o remoto
externo fue ejecutado por el navegador.

- [Crear local](01-desktop-explicit-local-creation.png): modo, nombre, ruta y rama
  explícitos; ejemplo de carpeta que ya contiene trabajo.
- [Respuesta desconocida](02-desktop-reply-unknown-original-retained.png) y
  [recarga](03-desktop-reload-recovers-without-another-post.png): una sola solicitud
  de creación. Consultar recupera el resultado sin otro POST ni inicialización.
- [Adoptar](04-mobile-explicit-readonly-adoption.png): fuente existente y configuración
  conservadas; HEAD y `.git/config` comprobados independientemente.
- [Clonar](05-mobile-clone-choices-and-credential-boundary.png): elección de URL y
  autenticación. Sólo se inspecciona el formulario; HTTPS/TLS real se prueba aparte
  en los tests instalados, sin tráfico a la URL de ejemplo.
- [Stop móvil](06-mobile-stopped-partial-source-retained.png) y
  [escritorio](07-desktop-stopped-operation-and-history.png): pausa controlada entre
  init real y commit, Stop de su trabajador original, carpeta Git retenida.
- [Explicación final](08-mobile-final-stopped-source-explanation.png): diferencia
  entre cerrar el trabajador y completar la fuente. Consulta readonly adicional,
  cero POST de preparación.
- [Rechazo corregible](09-mobile-definite-rejection-can-be-corrected.png) y
  [formulario recuperado](10-mobile-correction-restores-editable-choices.png): el
  servidor rechaza crear sobre una fuente útil. Sólo un409/422 explícito seguido
  por un404 más reciente de esa operación permite descartar el paquete por decisión
  del usuario; un error de red no lo permite. HEAD existente sin cambios.

Se inspeccionaron las capturas desktop de creación y móvil de Stop/rechazo.
Las primeras siete preceden los últimos ajustes de explicación/acciones;8comprueba
la explicación final y9–10la corrección. Dos fallos de localizadores se corrigieron
usando roles accesibles de combobox/textbox: el localizador de label incluía las
opciones del select. La continuación recuperó el paquete registrado original;
no reinició ni recreó la fuente.

La fixture final conserva tres operaciones: crear y adoptar completadas y una
inicialización detenida. Tres concesiones retiradas, ningún grant global activo,
cero runtime_runs, despachos de inferencia o tool_grants. Ambos servidores de QA
cerrados con su PID/handle original; sus carpetas y recibos se conservan.

Diferidos DD033: foco inicial al cambiar formulario, densidad de rutas largas y
traducción de algún error técnico final. Remoto separado, reparación de etapas
incompletas, historia entre navegadores y aceptación integral son trabajo principal,
no pulido de estas capturas. [Contrato y límites](../../../architecture/source-operations.md).
