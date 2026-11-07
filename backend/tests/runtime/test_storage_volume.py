"""Exercise storage admission and host wiring; real capacity exhaustion lives in the VM evaluation."""

import json
from pathlib import Path

import pytest

from backend.runtime.contracts import RunConflict
from backend.runtime.storage_volume import StorageVolume
from backend.tests.runtime.test_host_installation import host_assets  # noqa: F401
from backend.tests.runtime.test_installation_backup import installation  # noqa: F401


@pytest.fixture
def observed_volume(tmp_path, monkeypatch):
    """Supply explicit synthetic observations only for host composition, never a kernel-quota claim."""
    import backend.runtime.storage_volume as module

    root = tmp_path / 'volume'
    root.mkdir(mode=0o700)
    info = root.stat()
    policy = {'mount': str(root), 'max_bytes': 64 * 1024**2, 'admission_free_bytes': 1024**2}
    receipt = {'policy': policy, 'device': info.st_dev, 'inode': info.st_ino,
               'fsid': 123, 'device_bytes': policy['max_bytes'],
               'filesystem_bytes': 60 * 1024**2, 'inodes': 16384}
    observation = {'available_bytes': 32 * 1024**2, 'available_inodes': 10000}
    monkeypatch.setattr(module, '_observe', lambda policy: (dict(receipt), dict(observation)))
    return root, policy, receipt, observation


def test_ordinary_directory_is_not_a_durable_quota(tmp_path):
    """An existing host directory must not become 'bounded' through a configured number alone."""
    with pytest.raises(ValueError, match='mount is missing'):
        StorageVolume.capture({'mount': str(tmp_path), 'max_bytes': 64 * 1024**2,
                               'admission_free_bytes': 1024**2})


def test_bound_host_records_volume_and_rechecks_on_open(observed_volume, host_assets):
    """Host setup persists the original volume; replacement is refused before normal reopening."""
    from backend.runtime.host_installation import initialize_host, host_environment, inspect_host

    mount, policy, receipt, _ = observed_volume
    root = mount / 'installation'
    result = initialize_host(root, witness_dir=mount/'witness', assets={**host_assets, 'storage': policy})
    assert result['storage']['enforced'] is True
    assert inspect_host(root)['storage']['enforced'] is True
    config = json.loads((root/'runtime.json').read_text())
    assert config['storage_receipt'] == receipt
    assert host_environment(root)['INFINIBAY_DB'] == str(root/'source.db')
    receipt['fsid'] += 1
    with pytest.raises(ValueError, match='Original storage'):
        host_environment(root)
    assert (root/'source.db').is_file()


def test_bound_host_rejects_uncovered_witness_before_writes(observed_volume, host_assets, tmp_path):
    """Independent authority storage must also fit within the selected aggregate boundary."""
    from backend.runtime.host_installation import initialize_host

    mount, policy, _, _ = observed_volume
    root = mount/'installation'
    with pytest.raises(ValueError, match='Mutable host data'):
        initialize_host(root, witness_dir=tmp_path/'outside', assets={**host_assets, 'storage': policy})
    assert not root.exists()


def test_low_space_rejects_new_work_but_keeps_existing_data_readable(observed_volume):
    """Admission headroom is distinct from recovery/read access and never deletes retained work."""
    mount, _, receipt, available = observed_volume
    retained = mount/'unfinished.txt'
    retained.write_text('useful uncommitted changes')
    volume = StorageVolume(receipt)
    available['available_bytes'] = 0
    assert volume.check([retained])['available_bytes'] == 0
    with pytest.raises(RunConflict, match='conserva el trabajo'):
        volume.check([retained], admission=True)
    assert retained.read_text() == 'useful uncommitted changes'


def test_storage_guard_rejects_before_admission():
    """Reject new work through the service admission port before any native execution."""
    from backend.runtime.service import RuntimeService

    service = object.__new__(RuntimeService)
    service._lock_fd, service._closing = 1, False

    def exhausted():
        """Represent a failed storage observation at the existing admission boundary."""
        raise RunConflict('storage exhausted')

    service.storage_guard = exhausted
    with pytest.raises(RunConflict, match='storage exhausted'):
        service._accepting()
    service._accepting(new_work=False)


def test_symlink_cannot_redirect_mutable_root(observed_volume, tmp_path):
    """A lexical child of the selected volume is insufficient when its resolved storage escapes."""
    mount, _, receipt, _ = observed_volume
    (mount/'redirected').symlink_to(tmp_path)
    with pytest.raises(ValueError, match='Mutable host data'):
        StorageVolume(receipt).check([mount/'redirected'/'new'])


@pytest.mark.parametrize('field,value', [('max_bytes', True), ('max_bytes', 1024),
                                        ('admission_free_bytes', 0), ('admission_free_bytes', True)])
def test_invalid_capacity_policy_is_not_coerced(tmp_path, field, value):
    """Reject false ceilings before any volume observation or write."""
    policy = {'mount': str(tmp_path), 'max_bytes': 64 * 1024**2, 'admission_free_bytes': 1024**2}
    with pytest.raises(ValueError):
        StorageVolume.capture({**policy, field: value})


