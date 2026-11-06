"""Actual fixed repair driver refuses unsafe initial state and preserves owner files, staged content and redirected metadata."""

import json
from pathlib import Path
import subprocess
import sys

import pytest

from backend.runtime.development_workspace import _POLICY
from backend.tests.runtime.test_owned_source_setup import git


@pytest.mark.parametrize('blocked',['staged_content','changed_origin','redirected_metadata'])
def test_fixed_initial_repair_refuses_to_overwrite_existing_owner_state(tmp_path,blocked):
    """The actual driver must fail before publishing an initial ref when staged work, another origin or a metadata redirect requires owner review."""
    from backend.git import source_repair_program
    from backend.git.source_operations import SourceRequest
    from dataclasses import asdict

    source=tmp_path/'source';source.mkdir();git(source,'init','-b','main');(source/'notes.txt').write_text('owner work 137')
    if blocked=='staged_content':git(source,'add','notes.txt')
    if blocked=='changed_origin':git(source,'remote','add','origin','https://different.example/owner/source.git')
    metadata=source/'.git'
    if blocked=='redirected_metadata':
        original=tmp_path/'original-metadata';metadata.rename(original);metadata.symlink_to(original,target_is_directory=True)
    before={path.relative_to(metadata):path.read_bytes() for path in metadata.rglob('*') if path.is_file()}
    request=SourceRequest(mode='create',name='source',path=str(source),branch='main')
    result=subprocess.run([sys.executable,'-I','-S',source_repair_program.__file__,'/usr/bin/git',json.dumps(_POLICY),json.dumps(asdict(request)),'a'*32],cwd=source,capture_output=True,text=True,timeout=15)
    assert result.returncode==1 and not result.stdout
    assert (source/'notes.txt').read_text()=='owner work 137'
    assert {path.relative_to(metadata):path.read_bytes() for path in metadata.rglob('*') if path.is_file()}==before
    assert subprocess.run(['/usr/bin/git','-C',str(source),'rev-parse','--verify','HEAD'],capture_output=True).returncode==128
