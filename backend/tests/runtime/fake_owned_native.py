"""Controlled generation/command protocol; actual SDK/kernel has separate checks."""

import base64
import json
import subprocess
import sys
import tomllib
from pathlib import Path

features = {}
config = {}
args = iter(sys.argv[1:])
for arg in args:
    if arg in ("--enable", "--disable"):
        features[next(args)] = arg == "--enable"
    elif arg == "-c":
        config.update(tomllib.loads(next(args)))
steps = 0
source = finding = job = report = None
scientific_mode = False
scientific_finding_ids = []
scientific_output_source = None
investigation_mode = False
planning_mode = False
plan_material = None
review_mode = False
development_mode = False
prior_code_patch = None
prior_selected_branch = False
causal_task = None
causal_ready = False
causal_section = 0
causal_bytes = {}
causal_resume = None
prior_selected_files = None
code_prior_files = False
review_subject = None
code_review_mode = False
code_packet = code_file = None
native_thread_id = "owned-thread"
native_turn_id = "owned-turn"


def send(message):
    print(json.dumps(message), flush=True)


def call(name, arguments):
    """Emit a controlled tool request attributed to this fixture's native thread and turn."""
    send(
        {
            "id": "tool-" + str(steps),
            "method": "item/tool/call",
            "params": {
                "threadId": native_thread_id,
                "turnId": native_turn_id,
                "callId": "tool-" + str(steps),
                "tool": name,
                "arguments": arguments,
            },
        }
    )


def next_tool(response=None):
    """Advance controlled author or reviewer generation while using the real admitted tool bridge."""
    if causal_task is not None and not causal_ready:
        return next_causal_material(response)
    if planning_mode:
        return next_planning_tool(response)
    if code_review_mode:
        return next_code_review_tool(response)
    if review_mode:
        return (
            next_scientific_review_tool(response)
            if scientific_mode
            else next_review_tool(response)
        )
    if development_mode:
        return next_development_tool(response)
    if scientific_mode:
        return next_scientific_tool(response)
    global steps, source, finding, job, report
    if response is not None:
        Path("/home/actor/.codex/fixture-progress.json").write_text(
            json.dumps({"step": steps, "response": response})
        )
        if not response["success"]:
            raise RuntimeError("Controlled tool failed: " + str(response))
        value = json.loads(response["contentItems"][0]["text"])
        if steps == 2:
            job = value["job_id"]
        if steps == 3 and value["status"] != "exited":
            call("researcher_command_read", {"job_id": job, "wait_ms": 1000})
            return
        if steps == 4:
            source = value["source_id"]
        if steps == 5:
            finding = value["finding_id"]
        if steps == 6:
            report = value["artifact_id"]
    steps += 1
    if steps == 1:
        call("ken_read", {"path": "fact.txt"})
    elif steps == 2:
        call(
            "researcher_python",
            {
                "operation_key": "calculation",
                "code": "from pathlib import Path; print(int(Path('fact.txt').read_text())+63)",
                "timeout_seconds": 5.0,
            },
        )
    elif steps == 3:
        call("researcher_command_read", {"job_id": job, "wait_ms": 1000})
    elif steps == 4:
        call(
            "researcher_capture_reference",
            {"operation_key": "capture", "reference_file_id": 7},
        )
    elif steps == 5:
        call(
            "researcher_finding_record",
            {
                "operation_key": "finding",
                "topic": "fixture",
                "content": "Inspected a synthetic attachment; calculation200 is separate execution evidence.",
                "evidence": [{"source_id": source, "quote": "Fixture base 137 units."}],
            },
        )
    elif steps == 6 and investigation_mode:
        call(
            "researcher_investigation_summary",
            {
                "operation_key": "report",
                "summary": {
                    "title": "Fixture investigation",
                    "question": "¿Qué cuenta consta y qué sigue sin verificarse?",
                    "scope_includes": [
                        "Inspeccionar la fuente aportada y ejecutar un cálculo separado."
                    ],
                    "scope_excludes": ["Repetir la medición original."],
                    "areas": [
                        {
                            "title": "Cuenta documentada",
                            "observations": "La fuente registra 137 unidades; el cálculo separado da 200.",
                            "finding_ids": [finding],
                        },
                        {
                            "title": "Método de medición",
                            "observations": "No se aportó un protocolo de medición.",
                            "finding_ids": [],
                        },
                    ],
                    "conclusion": "Se verificó el texto, no la medición original.",
                    "limitations": [
                        "La medición original no se repitió; el cálculo es evidencia separada."
                    ],
                    "next_steps": [
                        "Obtener el protocolo si la decisión requiere verificar la medición."
                    ],
                },
            },
        )
    elif steps == 6:
        call(
            "researcher_report_write",
            {
                "operation_key": "report",
                "title": "Fixture inspection",
                "content": "Inspección y cálculo acotado. El informe sigue siendo un borrador.",
                "finding_ids": [finding],
            },
        )
    elif steps == 7:
        call(
            "researcher_result_propose",
            {
                "operation_key": "deliver",
                "report_ids": [report],
                "summary": "Inspección documental y cálculo acotado.",
                "limitations": [
                    "La medición original no se repitió; el cálculo es evidencia separada."
                ],
            },
        )
    else:
        send(
            {
                "method": "item/completed",
                "params": {
                    "threadId": native_thread_id,
                    "turnId": native_turn_id,
                    "item": {
                        "id": "answer",
                        "type": "agentMessage",
                        "text": "Borrador persistido; la tarea requiere revisión.",
                    },
                },
            }
        )
        send(
            {
                "method": "turn/completed",
                "params": {
                    "threadId": native_thread_id,
                    "turn": {
                        "id": native_turn_id,
                        "status": "completed",
                        "error": None,
                    },
                },
            }
        )


