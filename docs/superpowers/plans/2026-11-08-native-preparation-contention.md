# Preparación nativa: contención y explicación de fallos

La investigación correctiva empezó el2026-11-08 a las00:49:17 UTC. La explicación
del cierre se corrigió y se añadieron ubicaciones seguras al log. La contención
original todavía no se reprodujo ni se corrigió. Conservar las ejecuciones originales.

## Evidencia conocida

- Instalación retenida: `.researcher/evaluations/projects-acceptance-label-20261107`.
  Todos sus servidores y peers están cerrados; no hay un proceso por el que esperar.
- Proyecto 2: intento cancelado, log AuthorityConflict, ninguna inferencia; reserva
  de preparación conservada. Otra solicitud fue rechazada por presupuesto.
- Proyecto 3: plan real aceptado,139193 tokens observados, despacho settled.
- Proyecto 5: solicitud española persistida, fallo AuthorityBusy antes de inferir;
  peers cerrados. No hubo respuesta española ni reintento.
- Log del producto: `host/logs/infinibay.log`, no sólo stdout del servidor.
  No copiar códigos de acceso ni el fichero privado de recursos.
- `authority_journal.py::_operation` tiene RLock por instancia, flock no bloqueante
  y traducción de SQLITE_BUSY/LOCKED. Falta localizar qué operación contendió.

## Trabajo

1. Revalidar recibos, logs y cierre original. Recuperar el llamador con diagnóstico
   acotado del operador; no exponer stack/credenciales en la interfaz. Distinguir
   hipótesis de concurrencia interna de un lock externo realmente poseído.
2. Reproducir la frontera sin inferencia de pago, usando procesos/journal reales
   cuando haga falta. Inspeccionar propietarios, callers, pruebas y blast radius
   antes de cambiar la transacción compartida.
3. Corregir sólo la causa demostrada. No ignorar locks, secuencias o hashes;
   no repetir escrituras inciertas ni liberar reservas por suposición. Una espera
   o conciliación tiene que estar acotada y preservar el efecto original.
4. Corregir la explicación de fallo para distinguir preparación fallida, inferencia
   no iniciada y cierre desconocido, usando pruebas de los estados reales.
5. Validar el cambio instalado. Sólo después, registrar una comprobación nueva de
   idioma sobre el producto corregido, conservando la propuesta inglesa y el
   intento español fallido. El proyecto 5 no tiene presupuesto libre para repetir
   su preparación: no reescribir ni borrar esa historia.
6. Volver a la aceptación de Proyectos y luego al resto de páginas. DD123/124 son
   detalles separados; esta fiabilidad del engine es trabajo principal.

## Corte diagnóstico

Cuatro preparaciones con generación prohibida llegaron a la guardia y cerraron
sus peers: tres con asyncio y la rueda previa; una con uvloop y la rueda nueva.
Cero turnos enviados. No bastan para cerrar la contención ni aceptar Proyectos.
La explicación ahora distingue cierre comprobado e inferencia incierta; los logs
permiten localizar el llamador sin registrar mensajes privados de excepción.
[Revisión y límites](../../modernization/native-preparation-review.md).

Antes de construir otro artefacto, consultar la regla de sdist + wheel limpio en
`docs/architecture/native-python-installation.md`. Un build directo arrastró306
módulos retirados y fue rechazado antes de ejecutar pruebas. Se sustituyó por
una rueda limpia verificada; no reutilizar el artefacto descartado.
