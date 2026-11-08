# Búsqueda local en instalación administrada

Inicio06:29:16UTC, baseefbf84e; continúa Hallazgos del bloque anterior.

Evidencia: GET real del hostretenido devuelve503retrieval_unavailable, «Local
semantic retrieval is not prepared/configured». Configuración actual no acepta
una ruta para los pesos multilingües de Hallazgos y host_environment no la entrega
al API. Hay pesos públicos ya preparados; no descargar ni lanzar modelos generativos.

1. RED: opción explícita retrieval_asset_dir debe validarse antes de crear estado,
   persistir canónica y pasar a INFINIBAY_RETRIEVAL_ASSET_DIR al preparar/reabrir.
   Ausencia conserva compatibilidad; directorio relativo/ausente o bytes cambiados
   se rechazan, sin host/witness parciales. No aceptar un directorio arbitrario como
   modelo válido: reusar verified_assets y su modelo/hash fijos.
2. Conectar sólo preparación/entorno, no otro modelo, worker, cuota o fallback.
   Recursos documentados como verificados, sin afirmar inferencia. Docstrings en
   inglés. Revisar consumidores actuales y formato antes de ampliar configuración.
3. Comprobar fuente e instalación limpia; test de launcher y host existing/unset.
   Enseñar el campo opcional y preparación offline existente en documentación.
4. Nuevo host de evidencia con campo explícito y pesos actuales, búsqueda positiva
   local desde navegador. Ranking/hashes/cobertura/cursor y ciencia sin certeza;
   cierre de worker/presupuesto local y dominio. Sin suscripción/generación.
5. Mantener Hallazgos abierto hasta completar también revisión independiente;
   errores/casos de origen no sustituyen prueba positiva. Detalles al final.

## Resultado de esta fase

06:47:58UTC:18min42s hasta verificar/inspeccionar.30fuente/6CLI de checkout y38
instalados pasan,22definiciones documentadas;685fuentes/365producto coinciden.
Browser real200sobre53registros y continuación200con iguales hashes; un cálculo
local settled3788msCPUpara ambas consultas,workerclosedtrue. Servicio143/dominio
eliminado.0generación; se respetó el agrupado real de fragmentos por hallazgo.

Primera selección instalada incluía un fixture de start.shdelcheckout: fallo
conservado y probado en su lugar, no skip ni nuevo wrapper del wheel. Estilo10Ruff
enDD136. Búsqueda positiva cerrada; admisión/historia de revisión continúa.
7/12páginas,41/43escenarios. [Evidencia](../../modernization/managed-semantic-review.md).
