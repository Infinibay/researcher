# Installed service image

The root `Containerfile` builds the owner web application with `npm ci` and
installs the Python project as a wheel, including `_domain_spawn`. The final
image contains compiled assets and installed packages, not a checkout on
`PYTHONPATH`. Python and Node base images use explicit digests; application
dependencies come from `requirements.txt` with hashes and `package-lock.json`.
The build context excludes credentials, databases, local environments and
modernization scratch. OS packages and Python build tooling still resolve
within their configured repositories/ranges; this is not a byte-reproducible build.

## New local installation

These commands are for rootless Podman on Linux, with host UID 1000. Keep the
data directory outside agent workspaces. For an existing installation, select
its actual database and attachment roots and rehearse migration/restore first;
initialization is not an upgrade or repair command.

```sh
podman build -t localhost/researcher:modernization -f Containerfile .

export RESEARCHER_CONTAINER_DATA="${XDG_STATE_HOME:-$HOME/.local/state}/researcher-container"
mkdir -p -m 700 "$RESEARCHER_CONTAINER_DATA"

podman run --rm --userns=keep-id --network=none \
  --mount "type=bind,source=$RESEARCHER_CONTAINER_DATA,destination=/data" \
  localhost/researcher:modernization \
  researcher-bootstrap init-db --database /data/infinibay.db

podman run --name researcher-web --userns=keep-id --network=host \
  --mount "type=bind,source=$RESEARCHER_CONTAINER_DATA,destination=/data" \
  localhost/researcher:modernization
```

Open `http://127.0.0.1:8000`. The API continues to bind numeric loopback and serves
the compiled web application from the same origin. Host networking preserves that
local-access contract; publishing a bridge port does not make a loopback-bound
process reachable. The image does not change the API to bind all interfaces.
For a different host UID, choose an explicit user mapping and prepare directory
ownership rather than running the service as root or broadly changing permissions.

Startup prints the path of a private pairing-code file. In another terminal,
read the code from this particular container and enter it in the access form:

```sh
podman exec researcher-web python -c 'from pathlib import Path; print(next(Path("/run/researcher/auth").glob("owner-*.key")).read_text().strip())'
podman stop --time 20 researcher-web
podman start researcher-web
```

The launcher returns 143 after an orderly SIGTERM; its API child closes first.
A restart requires new owner pairing. It preserves the mounted database and
attachments. Normal startup refuses missing/empty databases; it does not install
dependencies, initialize data, create Forgejo users, download models or start a
second provider backend. Rootless Podman was exercised; Docker and other UID or
kernel configurations still need their own acceptance evidence.

## Storage selection

Inside the image, `/data/infinibay.db` is the explicit database, `/data/uploads`
contains attachments, and logs use `/data`. Built assets are in
`/app/frontend/dist`; private owner pairing files are outside that workspace.
The process runs as UID 1000. Persist `/data` across container replacement.

For a non-container installation, `INFINIBAY_UPLOAD_BASE_DIR` explicitly selects
existing attachments. Otherwise they use `<INFINIBAY_DATA>/uploads`, falling
back to `.data/uploads` below the working directory. `INFINIBAY_STATIC_DIR`
selects installed web assets. Reading configuration creates or moves no files.
An installation that formerly stored uploads below site-packages must explicitly
keep that old root or perform a verified data migration; no files are silently moved.
Database selection remains independent, through `INFINIBAY_DB` and the existing
database resolver. The health endpoint checks the selected upload root or its
nearest existing ancestor rather than requiring the historical `/research` path.

## Native execution and remaining deployment work

The image packages the service; it does not provision the native execution host.
Native runs require the external JSON selected by `INFINIBAY_RUNTIME_CONFIG`,
the managed Codex subscription, published `ken-rank` MCP, a trusted toolchain,
delegated cgroup v2 resources, workspaces and independent authority/witness
storage described in the [owned-runtime contract](owned-product-runtime.md).
These resources must be mounted and enrolled consistently; do not mount broad
host directories or remove native admission checks to make the container start.

Without that configuration the service explicitly runs in inspection mode.
Containerized native admission, host provisioning and real-data restore remain
open deployment work. The separate [Forgejo upgrade rehearsal](forgejo-upgrade.md)
now covers the pinned service configuration, TLS and synthetic backup/restore. A passing HTTP smoke test does not
close those requirements or the twelve-page visual/functional acceptance.

## Reproducible operation check

After building the image, run with the project's installed Python environment:

```sh
python evals/operation/container_smoke.py --output /tmp/researcher-container-check
```

The output directory must not exist. The check uses synthetic data and no model
or account: refusal before initialization, explicit database bootstrap, refusal
to overwrite existing data, built web assets, owner pairing, project creation,
attachment upload/download, two starts and observed shutdown, session invalidation,
persisted bytes and SQLite integrity. It retains logs/data and a scoped JSON
receipt, then removes only its uniquely named test container. It does not remove
the image or any operator data.
