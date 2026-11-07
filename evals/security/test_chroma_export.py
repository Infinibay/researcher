"""Exercise the actual exporter boundary with hostile reader behavior and real persistent Chroma data."""

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import socket
import sqlite3
import subprocess
import sys
import time
import venv

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / 'scripts/export_legacy_chroma.py'


@pytest.fixture
def reader_fixture(tmp_path):
    """Install a controlled external reader that probes only synthetic sentinels, never real credentials."""
    environment = tmp_path / 'reader-env'
    venv.EnvBuilder(with_pip=False, symlinks=True).create(environment)
    site = next(environment.glob('lib/python*/site-packages'))
    package = site / 'chromadb'; package.mkdir()
    (package / 'config.py').write_text('class Settings:\n    def __init__(self, **kwargs): pass\n')
    (package / '__init__.py').write_text('''import atexit,json,os,socket,sqlite3,sys,time
from pathlib import Path
class PersistentClient:
    def __init__(self, path, **kwargs):
        with sqlite3.connect(Path(path)/'chroma.sqlite3') as db:
            mode,secret,original,port=db.execute('select mode,secret,original,port from probe').fetchone()
        if mode=='hang':
            time.sleep(30)
            return
        if mode=='link-output':
            def replace_output():
                target=Path('/work/out/records.jsonl')
                target.unlink()
                target.symlink_to(secret)
            atexit.register(replace_output)
        observations={'environment_secret':os.environ.get('OPENAI_API_KEY'),
                      'host_secret_visible':Path(secret).exists(),'original_visible':Path(original).exists(),
                      'inherited_input':sys.stdin.read(64)}
        try:
            with socket.create_connection(('127.0.0.1',port),timeout=.2):pass
            observations['host_network_reachable']=True
        except OSError:observations['host_network_reachable']=False
        Path(path,'probe.json').write_text(json.dumps(observations))
    def list_collections(self):return []
''')
    metadata = site / 'chromadb-1.5.9.dist-info'; metadata.mkdir()
    (metadata / 'METADATA').write_text('Metadata-Version: 2.1\nName: chromadb\nVersion: 1.5.9\n')
    source = tmp_path / 'original'; source.mkdir()
    secret = tmp_path / 'owner-secret.txt'; secret.write_text('SYNTHETIC_OWNER_SECRET')
    with socket.socket() as listener:
        listener.bind(('127.0.0.1', 0));listener.listen()
        with sqlite3.connect(source / 'chroma.sqlite3') as db:
            db.execute('create table probe(mode text,secret text,original text,port integer)')
            db.execute('insert into probe values(?,?,?,?)', ('probe',str(secret),str(source),listener.getsockname()[1]))
        yield environment/'bin/python', source, secret


@pytest.mark.enable_socket
def test_exported_reader_cannot_observe_original_credentials_or_host_network(reader_fixture, tmp_path):
    """Removing the namespace or mounting the host root would expose these sentinels to the dependency."""
    python, source, secret = reader_fixture
    before = hashlib.sha256((source/'chroma.sqlite3').read_bytes()).hexdigest()
    output = tmp_path/'export'
    result = subprocess.run([str(python),'-I',str(SCRIPT),'--source',str(source),'--output',str(output)],
                            env={**os.environ,'OPENAI_API_KEY':'SYNTHETIC_ENV_SECRET'},input='SYNTHETIC_STDIN_SECRET',capture_output=True,text=True,timeout=15)
    assert result.returncode == 0,result.stderr
    observed=json.loads((output/'reader/probe.json').read_text())
    assert observed == {'environment_secret':None,'host_secret_visible':False,'original_visible':False,'host_network_reachable':False,'inherited_input':''}
    assert hashlib.sha256((source/'chroma.sqlite3').read_bytes()).hexdigest()==before
    assert secret.read_text()=='SYNTHETIC_OWNER_SECRET'
    manifest=json.loads((output/'manifest.json').read_text())
    assert manifest['reader_isolation']['network']=='none'
    assert manifest['records']['count']==0


