"""Fixed offline multilingual encoder; untrusted text is data, never code or an asset path."""

import hashlib
import json
import os
import sys


def main():
    """Apply OS fuses, verify inherited public bytes, and rank every bounded source chunk."""
    options = json.loads(sys.argv[1])
    sys.path.insert(0, options["package_root"])
    from backend.research.worker_limits import apply_limits, observed_limits

    apply_limits(options)
    from backend.research.models import SourceTooLarge, SourceUnavailable
    from backend.research.retrieval_assets import ARTIFACTS, FINGERPRINT

    try:
        raw = sys.stdin.buffer.read(options["max_input_bytes"] + 1)
        if len(raw) > options["max_input_bytes"]:
            raise SourceTooLarge("Semantic input exceeds the worker byte limit")
        request = json.loads(raw)
        text = request["text"]
        query = request["query"]

        def asset(name):
            """Load exactly the verified bytes that the encoder will use, without a path race."""
            fd = options["assets"][name]
            _, size, digest = ARTIFACTS[name]
            data = bytearray()
            while len(data) <= size:
                chunk = os.read(fd, min(131072, size + 1 - len(data)))
                if not chunk:
                    break
                data.extend(chunk)
            if len(data) != size or hashlib.sha256(data).hexdigest() != digest:
                raise SourceUnavailable("Pinned semantic asset changed")
            return bytes(data)

        model = asset("model.onnx")
        tokenizer = asset("tokenizer.json").decode("utf-8")
        import numpy as np
        import onnxruntime as ort
        from tokenizers import Tokenizer

        ort.disable_telemetry_events()
        tok = Tokenizer.from_str(tokenizer)
        tok.no_truncation()
        tok.no_padding()
        query_encoding = tok.encode(query)
        if len(query_encoding.ids) > 128:
            raise SourceTooLarge(
                "Semantic query exceeds 128 model tokens; shorten it explicitly"
            )
        configuration = ort.SessionOptions()
        configuration.intra_op_num_threads = 1
        configuration.inter_op_num_threads = 1
        configuration.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
        configuration.enable_cpu_mem_arena = False
        session = ort.InferenceSession(
            model, sess_options=configuration, providers=["CPUExecutionProvider"]
        )
        del model, tokenizer

        usage = {"batches": 0, "vectors": 0}

        def encode(encodings):
            """Masked mean-pool and normalize pinned 384-dimensional CPU output, without truncation."""
            width = max(len(e.ids) for e in encodings)
            if width > 128:
                raise SourceTooLarge("A semantic passage exceeds the model context")
            ids = np.ones((len(encodings), width), dtype=np.int64)
            mask = np.zeros_like(ids)
            types = np.zeros_like(ids)
            for index, entry in enumerate(encodings):
                ids[index, : len(entry.ids)] = entry.ids
                mask[index, : len(entry.ids)] = 1
            inputs = {"input_ids": ids, "attention_mask": mask, "token_type_ids": types}
            output = session.run(
                None, {item.name: inputs[item.name] for item in session.get_inputs()}
            )[0]
            pooled = (output * mask[:, :, None]).sum(1) / mask.sum(1)[:, None]
            norms = np.linalg.norm(pooled, axis=1, keepdims=True)
            if (
                pooled.shape != (len(encodings), 384)
                or not np.isfinite(pooled).all()
                or not (norms > 0).all()
            ):
                raise SourceUnavailable("Semantic encoder returned invalid vectors")
            usage["batches"] += 1
            usage["vectors"] += len(encodings)
            return pooled / norms

        chunks = []
        encodings = []
        start = 0
        while start < len(text):
            candidate = text[start : start + 1200]
            encoded = tok.encode(candidate, add_special_tokens=False)
            end = start + len(candidate)
            if len(encoded.ids) > 96:
                end = start + encoded.offsets[95][1]
            if end <= start:
                raise SourceUnavailable("Semantic tokenizer did not advance")
            entry = tok.encode(text[start:end])
            if len(entry.ids) > 128:
                raise SourceTooLarge("Semantic passage cannot fit without truncation")
            chunks.append({"start": start, "end": end, "tokens": len(entry.ids)})
            encodings.append(entry)
            if len(chunks) > 2048:
                raise SourceTooLarge(
                    "Source exceeds the complete semantic chunk budget; no partial results"
                )
            if end == len(text):
                break
            start = end - min(96, (end - start) // 4)
        query_vector = encode([query_encoding])[0]
        for start in range(0, len(chunks), 8):
            vectors = encode(encodings[start : start + 8])
            for index, score in enumerate(vectors @ query_vector):
                chunks[start + index]["score"] = max(-1.0, min(1.0, float(score)))
        result = {
            "ok": True,
            "chunks": chunks,
            "query_tokens": len(query_encoding.ids),
            "encoder_usage": usage,
            "fingerprint": FINGERPRINT,
            "model_runtime": {
                "onnxruntime": ort.__version__,
                "provider": "CPUExecutionProvider",
            },
            "execution": observed_limits(),
        }
    except (MemoryError, SourceTooLarge):
        result = {
            "ok": False,
            "code": "too_large",
            "message": "Semantic query exceeds CPU/memory/token/chunk budgets; no partial results",
        }
    except Exception:  # noqa: BLE001 - redact internal asset/encoder exceptions at the worker boundary
        result = {
            "ok": False,
            "code": "unavailable",
            "message": "Pinned local semantic encoder could not complete this query",
        }
    encoded = json.dumps(result, ensure_ascii=False, allow_nan=False).encode()
    if len(encoded) > options["max_output_bytes"]:
        encoded = b'{"ok":false,"code":"too_large","message":"Semantic output exceeds its byte budget"}'
    sys.stdout.buffer.write(encoded)
    sys.stdout.buffer.flush()


if __name__ == "__main__":
    main()
