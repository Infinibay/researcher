"""Capture current source metadata without serving requests, entering lifespan or invoking a model."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[3]
if '--installed' not in sys.argv:
    sys.path.insert(0, str(ROOT))


class NoIOClient:
    """Bind tool handlers while refusing any accidental attempt to perform HTTP IO."""

    async def request(self, *args, **kwargs):
        """Refuse handler execution during schema-only capture."""
        raise AssertionError("Metadata capture must not execute a tool")


def main():
    """Inspect actual policies, business schemas and owner OpenAPI with disposable metadata-only configuration."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--installed', action='store_true', help='Require the noneditable installed backend instead of the worktree')
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix='researcher-doc-metadata-') as directory:
        temporary = Path(directory)
        os.environ.update(INFINIBAY_DB=str(temporary/'not-created.db'), INFINIBAY_DATA=str(temporary/'data'), INFINIBAY_AUTH_DIR=str(temporary/'auth'), INFINIBAY_STATIC_DIR=str(ROOT/'frontend/dist'))
        os.environ.pop('INFINIBAY_RUNTIME_CONFIG', None)
        import backend
        if args.installed:
            assert Path(backend.__file__).resolve().is_relative_to(Path(sys.prefix).resolve())
        else:
            assert Path(backend.__file__).resolve() == ROOT/'backend/__init__.py'
        from backend.api.main import create_app
        from backend.api.local_access import LocalAccess
        from backend.prompts.native import build_instructions
        from backend.runtime.business_definitions import definitions
        from backend.runtime.business_mediation import ALL_BUSINESS_NAMES
        profiles = [('development','code'), ('code_review','review'), ('finding_review','review'), ('research','plan'), ('research','investigation'), ('research','review'), ('research','research')]
        policies = {kind+':'+task:build_instructions(kind,task) for kind,task in profiles}
        catalog = {tool.name:{'description':tool.description,'schema':tool.wire_schema(),'annotations':tool.annotations} for tool in definitions(NoIOClient(),names=ALL_BUSINESS_NAMES)}
        app = create_app(access=LocalAccess(pairing_key='synthetic-metadata-only-pairing-code-at-least32'))
        try:
            openapi = app.openapi()
        finally:
            app.state.live_grants.close()
            app.state.local_access.close()
        assert list(temporary.rglob('*')) == [], 'Metadata construction created unexpected storage'
        result = {'scope':'Actual source introspection only; no lifespan, requests, database, native actors, models or owner account','policies':policies,'business_catalog':catalog,'openapi':openapi,'backend_source':str(Path(backend.__file__).resolve())}
        with args.output.open('x') as stream:
            json.dump(result,stream,ensure_ascii=False,sort_keys=True,indent=2)
            stream.write('\n')
        print(json.dumps({'policies':len(policies),'tools':len(catalog),'schemas':len(openapi.get('components',{}).get('schemas',{})),'sha256':hashlib.sha256(args.output.read_bytes()).hexdigest()}))


if __name__ == '__main__':
    main()
