"""Deterministic software-only delivery gates. Never calls or signs for models."""
import argparse
import csv
import json
import os
from pathlib import Path, PurePosixPath
import re
import sys
import time
import uuid
import zipfile
from common import digest, inside, no_links, read_json, write_json, state, delivery_paths
from package_policy import excluded_delivery_document, audit_delivery_text
from data_preflight import audit_csv_exports, check_expansion

BASE = Path(__file__).resolve().parents[1]
DEFAULT_WORK = Path(r'E:\研发自动化\work')
DEFAULT_STAGING = Path(r'E:\研发自动化\.staging')
DEFAULT_DELIVERY = Path(r'E:\研发自动化\交付成果')
TEXT = {'.py','.js','.cjs','.mjs','.jsx','.ts','.tsx','.html','.css','.scss','.json','.csv',
        '.yaml','.yml','.toml','.ini','.cfg','.txt','.md','.sql','.sh','.bat','.cmd','.ps1',
        '.xml','.svg','.vue','.svelte','.java','.kt','.c','.h','.cpp','.cs','.go','.rs','.lock','.example'}
FORBIDDEN_PARTS = {'node_modules','.git','.venv','venv','__pycache__','.cache','cache','logs',
                   'evidence','tests','test-results','downloads','raw','source-materials',
                   '.ssd','.staging','dist-evidence','credentials','sessions'}
FORBIDDEN_SUFFIX = {'.doc','.docx','.pdf','.db','.sqlite','.sqlite3','.log','.pyc','.pyo','.pem','.key', '.mp4','.zip'}
META_COLUMNS={'生成数据','数据来源','是否生成','是否生成数据','生成标记','数据生成方式','数据来源类型',
              'generateddata','isgenerated','synthetic','issynthetic','datasource','dataprovenance','sourcetype','generationmethod'}


def clean_csv(source,destination):
    """Delete exactly declared metadata columns, preserving every other cell string/order."""
    source,destination=no_links(source),no_links(destination)
    if source==destination or destination.exists(): raise ValueError('Clean into a wholly new delivery copy; never alter input/completed CSV')
    with source.open(encoding='utf-8-sig',newline='') as stream:
        rows=list(csv.reader(stream,strict=True))
    if len(rows)<2 or len(set(rows[0]))!=len(rows[0]):raise ValueError('Empty/duplicate-header CSV')
    removed=[i for i,h in enumerate(rows[0]) if re.sub(r'[\s_-]','',h).casefold() in META_COLUMNS]
    kept=[i for i in range(len(rows[0])) if i not in removed]
    if not kept or any(len(row)!=len(rows[0]) for row in rows): raise ValueError('Malformed CSV')
    result=[[row[i] for i in kept] for row in rows]
    destination.parent.mkdir(parents=True,exist_ok=True)
    with destination.open('x',encoding='utf-8-sig',newline='') as stream:
        csv.writer(stream).writerows(result)
    with destination.open(encoding='utf-8-sig',newline='') as stream:
        if list(csv.reader(stream))!=result: raise ValueError('Cleaned CSV cell preservation check failed')
    return {'source_sha256':digest(source),'sha256':digest(destination),
            'removed_columns':[rows[0][i] for i in removed],'other_cells_unchanged':True,'rows':len(rows)-1}


def clean_data(args):
    workspace,output,run=state(args.workspace)
    manifest=read_json(args.manifest)
    receipts={}
    for item in manifest:
        name=item['name']
        if Path(name).name!=name or not name.endswith('.csv'): raise ValueError('Simple CSV basename required')
        source=inside(workspace,item['source'])
        destination=delivery_paths(run,output)['data_dir']/name
        receipts[name]=clean_csv(source,destination)
    write_json(workspace/'.ssd/data-cleaning.json',receipts)
    return receipts


def ref(workspace, value):
    if not isinstance(value, dict) or set(value) != {'path','sha256'}:
        raise ValueError('Evidence reference requires exactly path/sha256')
    target = inside(workspace, value['path'])
    if not target.is_file() or digest(target) != value['sha256']:
        raise ValueError('Missing/changed evidence: '+value['path'])
    return target


