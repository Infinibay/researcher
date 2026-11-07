"""Compare exact retained baseline policies with current native profiles using bytes and hashes, never estimated tokens or a fabricated quality score."""
import hashlib
import json
from pathlib import Path

from backend.prompts.native import CATALOG_VERSION, build_instructions

PROFILES={'scientific_research':('research','research'),'code_audit':('research','review'),'planning':('research','plan'),'investigation':('research','investigation'),'development':('development','code'),'code_review':('code_review','code'),'finding_review':('finding_review','research')}


def main():
    """Measure only material actually constructed for these profiles; real model/communication outcomes remain unmeasured."""
    baseline=json.loads(Path('evals/prompts/baseline.json').read_text());rows=[]
    for profile,(kind,task) in PROFILES.items():
        old=baseline['instructions'][profile];new=build_instructions(kind,task)
        rows.append({'profile':profile,'baseline_utf8_bytes':len(old.encode()),'current_utf8_bytes':len(new.encode()),'baseline_sha256':hashlib.sha256(old.encode()).hexdigest(),'current_sha256':hashlib.sha256(new.encode()).hexdigest()})
    result={'baseline_commit':baseline['source_commit'],'current_catalog_version':CATALOG_VERSION,'measurement':'UTF-8 bytes and exact text hashes. Not model tokens, cost, latency, semantic correctness or user understanding.','profiles':rows,'model_evaluations':'not_run'}
    Path('docs/prompts/profile-comparison.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(rows))


if __name__=='__main__':main()
