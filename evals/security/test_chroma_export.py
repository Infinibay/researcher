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
    (package / '__init__.py').write_text('''import atexit,json,os,socket,sqlite3,stat,sys,time
from pathlib import Path
class PersistentClient:
    def __init__(self, path, **kwargs):
        with sqlite3.connect(Path(path)/'chroma.sqlite3') as db:
            mode,secret,original,port=db.execute('select mode,secret,original,port from probe').fetchone()
        if mode=='hang':
            time.sleep(30)
            return
        if mode=='flood-log':
            for _ in range(32):print('x'*65536,flush=True)
        if mode=='fill-scratch':
            blocked={}
            for name in ('/outside-work', '/dev/shm/outside-work'):
                try:Path(name).write_bytes(b'escape')
                except OSError as error:blocked[name]=error.errno
                else:blocked[name]='unexpectedly_writable'
            count=0
            try:
                for count in range(64):
                    Path(path,str(count)).write_bytes(b'x'*65536)
            except OSError as error:
                blocked['scratch_error']=error.errno
            blocked['files_attempted']=count+1
            print('SCRATCH_PROBE:'+json.dumps(blocked),flush=True)
        if mode=='link-output':
            def replace_output():
                target=Path('/work/out/records.jsonl')
                try:
                    target.unlink()
                    target.symlink_to(secret)
                except OSError as error:
                    print('OUTPUT_REPLACEMENT_DENIED:'+str(error.errno),flush=True)
            atexit.register(replace_output)
        observations={'environment_secret':os.environ.get('OPENAI_API_KEY'),
                      'host_secret_visible':Path(secret).exists(),'original_visible':Path(original).exists(),
                      'inherited_input':sys.stdin.read(64),'inherited_directory_fds':[]}
        for descriptor in os.listdir('/proc/self/fd'):
            try:info=os.fstat(int(descriptor))
            except OSError:continue
            if stat.S_ISDIR(info.st_mode):observations['inherited_directory_fds'].append(int(descriptor))
        try:
            with socket.create_connection(('127.0.0.1',port),timeout=.2):pass
            observations['host_network_reachable']=True
        except OSError:observations['host_network_reachable']=False
        print('READER_PROBE:'+json.dumps(observations),flush=True)
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
    observed=json.loads(next(line.removeprefix('READER_PROBE:') for line in (output/'reader.log').read_text().splitlines() if line.startswith('READER_PROBE:')))
    assert observed == {'environment_secret':None,'host_secret_visible':False,'original_visible':False,'host_network_reachable':False,'inherited_input':'','inherited_directory_fds':[]}
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
    assert result.returncode==0,result.stderr
    assert 'OUTPUT_REPLACEMENT_DENIED:16' in (output/'reader.log').read_text()
    assert not (output/'records.jsonl').is_symlink()
    assert (output/'records.jsonl').read_bytes()==b''
    assert secret.read_text()=='SYNTHETIC_OWNER_SECRET'


@pytest.mark.enable_socket
def test_reader_scratch_has_aggregate_capacity_and_cannot_write_elsewhere(reader_fixture, tmp_path):
    """Many small writes share a real tmpfs ceiling; writable root or shared-memory mounts cannot bypass it."""
    python,source,_secret=reader_fixture
    with sqlite3.connect(source/'chroma.sqlite3') as db:db.execute("update probe set mode='fill-scratch'")
    output=tmp_path/'bounded-export'
    result=subprocess.run([str(python),'-I',str(SCRIPT),'--source',str(source),'--output',str(output),
                           '--scratch-bytes',str(1024**2)],capture_output=True,text=True,timeout=15)
    assert result.returncode==0,result.stderr
    observed=json.loads(next(line.removeprefix('SCRATCH_PROBE:') for line in (output/'reader.log').read_text().splitlines() if line.startswith('SCRATCH_PROBE:')))
    assert observed['scratch_error']==28 and observed['files_attempted']<64
    assert observed['/outside-work']==30 and observed['/dev/shm/outside-work']==30
    manifest=json.loads((output/'manifest.json').read_text())
    assert manifest['reader_isolation']['scratch_capacity_bytes']==1024**2
    assert not (output/'reader').exists()


@pytest.mark.enable_socket
def test_reader_log_is_drained_without_unbounded_disk_growth(reader_fixture, tmp_path):
    """A noisy dependency cannot block on its pipe or grow the retained diagnostic beyond64KiB."""
    python,source,_secret=reader_fixture
    with sqlite3.connect(source/'chroma.sqlite3') as db:db.execute("update probe set mode='flood-log'")
    output=tmp_path/'noisy-export'
    result=subprocess.run([str(python),'-I',str(SCRIPT),'--source',str(source),'--output',str(output)],
                          capture_output=True,text=True,timeout=15)
    assert result.returncode==0,result.stderr
    assert (output/'reader.log').stat().st_size==65536
    assert json.loads((output/'manifest.json').read_text())['reader_isolation']['log_truncated'] is True


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
