# Capacidad Ken estructural disponible sin red

Base de diagnóstico: `dac2b4e`; [causas y recibos](../../modernization/ken-capability-diagnosis.md).
Autorizado dentro de la modernización, sin nueva generación para verificarlo.

1. Seguir `KenInstallation.inspect`, `worker_process`, bootstrap/host preflight y
   sus consumidores reales antes de cambiar el contrato compartido. Ken no indexa
   el runtime moderno: contrastar sus resultados con imports del checkout b09e.
2. Definir un conjunto explícito de gramáticas soportadas/preparadas y su versión,
   procedencia, tamaños y hashes. Prepararlas como recursos públicos fuera del
   peer. Reusar la provisión existente si cubre ese contrato; evitar otro sistema
   de configuración si no aporta capacidad necesaria.
3. RED: un análisis Python real con llamador conocido falla bajo el worker offline
   actual. Verificar además que instalación incompleta o recurso alterado se rechaza
   antes de inferir. Conservar presupuestos, montajes de fuente y aislamiento.
4. Implementar preflight y montaje de sólo lectura de recursos fijados; comprobar
   compatibilidad del loader instalado. No descargar dentro de Ken ni aceptar una
   caché arbitraria modificable desde la fuente. Docstrings en inglés.
5. GREEN: mismo análisis con árbol/llamador correctos y un caso negativo, MCP real
   sin red, cero modelos. Distinguir éxito de transporte y contenido. Comprobar
   originales intactos y terminación de los procesos; no contar generaciones.
6. Orientar el uso de `ken_find`: compact para files/symbols; tests con argumentos
   admitidos. Mantener errores originales, sin éxito inventado ni reintento de
   efectos. Verificar la política enviada al actor y su revisión estática; su
   eficacia generativa se evalúa después, sin repetir el plan aceptado.
7. Construir sdist→wheel limpio, instalar y ejecutar selección de consumidores;
   verificar inventario y docstrings. Actualizar matrices sin cerrar AuthorityBusy,
   Proyectos o comprensión humana por esta reparación. Detalles visuales al final.

## Resultado verificado

2026-11-08,03:58:40–04:24:03UTC,25min23s. Se reutiliza la instalación confiable
de Ken, sin otro campo de configuración. Preparación explícita del archivo fijado,
372gramáticas verificadas; caché de sólo lectura, huella en broker/preparación y
preflight antes de nuevas admisiones. Error correctivo para tests+compact/evidence
sin enviar ni reintentar llamadas.92casos fuente y92instalados pasan, sin skips.
MCP publicado real encuentra llamadores positivos/negativos y pruebas, también bajo
el perfil de broker/kernel de producción; cero turnos generativos.26definiciones
con docstrings. No se tocó el Ken hermano ni se abrió red al peer.

Conservados: rechazo inicial de TSQL por nombre en mayúsculas;14fallos al ampliar
la suite que localizaron la comparación exacta del consumidor de preparación;
comprobación inicial demasiado amplia del seed opcional. Corregidos con evidencia,
sin ocultar los fallos. Estilo no verde, DD131.65revisiones estáticas de prompts
requieren revalidación sobre el árbol final; no se revalidan por cambiar sólo hashes.
Proyectos/contención/U08/C10/otras páginas continúan abiertos. No eficacia generativa
nueva, aceptación humana, suite global, push ni despliegue.
[Resultado y alcance](../../modernization/ken-grammars-review.md).
