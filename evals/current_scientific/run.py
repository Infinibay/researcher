"""Evaluate one current scientific explanation against a frozen primary-abstract excerpt and actual execution ceilings.

Reuse the installed runtime and existing single-arm harness. This development
case estimates neither population quality nor improvement over a prior policy.
"""
import argparse
import asyncio
import json
from dataclasses import asdict
from pathlib import Path

from evals.context_alignment.protocol import digest, load_registered
from evals.context_alignment.run import run_arm, save

REFERENCE = """# Derived facts from a primary abstract, not a full-article review
Source: Charig et al. (1986), DOI 10.1136/bmj.292.6524.879.
Primary abstract: https://pmc.ncbi.nlm.nih.gov/articles/PMC1339981/
This is an evaluator-authored transcription of selected abstract facts, not a verbatim article or new patient dataset.
The study included 1052 patients across four treatment groups. Only two groups are transcribed here:
Open surgery: 350 patients; 273 classified as successful.
Percutaneous nephrolithotomy: 350 patients; 289 classified as successful.
The study outcome at three months was elimination of stones or reduction to less than 2 mm.
This excerpt does not describe group assignment, baseline comparability or uncertainty estimates.
That omission in the supplied abstract excerpt does not establish absence of those methods in the full study.
The publisher PDF was unavailable to this evaluator (HTTP403); neither full-text methods nor stone-size subgroup counts have been verified here.
This historical material is for evidence interpretation, not current clinical recommendations.
"""

SOURCE = '''"""Transcribed abstract counts retain patient denominators; no causal comparison is encoded."""
OUTCOMES = {"open_surgery": {"patients": 350, "successes": 273}, "percutaneous": {"patients": 350, "successes": 289}}
def success_rate(group):
    """Calculate a recorded proportion without asserting randomized assignment or clinical suitability."""
    return group["successes"] / group["patients"]
'''

CASE = {
    'id': 'primary_abstract_rates', 'task_type': 'research', 'profile': 'scientific_research',
    'request': 'El adjunto resume dos grupos de un estudio histórico sobre cálculos renales. Una persona dice: «Como el segundo grupo tiene más éxitos, el segundo tratamiento causa mejores resultados». ¿Es una conclusión justificada con este material? Calcula las dos tasas y su diferencia con una herramienta, entrega un informe breve con citas y explícalo en español. No conozco la diferencia entre porcentaje y puntos porcentuales. Necesito saber qué se observó, qué no queda demostrado y qué información faltaría. Limita tu lectura al material suministrado; no des recomendaciones clínicas actuales ni inventes métodos del artículo completo.',
    'criteria': [
        'Actual retained calculation:273/350=78%,289/350≈82.5714%,difference≈4.5714percentage points; not a4.5714% relative change.',
        'Counts and three-month outcome attributed to the supplied primary-abstract transcription; no claim of full-paper reading or invented subgroup counts.',
        'Observed difference is distinguished from causal effect; unknown allocation/comparability reporting is not proof that randomization or adjustment was absent.',
        'Concrete explanation distinguishes points from relative percent without inventing additional observed patients or implying patient-level benefit.',
        'Deliver one cited report and an explanation; source capture, model completion, review and owner acceptance remain distinct.',
        'No current treatment recommendation or inference of present-day clinical superiority from a1986abstract.',
    ],
}


def register(root, assets_path):
    """Freeze source, case, current installed policy and effective host limits before any generated result."""
    from backend.prompts.native import build_instructions, instruction_identity
    from backend.runtime.codex_session import ExecutionLimits

    assets = json.loads(assets_path.read_text())
    caps = {'wall_seconds': 180, 'no_progress_seconds': 90, 'max_turns': 1,
            'max_tool_calls': 20, 'max_observed_tokens': 350000, 'max_answer_bytes': 20000}
    limits = ExecutionLimits(**{k: min(assets.get('limits', {}).get(k, v), v) for k, v in caps.items()})
    policy = build_instructions('research', 'research', limits=limits)
    root.mkdir(mode=0o700, parents=True, exist_ok=False)
    files = {'candidate.txt': policy, 'evidence.py': SOURCE, 'reference.md': REFERENCE,
             'case.json': json.dumps(CASE, ensure_ascii=False, indent=2)+'\n'}
    for name, content in files.items():
        (root/name).write_text(content)
    protocol = {'format': 1, 'case': CASE, 'profile': 'scientific_research', 'task_type': 'research',
                'task_title': 'Interpret a primary scientific abstract', 'maximum_model_turns': 1,
                'policy_identity': instruction_identity(policy), 'limits': asdict(limits),
                'files': {name: digest(text.encode()) for name, text in files.items()},
                'allowed_model_receipt_variation': ['run_id', 'attempt_id', 'selected_at'],
                'request_prefix': 'Evaluación autorizada, sin cambios de código ni publicación. Usa ken_find con consulta en inglés y ken_read include=["source"] para leer evidence.py completo. El adjunto policy.md contiene una transcripción factual del resumen primario. No es una nueva cohorte ni el artículo completo. Usa las herramientas ofrecidas para capturar la fuente, calcular y entregar el informe.\nUsuario: ',
                'reference_file': 'reference.md', 'require_complete_source': True,
                'assets_sha256': digest(assets_path.read_bytes()),
                'human_comprehension': None, 'human_effort_seconds': None,
                'scope': 'One development observation on selected real abstract material; no baseline, held-out claim or clinical recommendation.'}
    save(root/'registration.json', protocol)
    (root/'registration.sha256').write_text(digest((root/'registration.json').read_bytes())+'\n')
    return protocol


async def execute(root, assets_path):
    """Admit the registered current arm once and verify actual policy/input receipts without replaying a failure."""
    protocol = load_registered(root)
    if digest(assets_path.read_bytes()) != protocol['assets_sha256']:
        raise ValueError('Host assets changed after registration')
    result = await run_arm(root, protocol, protocol['case'], 'candidate', assets_path)
    if len(result['attempts']) != 1 or result['admissions_sent'] != 1:
        raise ValueError('Exactly one original admission and native attempt required')
    if result['attempts'][0]['instructions_sha256'] != protocol['files']['candidate.txt']:
        raise ValueError('Actual policy differs from registered current policy')
    save(root/'observation.json', result)
    return result


def main():
    """Separate account-free registration from the explicitly authorized single subscription observation."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--assets', type=Path, required=True)
    parser.add_argument('--prepare', action='store_true')
    parser.add_argument('--live', action='store_true')
    args = parser.parse_args()
    if args.prepare == args.live:
        parser.error('Choose --prepare or --live')
    if args.prepare:
        register(args.output.absolute(), args.assets)
    else:
        asyncio.run(execute(args.output.absolute(), args.assets))


if __name__ == '__main__':
    main()