def make_ref(workspace, target):
    target = no_links(target)
    return {'path':target.relative_to(workspace).as_posix(),'sha256':digest(target)}


def tree(root):
    root = no_links(root)
    return {p.relative_to(root).as_posix():digest(no_links(p)) for p in sorted(root.rglob('*')) if p.is_file()}


def prepare(args):
    workspace, output = no_links(args.workspace), no_links(args.output)
    staging, delivery = no_links(args.staging_root), no_links(args.delivery_root)
    if staging not in output.parents or staging.drive.casefold() != delivery.drive.casefold():
        raise ValueError('Candidate must be a unique child of staging on delivery volume')
    if output.exists() and any(output.iterdir()):
        raise ValueError('Candidate already contains files; resume its existing run')
    if (workspace/'.ssd/run.json').exists():
        raise ValueError('Already prepared; use status/resume instead of resetting')
    if not args.case_id or not re.fullmatch(r'[A-Za-z0-9_-]+', args.case_id):
        raise ValueError('case-id must be a stable ASCII identifier')
    sources=[]
    for path in args.source:
        p=no_links(path)
        if not p.is_file(): raise ValueError('Source is missing')
        sources.append({'path':str(p),'sha256':digest(p)})
    if len({s['sha256'] for s in sources}) != len(sources):
        raise ValueError('Duplicate input content; keep one canonical source')
    workspace.mkdir(parents=True,exist_ok=True)
    output.mkdir(parents=True,exist_ok=True)
    (output/'系统材料'/'数据').mkdir(parents=True,exist_ok=True)
    run={'schema_version':1,'profile':'software-only-v1','run_id':uuid.uuid4().hex,
         'case_id':args.case_id,'title':args.title,'workspace':str(workspace),'output':str(output),
         'delivery_root':str(delivery),'staging_root':str(staging),'sources':sources,
         'created_ns':time.time_ns(),'rules_sha256':digest(BASE/'references'/'inheritance.json'),
         'legacy_environment_entry':{'path':r'D:\软通图表\Enter-SoftwareCaseEnvironment.ps1',
                                      'exists_at_prepare':Path(r'D:\软通图表\Enter-SoftwareCaseEnvironment.ps1').exists()},
         'required_roles':{'build':['gpt-6.1-sol','high'],'repair':['gpt-6.1-sol','ultra'],
                           'review':['gpt-6.1-sol','ultra']}}
    write_json(workspace/'.ssd/run.json',run,exclusive=True)
    return run


def check_frozen_rules():
    entries=read_json(BASE/'references/frozen-sources.json')
    for item in entries:
        path=inside(BASE,item['snapshot'])
        if digest(path)!=item['sha256']:raise ValueError('Frozen original rule bytes changed: '+item['snapshot'])
    for item in read_json(BASE/'references/helper-provenance.json'):
        path=BASE/'scripts'/item['name']
        if digest(path)!=item['new_sha256']:raise ValueError('Deterministic helper changed without reviewed provenance: '+item['name'])


def ui_hits(name,text):
    policy=read_json(BASE/'references/ui-policy.json')
    hits=audit_delivery_text(name,text)
    for number,line in enumerate(text.splitlines(),1):
        terms=[term for term in policy['chinese'] if term in line]
        terms += [match.group() for pattern in policy['english_patterns'] for match in re.finditer(pattern,line,re.I)]
        if terms: hits.append({'path':name,'line':number,'kind':'ui-policy','words':terms})
    return hits