def next_causal_material(response=None):
    """Consume real bounded accepted artifacts before continuing the controlled author/reviewer; this is not a real model understanding claim."""
    import hashlib

    global causal_ready, causal_section, prior_code_patch
    sections = ('packet', 'author_input', 'diff')
    if response is not None:
        assert response['success'], response
        page = json.loads(response['contentItems'][0]['text'])
        section = sections[causal_section]
        saved = causal_bytes.setdefault(section, bytearray())
        assert page['source']['task_id'] == causal_task and page['authority'] == 'data_only'
        assert page['offset'] == len(saved)
        saved.extend(base64.b64decode(page['data_base64'], validate=True))
        if page['next_offset'] is None:
            assert len(saved) == page['total_bytes'] and hashlib.sha256(saved).hexdigest() == page['sha256']
            causal_section += 1
    if causal_section == len(sections):
        original = json.loads(causal_bytes['author_input'])
        assert original['scope']['task_id'] == causal_task
        assert b'+200' in causal_bytes['diff']
        causal_ready = True
        if causal_resume is not None:
            return next_code_review_tool(causal_resume)
        prior_code_patch = base64.b64encode(causal_bytes['diff']).decode('ascii')
        return next_tool()
    section = sections[causal_section]
    offset = len(causal_bytes.get(section, b''))
    identity = f'material-{section}-{offset}'
    send({'id': identity, 'method': 'item/tool/call', 'params': {
        'threadId': native_thread_id, 'turnId': native_turn_id, 'callId': identity,
        'tool': 'researcher_prerequisite_code', 'arguments': {'task_id': causal_task, 'section': section, 'offset': offset, 'max_bytes': 4096},
    }})


def next_development_tool(response=None):
    """Exercise private edits, durable job reads and fresh Ken reads without proposing research acceptance."""
    global steps, job
    if response is not None:
        assert response["success"], response
        value = json.loads(response["contentItems"][0]["text"])
        if steps == 2:
            job = value["job_id"]
        if steps == 3 and value["status"] != "exited":
            call("researcher_command_read", {"job_id": job, "wait_ms": 1000})
            return
        if steps == 4:
            assert value == 200, value
    steps += 1
    if steps == 1:
        call("ken_read", {"path": "fact.txt"})
    elif steps == 2:
        call(
            "researcher_python",
            {
                "operation_key": "edit-private",
                "code": development_edit_code(),
                "timeout_seconds": 5.0,
            },
        )
    elif steps == 3:
        call("researcher_command_read", {"job_id": job, "wait_ms": 1000})
    elif steps == 4:
        call("ken_read", {"path": "fact.txt"})
    else:
        send(
            {
                "method": "item/completed",
                "params": {
                    "threadId": native_thread_id,
                    "turnId": native_turn_id,
                    "item": {
                        "id": "answer",
                        "type": "agentMessage",
                        "text": "Copia privada actualizada; pendiente de candidato y revisión.",
                    },
                },
            }
        )
        send(
            {
                "method": "turn/completed",
                "params": {
                    "threadId": native_thread_id,
                    "turn": {
                        "id": native_turn_id,
                        "status": "completed",
                        "error": None,
                    },
                },
            }
        )


