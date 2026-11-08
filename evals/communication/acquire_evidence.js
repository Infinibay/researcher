/** Acquire one registered code/document pair through the existing native tools.
 *
 * This authored evaluation recipe makes no semantic conclusion. A later model
 * step must inspect the emitted evidence before drafting a finding or summary.
 * __REQUEST__ is replaced with JSON fixture data, never executable source.
 */
const request = __REQUEST__;
const receipts = {};
let calls = 0;

/** Stop with a stable reason without forwarding raw transport diagnostics. */
function stop(code) {
  const error = new Error(code);
  error.safeCode = code;
  throw error;
}

/** Check each real tool envelope before using its returned identifiers. */
async function invoke(tool, args) {
  if (++calls > request.max_calls) stop("acquisition_call_bound");
  const reply = await tool(args);
  if (!reply.success || !Array.isArray(reply.contentItems)) stop("tool_refused");
  return reply.contentItems;
}

/** Decode the canonical JSON boundary without treating a failed reply as data. */
async function jsonCall(tool, args) {
  const items = await invoke(tool, args);
  if (items.length !== 1 || items[0].type !== "inputText") stop("json_envelope");
  return JSON.parse(items[0].text);
}

/** Recover all canonical windows under one immutable source identity. */
async function sourceRead(sourceId) {
  let first;
  let offset = 0;
  let content = "";
  for (let window = 0; window < 16; window++) {
    const part = await jsonCall(tools.researcher_source_read, {
      source_id: sourceId, offset, max_chars: 20000
    });
    first ??= part;
    if (part.source_id !== sourceId || part.sha256 !== first.sha256 ||
        part.total_chars !== first.total_chars || part.offset !== offset ||
        typeof part.content !== "string") stop("source_identity_or_coverage");
    content += part.content;
    if (part.next_offset === null) {
      if ([...content].length !== first.total_chars) stop("source_incomplete");
      return {...first, content, offset: 0, next_offset: null};
    }
    if (!Number.isInteger(part.next_offset) || part.next_offset <= offset)
      stop("source_cursor");
    offset = part.next_offset;
  }
  stop("source_window_bound");
}

try {
  const found = await invoke(tools.ken_find, {
    query: request.query, scope: "files", piece_kind: "file"
  });
  const code = await invoke(tools.ken_read, {
    path: request.path, include: ["source"], start_line: 1,
    end_line: request.expected_lines, max_chars: 40000
  });
  const kenText = code.map(item => item.text).join("\n");
  const lineNumbers = [...kenText.matchAll(/^(\d+) \| /gm)].map(match => Number(match[1]));
  if (lineNumbers.length !== request.expected_lines ||
      lineNumbers.some((value, index) => value !== index + 1)) stop("ken_coverage");

  const references = await jsonCall(tools.researcher_reference_list, {});
  const matches = references.references.filter(item => item.filename === request.reference);
  if (matches.length !== 1) stop("reference_identity");
  const document = await jsonCall(tools.researcher_capture_reference, {
    reference_file_id: matches[0].id, operation_key: request.key + ":document"
  });
  receipts.document_source_id = document.source_id;
  const documentSource = await sourceRead(document.source_id);

  const started = await jsonCall(tools.researcher_command_start, {
    operation_key: request.key + ":code", argv: ["cat", "--", request.path],
    output_bytes: request.output_bytes, timeout_seconds: 10
  });
  receipts.job_id = started.job_id;
  let job = started;
  for (let poll = 0; poll < 6 &&
       (job.status !== "exited" || !job.local_execution_closed); poll++) {
    job = await jsonCall(tools.researcher_command_read, {
      job_id: started.job_id, max_bytes: 1, wait_ms: 1000
    });
    if (job.status === "unknown") stop("command_uncertain");
  }
  if (job.status !== "exited" || !job.local_execution_closed || job.exit_code !== 0 ||
      job.error || job.output_limited) stop("command_incomplete");
  // Capture reads the complete durable receipt itself; do not emit its base64 copy.
  const captured = await jsonCall(tools.researcher_capture_command, {
    job_id: started.job_id, operation_key: request.key + ":capture"
  });
  receipts.code_source_id = captured.source_id;
  const codeSource = await sourceRead(captured.source_id);
  if (codeSource.provenance.job.stdout_sha256 !== request.expected_sha256)
    stop("captured_code_changed");
  const evidence = {
    status: "ACQUISITION_READY", receipts, ken_find: found, ken_read: code,
    sources: [documentSource, codeSource]
  };
  if (JSON.stringify(evidence).length > 30000) stop("emitted_evidence_bound");
  text(evidence);
} catch (error) {
  text({status: "ACQUISITION_STOPPED", reason: error.safeCode ?? "tool_or_transport_failure",
        receipts});
}