def package(args):
    workspace,output,run=state(args.workspace)
    manifest=read_json(no_links(args.manifest))
    source=inside(workspace,manifest['source_root'])
    files=manifest.get('files')
    if not isinstance(files,list) or not files or any(not isinstance(p,str) for p in files):
        raise ValueError('Use a nonempty explicit file allowlist')
    # One canonical ZIP name is used for validation, bytes and receipts.
    files=[p.replace('\\','/') for p in files]
    if any(not p or p.startswith('/') or ':' in p or any(x in {'','.', '..'} for x in p.split('/')) for p in files):
        raise ValueError('Unsafe/noncanonical source member')
    if len({p.casefold() for p in files}) != len(files):
        raise ValueError('Use a nonempty explicit file allowlist, no duplicates')
    selected=[]
    for name in files:
        path=inside(source,name)
        if not path.is_file(): raise ValueError('Only regular file members accepted')
        rel=PurePosixPath(name)
        reason=excluded_delivery_document(name)
        if (reason or any(part.casefold() in FORBIDDEN_PARTS for part in rel.parts)
                or rel.suffix.lower() in FORBIDDEN_SUFFIX or path.name=='.env'
                or re.search(r'(extract[_-]?docx|source[_-]?trace|data[_-]?(?:generate|generation|construct)|seed[_-]?data)',name,re.I)):
            raise ValueError('Excluded source member '+name+': '+str(reason or 'internal/runtime residue'))
        if rel.suffix.lower() in TEXT or path.name.startswith('.env.'):
            text=path.read_text(encoding='utf-8-sig',errors='strict')
            hits=ui_hits(name,text)
            if hits: raise ValueError('Source text policy failure: '+json.dumps(hits[:5],ensure_ascii=False))
        selected.append((name,path))
    archive=delivery_paths(run,output)['source_zip']
    temporary=archive.with_suffix('.pending')
    if temporary.exists(): raise ValueError('Unfinished package pending; inspect it before retry')
    try:
        with zipfile.ZipFile(temporary,'x',zipfile.ZIP_DEFLATED) as z:
            for name,path in selected: z.write(path,name)
        os.replace(temporary,archive)
    finally:
        if temporary.exists(): temporary.unlink()
    receipt={'schema_version':1,'run_id':run['run_id'],'sha256':digest(archive),
             'members':{name:digest(path) for name,path in selected},'manifest_sha256':digest(args.manifest)}
    write_json(workspace/'.ssd/source-package.json',receipt)
    return receipt