def development_edit_code():
    """Consume actual delivered prior bytes when selected; the controlled fresh author applies them with Git in its private copy."""
    if prior_selected_files is not None:
        assert all(entry["kind"] == "file" for entry in prior_selected_files)
        return (
            "import base64,json,os\nfrom pathlib import Path\n"
            + "entries=json.loads(" + repr(json.dumps(prior_selected_files)) + ")\n"
            + "for entry in entries:\n p=Path(entry['path']);p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(base64.b64decode(entry['content_base64'],validate=True));p.chmod(0o755 if entry['git_mode']=='100755' else 0o644)\n"
            + "print('selected old files applied');print(Path('fact.txt').read_text())"
        )
    if prior_code_patch is None:
        return "from pathlib import Path;p=Path('fact.txt');p.write_text(str(int(p.read_text())+63));print(p.read_text())"
    return (
        "import base64,subprocess\nfrom pathlib import Path\n"
        + "patch=base64.b64decode(" + repr(prior_code_patch) + ",validate=True)\n"
        + "subprocess.run(['/usr/bin/git','apply','--check','--binary','-'],input=patch,check=True)\n"
        + "subprocess.run(['/usr/bin/git','apply','--binary','-'],input=patch,check=True)\n"
        + ("print('causal predecessor applied')\n" if causal_task is not None else "")
        + ("p=Path('fact.txt');assert p.read_text()=='999';p.write_text('200');print('selected old branch adapted')\n" if prior_selected_branch else "")
        + "print('prior patch applied');print(Path('fact.txt').read_text())"
    )


def next_review_tool(response=None):
    """Exercise admitted review reads and one decision without any author mutation."""
    global steps, review_subject
    if response is not None:
        if not response["success"]:
            raise RuntimeError("Controlled review tool failed: " + str(response))
        value = json.loads(response["contentItems"][0]["text"])
        if steps == 2:
            assert value["next_offset"] is None
            review_subject = json.loads(value["content"])
        if steps == 3:
            assert "137 units" in value["content"]
    steps += 1
    if steps == 1:
        call("ken_read", {"path": "fact.txt"})
    elif steps == 2:
        call("researcher_review_subject", {"max_chars": 20000})
    elif steps == 3:
        call(
            "researcher_source_read",
            {"source_id": review_subject["evidence"][0]["source"]["id"]},
        )
    elif steps == 4:
        call(
            "researcher_review_decide",
            {
                "operation_key": "controlled-review-decision",
                "verdict": "supported",
                "rationale": "The captured text supports the recorded count.",
                "checks": [
                    {
                        "criterion": "claim_support",
                        "outcome": "supported",
                        "explanation": "The source explicitly reports 137 units.",
                    }
                ],
                "evidence": [
                    {
                        "source_id": review_subject["evidence"][0]["source"]["id"],
                        "quote": "137 units",
                    }
                ],
                "limitations": [
                    "The original measurement was not independently repeated."
                ],
            },
        )
    else:
        send(
            {
                "method": "item/completed",
                "params": {
                    "threadId": native_thread_id,
                    "turnId": native_turn_id,
                    "item": {
                        "id": "answer",
                        "type": "agentMessage",
                        "text": "Revisión registrada con alcance limitado; tarea sin aceptar.",
                    },
                },
            }
        )
        send(
            {
                "method": "turn/completed",
                "params": {
                    "threadId": native_thread_id,
                    "turn": {
                        "id": native_turn_id,
                        "status": "completed",
                        "error": None,
                    },
                },
            }
        )


