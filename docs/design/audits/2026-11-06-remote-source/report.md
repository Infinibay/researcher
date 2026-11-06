# Preparación de remoto: verificación web

Se amplía la dirección visual seleccionada de Repositorios; no se presenta esta
integración como otra ronda de conceptos ni como aceptación completa de la página.
El recorrido usa React compilado, API owner real, SQLite y un servidor TLS local
controlado con el contrato de Forgejo. No hay efectos en servidores del usuario.

El propietario selecciona servidor, cuenta/organización y visibilidad: el botón
permanece deshabilitado hasta completar esas elecciones. El formulario remoto
oculta ruta local y rama. Una respuesta perdida del servidor conserva la solicitud
al recargar; «Observar la creación original» consulta y reconoce el mismo recurso.
La pantalla explica que no hay una fuente local nueva y que cerrar el cliente no
garantiza detener al servidor.

Cinco capturas: formulario de escritorio, elecciones móviles, respuesta perdida
móvil y resultado original en móvil/escritorio. Se revisaron visualmente las
capturas de resultado; Axe no reportó incidencias en header/workbench y no hubo
scroll horizontal a390/1440px ni errores JS. La prueba observó1POST administrativo
y1observación; el servidor confirmó1POST de creación,0Git y0turnos nativos.
[Evidencia y hashes](evidence.json).

El primer intento del verificador usó la etiqueta completa de un select anidado
y falló antes de emitir una operación; se corrigió el localizador a su rol/nombre
accesible. No fue necesario recrear un remoto ni descartar una solicitud incierta.

Pulido del texto de entrada lateral y navegación/foco sigue en la pasada posterior.
Historia entre navegadores, reparación local, restore y aceptación humana completa
siguen abiertos.
