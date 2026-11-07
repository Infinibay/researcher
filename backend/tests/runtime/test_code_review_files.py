"""Bounded, quoted candidate-file observations reject redirected paths and fabricated source evidence."""

import hashlib
from types import SimpleNamespace

import pytest


@pytest.fixture
def code_files(tmp_path):
    """Pin a private candidate directory without pretending its bytes have already passed Git or native review."""
    from backend.runtime.code_review_files import CodeReviewFiles

    root = tmp_path / "candidate"
    root.mkdir(mode=0o700)
    (root / "value.py").write_text('"""Observed fixture."""\nVALUE = 200\n')
    info = root.stat()
    return root, CodeReviewFiles(
        SimpleNamespace(workspace=str(root), device=info.st_dev, inode=info.st_ino)
    )


def test_code_file_window_retains_full_hash_and_explicit_unread_tail(code_files):
    """A source hash identifies complete bytes while a short text window does not claim complete inspection."""
    root, reader = code_files
    result = reader.read("value.py", offset=0, max_chars=8)
    assert (
        result["sha256"] == hashlib.sha256((root / "value.py").read_bytes()).hexdigest()
    )
    assert result["text"] == (root / "value.py").read_text()[:8]
    assert not result["complete_file"] and result["next_offset"] == 8
    assert reader.read("value.py")["complete_file"]


@pytest.mark.parametrize(
    "path",
    [
        "../outside",
        "/etc/passwd",
        ".git/config",
        ".ken/index",
        "a/../value.py",
        "a//value.py",
        ".",
    ],
)
def test_code_file_reader_rejects_paths_outside_its_canonical_source_policy(
    code_files, path
):
    """Neither absolute paths nor metadata or traversal aliases are model-readable source references."""
    from backend.research.models import ResearchInputError, SourceUnavailable

    _root, reader = code_files
    with pytest.raises((ResearchInputError, SourceUnavailable)):
        reader.read(path)


def test_code_file_reader_refuses_symlink_and_fifo_without_waiting(
    code_files, tmp_path
):
    """Candidate-controlled directory components and special files cannot redirect or block a host source read."""
    import os

    from backend.research.models import SourceUnavailable

    root, reader = code_files
    (tmp_path / "secret").write_text("outside")
    (root / "link").symlink_to(tmp_path, target_is_directory=True)
    os.mkfifo(root / "fifo")
    for path in ("link/secret", "fifo"):
        with pytest.raises(SourceUnavailable):
            reader.read(path)


def test_code_reference_requires_the_actual_file_hash_line_and_exact_quote(code_files):
    """A model assertion cannot turn another file version or line into verified evidence."""
    from dataclasses import replace

    from backend.research.models import InvalidEvidence
    from backend.runtime.code_review_models import CodeReviewReference

    _root, reader = code_files
    source = reader.read("value.py")
    reference = CodeReviewReference(
        "file", "value.py", source["sha256"], 2, "VALUE = 200"
    )
    verified = reader.verify(reference)
    assert verified["start_line"] == 2 and verified["quote"] == "VALUE = 200"
    for wrong in (
        replace(reference, sha256="e" * 64),
        replace(reference, start_line=1),
        replace(reference, quote="VALUE = 137"),
    ):
        with pytest.raises(InvalidEvidence):
            reader.verify(wrong)


def test_supported_code_review_cannot_hide_a_not_checked_criterion(code_files):
    """Explicit unresolved checks contradict a supported verdict instead of being lost in persuasive prose."""
    from backend.research.models import InvalidEvidence, ReviewCheck
    from backend.runtime.code_review_models import (
        CodeReviewDecision,
        CodeReviewReference,
    )

    _root, reader = code_files
    source = reader.read("value.py")
    reference = CodeReviewReference(
        "file", "value.py", source["sha256"], 2, "VALUE = 200"
    )
    with pytest.raises(InvalidEvidence):
        CodeReviewDecision(
            "supported",
            "Looks correct",
            (ReviewCheck("tests", "not_checked", "No tests were run."),),
            (reference,),
            ("Source inspection only.",),
        )


def test_tail_counterevidence_remains_readable_and_external_edit_invalidates_old_quote(code_files):
    """Exact windows recover a final contradiction; unchanged quoted words cannot conceal a different full-file version."""
    from backend.research.models import InvalidEvidence
    from backend.runtime.code_review_models import CodeReviewReference

    root, reader = code_files
    prefix = 'Preliminary summary: all checks passed.\n' + 'Routine observation.\n' * 3500
    conclusion = 'Final correction: one check failed; do not report full success.\n'
    (root/'evidence.txt').write_text(prefix+conclusion)
    first = reader.read('evidence.txt', max_chars=100)
    assert first['next_offset'] == 100 and not first['complete_file']
    tail = reader.read('evidence.txt', offset=len(prefix))
    assert tail['text'] == conclusion and tail['sha256'] == first['sha256']
    assert tail['next_offset'] is None and not tail['complete_file']
    reference = CodeReviewReference('file','evidence.txt',tail['sha256'],3502,conclusion.strip())
    assert reader.verify(reference)['quote'] == conclusion.strip()
    (root/'evidence.txt').write_text((prefix+conclusion).replace('Preliminary summary','Revised old summary',1))
    fresh = reader.read('evidence.txt', offset=len(prefix))
    assert fresh['sha256'] != first['sha256'] and fresh['text'] == conclusion
    with pytest.raises(InvalidEvidence, match='another source version'):
        reader.verify(reference)