def next_code_review_tool(response=None):
    """Generate controlled independent review calls; every source/proposal/Git/closure operation remains production code."""
    global steps, code_packet, code_file, job, code_prior_files, causal_task, causal_resume
    if response is not None:
        if not response["success"]:
            raise RuntimeError("Controlled code review tool failed: " + str(response))
        value = json.loads(response["contentItems"][0]["text"])
        if steps == 1:
            assert value == 200
        elif steps == 2:
            assert value["complete_material"]
            code_packet = value
            origin = json.loads(value["text"])["author_request"]
            assert origin["source_kind"] in (
                "owner_admission",
                "coordinated_owner_execution",
            )
            if origin["source_kind"] == "coordinated_owner_execution":
                assert origin["work_delivery_id"] and origin["plan_run_id"]
                assert len(origin["work_delivery_sha256"]) == 64
        elif steps == 3:
            assert value["complete_material"]
            actual_input = json.loads(value["text"])
            if (
                json.loads(code_packet["text"])["author_request"]["source_kind"]
                == "coordinated_owner_execution"
            ):
                original = actual_input["work_delivery"]["plan_context"][
                    "original_material"
                ]
                assert original["instruction_origin"] == "owner_message"
                assert "137 to 200" in original["owner_request"]
                assert actual_input["work_delivery"]["plan_context"]["accepted_plan"][
                    "assumptions"
                ]
                code_sources = [item for item in actual_input['work_delivery']['prerequisites'] if item['kind']=='accepted_code_candidate']
                if code_sources and not causal_ready:
                    causal_task = code_sources[0]['task_id']
                    causal_resume = response
                    return next_causal_material()
            elif actual_input.get("prior_code") and "files" in actual_input["prior_code"]["snapshot"]:
                assert "Import selected older" in actual_input["request"]
                earlier = actual_input["prior_code"]["snapshot"]
                assert earlier["original_input"] is None
                assert earlier["original_input_status"] == "unknown"
                assert earlier["origin"]["task_relation"] == "selected_by_owner_not_historically_verified"
                code_prior_files = True
            elif actual_input.get("prior_code") and actual_input['prior_code']['snapshot']['origin']['kind']=='selected_legacy_branch':
                assert 'Adapt selected older branch' in actual_input['request']
                earlier = actual_input['prior_code']['snapshot']
                assert earlier['acquisition']=='captured' and earlier['original_input'] is None
                assert 'fact.txt' in earlier['changed_paths']
                assert earlier['candidate']['head_sha']==earlier['selection']['selected_commit_sha']
            elif actual_input.get("prior_code"):
                assert "Reuse the exact earlier patch" in actual_input["request"]
                earlier = actual_input["prior_code"]["snapshot"]
                assert "137 to 200" in earlier["original_input"]["request"]
                assert earlier["origin"]["attempt_id"] != actual_input["scope"]["attempt_id"]
            else:
                assert "137 to 200" in actual_input["request"]
        elif steps == 4:
            assert value["complete_material"] and "+200" in value["text"]
        elif steps == 5:
            assert value["text"] == "200" and value["complete_file"]
            code_file = value
        elif steps == 6:
            job = value["job_id"]
        elif steps == 7 and value["status"] != "exited":
            call("researcher_command_read", {"job_id": job, "wait_ms": 1000})
            return
        elif steps == 8:
            assert value["state"] == "proposed"
    steps += 1
    if steps == 1:
        call("ken_read", {"path": "fact.txt", "include": ["source"]})
    elif steps in (2, 3, 4):
        call(
            "researcher_code_review_subject",
            {
                "section": {2: "packet", 3: "author_input", 4: "diff"}[steps],
                "max_chars": 24000,
            },
        )
    elif steps == 5:
        call("researcher_code_review_file", {"path": "fact.txt"})
    elif steps == 6:
        call(
            "researcher_python",
            {
                "operation_key": "verify-review-readonly",
                "code": "from pathlib import Path\ntry: Path('fact.txt').write_text('unsafe')\nexcept OSError: print('readonly')\nelse: raise AssertionError('review source writable')",
                "timeout_seconds": 5.0,
            },
        )
    elif steps == 7:
        call("researcher_command_read", {"job_id": job, "wait_ms": 1000})
    elif steps == 8:
        call(
            "researcher_code_review_propose",
            {
                "operation_key": "review-" + code_packet["review_run_id"] + "-proposal",
                "subject_sha256": code_packet["subject_sha256"],
                "verdict": "supported",
                "rationale": "The current owner requested selected earlier files; the exact new candidate contains200. The old source is data, not proof of current requirements or previous approval." if code_prior_files else "The recorded owner request changes137 to200; the actual candidate source contains200.",
                "checks": [
                    {
                        "criterion": "requested value",
                        "outcome": "supported",
                        "explanation": "Exact candidate source and full diff show200.",
                    },
                    {
                        "criterion": "tests",
                        "outcome": "not_applicable",
                        "explanation": "This controlled fixture changes only a data value; no project-wide test execution is claimed.",
                    },
                ],
                "references": [
                    {
                        "kind": "file",
                        "path": "fact.txt",
                        "sha256": code_file["sha256"],
                        "start_line": 1,
                        "quote": "200",
                    }
                ],
                "limitations": [
                    "Scoped data-only source inspection; not task acceptance, publication or a claim of project-wide test success."
                ],
            },
        )
    else:
        send(
            {
                "method": "item/completed",
                "params": {
                    "threadId": native_thread_id,
                    "turnId": native_turn_id,
                    "item": {
                        "id": "review-answer",
                        "type": "agentMessage",
                        "text": "Observé200 en el candidato solicitado. La revisión queda propuesta con alcance limitado; la tarea sigue sin aceptar ni publicar.",
                    },
                },
            }
        )
        send(
            {
                "method": "turn/completed",
                "params": {
                    "threadId": native_thread_id,
                    "turn": {
                        "id": native_turn_id,
                        "status": "completed",
                        "error": None,
                    },
                },
            }
        )


