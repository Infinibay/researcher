# Política de captura web directa

La captura nativa de HTML, texto y PDF comprueba ahora `robots.txt` antes de
solicitar cada página y cada destino de redirección. La composición HTTP comparte
una instancia de `WebAccessPolicy` entre solicitudes; construir un nuevo lector
no reinicia su cuota. El cambio no usa modelos ni proveedores de pago.

## Comportamiento

El identificador es `Researcher`. Se combinan sus grupos; si no existen se usan
los grupos `*`. La regla coincidente más específica decide, con preferencia por
`Allow` en empate. Se admiten comodines, ancla final y normalización de UTF-8 y
escapes. Los errores de red y respuestas 5xx impiden la captura; una respuesta
4xx permite continuar salvo 429, que se rechaza. El diseño toma estas reglas del
[RFC 9309](https://www.rfc-editor.org/rfc/rfc9309.html); las pruebas verifican casos
concretos, no certifican conformidad completa.

Las reglas viajan por el mismo transporte HTTPS público que las fuentes, con
DNS fijado, identidad TLS y propiedad de la operación. Se permiten hasta cinco
redirecciones de robots, validando cada destino. El presupuesto admite 500 KiB
de reglas, independientemente del límite de la página. Se exige `text/plain` y
no se descomprimen respuestas. Los destinos privados y cambios a HTTP siguen
rechazados. Estos límites del producto pueden impedir consultar algunos sitios.

La frecuencia predeterminada es 20 inicios HTTP por minuto, incluyendo robots y
redirecciones. La espera comparte el plazo original de captura y responde a Stop;
si la cuota no puede liberarse dentro del plazo, devuelve un error sin solicitar
la página. Los ajustes existentes `WEB_RPM_LIMIT` y `WEB_ROBOTS_CACHE_TTL` se leen
al crear la aplicación. El TTL predeterminado es una hora, con máximo de 24 horas.
La caché está limitada a 64 orígenes y 4 MiB de contenido de reglas.

Cada fuente conserva las decisiones de sus saltos, URL de robots, estado HTTP,
hash de reglas retenidas y uso de caché. Para respuestas 4xx no se conserva su
cuerpo: el hash corresponde al contenido vacío, junto al estado que justificó
la ausencia de reglas. Un rechazo no crea una fuente parcial ni un hallazgo.

## Evidencia inicial y límites

- 161 pruebas pasan en fuente y 161 en el paquete instalado: URL/DNS/TLS, reglas,
  redirecciones, caché compartida/expirada, cuota, Stop, PDF y HTTP → SQLite → cita.
  Las respuestas públicas son controladas; se conserva una prueba de TLS local
  con CA privada y los lectores/parsers reales.
- El paquete tiene 732 archivos Python/SQL coincidentes; 207 módulos backend
  cargados proceden del entorno instalado, con 85 distribuciones y sin frameworks
  antiguos. No hay llamadas nuevas a modelos o proveedores reales.
- La cuota pertenece a la instancia de política. No se comparte entre procesos,
  instalaciones ni reinicios. Peticiones concurrentes sin caché pueden volver a
  consultar las reglas, consumiendo igualmente la cuota compartida.
- **Actualización posterior:** Spider ya comprueba su URL inicial y comparte
  cuota; los wrappers web están retirados. HTML conserva enlaces y tablas en
  Markdown mediante el worker. Véase el [corte posterior](native-web-retirement.md)
  y sus pruebas; las cifras de este apartado corresponden al corte inicial.
- Siguen pendientes los otros bloques del plan. El fallo anterior de migración
  54/55 permanece fuera de esta batería.

Resultados: [fuente](../modernization/web-policy-results.json),
[paquete](../modernization/web-policy-packaging.json),
[docstrings](../modernization/web-policy-docstrings.json).
