# Ejecución nativa desde la imagen instalada

La imagen contiene web/API instaladas, la extensión de cgroups, bubblewrap y
`ken-rank==0.18.0` en `/opt/ken`. Sus dependencias se resuelven en
`requirements-ken.txt` con hashes y quedan separadas de `/opt/venv`, que contiene
el backend. El build no recibe cuentas, bases ni cachés del operador.

La ruta comprobable usa Linux, Podman rootless y usuario anfitrión UID1000.
El host debe ofrecer cgroup v2 delegado, `memory`/`pids`, namespaces sin privilegios
y el ABI nativo soportado por el proyecto. No se da por comprobada la misma
configuración con Docker, otros UID, políticas SELinux/AppArmor ni otros kernels.
[Resultados del ensayo](../modernization/native-container-results.json).

## Preparación explícita

Construir la imagen desde el checkout:

```sh
podman build --network=host -t localhost/researcher:native-host -f Containerfile .
```

Seleccionar las rutas existentes de Codex 0.166.0, su code-mode-host, la cuenta
de suscripción y los modelos públicos fijados por Ken. Elegir también un
subdirectorio nuevo dentro de un cgroup ya delegado al usuario. El ejemplo es
para una instalación nueva: sus directorios de instalación/autoridad aún no deben
existir. La preparación no migra ni repara datos anteriores.

```bash
export RESEARCHER_NATIVE_STATE="${XDG_STATE_HOME:-$HOME/.local/state}/researcher-native"
export RESEARCHER_CODEX_BIN="/opt/codex-0.166.0/bin"
export RESEARCHER_ACCOUNT_FILE="$HOME/.codex/auth.json"
export RESEARCHER_MODEL_CACHE="$HOME/.cache/huggingface/hub"
export RESEARCHER_CGROUP_ROOT="/sys/fs/cgroup/YOUR_DELEGATED_PARENT/researcher"

mkdir -p -m 700 "$RESEARCHER_NATIVE_STATE/data" "$RESEARCHER_NATIVE_STATE/witness"
mkdir -m 700 "$RESEARCHER_CGROUP_ROOT"
printf '%s' '+memory +pids' > "$RESEARCHER_CGROUP_ROOT/cgroup.subtree_control"
cp docs/config/container-host-assets.example.json "$RESEARCHER_NATIVE_STATE/data/assets.json"
chmod 600 "$RESEARCHER_NATIVE_STATE/data/assets.json"
```

Editar `assets.json`: su `cgroup_parent` debe coincidir exactamente con
`RESEARCHER_CGROUP_ROOT`; seleccionar modelo y límites. Las demás rutas del
ejemplo corresponden a los montajes de abajo. No reemplazar el archivo de cuenta
por una API key ni escribir sus tokens dentro del JSON de configuración.

```bash
native=(podman run --pull=never --userns=keep-id --cgroupns=host --pid=host
  --security-opt 'unmask=/proc/*'
  --cgroup-parent "${RESEARCHER_CGROUP_ROOT#/sys/fs/cgroup}"
  --mount "type=bind,source=$RESEARCHER_CGROUP_ROOT,destination=$RESEARCHER_CGROUP_ROOT"
  --mount "type=bind,source=$RESEARCHER_NATIVE_STATE/data,destination=/data"
  --mount "type=bind,source=$RESEARCHER_NATIVE_STATE/witness,destination=/witness"
  --mount "type=bind,source=$RESEARCHER_CODEX_BIN/codex,destination=/opt/researcher-native/codex,ro"
  --mount "type=bind,source=$RESEARCHER_CODEX_BIN/codex-code-mode-host,destination=/opt/researcher-native/codex-code-mode-host,ro"
  --mount "type=bind,source=$RESEARCHER_MODEL_CACHE,destination=/opt/researcher-models,ro"
  --mount "type=bind,source=$RESEARCHER_ACCOUNT_FILE,destination=/run/researcher/subscription/auth.json,ro"
)

"${native[@]}" --rm --network=none localhost/researcher:native-host \
  researcher-bootstrap init-host --directory /data/installation \
  --witness-dir /witness/authority --assets /data/assets.json

"${native[@]}" --rm --network=none localhost/researcher:native-host \
  researcher-bootstrap check-host --directory /data/installation --probe

"${native[@]}" -d --name researcher-native --network=host \
  localhost/researcher:native-host \
  researcher-start --installation /data/installation --port 8000
```