def finish_scientific_turn(message):
    """End the controlled protocol with an explicitly limited research or review candidate."""
    send(
        {
            "method": "item/completed",
            "params": {
                "threadId": native_thread_id,
                "turnId": native_turn_id,
                "item": {
                    "id": "science-answer",
                    "type": "agentMessage",
                    "text": message,
                },
            },
        }
    )
    send(
        {
            "method": "turn/completed",
            "params": {
                "threadId": native_thread_id,
                "turn": {"id": native_turn_id, "status": "completed", "error": None},
            },
        }
    )


def next_scientific_tool(response=None):
    """Exercise actual source/job capture, competing hypotheses, experiment, synthesis and wiki through native host tools; generation is scripted."""
    global steps, source, job, report, scientific_output_source
    if response is not None:
        if not response["success"]:
            raise RuntimeError("Controlled scientific tool failed: " + str(response))
        value = json.loads(response["contentItems"][0]["text"])
        if steps == 2:
            job = value["job_id"]
        if steps == 3 and (
            value["status"] != "exited" or not value["local_execution_closed"]
        ):
            call("researcher_command_read", {"job_id": job, "wait_ms": 1000})
            return
        if steps == 4:
            source = value["source_id"]
        if steps == 5:
            scientific_output_source = value["source_id"]
        if steps in (6, 7, 8, 9):
            scientific_finding_ids.append(value["finding_id"])
        if steps == 11:
            report = value["artifact_id"]
    steps += 1
    if steps == 1:
        call("ken_read", {"path": "fact.txt"})
    elif steps == 2:
        call(
            "researcher_python",
            {
                "operation_key": "science-calc",
                "code": "from pathlib import Path;print(int(Path('fact.txt').read_text())+63)",
                "timeout_seconds": 5.0,
            },
        )
    elif steps == 3:
        call("researcher_command_read", {"job_id": job, "wait_ms": 1000})
    elif steps == 4:
        call(
            "researcher_capture_reference",
            {"operation_key": "science-input", "reference_file_id": 7},
        )
    elif steps == 5:
        call(
            "researcher_capture_command",
            {"operation_key": "science-output", "job_id": job},
        )
    elif steps in (6, 7, 8, 9):
        kind, topic, body = {
            6: (
                "hypothesis",
                "H1: explicit arithmetic",
                "Adding63to the recorded137predicts200; this is an interpretation to test, not empirical replication.",
            ),
            7: (
                "hypothesis",
                "H2: no arithmetic needed",
                "Treating the original recorded count as already200is an alternative contradicted by the supplied137and the explicit calculation.",
            ),
            8: (
                "experiment",
                "Retained calculation",
                "Read fact.txt and add63once. The actual closed command output is200. This is one deterministic calculation, not a repeated sampling experiment.",
            ),
            9: (
                "conclusion",
                "Scope-limited arithmetic",
                "The supplied text records137; the separately retained calculation gives200. H1fits that bounded arithmetic and H2does not. No empirical measurement protocol, independent sampling units or population causal effect were tested.",
            ),
        }[steps]
        evidence = [{"source_id": source, "quote": "Fixture base 137 units."}]
        if steps >= 8:
            evidence.append({"source_id": scientific_output_source, "quote": "200"})
        call(
            "researcher_finding_record",
            {
                "operation_key": "science-finding-" + str(steps),
                "topic": topic,
                "content": body,
                "finding_type": kind,
                "evidence": evidence,
            },
        )
    elif steps == 10:
        call(
            "researcher_wiki_write",
            {
                "operation_key": "science-note",
                "path": "scientific-fixture",
                "title": "Cálculo y medición son evidencias distintas",
                "content": "La fuente registra137. El cálculo retenido da200. No se repitió la medición ni se conoce el protocolo. Nota contextual; no validación científica.",
                "expected_revision": 0,
            },
        )
    elif steps == 11:
        text = (
            "## Pregunta y unidad\n¿Qué interpretación aritmética concuerda con el dato aportado? Una entrada de fixture; ninguna unidad muestral empírica identificada.\n## Métodos y alcance de búsqueda\nKen leyó fact.txt. Sólo se inspeccionó el adjunto y se ejecutó una suma con Python estándar. No hubo revisión bibliográfica ni búsqueda web.\n## Hipótesis y evidencia por tema\nH1:137+63produce200. H2:137ya representa200. La fuente dice137 y la salida capturada es200; H2contradice esas observaciones en este alcance. No se elige una hipótesis contando páginas o inconsistencias.\n## Experimento\nJob "
            + str(job)
            + "; código: leer fact.txt y sumar63. Se conserva stdout, argv, salida y cierre en una fuente citable. Una ejecución determinista; no replicación empírica.\n## Discusión y contraevidencia\nSin la entrada original no puede atribuirse el resultado al dato137. Ambas fuentes dependen del mismo fixture; no son dos réplicas independientes. La medición original, protocolo y población siguen desconocidos.\n## Evaluación\nNo se realizó GRADE ni se asignó certeza numérica. La revisión documental independiente y aceptación del propietario son decisiones separadas.\n## Conclusión y próximos pasos\nEl resultado acotado es aritmético. Obtener el protocolo y unidades independientes si la decisión exige verificar una medición.\n## Referencias\nFuente de entrada #"
            + str(source)
            + "; recibo de comando #"
            + str(scientific_output_source)
            + "."
        )
        call(
            "researcher_report_write",
            {
                "operation_key": "science-report",
                "title": "Investigación de cálculo y medición",
                "content": text,
                "finding_ids": scientific_finding_ids,
                "report_type": "research",
            },
        )
    elif steps == 12:
        call(
            "researcher_result_propose",
            {
                "operation_key": "science-deliver",
                "report_ids": [report],
                "summary": "Contraste de hipótesis con cálculo retenido y límites explícitos.",
                "limitations": [
                    "La medición original no se repitió; el cálculo es evidencia separada."
                ],
            },
        )
    else:
        finish_scientific_turn(
            "Informe y nota guardados; revisión y aceptación siguen siendo decisiones explícitas."
        )