def check_data(workspace,paths,evidence):
    plan=read_json(ref(workspace,evidence['data_plan']))
    csvs=sorted(paths['data_dir'].glob('*.csv'))
    if not csvs or any(p.suffix.lower()!='.csv' or not p.is_file() for p in paths['data_dir'].iterdir()):
        raise ValueError('Important data directory must contain CSV files only')
    members={p.name:digest(no_links(p)) for p in csvs}
    _,_,run=state(workspace)
    completion=workspace/'.ssd/data-completion.json'
    if completion.exists():
        completed=read_json(completion)
        if (completed.get('contract')!='ssd-data-completion-v1' or completed.get('run_id')!=run['run_id']
                or completed.get('workspace')!=str(workspace) or completed.get('members')!=members):
            raise ValueError('Completed CSV changed; retain original fact and explicitly revalidate changed data')
        if completed.get('quality',{}).get('data_status')!='pass' or completed.get('expansion',{}).get('expansion_status')!='pass':
            raise ValueError('Invalid completed data fact')
        if {name:item.get('sha256') for name,item in completed['quality'].get('files',{}).items()}!=members:
            raise ValueError('Completed quality fact does not describe exact CSV bytes')
        # The original plan/provenance/cleaning bytes are part of the pass fact.
        # A later algorithm/plan cannot retroactively invalidate unchanged data.
        for value in completed['original_evidence'].values():ref(workspace,value)
        return {'quality':completed['quality'],'expansion':completed['expansion'],
                'completion':make_ref(workspace,completion),'reused':True}
    for file in csvs:
        if not file.read_bytes().startswith(b'\xef\xbb\xbf'): raise ValueError('CSV needs UTF-8 BOM: '+file.name)
        hits=ui_hits(file.name,file.read_text(encoding='utf-8-sig'))
        if hits: raise ValueError('CSV prohibited text: '+json.dumps(hits[:5],ensure_ascii=False))
        with file.open(encoding='utf-8-sig',newline='') as stream:
            headers=next(csv.reader(stream))
        if any(re.sub(r'[\s_-]','',h).casefold() in META_COLUMNS for h in headers):
            raise ValueError('CSV source/generation metadata column must be removed as a whole')
    for name,spec in plan['export_schema'].items():
        for column,rule in spec['columns'].items():
            if not str(rule.get('meaning','')).strip(): raise ValueError('Column meaning missing: '+name+':'+column)
            if rule['kind']=='number' and not str(rule.get('unit','')).strip():
                raise ValueError('Number unit required (use 1 if dimensionless): '+column)
    quality=audit_csv_exports(csvs,plan['export_schema'],plan.get('known_names',[]),
                              plan.get('allowed_terms',[]),plan.get('name_review',{}))
    expansion=check_expansion(plan.get('baseline_metrics',{}),quality,plan['expansion_plan'])
    if quality['data_status']!='pass' or expansion['expansion_status']!='pass':
        raise ValueError('CSV quality/scale gate failed: '+json.dumps({'quality':quality,'expansion':expansion},ensure_ascii=False))
    provenance=read_json(ref(workspace,evidence['provenance']))
    if not provenance.get('nature') or not provenance.get('sources') or not provenance.get('validation'):
        raise ValueError('Internal data provenance/nature/sources/validation required')
    for item in provenance['sources']:
        if not item.get('url') or not item.get('license') or not item.get('accessed_at'):
            raise ValueError('Actual source URL/license/access time required')
        if item.get('obtained') is True: ref(workspace,item['raw_file'])
        elif not item.get('restriction'): raise ValueError('Unobtained sources need truthful restriction')
    # Completed data owns copies of the actual reviewed facts. Replacing a
    # later algorithm's plan does not change these prior byte-identical facts.
    fact_dir=workspace/'.ssd/data-facts'/uuid.uuid4().hex
    original={}
    for key in ('data_plan','provenance'):
        frozen=fact_dir/(key+'.json')
        write_json(frozen,read_json(ref(workspace,evidence[key])),exclusive=True)
        original[key]=make_ref(workspace,frozen)
    cleaning=workspace/'.ssd/data-cleaning.json'
    if cleaning.exists():
        frozen=fact_dir/'cleaning.json';write_json(frozen,read_json(cleaning),exclusive=True)
        original['cleaning']=make_ref(workspace,frozen)
    completed={'contract':'ssd-data-completion-v1','run_id':run['run_id'],'workspace':str(workspace),
               'members':members,'quality':quality,'expansion':expansion,'original_evidence':original,
               'checker_sha256':digest(BASE/'scripts/data_preflight.py'),'completed_ns':time.time_ns()}
    write_json(completion,completed,exclusive=True)
    return {'quality':quality,'expansion':expansion,'completion':make_ref(workspace,completion),'reused':False}


def check_execution(workspace,evidence,run):
    execution=read_json(ref(workspace,evidence['execution']))
    required={'algorithm','api','persistence','browser','export','lifecycle'}
    checks=execution.get('checks',[])
    if not required.issubset({c.get('kind') for c in checks}):
        raise ValueError('Six real execution categories required: '+','.join(sorted(required)))
    for item in checks:
        if item.get('exit_code')!=0 or not item.get('command') or not item.get('summary'):
            raise ValueError('Execution checks need actual successful command and concrete summary')
        ref(workspace,item['log'])
    if execution.get('run_id')!=run['run_id']:
        raise ValueError('Execution belongs to another run')
    cleanup=read_json(ref(workspace,evidence['cleanup']))
    if (cleanup.get('status')!='stopped' or cleanup.get('workspace')!=str(workspace)
            or cleanup.get('remaining') or cleanup.get('ports_still_listening')):
        raise ValueError('Real case process cleanup receipt required')
    probe=read_json(ref(workspace,evidence['package_probe']))
    if (probe.get('status')!='completed' or probe.get('run_id')!=run['run_id']
            or probe.get('source_zip_sha256')!=digest(delivery_paths(run)['source_zip'])
            or probe.get('cleanup',{}).get('status')!='stopped'):
        raise ValueError('Final ZIP requires a real isolated startup/core-flow/cleanup probe')
    from package_probe import validate_result
    validate_result(probe['case_assertions'])
    if not Path(probe['log']).is_file() or digest(probe['log'])!=probe.get('log_sha256'):
        raise ValueError('Package probe log missing/changed')
    if probe.get('checker_sha256')!=digest(BASE/'scripts/package_probe.py'):
        raise ValueError('Package probe must use this independent checker version')
    return execution


