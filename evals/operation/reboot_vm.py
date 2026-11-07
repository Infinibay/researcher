"""Build one disposable VM and verify recovery across an actual guest kernel restart.

Requires local QEMU/KVM, a compatible Linux kernel with built-in ext4/virtio, the
installed product environment, and already prepared public native/Ken assets.
Only a NEW output directory is accepted. No network card or real account enters
the VM. Failures retain its disk and serial log; this program never retries a VM.
"""

import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time


def copy_file(source, target):
    """Copy a trusted local asset's bytes into the new fixture, dereferencing asset symlinks."""
    target.parent.mkdir(parents=True,exist_ok=True)
    shutil.copy2(source,target,follow_symlinks=True)


def copy_tree(source, target):
    """Copy a trusted environment without interpreter caches, preserving virtualenv symlinks."""
    shutil.copytree(source,target,symlinks=True,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))


def libraries(root, trees, executables):
    """Copy the host dynamic-loader closure needed by the portable interpreter and installed extensions."""
    candidates = set(executables)
    for tree in trees:
        candidates.update(tree.rglob('*.so'))
        candidates.update(tree.rglob('*.so.*'))
    copied = set()
    for source in sorted(candidates):
        if not source.is_file():
            continue
        with source.open('rb') as stream:
            if stream.read(4) != b'\x7fELF':
                continue
        result = subprocess.run(['ldd',str(source)],env={**os.environ,'LD_LIBRARY_PATH':str(source.parent)},
                                capture_output=True,text=True,timeout=10,check=False)
        if 'not found' in result.stdout:
            raise RuntimeError(f'Missing local dynamic library for {source.name}')
        for name in re.findall(r'(/[^\s()]+)',result.stdout):
            library = Path(name)
            if any(library.resolve().is_relative_to(tree.resolve()) for tree in trees):
                continue
            if library.is_file() and library not in copied:
                copy_file(library,root/library.relative_to('/'))
                copied.add(library)
    return len(copied)


def prepare(args, output):
    """Build a private initramfs and persistent synthetic disk from explicitly selected installed assets."""
    from backend.runtime.ken_worker import KenInstallation

    assets = json.loads(args.assets.read_text())
    installation = KenInstallation.inspect(Path(assets['ken_command']))
    root, payload = output/'initramfs', output/'payload'
    root.mkdir();payload.mkdir()
    for directory in ('usr/lib','usr/bin','etc/ssl/certs','proc','sys','dev','state','tmp'):
        (root/directory).mkdir(parents=True,exist_ok=True)
    for name,target in [('lib','usr/lib'),('lib64','usr/lib'),('bin','usr/bin'),('usr/lib64','lib')]:
        (root/name).symlink_to(target,target_is_directory=True)
    base = Path(sys.base_prefix).resolve(strict=True)
    copy_tree(base,root/'python')
    aliases = {base,installation.python_root}
    for environment in (args.runtime_env,installation.tool_root):
        values = dict(line.split(' = ',1) for line in (environment/'pyvenv.cfg').read_text().splitlines() if ' = ' in line)
        aliases.add(Path(values['home']).parent)
    for alias in aliases:
        destination = root/alias.relative_to('/')
        destination.parent.mkdir(parents=True,exist_ok=True)
        destination.symlink_to('/python',target_is_directory=True)
    copy_tree(args.runtime_env,payload/'env')
    copy_tree(installation.tool_root,payload/'ken')
    for key,name in [('codex_binary','codex'),('code_mode_host','codex-code-mode-host')]:
        copy_file(Path(assets[key]),payload/'native'/name)
    copied_models = 0
    for model in installation.assets:
        relative = Path('models--'+model['model_id'].replace('/','--'))/'snapshots'/model['revision']
        for name,expected in model['artifacts'].items():
            source = Path(assets['model_cache'])/relative/name
            target = payload/'models'/relative/name
            copy_file(source,target)
            with target.open('rb') as stream:
                if target.stat().st_size != expected['bytes'] or hashlib.file_digest(stream,'sha256').hexdigest() != expected['sha256']:
                    raise ValueError('Public Ken model bytes differ from the published manifest')
            copied_models += 1
    for name in ('reboot_guest.py','host_smoke.py'):
        copy_file(Path(__file__).with_name(name),payload/'eval'/name)
    copy_file(Path(__file__).with_name('reboot_guest_init.py'),root/'guest_init.py')
    copy_file(Path(__file__).with_name('reboot_guest_boot.sh'),root/'init')
    (root/'init').chmod(0o755)
    (root/'RESEARCHER_DISPOSABLE_VM').write_text('owned evaluation fixture\n')
    (root/'etc/passwd').write_text('root:x:0:0:root:/root:/bin/sh\nfixture:x:1000:1000:fixture:/home/fixture:/bin/sh\n')
    (root/'etc/group').write_text('root:x:0:\nfixture:x:1000:\n')
    (root/'etc/resolv.conf').write_text('nameserver 1.1.1.1\n')
    copy_file(Path('/etc/ssl/certs/ca-certificates.crt'),root/'etc/ssl/certs/ca-certificates.crt')
    tools = [Path(shutil.which(name)) for name in ('git','bwrap','sh','mount')]
    for tool in tools:
        copy_file(tool,root/'usr/bin'/tool.name)
    count = libraries(root,[base,args.runtime_env,installation.tool_root],[base/'bin/python3.12',*tools])
    token = payload/'synthetic-account.json'
    token.write_text(json.dumps({'auth_mode':'chatgpt','tokens':{'access_token':'fixture.header.signature','account_id':'fixture-only'}}))
    token.chmod(0o600)
    config = {'model':'controlled-no-inference','codex_binary':'/state/native/codex',
              'code_mode_host':'/state/native/codex-code-mode-host','ken_command':'/state/ken/bin/ken',
              'model_cache':'/state/models','token_file':'/state/synthetic-account.json',
              'cgroup_parent':'/sys/fs/cgroup/researcher','project_turn_limit':1,'project_token_limit':1}
    (payload/'assets.json').write_text(json.dumps(config))
    (payload/'eval-mode.json').write_text(json.dumps({'active_command': args.active_command}))
    disk = output/'disk.raw'
    with disk.open('xb') as stream:
        stream.truncate(4*1024**3)
    subprocess.run(['mkfs.ext4','-q','-F','-E','lazy_itable_init=0,lazy_journal_init=0','-d',str(payload),str(disk)],check=True,timeout=180)
    names = ['.']+[str(path.relative_to(root)) for path in sorted(root.rglob('*'))]
    listing = output/'initramfs-files.txt'
    listing.write_text('\n'.join(names)+'\n')
    with listing.open('rb') as entries, (output/'initramfs.cpio.gz').open('wb') as raw, gzip.GzipFile(fileobj=raw,mode='wb',compresslevel=1) as compressed:
        with subprocess.Popen(['cpio','-o','-H','newc','--quiet','--owner=0:0'],cwd=root,stdin=entries,stdout=subprocess.PIPE) as process:
            shutil.copyfileobj(process.stdout,compressed)
            if process.wait(timeout=30):
                raise RuntimeError('Could not build the guest initramfs')
    return {'ken_model_files':copied_models,'host_dynamic_libraries':count,
            'real_account_copied':False,'installed_environment':str(args.runtime_env),
            'kernel_sha256':hashlib.sha256(args.kernel.read_bytes()).hexdigest()}