def next_scientific_review_tool(response=None):
    """Inspect the author's exact finding and both retained sources through an independently admitted review-only session."""
    global steps, review_subject
    if response is not None:
        if not response["success"]:
            raise RuntimeError("Controlled scientific review failed: " + str(response))
        value = json.loads(response["contentItems"][0]["text"])
        if steps == 1:
            review_subject = json.loads(value["content"])
        if steps == 2:
            assert "137 units" in value["content"]
        if steps == 3:
            assert "Standard output" in value["content"] and "200" in value["content"]
    steps += 1
    if steps == 1:
        call("researcher_review_subject", {"max_chars": 20000})
    elif steps in (2, 3):
        call(
            "researcher_source_read",
            {"source_id": review_subject["evidence"][steps - 2]["source"]["id"]},
        )
    elif steps == 4:
        call(
            "researcher_review_decide",
            {
                "operation_key": "science-review",
                "verdict": "supported",
                "rationale": "El texto y el cálculo retenido respaldan la conclusión acotada; no verifican la medición empírica.",
                "checks": [
                    {
                        "criterion": "claim_support",
                        "outcome": "supported",
                        "explanation": "Se leyeron las dos fuentes originales.",
                    },
                    {
                        "criterion": "method_scope",
                        "outcome": "supported",
                        "explanation": "El informe limita el resultado a una suma y distingue hipótesis, ejecución y medición.",
                    },
                    {
                        "criterion": "counterevidence",
                        "outcome": "supported",
                        "explanation": "La alternativaH2se contrasta con137y200; no hay réplicas independientes.",
                    },
                    {
                        "criterion": "empirical_replication",
                        "outcome": "not_applicable",
                        "explanation": "La conclusión examinada se limita al cálculo; no afirma replicación empírica, protocolo ni población.",
                    },
                ],
                "evidence": [
                    {
                        "source_id": review_subject["evidence"][0]["source"]["id"],
                        "quote": "137 units",
                    },
                    {
                        "source_id": review_subject["evidence"][1]["source"]["id"],
                        "quote": "200",
                    },
                ],
                "limitations": [
                    "Revisión documental de dos fuentes dependientes; no certeza científica calibrada."
                ],
            },
        )
    else:
        finish_scientific_turn(
            "Revisión documental propuesta; no acepta la tarea ni valida una medición."
        )


