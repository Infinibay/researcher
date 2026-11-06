"""Repository prompt auditing includes executable wire descriptions and notices new sources without importing application modules."""

import importlib.util
from pathlib import Path


def test_inventory_includes_actual_tool_docstrings_and_new_source_candidates(tmp_path):
    """A method exposed through inspect.getdoc is model-visible policy, while a new prompt file must invalidate the scanned tree rather than disappear from coverage."""
    path=Path(__file__).resolve().parents[3]/'scripts/audit_prompt_inventory.py'
    spec=importlib.util.spec_from_file_location('prompt_inventory_audit',path);audit=importlib.util.module_from_spec(spec);spec.loader.exec_module(audit)
    target=tmp_path/'backend/runtime/business_definitions.py';target.parent.mkdir(parents=True)
    doc='Read exact captured sources and retain the original operation_key after an unknown reply.'
    target.write_text('class ResearchTools:\n    def researcher_example(self):\n        """'+doc+'"""\n        return {}\n')
    first=audit.inventory(tmp_path)
    entry=next(item for item in first['entries'] if 'wire_description' in item['id'])
    assert entry['rendered_utf8_bytes']==len(doc.encode()) and entry['variables']==['self']
    extra=tmp_path/'backend/prompts/new_role.py';extra.parent.mkdir();extra.write_text('INSTRUCTIONS="Always inspect original code and its observed state before claiming this task succeeded."\n')
    second=audit.inventory(tmp_path)
    assert first['source_tree']!=second['source_tree'] and len(second['entries'])==len(first['entries'])+1


def test_inventory_never_auto_approves_a_new_or_changed_template(tmp_path):
    """A family/name match cannot establish a review; source changes make a saved review stale until a new explicit decision is recorded."""
    path=Path(__file__).resolve().parents[3]/'scripts/audit_prompt_inventory.py'
    spec=importlib.util.spec_from_file_location('prompt_inventory_review',path);audit=importlib.util.module_from_spec(spec);spec.loader.exec_module(audit)
    target=tmp_path/'backend/prompts/new_role.py';target.parent.mkdir(parents=True)
    target.write_text('INSTRUCTIONS="Inspect the original code and observed state before claiming any task has succeeded."\n')
    initial=audit.inventory(tmp_path);entry=initial['entries'][0]
    assert entry['review_status']=='unreviewed'
    reviews={entry['id']:{'dependencies_sha256':entry['dependencies_sha256'],'decision':'retained','rationale':'Inspected this fixture policy; no runtime or comprehension claim.'}}
    assert audit.inventory(tmp_path,reviews=reviews)['entries'][0]['review_status']=='reviewed'
    target.write_text('INSTRUCTIONS="Different instructions now require an explicit review before they may be accepted."\n')
    assert audit.inventory(tmp_path,reviews=reviews)['entries'][0]['review_status']=='stale'