def run(args, output):
    """Own one QEMU process across both boots and preserve the original outcome without replay."""
    prefix = args.qemu.parent.parent
    command = [str(args.qemu),'-L',str(prefix/'share/qemu'),'-no-user-config','-nodefaults',
               '-machine','q35,accel=kvm','-cpu','host','-smp','2','-m','4096',
               '-display','none','-serial','stdio','-monitor','none','-nic','none',
               '-kernel',str(args.kernel),'-initrd',str(output/'initramfs.cpio.gz'),
               '-append','rdinit=/init console=ttyS0 loglevel=4 panic=0 researcher_disposable_vm=1',
               '-drive',f'file={output / "disk.raw"},format=raw,if=virtio,cache=none']
    environment = {'PATH':os.defpath,'LANG':'C.UTF-8','LD_LIBRARY_PATH':str(prefix/'lib'),
                   'QEMU_MODULE_DIR':str(prefix/'lib/qemu')}
    with (output/'serial.log').open('w') as log:
        process = subprocess.Popen(command,env=environment,stdout=log,stderr=subprocess.STDOUT,stdin=subprocess.DEVNULL)
        try:
            deadline = time.monotonic()+args.timeout
            while process.poll() is None:
                if time.monotonic() >= deadline:
                    raise TimeoutError('Owned VM execution deadline expired; no retry')
                if 'Kernel panic - not syncing' in (output/'serial.log').read_text(errors='replace'):
                    raise RuntimeError('Original guest kernel panicked; retain its disk/log without automatic reboot')
                try:
                    process.wait(timeout=.5)
                except subprocess.TimeoutExpired:
                    pass
            code = process.returncode
        except BaseException:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill();process.wait(timeout=10)
            raise
    records = [json.loads(line.split('RESEARCHER-REBOOT-RESULT:',1)[1])
               for line in (output/'serial.log').read_text(errors='replace').splitlines()
               if 'RESEARCHER-REBOOT-RESULT:' in line]
    if code or len(records) != 1 or records[0].get('status') != 'passed':
        raise RuntimeError(f'Original VM trial failed (exit {code}); inspect its retained serial.log')
    return {**records[0],'qemu_exit':code,'network_card':False,'qemu_processes_started':1}


def main():
    """Prepare and execute one NEW isolated trial with a declared original-process deadline."""
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('output','qemu','kernel','assets','runtime-env'):
        parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--timeout',type=int,default=240)
    parser.add_argument('--active-command', action='store_true',
                        help='Keep a real Codex command peer and child alive until the guest kernel restarts; no inference')
    args = parser.parse_args()
    for name in ('qemu','kernel','assets','runtime_env'):
        setattr(args,name,getattr(args,name).resolve(strict=True))
    if os.getuid() != 1000 or not os.access('/dev/kvm',os.R_OK|os.W_OK):
        raise ValueError('This fixture requires UID1000 and accessible KVM; never run it as root')
    output = args.output.absolute()
    output.mkdir(mode=0o700)
    start = time.monotonic()
    result = {'status':'preparing','model_turns':0}
    try:
        result['preparation'] = prepare(args,output)
        print('Disposable disk prepared; starting one VM.',flush=True)
        result.update(run(args,output))
    except BaseException as error:
        result.update(status='failed',error_type=type(error).__name__)
        raise
    finally:
        result['elapsed_seconds'] = round(time.monotonic()-start,2)
        (output/'host-result.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result))


if __name__ == '__main__':
    main()