def test_configured_factory_keeps_storage_admission_guard(observed_volume, host_assets, monkeypatch):
    """The real serving composition carries the volume gate into its runtime service."""
    from backend.api import config as api_config
    from backend.api.main import create_app
    from backend.api.runtime_dependencies import configured_runtime
    from backend.runtime.host_installation import initialize_host

    mount, policy, _, available = observed_volume
    root = mount/'installation'
    prepared = initialize_host(root, witness_dir=mount/'witness', assets={**host_assets, 'storage': policy})
    for key, value in prepared['environment'].items():
        monkeypatch.setenv(key, value)
    monkeypatch.setattr(api_config, 'UPLOAD_DIR', str(root/'uploads'))
    app = create_app()
    service = configured_runtime(app.state.live_grants, app=app)
    service.storage_guard()
    available['available_bytes'] = 0
    with pytest.raises(RunConflict, match='espacio'):
        service.storage_guard()


@pytest.mark.asyncio
async def test_startup_checks_storage_before_logging_migrations_or_pairing(observed_volume, host_assets, monkeypatch, tmp_path):
    """A redirected mutable root must fail before any ordinary startup writer runs."""
    from backend.api import config as api_config
    from backend.api import run as api_run
    from backend.api.main import create_app, lifespan
    from backend.runtime.host_installation import initialize_host

    mount, policy, _, _ = observed_volume
    root = mount/'installation'
    prepared = initialize_host(root, witness_dir=mount/'witness', assets={**host_assets, 'storage': policy})
    for key, value in prepared['environment'].items():
        monkeypatch.setenv(key, value)
    monkeypatch.setattr(api_config, 'UPLOAD_DIR', str(root/'uploads'))
    monkeypatch.setenv('INFINIBAY_DATA', str(tmp_path/'outside-logs'))
    calls = []
    monkeypatch.setattr(api_run, 'setup_file_logging', lambda: calls.append('logging'))
    with pytest.raises(ValueError, match='Mutable host data'):
        async with lifespan(create_app()):
            raise AssertionError('Invalid storage began serving')
    assert calls == []
    assert list((root/'auth').iterdir()) == []
    assert not (tmp_path/'outside-logs').exists()


def test_missing_receipt_never_downgrades_a_configured_bound(observed_volume):
    """Missing enrollment evidence is an error even when the policy names a plausible volume."""
    from backend.runtime.storage_volume import configured_storage

    _, policy, _, _ = observed_volume
    with pytest.raises(ValueError, match='receipt'):
        configured_storage({'storage': policy})
    assert configured_storage({}) is None


@pytest.mark.parametrize('obstacle',[None,'outside_witness','no_space'])
def test_restore_enrollment_captures_bound_before_publishing(observed_volume,host_assets,installation,tmp_path,obstacle):
    """Move copied data into a selected volume, rejecting uncovered or exhausted storage before new authority or history writes."""
    from backend.runtime.installation_backup import backup_installation
    from backend.runtime.installation_restore import restore_installation
    from backend.runtime.restored_enrollment import enroll_restored_host
    from backend.runtime.host_installation import host_environment

    mount,policy,receipt,available=observed_volume
    original,_=installation
    backup=tmp_path/'migration-backup';backup_installation(original,backup)
    restored=mount/'restored';restore_installation(backup,restored)
    before=(restored/'source.db').read_bytes()
    witness=(tmp_path if obstacle=='outside_witness' else mount)/'new-witness'
    if obstacle=='no_space':available['available_bytes']=0
    if obstacle is not None:
        with pytest.raises((ValueError,RunConflict)):
            enroll_restored_host(restored,witness_dir=witness,assets={**host_assets,'storage':policy})
        assert not witness.exists() and not (restored/'authority').exists()
        assert (restored/'source.db').read_bytes()==before
        assert json.loads((restored/'installation.json').read_text())['status']=='restored_pending_enrollment'
        return
    result=enroll_restored_host(restored,witness_dir=witness,assets={**host_assets,'storage':policy})
    assert result['storage']['enforced'] is True
    config=json.loads((restored/'runtime.json').read_text())
    assert config['storage_receipt']==receipt
    assert host_environment(restored)['INFINIBAY_DB']==str(restored/'source.db')
    receipt['fsid']+=1
    with pytest.raises(ValueError,match='Original storage'):
        host_environment(restored)


@pytest.mark.asyncio
async def test_live_stop_bypasses_exhausted_admission_margin(service_setup):
    """An already running peer still receives Stop when subsequent storage admission is rejected."""
    import asyncio
    from backend.tests.runtime.test_runtime_service import ControlledInference, coordinator

    native = ControlledInference(service_setup)
    service = coordinator(service_setup, native)
    async with service:
        run = await service.submit(service_setup.c.spec)
        await asyncio.wait_for(native.started.wait(), 2)

        def exhausted():
            """Refuse every new dispatch after the original run has started."""
            raise RunConflict('storage exhausted')

        service.storage_guard = exhausted
        await service.stop(101, run.run_id)
        await service.wait(run.run_id)
        assert native.interrupted.is_set()
        assert native.closed.is_set()
        assert service_setup.c.store.get(101, run.run_id).status == 'cancelled'