El supervisor sirve la aplicación en `http://127.0.0.1:8000`. Emparejar al
propietario usando el archivo privado que indica el arranque; después de cerrar
y reiniciar se requiere otro emparejamiento. El modo `--network=host` mantiene
el servidor en loopback y permite al mediador de inferencia llegar al proveedor;
los peers mantienen sus propios namespaces y controles de salida.

## Recursos y cierre

El backend de control usa el namespace de PID del host, igual que al ejecutarlo
directamente. El registro de autoridad vincula su observador: crear otro
namespace al reiniciar no permite adoptar la identidad anterior. La imagen es
un empaquetado del backend confiable, no una frontera de aislamiento entre ese
backend y el host. Los peers siguen creando namespaces privados y no reciben
la vista de procesos del controlador. Se permite ver las rutas `/proc` del
controlador para que bubblewrap monte el `/proc` de cada peer; el perfil
predeterminado impide ese montaje. Es la opción específica
[`unmask=/proc/*` de Podman](https://docs.podman.io/en/v6.1.3/markdown/podman-run.1.html),
sin añadir privilegios del host ni desactivar seccomp. El cgroup namespace del
controlador muestra las rutas reales, y sólo su subárbol dedicado se monta
escribible. Los peers no reciben ese montaje ni la cuenta general del host.

Bubblewrap de Debian `0.8.0-2+deb12u1` incluye `--ro-bind-fd`; el build verifica
esa capacidad. El proyecto necesita montar descriptores ya abiertos: la opción
fue incorporada y también retroportada por
[bubblewrap](https://github.com/containers/bubblewrap/releases/tag/v0.10.0).
La versión principal que imprime el ejecutable, por sí sola, no describe sus
parches de distribución.

```sh
podman stop --time 20 researcher-native
podman start researcher-native
```

Un cierre ordenado del launcher devuelve143. Conservar tanto `/data` como el
testigo externo de `/witness`; no usar `init-host` para un reinicio. Si el login
del host reemplaza el archivo de cuenta, recrear el contenedor con el montaje
actualizado y los mismos datos/testigo: un bind de archivo conserva el inode
anterior. La renovación de cuenta no se ensaya como ciclo completo aquí.

Los upgrades de imagen/Ken deben mantener datos y autoridad y verificar los
modelos fijados; una caché antigua incompatible se rechaza antes de inferir.
El aprovisionamiento del cgroup depende de la política del host y sigue siendo
explícito. No se declara restauración de datos reales ni adopción automática de
procesos de una instalación previa.

## Ensayo reproducible

Con el entorno Python instalado del proyecto, un JSON de recursos del host
(el del [host nativo](native-host-installation.md)) y una salida nueva:

```sh
python evals/operation/native_container.py \
  --image localhost/researcher:native-host \
  --host-assets /etc/researcher/host-assets.json \
  --output /tmp/researcher-native-container-check --live
```

El runner crea su propio subárbol, prepara sólo datos sintéticos, comprueba
cgroup y namespaces antes de admitir la tarea, envía como máximo una admisión,
conserva el resultado tras reiniciar y observa los cierres. `--live` usa la
suscripción; omitirlo evita inferencia. Reutiliza el mismo ejercicio de
investigación del host, con las rutas que ve el contenedor. Una ejecución
incierta no se repite. La salida incluye logs privados y datos para inspección;
el runner sólo elimina su contenedor y su cgroup vacío.
