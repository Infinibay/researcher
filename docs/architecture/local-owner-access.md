# Acceso local del propietario y autoridad de herramientas

La API usa una sesión local del propietario. No es el login de OpenAI: el
flujo de acceso no entrega OAuth, credenciales del MCP ni claves de proveedor.
El servidor conserva la suscripción y la ejecución como una frontera separada.

## Arranque y uso

`python -m backend.api.run` escucha en `127.0.0.1:8000`. Al servir, después de
migrar la DB, genera un código aleatorio y muestra **la ruta del archivo**, nunca
el código. Por defecto vive en `$XDG_STATE_HOME/researcher/auth/` o
`~/.local/state/researcher/auth/`. `INFINIBAY_AUTH_DIR` permite un directorio
privado alternativo fuera del workspace. El directorio debe pertenecer al
usuario y tener permisos 0700; cada instancia crea un archivo 0600 distinto.
Se rechaza un directorio público, un symlink de directorio o una ubicación dentro
del workspace. Construir/importar la aplicación no crea archivos ni credenciales.

Abrir la web, leer ese archivo e introducir su código. La sesión dura ocho horas
como máximo y no se prolonga por leer datos. Reiniciar requiere volver a abrir
el acceso; cerrar sesión revoca también copias previas de su cookie. El apagado
retira el archivo y las sesiones de esa instancia. Un archivo residual tras
SIGKILL no permite autenticarse en la instancia siguiente.

Para desarrollo, Vite escucha en 127.0.0.1:5173 y proxifica API/WS. Los orígenes
locales permitidos están en `backend/api/config.py`; son servicios confiados,
no un comodín para cualquier puerto. Esta implementación usa un único proceso
servidor y primitivas POSIX. No anuncia despliegue remoto o multiusuario.

## Qué autoriza cada credencial

| Autoridad | Entrada | Alcance |
|---|---|---|
| Propietario humano | Cookie opaca; prueba CSRF en mutaciones | API de producto, documentación y canal WS |
| Intento/agente | Bearer emitido por host | Sólo rutas `research-tools`, con proyecto/tarea/actor/permisos/vigencia validados por su adapter |
| Emparejamiento | Código en JSON a `POST /api/session` | Crear una sesión humana; no es bearer de herramientas |

La sesión humana puede administrar los proyectos locales. No es un sistema de
membresías por proyecto. El bearer A no abre el proyecto B, SQL interno ni WS.
Las rutas legacy internas requieren sesión humana mientras sus consumidores
migran a operaciones tipadas; el MCP legacy sin credenciales ya no las abre.
No transmitir la cookie humana para arreglar esa incompatibilidad.

Se valida Host y Origin antes de los handlers. CORS se aplica aparte. No se
aceptan credenciales por query string. El emparejamiento exige JSON, header
explícito, límite de 4096 bytes, deadline y código válido; los intentos fallidos
y las sesiones en memoria tienen límites. Las mutaciones humanas requieren
prueba CSRF; los grants de negocio conservan su validación independiente.

La cookie es HttpOnly y SameSite=Strict, sin Domain; en HTTPS añade Secure.
Estas propiedades siguen la [guía de cookies de MDN](https://developer.mozilla.org/en-US/docs/Web/HTTP/Guides/Cookies).
El valor de cookie nunca vuelve en JSON. El estado/errores de sesión no se
cachean; el frontend conserva únicamente la prueba CSRF en memoria, sin
localStorage. Sus peticiones rechazan destinos externos, barras inversas,
controles de URL y redirecciones, para no enviar la prueba a otro servidor.
La política se ejecuta como [middleware ASGI](https://www.starlette.io/middleware/),
también para conexiones WS.

WS exige cookie vigente y origen confiado. Logout/vencimiento cierran un socket
inactivo en hasta un intervalo de supervisión de 250 ms, y cada envío vuelve a
comprobar autoridad. Esto no cancela automáticamente el trabajo del servidor.
Una conexión retirada del proyecto A no puede enviar eventos a B ni cerrarlo por
un error tardío. Al perder acceso, la web retira sus datos cacheados y deja de
reconectar. Una respuesta HTTP antigua tampoco invalida una sesión recién abierta.

## Evidencia y límites

`backend/tests/api/test_local_access.py` recorre los métodos de todas las rutas
OpenAPI de producto, además de credenciales, CSRF, orígenes, cookies, expiración,
arranque y WS. `test_websocket_lifecycle.py` comprueba reconexión tras cerrar el
loop anterior; el manager deja de retener su suscripción y no crea coroutines
contra un loop cerrado. Los tests Node comprueban aislamiento del transporte,
respuestas tardías y sockets retirados.

`evals/security/run_local_access.py --live` repitió la separación de autoridades,
CSRF, rechazo HTTP/WS anónimo, ping autorizado y logout sobre servidores y
sockets reales con una DB sintética. Cero turnos de modelo. Usa el backend real
y el mismo emparejamiento que el lector humano del runner de investigación.

El host de navegador de CUA sigue indisponible. El build web pasa, pero no hay
aceptación visual ni de teclado en un navegador real. La pantalla funcional de
acceso debe entrar en la exploración visual junto a los estados compartidos;
no sustituye ninguno de los 48 conceptos/adaptaciones exigidos para las doce
páginas del plan. Tampoco se han migrado todos los clientes CLI/MCP antiguos,
retirado el engine, integrado aún la admisión productiva o demostrado aislamiento
de todos sus efectos. No presentar esta frontera como seguridad de todo el producto.
