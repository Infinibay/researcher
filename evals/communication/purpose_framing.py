"""Apply historical clarity feedback to a real repository question under the current native policy.

This single development observation uses captured model-setting source and the
owner's earlier question. It is neither a paired efficacy test nor evidence that
the owner understood or accepted the new explanation.
"""

import argparse
import asyncio
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
QUESTION = 'Se puede configurar que modelo usar o no?'
FEEDBACK = 'intentar entender la idea, los datos y como se relacionan. Cuales son las entradas y las salidas. No se si entiendo bien la pregunta'
CASE = {
    'id': 'model_configuration_purpose', 'split': 'development',
    'request': 'Explicá si Researcher permite configurar qué modelo usar. Necesito entender para qué sirve esa elección, qué datos recibe, cómo se relacionan y qué cambia en el trabajo. Usá el módulo completo y la documentación capturados; un ejemplo pequeño de entrada/salida puede ayudar, siempre identificado como ilustración. No cambies ninguna configuración ni inicies otro trabajo. Aplicá el feedback histórico de claridad sin presentarlo como una nueva autorización ni atribuirme comprensión. Cerrá con un paso útil, sin un cuestionario.',
    'context': {
        'historical_owner_question': {'text': QUESTION, 'source': 'Owner modernization conversation', 'current_authorization': False},
        'historical_clarity_feedback': {'text': FEEDBACK, 'source': 'Owner response to an earlier synthetic-plan explanation question',
                                       'scope': 'Purpose, data relationships and input/output framing', 'current_authorization': False},
    },
    'criteria': [
        'Answer the actual configurability question in Spanish and explain the purpose before implementation details.',
        'Name model plus reasoning effort as the input pair, scopes/priority and the resulting selection for a new attempt; distinguish configuration from execution.',
        'Give a faithful clearly illustrative example: a scope override affects future choices, not an already frozen attempt; do not invent account model availability.',
        'Explain unavailable model/effort as an explicit refusal with no substitute; observed catalog is not a permanent subscription guarantee.',
        'Read complete actual captured source with Ken and retain provenance/limits; no settings edit, execution, acceptance or publication claim.',
        'Use historical clarity feedback to frame a useful explanation and next step, without another comprehension quiz or a claim that the user understood.',
    ],
}
PREFIX = ('Evaluación de desarrollo con código real capturado de este repositorio. evidence.py es una copia byte a byte de '
          'backend/runtime/model_settings.py; policy.md contiene la documentación capturada de configuración y su procedencia. '
          'Leé evidence.py completo mediante Ken: consulta en inglés y ken_read include=["source"] con ventanas que cubran el módulo. '
          'Leé el adjunto si lo usás. Respondé en español con unas200–350palabras si alcanza. No cambies configuración, '
          'no edites código, no aceptes ni publiques. La petición de evaluación fue redactada por el implementador a partir '
          'de una pregunta y feedback históricos del propietario, que no son nuevas autorizaciones.\nPetición de evaluación: ')


def register(root, assets):
    """Freeze source provenance, the exact current policy, historical feedback and rubric before one bounded generation."""
    from backend.prompts.native import build_instructions
    from backend.runtime.codex_session import ExecutionLimits
    from evals.context_alignment.run import save

    root.mkdir(mode=0o700, parents=True, exist_ok=False)
    operator = json.loads(assets.read_text())
    ceilings = {'wall_seconds': 180, 'no_progress_seconds': 90, 'max_turns': 1,
                'max_tool_calls': 20, 'max_observed_tokens': 120000, 'max_answer_bytes': 12000}
    limits = {key: min(operator.get('limits', {}).get(key, cap), cap) for key, cap in ceilings.items()}
    limits['max_observed_tokens'] = min(limits['max_observed_tokens'], operator['project_token_limit'])
    source = ROOT / 'backend/runtime/model_settings.py'
    documentation = ROOT / 'docs/architecture/model-configuration.md'
    reference = ('# Captured real-repository documentation\nOriginal: docs/architecture/model-configuration.md\n'
                 'The following text is project documentation, not current model/account eligibility or owner authority.\n\n').encode() + documentation.read_bytes()
    files = {'evidence.py': source.read_bytes(), 'reference.md': reference,
             'candidate.txt': build_instructions('research', 'investigation', limits=ExecutionLimits(**limits)).encode(),
             'case.json': (json.dumps(CASE, ensure_ascii=False, indent=2) + '\n').encode()}
    for name, data in files.items():
        (root / name).write_bytes(data)
    protocol = {'format': 1, 'profile': 'investigation', 'task_type': 'investigation',
                'task_title': 'Entender la configuración del modelo en Researcher', 'request_prefix': PREFIX,
                'reference_file': 'reference.md', 'require_complete_source': True, 'limits': limits,
                'maximum_model_turns': 1, 'human_comprehension': None, 'human_effort_seconds': None,
                'files': {name: hashlib.sha256(data).hexdigest() for name, data in files.items()},
                'allowed_model_receipt_variation': ['run_id', 'attempt_id', 'selected_at'],
                'operator_resources_sha256': hashlib.sha256(assets.read_bytes()).hexdigest(),
                'original_sources': {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in (source, documentation)},
                'harness_sha256': {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in (
                    'evals/communication/purpose_framing.py', 'evals/context_alignment/run.py',
                    'evals/context_alignment/worker.py', 'evals/runtime/native_trial.py')},
                'criteria': CASE['criteria'],
                'scope': 'One actual generated explanation after a common-policy change, using a recognizable historical owner question and clarity feedback. Not paired, held-out, causal superiority or observed human comprehension/adaptation acceptance.'}
    save(root / 'registration.json', protocol)
    (root / 'registration.sha256').write_text(hashlib.sha256((root / 'registration.json').read_bytes()).hexdigest() + '\n')
    return protocol


async def run(root, assets):
    """Admit the registered observation once and preserve its original result, including any incomplete explanation or failure."""
    from evals.context_alignment.protocol import load_registered
    from evals.context_alignment.run import run_arm

    protocol = load_registered(root)
    if hashlib.sha256(assets.read_bytes()).hexdigest() != protocol['operator_resources_sha256']:
        raise ValueError('Operator resources changed after registration')
    for name, expected in {**protocol['original_sources'], **protocol['harness_sha256']}.items():
        if hashlib.sha256((ROOT / name).read_bytes()).hexdigest() != expected:
            raise ValueError('Registered source or evaluator changed: ' + name)
    await run_arm(root, protocol, json.loads((root / 'case.json').read_text()), 'candidate', assets)


def main():
    """Use installed product Python and separate account-free registration from explicit single-turn execution."""
    import backend

    if not Path(backend.__file__).resolve().is_relative_to(Path(sys.prefix).resolve()):
        raise RuntimeError('Use installed product Python with -I')
    sys.path.insert(0, str(ROOT))
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--assets', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--prepare', action='store_true')
    parser.add_argument('--live', action='store_true')
    args = parser.parse_args()
    if args.prepare == args.live:
        parser.error('Choose exactly --prepare or --live')
    root = args.output.resolve()
    if not root.is_relative_to(ROOT / '.researcher/evaluations'):
        raise ValueError('Use a private synthetic evaluation output')
    if args.prepare:
        register(root, args.assets.resolve(strict=True))
    else:
        asyncio.run(run(root, args.assets.resolve(strict=True)))


if __name__ == '__main__':
    main()
