# Native MCP entry

The public stdio command `researcher-mcp` and both historical script names now
share `backend.research.stdio_server`. They use the existing native research
definitions, typed argument models and bounded async HTTP client. This is an
adapter to the existing API, not another model engine or grant issuer.

The admitting host supplies `RESEARCHER_TOOL_TOKEN` and a numeric loopback HTTP
`RESEARCHER_API_URL`. Configuration validates syntax only. Every actual request
still passes the API's grant authorization, project/task context, permission and
withdrawal checks. Old environment actor labels are ignored. The research
catalogue cannot accept model-supplied project IDs, SQL or owner approvals.
Configure the required Ken MCP separately through the native host; this adapter
does not start Ken or claim that it has verified Ken's availability.

| Historical outcome | Native destination |
| --- | --- |
| Research, findings, sources, wiki, draft reports, material questions | Existing scoped research business catalogue; exact capability permissions remain API-owned |
| Task creation/decomposition, dependencies | Existing admitted planning catalogue and explicit owner graph acceptance |
| Development and checks | Existing admitted author/check runtime and captured candidate |
| Formal review | Distinct admitted reviewer of the exact candidate; documentary audit is separate |
| Task approval/rejection | Explicit owner acceptance/rejection, never an old task status or ambient actor ID |
| Role messages and session notes | Attributed durable conversation/context and native attempt outcomes; old labels do not activate peers or prove shared understanding |
| Read-only SQL queries | Retired standalone interface; use typed scoped business readers and owner history views |
| PR creation/publication | Existing explicit owner publication of an accepted candidate; retained legacy Git material/publication migration remains open |

This mapping identifies where capabilities belong; it does not assert that the
whole project migration, all old clients or every UI flow are finished. The old
SQL tool accepted SELECT/WITH queries, not arbitrary SQL writes.

The MCP SDK lists schemas from the same `ToolDefinition` objects as the native
runtime. Typed validation preserves nested questions and examples. Unknown tools
and additional authority fields fail before HTTP. HTTP failures retain the
original operation key and report uncertainty without retrying. Unexpected
exceptions return a generic response rather than exception text. The session
owns and closes one async HTTP client; existing transport tests cover pending
request draining, time/byte/capacity bounds, no proxy inheritance and no redirects.

Scripts pin MCP1.30.0 to the SDK already validated in the core runtime; this is a
consolidation, not a claim that it is the newest SDK release. The duplicate
FastMCP wrapper is removed. Both PEP723 script locks are independently runnable;
the console command is part of the normal package. Startup/help does not open
storage, provision accounts or invoke models.

Verification covers actual SDK memory and subprocess stdio initialization,
listing and rejection; real ASGI/API/SQLite project scope and grant withdrawal;
typed nested DTOs and uncertain-response behavior. Controlled transport tests
do not independently prove physical runtime ownership. The installed-wheel
receipt records the precise isolated environment and consumers tested. These
checks use no real model turn and make no claim about model/prompt quality,
real Ken ranking, host provisioning, global suite or whole-plan completion.