def check_video(workspace,paths,evidence):
    recording=read_json(ref(workspace,evidence['recording']))
    timeline=read_json(ref(workspace,evidence['timeline']))
    video_hash=digest(paths['video'])
    if (recording.get('video_sha256')!=video_hash or timeline.get('video_sha256')!=video_hash
            or recording.get('continuous_capture') is not True or recording.get('real_browser') is not True
            or recording.get('edited') is not False):
        raise ValueError('Video requires unchanged continuous real browser capture')
    duration=timeline.get('duration',0)
    if (not isinstance(duration,(int,float)) or duration<=60 or timeline.get('sample_fps')!=5
            or timeline.get('width')!=1920 or timeline.get('height')!=1080
            or timeline.get('decode_ok') is not True or timeline.get('codec')!='h264'
            or timeline.get('fps',0)<25
            or abs(recording.get('duration',0)-duration)>.2):
        raise ValueError('Measured video must exceed 60s, 1920x1080 H264, full decode and 5fps')
    events=recording.get('events',[])
    if len(events)<6 or len({e.get('action') for e in events})<3:
        raise ValueError('Complete varied natural operations required')
    previous=0
    for event in events:
        start,finish=event.get('started'),event.get('completed')
        if (not isinstance(start,(float,int)) or not isinstance(finish,(float,int))
                or start<previous or finish<start or finish>duration or not event.get('assertion')):
            raise ValueError('Ordered real interaction timings/assertions required')
        previous=finish
    import math
    samples=[f for f in timeline.get('frames',[]) if f.get('type')=='uniform_sample']
    if len(samples)!=math.ceil(duration*5-1e-7): raise ValueError('Incomplete 5fps full timeline')
    if len({f['file'] for f in samples})!=len(samples) or any(abs(f.get('seconds',-1)-i/5)>.001 for i,f in enumerate(samples)):
        raise ValueError('Timeline needs every distinct ordered sample file from 0s at 5fps')
    if not {'first','last','uniform_sample'}.issubset({f.get('type') for f in timeline.get('frames',[])}):
        raise ValueError('Missing first/last source frames')
    interactions=timeline.get('interaction_frames',[])
    if len(interactions)!=2*len(events): raise ValueError('Each operation needs before/after original frames')
    for item in [*timeline['frames'],*interactions,*timeline.get('contact_sheets',[])]:
        path=no_links(item['file'])
        if workspace not in path.parents or not path.is_file() or digest(path)!=item['sha256']:
            raise ValueError('Video evidence must be intact internal files')
    return timeline


def check_trace(workspace,evidence,run):
    trace=read_json(ref(workspace,evidence['source_trace']))
    if {s['sha256'] for s in trace.get('sources',[])} != {s['sha256'] for s in run['sources']}:
        raise ValueError('Trace must cover every frozen material')
    mappings=trace.get('mappings',[])
    if not mappings: raise ValueError('Input paragraphs/formulas/images/examples need implementation mapping')
    for item in mappings:
        if (not item.get('source_location') or not item.get('definition')
                or not all(item.get(k) for k in ('function','api','persistence','page','export','validation'))):
            raise ValueError('Every applicable source requirement needs full consumer mapping')
    for conflict in trace.get('conflicts',[]):
        if not all(conflict.get(k) for k in ('source_locations','discrepancy','implementation_basis','limitation')):
            raise ValueError('Source conflict must preserve discrepancy and explicit chosen basis')
    return trace