@pytest.mark.enable_socket
def test_blocked_reader_times_out_without_publishing_a_complete_manifest(reader_fixture, tmp_path):
    """A dependency stuck inside client construction cannot defeat the parent reader deadline."""
    python,source,_secret=reader_fixture
    with sqlite3.connect(source/'chroma.sqlite3') as db:db.execute("update probe set mode='hang'")
    output=tmp_path/'partial';started=time.monotonic()
    result=subprocess.run([str(python),'-I',str(SCRIPT),'--source',str(source),'--output',str(output),'--timeout','1'],
                          capture_output=True,text=True,timeout=8)
    assert result.returncode!=0 and time.monotonic()-started<5
    assert not (output/'manifest.json').exists()
    assert (output/'source/chroma.sqlite3').is_file()


@pytest.mark.enable_socket
def test_dependency_output_symlink_is_not_followed_by_parent(reader_fixture, tmp_path):
    """A dependency cannot use a post-exit output link to make the trusted parent read a host file."""
    python,source,secret=reader_fixture
    with sqlite3.connect(source/'chroma.sqlite3') as db:db.execute("update probe set mode='link-output'")
    output=tmp_path/'link-export'
    result=subprocess.run([str(python),'-I',str(SCRIPT),'--source',str(source),'--output',str(output)],
                          capture_output=True,text=True,timeout=10)
    assert result.returncode!=0 and 'bounded regular file' in result.stderr
    assert not (output/'manifest.json').exists()
    assert secret.read_text()=='SYNTHETIC_OWNER_SECRET'


@pytest.mark.enable_socket
def test_internal_worker_entry_refuses_accidental_unsandboxed_invocation(reader_fixture, tmp_path):
    """The internal subprocess entry is not a public escape hatch around the normal export boundary."""
    python,source,_secret=reader_fixture
    output=tmp_path/'direct-worker';output.mkdir()
    result=subprocess.run([str(python),'-I',str(SCRIPT),'--reader-worker','--source',str(source),'--output',str(output)],
                          capture_output=True,text=True,timeout=10)
    assert result.returncode!=0 and 'namespace' in result.stderr
    assert not (source/'probe.json').exists()


def test_missing_isolation_refuses_before_reading_or_creating_storage(tmp_path, monkeypatch):
    """An unavailable sandbox must never cause a transparent unsandboxed compatibility fallback."""
    spec=importlib.util.spec_from_file_location('exporter_under_test',SCRIPT)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    monkeypatch.setattr(module.importlib.metadata,'version',lambda name:'1.5.9')
    monkeypatch.setattr(module.shutil,'which',lambda name:None)
    with pytest.raises(ValueError,match='bubblewrap'):
        module.export(tmp_path/'missing-source',tmp_path/'must-not-exist')
    assert not (tmp_path/'must-not-exist').exists()


def test_real_chroma_export_retains_all_pages_and_metadata(tmp_path):
    """A real pinned reader exports 105 records without changing original data or generating embeddings."""
    from evals.operation.legacy_import import CHROMA_FIXTURE

    python=Path(os.environ['RESEARCHER_LEGACY_PYTHON'])
    source=tmp_path/'original';output=tmp_path/'export'
    seeded=subprocess.run([str(python),'-I','-c',CHROMA_FIXTURE,str(source)],capture_output=True,text=True,timeout=20)
    assert seeded.returncode==0,seeded.stderr
    before={p.relative_to(source).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in source.rglob('*') if p.is_file()}
    result=subprocess.run([str(python),'-I',str(SCRIPT),'--source',str(source),'--output',str(output)],capture_output=True,text=True,timeout=30)
    assert result.returncode==0,result.stderr
    manifest=json.loads((output/'manifest.json').read_text())
    assert manifest['reader_isolation']['network']=='none'
    rows=[json.loads(line) for line in (output/'records.jsonl').read_text().splitlines()]
    assert len(rows)==105 and manifest['records']['count']==105
    assert len({(r['collection'],r['id']) for r in rows})==105
    assert next(r for r in rows if r['id']=='p1-c37')['document']=='Fragmento histórico 37: 137 + 63 = 200.'
    assert next(r for r in rows if r['id']=='metadata-only')['document'] is None
    assert next(r for r in rows if r['id']=='p1-c37')['metadata']['project_id']==202
    after={p.relative_to(source).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in source.rglob('*') if p.is_file()}
    assert after==before