def next_planning_tool(response=None):
    """Produce a controlled justified graph through actual native host tools, with no child execution or owner approval capability."""
    global steps, plan_material
    if response is not None:
        if not response["success"]:
            raise RuntimeError("Controlled planning tool failed: " + str(response))
        value = json.loads(response["contentItems"][0]["text"])
        if steps == 2:
            assert value["next_offset"] is None
            plan_material = json.loads(value["content"])
    steps += 1
    if steps == 1:
        call("ken_read", {"path": "fact.txt"})
    elif steps == 2:
        call("researcher_plan_context", {})
    elif steps == 3:
        call(
            "researcher_plan_propose",
            {
                "operation_key": "controlled-plan-proposal",
                "plan": {
                    "title": "Understand then improve",
                    "rationale": "Inspect observed behavior before choosing a code change.",
                    "assumptions": [
                        "The registered repository remains the intended target."
                    ],
                    "basis": [
                        {
                            "source": "owner_request",
                            "quote": plan_material["owner_request"][:80],
                        },
                        *[
                            {"source":key,"quote":value[:80]}
                            for key,value in plan_material["sources"].items()
                            if key.endswith(":requirements")
                        ],
                    ],
                    "epics": [
                        {
                            "key": "behavior",
                            "title": "Verified behavior",
                            "description": "Understand and improve the registered code.",
                        }
                    ],
                    "tasks": [
                        {
                            "key": "inspect",
                            "epic_key": "behavior",
                            "type": "research",
                            "title": "Inspect current behavior",
                            "description": "Read relevant code and record cited evidence.",
                            "acceptance_criteria": "A supported explanation and explicit limits.",
                            "priority": 2,
                            "depends_on": [],
                        },
                        {
                            "key": "improve",
                            "epic_key": "behavior",
                            "type": "code",
                            "title": "Implement supported improvement",
                            "description": "Apply the change supported by inspection.",
                            "acceptance_criteria": "The demonstrated behavior is verified.",
                            "priority": 2,
                            "depends_on": ["inspect"],
                        },
                    ],
                },
            },
        )
    else:
        send(
            {
                "method": "item/completed",
                "params": {
                    "threadId": native_thread_id,
                    "turnId": native_turn_id,
                    "item": {
                        "id": "plan-answer",
                        "type": "agentMessage",
                        "text": "Guardé una propuesta: primero inspeccionar el comportamiento y después aplicar el cambio respaldado. La suposición sobre el repositorio queda explícita. No creé tareas ni inicié trabajo; falta tu aceptación.",
                    },
                },
            }
        )
        send(
            {
                "method": "turn/completed",
                "params": {
                    "threadId": native_thread_id,
                    "turn": {
                        "id": native_turn_id,
                        "status": "completed",
                        "error": None,
                    },
                },
            }
        )


