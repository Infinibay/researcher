"""Inventory owned prompt builders, instruction literals and tool descriptions without importing application code or invoking a model; unresolved consumers stay explicit."""

import argparse
import ast
import hashlib
import json
import re
from pathlib import Path

PROMPT_NAME=re.compile(r'prompt|instructions|backstory|expected_output|description|feedback',re.I)
SQL_START=re.compile(r'^\s*(SELECT|INSERT|UPDATE|DELETE|CREATE|ALTER|PRAGMA)\b',re.I)


def module_name(path):
    """Map a repository Python path to its import identity, including package initializers."""
    parts=path.with_suffix('').parts
    return '.'.join(parts[:-1] if parts[-1]=='__init__' else parts)


def prompt_nodes(tree,path):
    """Find source candidates with explicit syntax rules; source bytes are measured rather than misreported as rendered prompt tokens."""
    parents={child:parent for parent in ast.walk(tree) for child in ast.iter_child_nodes(parent)}
    for node in ast.walk(tree):
        symbol=None;value=node
        if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef)):
            if path.as_posix().startswith('backend/prompts/') or PROMPT_NAME.search(node.name):symbol=node.name
            elif node.name in ('freeze_input','conversation_history'):symbol=node.name
            elif node.name.startswith('researcher_') and ast.get_docstring(node):
                # definitions() uses inspect.getdoc(handler) as the actual wire description.
                symbol=node.name+'.wire_description';value=node.body[0].value
        elif isinstance(node,ast.Assign):
            names=[target.id for target in node.targets if isinstance(target,ast.Name)]
            symbol=next((name for name in names if PROMPT_NAME.search(name) or name=='_TOOLS'),None);value=node.value
            if symbol is None and path.as_posix().startswith('backend/prompts/') and isinstance(parents.get(node),ast.Module) and isinstance(value,(ast.Constant,ast.JoinedStr)):
                symbol=next(iter(names),None)
        elif isinstance(node,ast.AnnAssign) and isinstance(node.target,ast.Name):
            if PROMPT_NAME.search(node.target.id):symbol=node.target.id;value=node.value
        elif isinstance(node,ast.keyword) and node.arg in ('description','expected_output','backstory','goal'):
            symbol=node.arg+'@'+str(node.lineno);value=node.value
        elif isinstance(node,ast.Dict):
            # Tool metadata literals are captured individually, not arbitrary user payloads.
            for key,item in zip(node.keys,node.values):
                if isinstance(key,ast.Constant) and key.value in ('description','instructions') and isinstance(item,(ast.Constant,ast.JoinedStr)):
                    text=''.join(n.value for n in ast.walk(item) if isinstance(n,ast.Constant) and isinstance(n.value,str))
                    if text:yield node,str(key.value)+'@'+str(item.lineno),item
        if not symbol or value is None:continue
        strings=[n.value for n in ast.walk(value) if isinstance(n,ast.Constant) and isinstance(n.value,str) and not SQL_START.match(n.value)]
        doc=ast.get_docstring(node,clean=False) if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef)) else None
        if value is node and doc in strings:strings.remove(doc)
        if not strings and symbol not in ('freeze_input','conversation_history'):continue
        if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef)) and value is node and sum(len(text) for text in strings)<60 and symbol not in ('freeze_input','conversation_history'):continue
        owner=[];parent=parents.get(node)
        while parent is not None:
            if isinstance(parent,(ast.ClassDef,ast.FunctionDef,ast.AsyncFunctionDef)):owner.append(parent.name)
            parent=parents.get(parent)
        if owner and isinstance(node,ast.Assign):symbol+='@'+str(node.lineno)
        yield node,'.'.join([*reversed(owner),symbol]),value


def family(path):
    """Classify ownership without treating a heuristic candidate as a completed semantic review or proof of runtime reachability."""
    value=path.as_posix()
    if value.startswith('backend/cli/') or value=='backend/research/stdio_server.py':return 'owner_cli_metadata','excluded_human_interface'
    if value=='scripts/audit_prompt_inventory.py':return 'inventory_instrumentation','excluded_instrumentation'
    if value=='backend/prompts/native.py':return 'native_common_catalog','rewritten'
    if value=='backend/runtime/run_inputs.py':return 'attributed_input_renderer','retained'
    if value.endswith('_instructions.py') or value=='backend/planning/instructions.py' or value=='backend/runtime/development_policy.py':return 'native_capability_policy','reviewed_native'
    if value.startswith('backend/prompts/'):return 'historical_role_template','archived_not_native'
    if value.startswith(('backend/engine/','backend/flows/','backend/autonomy/','backend/agents/')):return 'historical_engine_or_coordination','pending_legacy_removal'
    if value.startswith('backend/tools/'):return 'retained_tool_or_historical_schema','requires_review'
    return 'other_owned_prompt_candidate','requires_review'


