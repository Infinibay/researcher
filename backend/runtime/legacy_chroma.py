"""Import verified Chroma text exports as explicitly scoped historical attachments, without Chroma at runtime."""

from collections import Counter
import hashlib
import json
from pathlib import Path

from backend.research.reference_storage import ReferenceStorage
from backend.runtime.snapshot_files import copy_regular, open_file, relative_name


def _object(root, name, limit):
    """Read one bounded JSON manifest through the same no-follow path contract as copied data."""
    with open_file(root,name) as stream:
        raw=stream.read(limit+1)
    if len(raw)>limit:raise ValueError('Chroma export manifest exceeds its bound')
    return json.loads(raw),hashlib.sha256(raw).hexdigest()


def import_chroma_exports(db, root, evidence, exports, budget):
    """Copy raw export evidence and retain each exact text fragment under an explicit owner project.

    Metadata-only records remain in the export/provenance receipt. No complete
    document, citation, task association or reviewed finding is inferred.
    """
    history=[]
    for ordinal,supplied in enumerate(exports):
        if not isinstance(supplied,dict) or set(supplied)!={'path','projects'} or not isinstance(supplied['projects'],dict):
            raise ValueError('Chroma export requires path and explicit project per collection')
        source=Path(supplied['path']).resolve(strict=True)
        if source.is_relative_to(root) or root.is_relative_to(source):
            raise ValueError('Chroma export must not overlap imported installation')
        manifest,manifest_hash=_object(source,'manifest.json',min(budget.max_bytes,128*1024**2))
        if manifest.get('format')!=1 or manifest.get('kind')!='researcher-chroma-export' or manifest.get('status')!='complete':
            raise ValueError('A completed compatible Chroma export is required')
        collections=manifest['collections']
        names=[item['name'] for item in collections]
        if len(set(names))!=len(names) or set(names)!=set(supplied['projects']):
            raise ValueError('Every Chroma collection requires exactly one explicit project assignment')
        for project in supplied['projects'].values():
            if type(project) is not int or project<=0 or not db.execute('SELECT 1 FROM projects WHERE id=?',(project,)).fetchone():
                raise ValueError('Chroma collection assignment must name an existing project')
        destination=evidence/'chroma'/str(ordinal)
        destination.mkdir(parents=True,mode=0o700)
        manifest_copy=copy_regular(source,'manifest.json',destination/'manifest.json',budget)
        if manifest_copy['sha256']!=manifest_hash:raise ValueError('Chroma export manifest changed before capture')
        records=manifest['records']
        if records['path']!='records.jsonl':raise ValueError('Unexpected Chroma records path')
        entries=[records,*manifest['source_files']]
        paths=set()
        for entry in entries:
            name=str(relative_name(entry['path']))
            if name in paths or (name!='records.jsonl' and not name.startswith('source/')):
                raise ValueError('Invalid or repeated Chroma evidence path')
            paths.add(name);budget.check(entries=len(paths)+len(history))
            target=destination/name;target.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
            observed=copy_regular(source,name,target,budget)
            if observed!={key:entry[key] for key in ('bytes','sha256')}:
                raise ValueError('Chroma export evidence hash or size differs')
        seen=set();counts=Counter()
        with open_file(destination,'records.jsonl') as stream:
            while raw:=stream.readline(16*1024**2+1):
                budget.check(entries=len(history)+1)
                if len(raw)>16*1024**2:raise ValueError('Chroma record exceeds16MiB import limit')
                row=json.loads(raw)
                if not isinstance(row,dict) or set(row)!={'collection','id','document','metadata'}:
                    raise ValueError('Invalid Chroma record fields')
                collection=row['collection'];identity=row['id'];text=row['document']
                if collection not in supplied['projects'] or not isinstance(identity,str) or not identity or (collection,identity) in seen:
                    raise ValueError('Unknown or repeated Chroma record identity')
                if text is not None and not isinstance(text,str):raise ValueError('Chroma document must be text or absent')
                if row['metadata'] is not None and not isinstance(row['metadata'],dict):raise ValueError('Chroma metadata must be an object or absent')
                seen.add((collection,identity));counts[collection]+=1
                project=supplied['projects'][collection]
                item={'export_ordinal':ordinal,'collection':collection,'original_id':identity,'project_id':project,
                      'assignment':'explicit_operator_mapping','metadata':row['metadata'],'reference_id':None,
                      'disposition':'metadata_only' if text is None else 'historical_text_fragment'}
                if text is not None:
                    data=text.encode('utf-8');budget.check(size=len(data));budget.bytes+=len(data)
                    target=ReferenceStorage(root/'uploads').save(project,data)
                    cursor=db.execute("INSERT INTO reference_files(project_id,file_name,file_path,file_type,file_size,description,uploaded_by,tags_json) VALUES(?,?,?,'text/plain',?,?,?,'[\"legacy-chroma-fragment\"]')",
                        (project,f'Chroma {collection} — {identity}.txt',str(target),len(data),
                         'Fragmento histórico conservado de Chroma. No equivale al documento original completo; proyecto asignado explícitamente al importar.','legacy-import'))
                    item.update(reference_id=cursor.lastrowid,sha256=hashlib.sha256(data).hexdigest(),bytes=len(data))
                    provenance={'kind':'legacy_chroma_fragment','complete_original_document':False,
                                'collection':collection,'original_id':identity,'metadata':row['metadata'],
                                'assignment':'explicit_operator_mapping','project_id':project,
                                'export_manifest_sha256':manifest_hash}
                    db.execute('INSERT INTO reference_import_provenance VALUES(?,?,?)',
                               (cursor.lastrowid,item['sha256'],json.dumps(provenance,ensure_ascii=False)))
                history.append(item)
        if len(seen)!=records['count'] or any(counts[item['name']]!=item['count'] for item in collections):
            raise ValueError('Chroma export record counts disagree with its manifest')
    return history