for line in sys.stdin:
    message = json.loads(line)
    method = message.get("method")
    params = message.get("params", {})
    result = {}
    if method is None:
        next_tool(message["result"])
        continue
    if method == "account/login/start":
        result = {"type": "chatgptAuthTokens"}
    elif method == "account/read":
        result = {
            "account": {"type": "chatgpt"} if features.get("code_mode_host") else None
        }
    elif method == "config/read":
        result = {
            "config": {
                "features": features,
                "mcp_servers": {},
                "forced_login_method": "chatgpt",
                "model_provider": "openai",
                "chatgpt_base_url": "https://chatgpt.com/backend-api/",
                "web_search": config.get("web_search", "disabled"),
            }
        }
    elif method == "modelProvider/capabilities/read":
        result = {
            "webSearch": not Path("search-unavailable").exists(),
            "imageGeneration": False,
        }
    elif method == "model/list":
        result = {'data':[{'model':name,'displayName':name,'supportedReasoningEfforts':[{'reasoningEffort':effort} for effort in ('low','medium','high')]} for name in ('controlled-only','controlled-alt')],'nextCursor':None}
    elif method == "command/exec":
        output = subprocess.run(
            params["command"],
            cwd=params.get("cwd"),
            capture_output=True,
            text=True,
            timeout=8,
            check=False,
        )
        if params.get("streamStdoutStderr"):
            for stream in ("stdout", "stderr"):
                raw = getattr(output, stream).encode()
                if raw:
                    send(
                        {
                            "method": "command/exec/outputDelta",
                            "params": {
                                "processId": params["processId"],
                                "stream": stream,
                                "deltaBase64": base64.b64encode(raw).decode(),
                                "capReached": False,
                            },
                        }
                    )
            result = {"exitCode": output.returncode, "stdout": "", "stderr": ""}
        else:
            result = {
                "exitCode": output.returncode,
                "stdout": output.stdout,
                "stderr": output.stderr,
            }
    elif method == "thread/start":
        investigation_mode = any(
            tool["name"] == "researcher_investigation_summary"
            for tool in params["dynamicTools"]
        )
        planning_mode = any(
            tool["name"] == "researcher_plan_propose" for tool in params["dynamicTools"]
        )
        code_review_mode = any(
            tool["name"] == "researcher_code_review_propose"
            for tool in params["dynamicTools"]
        )
        if code_review_mode:
            native_thread_id, native_turn_id = "code-review-thread", "code-review-turn"
        development_mode = params.get("sandbox") == "workspace-write"
        review_mode = any(
            tool["name"] == "researcher_review_decide"
            for tool in params["dynamicTools"]
        )
        if scientific_mode and review_mode:
            native_thread_id, native_turn_id = (
                "science-review-thread",
                "science-review-turn",
            )
        Path("/home/actor/.codex/fixture-thread.json").write_text(
            json.dumps(
                {
                    "model": params["model"],
                    "cwd": params["cwd"],
                    "sandbox": params.get("sandbox"),
                    "catalog": params["dynamicTools"],
                    "developer_instructions": params.get("developerInstructions"),
                }
            )
        )
        result = {
            "thread": {"id": native_thread_id},
            "modelProvider": "openai",
            "model": params["model"],
            "cwd": params["cwd"],
        }
    elif method == "turn/start":
        Path("/home/actor/.codex/fixture-turn.json").write_text(json.dumps(params))
        if development_mode:
            initial = json.loads(params["input"][0]["text"])
            code_sources = [item for item in (initial.get('work_delivery') or {}).get('prerequisites', []) if item['kind']=='accepted_code_candidate']
            if code_sources:
                causal_task = code_sources[0]['task_id']
            prior = initial.get("prior_code")
            if prior is not None:
                assert prior["authority"] == "data_only"
                if "files" in prior["snapshot"]:
                    assert prior["snapshot"]["origin"]["kind"] in ("selected_legacy_worktree_files", "selected_private_copy_files")
                    prior_selected_files = prior["snapshot"]["files"]
                elif prior['snapshot']['origin']['kind']=='selected_legacy_branch':
                    assert prior['snapshot']['acquisition']=='captured'
                    assert prior['snapshot']['original_input'] is None
                    prior_selected_branch = True
                    prior_code_patch = prior['snapshot']['diff_base64']
                else:
                    assert prior["snapshot"]["origin"]["attempt_id"] != initial["scope"]["attempt_id"]
                    prior_code_patch = prior["snapshot"]["diff_base64"]
        result = {"turn": {"id": native_turn_id}}
    if "id" in message:
        send({"id": message["id"], "result": result})
    if method == "turn/start":
        if Path("/run/researcher-source/.ken/hold-turn").exists():
            Path("/home/actor/.codex/turn-entered").write_text("entered")
        else:
            next_tool()