def inventory(root,*,reviews=None):
    """Scan all owned backend/scripts Python sources and report direct imports as a lower bound on consumers, with hashes binding the actual inspected tree."""
    sources={};reviews=reviews or {}
    for folder in ('backend','scripts'):
        for path in sorted((root/folder).rglob('*.py')):
            relative=path.relative_to(root)
            if 'tests' in relative.parts or '__pycache__' in relative.parts:continue
            source=path.read_text();sources[relative]=(source,ast.parse(source),hashlib.sha256(source.encode()).hexdigest())
    imports={}
    for path,(_,tree,_) in sources.items():
        module=module_name(path);package=module if path.name=='__init__.py' else module.rpartition('.')[0]
        for node in ast.walk(tree):
            if not isinstance(node,ast.ImportFrom):continue
            base=package.split('.')[:len(package.split('.'))-node.level+1] if node.level else []
            target='.'.join([*base,*([node.module] if node.module else [])])
            for alias in node.names:imports.setdefault(target+'.'+alias.name,[]).append({'path':path.as_posix(),'line':node.lineno})
    entries=[]
    for path,(source,tree,digest) in sources.items():
        owner=module_name(path)
        consumers={item['path']:sources[Path(item['path'])][2]
                   for target,items in imports.items() if target.startswith(owner+'.') for item in items}
        dependencies=hashlib.sha256(json.dumps({'source':digest,'direct_module_consumers':consumers},sort_keys=True).encode()).hexdigest()
        for node,symbol,value in prompt_nodes(tree,path):
            rendered=None
            try:
                literal=ast.literal_eval(value)
                if isinstance(literal,str):rendered=len(literal.encode())
            except (ValueError,TypeError,SyntaxError):pass
            group,disposition=family(path)
            entries.append({'id':path.as_posix()+'::'+symbol,'path':path.as_posix(),'symbol':symbol,'line':node.lineno,'end_line':node.end_lineno,'owner':module_name(path),'family':group,'disposition':disposition,'objective':ast.get_docstring(tree,clean=True) or 'Purpose requires semantic review.','source_sha256':digest,'source_bytes':len((ast.get_source_segment(source,value) or '').encode()),'rendered_utf8_bytes':rendered,'variables_kind':'function_parameters' if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef)) else 'referenced_identifiers','variables':[arg.arg for arg in node.args.args+node.args.kwonlyargs] if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef)) else sorted({n.id for n in ast.walk(value) if isinstance(n,ast.Name)}),'direct_import_consumers':imports.get(module_name(path)+'.'+symbol,[]),'consumer_coverage':'Direct from-imports only; local/dynamic/attribute callers require review. Empty does not prove unused.','evaluation_cases':['CTX01','CTX02','CTX03','CTX04','AUTH01','COMM01'],'review_limits':'Disposition classifies the family; requires_review and pending_legacy_removal entries are not semantically accepted or proof of runtime reachability.'})
            entry=entries[-1];record=reviews.get(entry['id'])
            entry.update(dependencies_sha256=dependencies,direct_module_consumers=consumers,suggested_disposition=disposition,
                         disposition='requires_review',review_status='unreviewed')
            if record:
                entry['review_status']='stale'
                if record.get('dependencies_sha256')==dependencies and record.get('decision') and record.get('rationale'):
                    entry.update(review_status='reviewed',disposition=record['decision'],review_rationale=record['rationale'],
                                 review_evidence=record.get('evidence',[]),review_conflicts=record.get('conflicts',[]))
    if len({entry['id'] for entry in entries})!=len(entries):raise ValueError('Ambiguous prompt candidate identities; preserve each source variant before review.')
    return {'schema_version':1,'scope':'Owned backend/ and scripts/ Python, excluding tests. Syntax-selected prompt builders/literals/tool descriptions; external native system prompts and arbitrary owner/source text are outside this static inventory.','coverage':'Candidates are not unique rendered prompts. Dynamic rendering size and non-direct consumers remain unknown. Reviews are explicit declarations bound to source and direct module consumers, not proof of efficacy or complete runtime reachability. requires_review entries are unfinished.','files_scanned':len(sources),'source_tree':{p.as_posix():value[2] for p,value in sources.items()},'entries':entries}


def main():
    """Write a deterministic review inventory or fail if the committed inventory no longer matches its declared source tree; no application imports or inference occur."""
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--root',type=Path,default=Path.cwd());parser.add_argument('--output',type=Path,default=Path('docs/prompts/inventory.json'));parser.add_argument('--reviews',type=Path,default=Path('docs/prompts/review-decisions.json'));parser.add_argument('--check',action='store_true');args=parser.parse_args()
    reviews=json.loads(args.reviews.read_text())['entries'] if args.reviews.exists() else {}
    result=inventory(args.root.resolve(),reviews=reviews);encoded=json.dumps(result,indent=2,ensure_ascii=False)+'\n'
    if args.check:
        if args.output.read_text()!=encoded:raise SystemExit('Prompt inventory changed; review new/changed candidates and regenerate it.')
        if any(entry['review_status']!='reviewed' for entry in result['entries']):raise SystemExit('Prompt inventory contains unreviewed or stale entries; record an explicit source-bound review.')
    else:args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(encoded)
    print(json.dumps({'files':result['files_scanned'],'entries':len(result['entries']),'requires_review':sum(item['disposition']=='requires_review' for item in result['entries'])}))


if __name__=='__main__':main()