def audit(args,require_review=True):
    workspace,output,run=state(args.workspace)
    if digest(BASE/'references/inheritance.json')!=run['rules_sha256']:
        raise ValueError('Frozen run rules changed')
    check_frozen_rules()
    for source in run['sources']:
        if digest(source['path'])!=source['sha256']: raise ValueError('Original source changed')
    paths=delivery_paths(run,output)
    if {p.name for p in output.iterdir()}!={'系统材料'} or {p.name for p in paths['system'].iterdir()}!={'源代码.zip','操作视频.mp4','数据'}:
        raise ValueError('Software-only layout permits only ZIP, MP4 and CSV directory; no Word/chart files')
    evidence_path=no_links(args.evidence)
    if workspace not in evidence_path.parents: raise ValueError('Evidence stays in internal workspace')
    evidence=read_json(evidence_path)
    check_trace(workspace,evidence,run)
    data=check_data(workspace,paths,evidence)
    check_execution(workspace,evidence,run)
    timeline=check_video(workspace,paths,evidence)
    package_receipt=read_json(workspace/'.ssd/source-package.json')
    if package_receipt.get('sha256')!=digest(paths['source_zip']): raise ValueError('Source ZIP changed')
    with zipfile.ZipFile(paths['source_zip']) as z:
        if {i.filename for i in z.infolist()}!=set(package_receipt['members']): raise ValueError('ZIP members differ from explicit allowlist')
        for info in z.infolist():
            content=z.read(info)
            import hashlib
            if hashlib.sha256(content).hexdigest()!=package_receipt['members'][info.filename]: raise ValueError('ZIP member changed')
            if excluded_delivery_document(info.filename): raise ValueError('Excluded guide in source ZIP')
            if Path(info.filename).suffix.lower() in TEXT and ui_hits(info.filename,content.decode('utf-8-sig',errors='strict')):
                raise ValueError('ZIP text policy failed')
    snapshot=tree(output)
    if require_review:
        from model_proof import verify_review
        verify_review(workspace,run,evidence,snapshot,timeline)
    return {'schema_version':1,'status':'passed' if require_review else 'inputs_ready',
            'run_id':run['run_id'],'profile':run['profile'],'snapshot':snapshot,
            'evidence':make_ref(workspace,evidence_path),'data':data,
            'independent_review_verified':require_review,'checked_ns':time.time_ns()}


def finalize(args):
    workspace,_,_=state(args.workspace)
    result=audit(args)
    destination=workspace/'.ssd/finalize.json'
    if destination.exists():
        old=read_json(destination)
        if old['snapshot']==result['snapshot'] and old['evidence']==result['evidence']: return old
        raise ValueError('Finalized run changed; create explicit new revision, never overwrite old acceptance')
    write_json(destination,result,exclusive=True)
    return result


