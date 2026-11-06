"""Fixed sandbox-only source repair driver: preserve working files and existing history, hydrate missing files, and create only absent refs.

The owning SourceGitLaunch supplies the original request, safe Git policy and
pinned executable. This module grants no host authority and accepts no commands.
Its bytes are hashed into the original launch before the sandbox gate opens.
"""

import base64
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys


class RepairConflict(RuntimeError):
    """A retained source cannot be continued without changing existing work or guessing its Git metadata."""


def repair(git_binary, policy, request, operation_id):
    """Finish only missing source preparation under the original private allocation; never reset, force checkout, delete files or publish remotely."""
    actions=[]
    environment=dict(os.environ)
    if request['use_configured_auth']:
        credential=json.loads(Path('/run/researcher-network/credential').read_text())
        environment.update(GIT_CONFIG_COUNT='1',GIT_CONFIG_KEY_0='http.'+request['remote_url']+'.extraHeader',GIT_CONFIG_VALUE_0='Authorization: Basic '+base64.b64encode((credential['username']+':'+credential['token']).encode()).decode())
    if request['mode']=='clone':
        policy=[*policy,'-c','protocol.https.allow=always','-c','http.followRedirects=false','-c','http.sslCAInfo=/run/researcher-network/ca.pem','-c','transfer.fsckObjects=true']

    def git(*args, data=None, allowed=(0,)):
        """Run only driver-selected Git arguments with fixed owner policy, finite deadlines and complete bounded output inside the owned domain."""
        result=subprocess.run([git_binary,*policy,*args],input=data,capture_output=True,env=environment,timeout=35)
        if len(result.stdout)>1024**2 or len(result.stderr)>65536 or result.returncode not in allowed:
            raise RepairConflict('Git could not safely finish this missing preparation stage')
        return result

    metadata=Path('.git')
    if os.path.lexists(metadata):
        if metadata.is_symlink() or not metadata.is_dir():
            raise RepairConflict('Retained Git metadata is redirected or not a directory')
        # A linked/shared repository requires a separate adoption decision.
        for entry in ('HEAD','config','index','commondir','objects','refs'):
            path=metadata/entry
            if path.is_symlink() or (entry=='commondir' and path.exists()):
                raise RepairConflict('Retained Git metadata redirects outside this allocation')
    else:
        git('init','--template=','-b',request['branch'] or 'main','.')
        actions.append('initialized_missing_metadata')
    root=git('rev-parse','--show-toplevel').stdout.decode().strip()
    if root!=os.getcwd():raise RepairConflict('A parent repository cannot be repaired as this source')
    config=git('config','--local','--null','--list').stdout
    for item in config.split(b'\0'):
        key=item.partition(b'\n')[0].lower()
        if key.startswith((b'credential.',b'include.',b'includeif.',b'filter.',b'url.',b'http.')) or key.endswith(b'.extraheader') or key in (b'core.worktree',b'extensions.worktreeconfig',b'core.sparsecheckout',b'core.sshcommand'):
            raise RepairConflict('Retained Git configuration needs explicit review')
    head=git('rev-parse','--verify','HEAD^{commit}',allowed=(0,128)).stdout.decode().strip()
    branch=git('symbolic-ref','--quiet','--short','HEAD',allowed=(0,1,128)).stdout.decode().strip()
    origin=git('remote','get-url','origin',allowed=(0,2)).stdout.decode().strip()
    if request['mode']=='create':
        if branch!=request['branch'] or origin:
            raise RepairConflict('Original branch or origin changed')
        if not head:
            if git('ls-files','--stage','-z').stdout:
                raise RepairConflict('An initial repair cannot commit owner-staged files')
            tree=git('hash-object','-t','tree','-w','--stdin',data=b'').stdout.decode().strip()
            head=git('-c','user.name=Researcher owner','-c','user.email=owner@localhost','-c','commit.gpgsign=false','commit-tree',tree,'-m','Initialize source ('+operation_id+')').stdout.decode().strip()
            # Compare-and-set can create this missing branch, never append to or replace a concurrent owner commit.
            git('update-ref','refs/heads/'+branch,head,'0'*len(head))
            actions.append('created_missing_initial_ref')
    elif request['mode']=='clone':
        if origin and origin!=request['remote_url']:
            raise RepairConflict('Original remote changed; repair cannot replace it')
        if not head:
            if git('ls-files','--stage','-z').stdout:
                raise RepairConflict('Unborn clone contains owner-staged files')
            advertised=git('ls-remote','--symref',request['remote_url'], 'refs/heads/'+request['branch'] if request['branch'] else 'HEAD').stdout.decode().splitlines()
            expected=None;selected=request['branch']
            for line in advertised:
                value,_,ref=line.partition('\t')
                if value.startswith('ref: refs/heads/') and ref=='HEAD':selected=value.removeprefix('ref: refs/heads/')
                elif re.fullmatch(r'(?:[a-f0-9]{40}|[a-f0-9]{64})',value):expected=value
            if not selected or not expected:
                raise RepairConflict('Remote has no complete selected branch')
            git('check-ref-format','refs/heads/'+selected)
            git('fetch','--no-tags','--no-recurse-submodules','--no-write-fetch-head','--',request['remote_url'],'refs/heads/'+selected)
            git('cat-file','-e',expected+'^{commit}')
            git('update-ref','refs/heads/'+selected,expected,'0'*len(expected))
            # Existing HEAD must still be unborn before selecting its newly created original clone branch.
            if branch!=selected:
                current=git('rev-parse','--verify','HEAD^{commit}',allowed=(0,128))
                if current.returncode==0:raise RepairConflict('Owner HEAD appeared during remote repair')
                git('symbolic-ref','HEAD','refs/heads/'+selected)
            head=expected;branch=selected
            actions.append('fetched_missing_selected_branch')
        if request['branch'] and branch!=request['branch']:
            raise RepairConflict('Original clone branch changed')
        if not origin:
            git('config','--local','--add','remote.origin.url',request['remote_url'])
            actions.append('restored_missing_origin')
        if not (metadata/'index').exists():
            git('read-tree','HEAD')
            actions.append('prepared_missing_index')
        entries=git('ls-files','--stage','-z').stdout.split(b'\0')
        missing=[]
        for entry in entries:
            if not entry:continue
            info,sep,raw=entry.partition(b'\t');parts=info.split()
            if not sep or len(parts)!=3 or parts[2]!=b'0':raise RepairConflict('Index contains unresolved entries')
            path=PurePosixPath(os.fsdecode(raw))
            if path.is_absolute() or any(part in ('.','..','.git') for part in path.parts):raise RepairConflict('Index contains unsafe paths')
            if parts[0]==b'160000':raise RepairConflict('Submodules require separate source preparation')
            for parent in list(Path(path).parents)[:-1]:
                if parent.is_symlink():raise RepairConflict('A parent symlink redirects checkout')
            if not os.path.lexists(path):missing.append(raw)
            if len(missing)>10000:raise RepairConflict('Missing-file manifest exceeds its complete budget')
        if missing:
            git('checkout-index','-z','--stdin',data=b'\0'.join(missing)+b'\0')
            actions.append('hydrated_missing_files')
    else:
        raise RepairConflict('Only explicit local creation or clone has writable repair stages')
    return {'actions':actions,'head_sha':head,'branch':branch,'preserved_existing_files':True}


if __name__=='__main__':
    try:
        result=repair(sys.argv[1],json.loads(sys.argv[2]),json.loads(sys.argv[3]),sys.argv[4])
        print(json.dumps(result,sort_keys=True))
    except (RepairConflict, OSError, ValueError, subprocess.SubprocessError):
        print('Source repair stopped; retained files and metadata need inspection.',file=sys.stderr)
        raise SystemExit(1) from None
