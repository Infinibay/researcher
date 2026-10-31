# Scoped research evidence and report slice

Status: implemented business boundary and verified fixtures; candidate runtimes
are not yet wired into the product's default engine. The full modernization
remains active. This slice supports the comparative research scenario in §4.2.

## Ownership and flow

`ResearchService` acquires snapshots through narrow file/web ports, using a
repository receipt before I/O when an operation has already committed.
`SQLiteResearchStore` atomically checks authority, validates domain evidence,
writes effects and records their receipt. `backend/research/models.py` contains
plain contracts and evidence rules, independent of FastAPI, SQLite and runtimes.
HTTP adapters translate typed commands; the isolated MCP process only calls
those HTTP endpoints. Neither agent-facing boundary offers SQL or grant issuance.

The flow is reference attachment / public HTTPS → immutable source snapshot →
provisional finding with exact excerpts → canonical Markdown report draft.
Sources preserve locator, byte and text hashes, capture time and extraction
provenance. External text never grants authority. Exact quotation is a structural
check, not a scientific proof or human comprehension evaluation.

Report text is canonical in `artifacts.content`; links to findings and source
excerpts are normalized. `reports/<id>.md` is a logical locator, not a second
filesystem copy. Binary storage, PDF extraction, exports and historical data
translation remain separate unfinished capabilities. This new capture route
currently accepts UTF-8 text attachments; it explicitly rejects unsupported
formats instead of misdecoding or silently truncating them. Legacy capabilities
are retained until their replacements are verified.

## Authority, context and retries

The trusted host issues an opaque expiring bearer grant bound to project, task,
actor, context version and explicit permissions. Only its hash is persisted.
Grant issuance is a Python host operation; it is not exposed by HTTP or MCP.
Every read checks scope. Every mutation checks it again under `BEGIN IMMEDIATE`,
including after acquisition, so revocation/context advance during slow I/O cannot
commit a stale source. A later runtime service must own issuance, revocation,
context corrections and task/attempt lifecycle; that integration is unfinished.

A `(project, task, operation_key)` receipt stores an intent hash covering actor,
context version and command. Same identity/intent returns the original receipt;
a different intent conflicts. Effects and receipt share a transaction. There is
no automatic replay with a new key after an uncertain response. Reopening a
process with a new valid grant for the same actor/context can reconcile the
original identity. This does not deduplicate unrelated keys or replace external
service reconciliation.

Migration 18 uses the single packaged `backend/db/research_schema.sql` resource,
executed statement-by-statement in one transaction. Additive tables/indexes and
the version marker roll back together. Existing report/project rows are
preserved in the tested v17 fixture. Historical migrations and complete
backup/restore acceptance remain pending. The stdlib connection policy is shared
with legacy callers through `backend/db/connection.py`.

## Interfaces and limits

The tool API is `/api/research-tools/*`. Body schemas forbid project/task/actor
overrides; those identities come from the grant. The MCP server exposes ten
`researcher_*` operations for references, capture, source windows/search,
findings and report persistence/recovery. Use its separate locked environment:

```bash
uv run --locked --script scripts/researcher_mcp_server.py
```

The host supplies `RESEARCHER_API_URL` (numeric loopback HTTP origin) and
`RESEARCHER_TOOL_TOKEN` outside prompts and tool arguments. The client disables
proxy inheritance and redirects, bounds responses, filters validation input from
errors, and reports failures as MCP errors. Container/remote origins need a
separately verified transport policy; they are not silently accepted here.

- Tool JSON ingress: 1,048,576 bytes and a 10-second body deadline.
- Attachments/public source bodies: 1,000,000 bytes; extracted text: 200,000 UTF-8
  bytes. Oversized content is refused, not presented as complete.
- Source/report text windows: default 12,000 and maximum 20,000 characters, with
  explicit offsets/total lengths. Exact source search can recover evidence at
  the end; it is not semantic ranking. Report citations paginate independently.
- Public web capture: 12-second total deadline, bounded/reaped DNS subprocess,
  vetted public address set pinned to the TLS connection, original TLS hostname
  verification, manual revalidation of at most three redirects, no compression
  expansion, and no inherited proxy/cookie/auth state. Slow-drip header reads
  are also bounded. These controls follow the [OWASP SSRF guidance](https://cheatsheetseries.owasp.org/cheatsheets/Server_Side_Request_Forgery_Prevention_Cheat_Sheet.html)
  and preserve the [Python HTTPS verification contract](https://docs.python.org/3.12/library/http.client.html).

The existing artifact API/UI reads canonical reports. Detail now requires
`project_id`; the only frontend consumer includes project identity in its query
and cache key and derives selection from the current project. Titles and draft
status are shown. This is a functional correction in the legacy UI, not the
planned visual redesign or its image concepts.

## Verification and remaining boundaries

Real SQLite/HTTP tests cover retry/conflict/concurrency, atomic receipt failure,
citation fidelity, foreign project denial, forged scope fields, expiry,
revocation/context change during acquisition, bounded windows/evidence pages,
symlink/traversal rejection and HTTP errors. Local TLS tests cover hostname/SNI,
wrong-host certificates and slow-drip deadlines; their ephemeral certificate
fixture requires the `openssl` executable. A real public documentation fetch
also passed.

The locked MCP script was initialized and exercised against the real API with
a temporary database: both source kinds, exact citations, report persistence,
identical retry receipt, artifact API recovery and revoked-scope error passed.
The same operations were repeated after backend/MCP process restart. No model
request was sent by those smoke checks. Candidate model trials for this new
research flow remain to be executed and assessed independently.

This boundary is not global application authentication. Legacy HTTP/WS/internal
routes still need the planned access-control migration, and native file/shell
and Ken path permissions still need complete isolation acceptance. Do not infer
whole-platform protection or completed task acceptance from these tool grants.
Reports remain drafts and findings provisional; the model cannot promote them
through these tools. Durability of runtime events, product Stop/recovery,
retention/deletion, prompt evaluations and human comprehension checks remain
required.