def publish(args):
    workspace,output,run=state(args.workspace)
    final=read_json(inside(workspace,'.ssd/finalize.json'))
    name=args.name or run['case_id']
    if not name or any(c in name for c in '/\\:') or name in {'.','..'}: raise ValueError('Simple independent case folder name required')
    destination=inside(run['delivery_root'],name,must_exist=False)
    intent_path=workspace/'.ssd/publish-intent.json'
    receipt_path=workspace/'.ssd/publish.json'
    intent={'contract':'ssd-publish-intent-v1','run_id':run['run_id'],'workspace':str(workspace),
            'candidate':str(output),'published':str(destination),'snapshot':final['snapshot'],
            'finalize_sha256':digest(workspace/'.ssd/finalize.json')}
    if intent_path.exists():
        if read_json(intent_path)!=intent:raise ValueError('Existing publication intent differs; preserve original destination')
        if not output.exists() and destination.exists():
            if tree(destination)!=intent['snapshot']:raise ValueError('Published target differs from immutable intent')
            ref(workspace,final['evidence'])
            if receipt_path.exists():
                existing=read_json(receipt_path)
                if any(existing.get(k)!=intent[k] for k in ('run_id','published','snapshot','finalize_sha256')):
                    raise ValueError('Existing publication receipt differs')
                return existing
            receipt={'schema_version':1,'run_id':run['run_id'],'case_id':run['case_id'],
                     'published':str(destination),'snapshot':intent['snapshot'],
                     'finalize_sha256':intent['finalize_sha256'],'published_ns':time.time_ns(),
                     'recovered_from_intent':True}
            write_json(receipt_path,receipt,exclusive=True)
            return receipt
    if final['snapshot']!=tree(output): raise ValueError('Candidate changed after finalization')
    evidence=ref(workspace,final['evidence'])
    audit(argparse.Namespace(workspace=str(workspace),evidence=str(evidence)))
    if destination.exists(): raise ValueError('Never overwrite historical published delivery')
    destination.parent.mkdir(parents=True,exist_ok=True)
    if destination.drive.casefold()!=output.drive.casefold(): raise ValueError('Atomic publication requires same volume')
    if not intent_path.exists():write_json(intent_path,intent,exclusive=True)
    os.rename(output,destination)
    receipt={'schema_version':1,'run_id':run['run_id'],'case_id':run['case_id'],
             'published':str(destination),'snapshot':tree(destination),
             'finalize_sha256':digest(workspace/'.ssd/finalize.json'),'published_ns':time.time_ns()}
    if receipt['snapshot']!=final['snapshot']: raise ValueError('Published bytes differ; inspect actual output')
    write_json(receipt_path,receipt,exclusive=True)
    return receipt


def main():
    p=argparse.ArgumentParser(description=__doc__)
    sub=p.add_subparsers(dest='action',required=True)
    q=sub.add_parser('prepare')
    for key in ('workspace','case-id','title','output'): q.add_argument('--'+key,required=True)
    q.add_argument('--source',action='append',required=True)
    q.add_argument('--staging-root',default=str(DEFAULT_STAGING)); q.add_argument('--delivery-root',default=str(DEFAULT_DELIVERY))
    for action in ('status','package','clean-data','audit','finalize','publish','admit-review','review-binding','role-receipt'):
        q=sub.add_parser(action); q.add_argument('--workspace',required=True)
        if action in {'package','clean-data'}: q.add_argument('--manifest',required=True)
        if action in {'audit','finalize','admit-review'}: q.add_argument('--evidence',required=True)
        if action=='admit-review':q.add_argument('--expedited-auth')
        if action=='audit': q.add_argument('--inputs-only',action='store_true')
        if action=='publish': q.add_argument('--name')
        if action=='review-binding':
            q.add_argument('--session-log',required=True);q.add_argument('--call-id',required=True)
        if action=='role-receipt':
            q.add_argument('--session-log',required=True);q.add_argument('--role',choices=['build','repair'],required=True)
            q.add_argument('--outputs',required=True);q.add_argument('--receipt',required=True)
            q.add_argument('--bootstrap',action='store_true');q.add_argument('--source-trace')
    args=p.parse_args()
    try:
        if args.action=='prepare': result=prepare(args)
        elif args.action=='package': result=package(args)
        elif args.action=='clean-data': result=clean_data(args)
        elif args.action=='audit': result=audit(args,not args.inputs_only)
        elif args.action=='finalize': result=finalize(args)
        elif args.action=='publish': result=publish(args)
        elif args.action=='role-receipt':
            from model_proof import role_receipt
            result=role_receipt(args)
        elif args.action in {'admit-review','review-binding'}:
            from model_proof import admit, binding
            result=admit(args) if args.action=='admit-review' else binding(args)
        else:
            workspace,output,run=state(args.workspace)
            receipt=workspace/'.ssd/publish.json'
            result={'run':run,'published':read_json(receipt) if receipt.exists() else None,
                    'candidate_exists':output.exists(),'finalized':(workspace/'.ssd/finalize.json').is_file()}
        print(json.dumps(result,ensure_ascii=False,indent=2)); return 0
    except (ValueError,OSError,KeyError,TypeError,zipfile.BadZipFile) as error:
        print(json.dumps({'status':'blocked','error':str(error)},ensure_ascii=False)); return 2


if __name__=='__main__': raise SystemExit(main())
