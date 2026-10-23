"""Verify real Codex dispatch/child final records, never manufacture attestations."""
import hashlib
import json
from pathlib import Path
import re
import time
import uuid
from datetime import datetime
from common import digest, inside, no_links, read_json, write_json, state

SESSION_ROOT=Path.home()/'.codex'/'sessions'


def events(path):
    path=no_links(path)
    root=no_links(SESSION_ROOT)
    if root not in path.parents or path.suffix.lower()!='.jsonl':
        raise ValueError('Only actual Codex session logs accepted; workspace transcripts are not proof')
    result=[]
    with path.open(encoding='utf-8') as stream:
        for line in stream:
            try: result.append(json.loads(line))
            except json.JSONDecodeError: continue
    meta=[e['payload'] for e in result if e.get('type')=='session_meta']
    if len(meta)!=1 or not meta[0].get('id'): raise ValueError('Exactly one real session identity required')
    return result,meta[0]


def timestamp(event):
    value=event.get('timestamp')
    parsed=datetime.fromisoformat(value.replace('Z','+00:00'))
    if parsed.tzinfo is None: raise ValueError('Timezone-aware real event chronology required')
    return int(parsed.timestamp()*1_000_000_000)


def event_digest(event):
    return hashlib.sha256(json.dumps(event,ensure_ascii=False,sort_keys=True).encode()).hexdigest()


def log_text(event):
    # Real exec tool inputs can contain multiple escaped Windows separators.
    return re.sub(r'\\+', '/', json.dumps(event,ensure_ascii=False)).casefold()


def case_operations(logged,workspace,after_ns=0):
    needle=str(workspace).replace('\\','/').casefold()
    return [e for e in logged if e.get('type')=='response_item'
            and e.get('payload',{}).get('type') in {'function_call','custom_tool_call'}
            and timestamp(e)>=after_ns and needle in log_text(e)]


def role_receipt(args):
    """Snapshot real completed role scope; only the actual child's final signs it."""
    from ssdflow import make_ref,ref
    workspace,_,run=state(args.workspace)
    logged,meta=events(args.session_log)
    spawn=meta.get('source',{}).get('subagent',{}).get('thread_spawn',{})
    if not spawn.get('agent_path') or not spawn.get('parent_thread_id'):raise ValueError('Actual child session required')
    turns=[e['payload'] for e in logged if e.get('type')=='turn_context']
    effort='high' if args.role=='build' else 'ultra'
    if not turns or any(t.get('model')!='gpt-6.1-sol' or t.get('effort')!=effort for t in turns):raise ValueError('Role receipt requires actual exact runtime')
    names=read_json(no_links(args.outputs))
    if not isinstance(names,list) or not names or any(not isinstance(p,str) for p in names):raise ValueError('Nonempty actual output file list required')
    names=[p.replace('\\','/') for p in names]
    if len(set(names))!=len(names):raise ValueError('Duplicate output scope')
    outputs={p:digest(inside(workspace,p)) for p in names}
    operations=case_operations(logged,workspace,run['created_ns'])
    if not operations:raise ValueError('Real child must perform this case operations after prepare')
    source_trace=getattr(args,'source_trace',None)
    source_ref=None;source_used=None
    if source_trace:
        trace_path=inside(workspace,source_trace);trace=read_json(trace_path)
        if trace.get('sources')!=run['sources']:raise ValueError('Source trace differs from frozen originals')
        trace_needle=str(trace_path).replace('\\','/').casefold()
        if not any(trace_needle in log_text(e) for e in case_operations(logged,workspace)):
            raise ValueError('Actual child must read/use the bound source trace')
        # Preserve the material mapping as used at completion, even if a later
        # repair legitimately adds mappings to its current trace.
        source_used=trace_path.relative_to(workspace).as_posix()
        frozen_trace=workspace/'.ssd'/('role-source-'+uuid.uuid4().hex+'.json')
        write_json(frozen_trace,trace,exclusive=True)
        source_ref=make_ref(workspace,frozen_trace)
    else:
        for source in run['sources']:
            needle=source['path'].replace('\\','/').casefold()
            if not any(needle in log_text(e) or source['sha256'] in log_text(e) for e in logged
                       if e.get('type')=='response_item' and e.get('payload',{}).get('type') in {'function_call','custom_tool_call'}):
                raise ValueError('Actual original read evidence required, or use --source-trace actually read by child')
    for source in run['sources']:
        if digest(source['path'])!=source['sha256']:raise ValueError('Frozen original changed')
    created=timestamp({'timestamp':meta['timestamp']})
    bootstrap=bool(getattr(args,'bootstrap',False))
    if created<run['created_ns'] and not bootstrap:raise ValueError('Pre-prepare builder requires explicit bootstrap receipt')
    result={'contract':'ssd-role-completion-v1','run_id':run['run_id'],'workspace':str(workspace),
            'sources':run['sources'],'role':args.role,'agent_id':spawn['agent_path'],
            'child_session_id':meta['id'],'parent_session_id':spawn['parent_thread_id'],
            'bootstrap':bootstrap,'prepared_ns':run['created_ns'],'completed_ns':time.time_ns(),
            'outputs':outputs,'operations':[{'event_sha256':event_digest(e),'timestamp':e['timestamp']} for e in operations],
            'source_trace':source_ref,'source_trace_used':source_used}
    destination=inside(workspace,args.receipt,must_exist=False)
    write_json(destination,result,exclusive=True)
    return {'agent_id':result['agent_id'],'role_completion':make_ref(workspace,destination)}


def verify_role_completion(workspace,run,record,role,check_outputs=True):
    from ssdflow import ref
    for source in run['sources']:
        if digest(source['path'])!=source['sha256']:raise ValueError('Frozen original changed')
    effort='high' if role=='build' else 'ultra'
    call,result,parent,args=dispatch(record,'gpt-6.1-sol',effort)
    meta,final,raw=child(record,parent,effort)
    created=timestamp({'timestamp':meta['timestamp']})
    if not timestamp(call)<=created<=timestamp(result) or timestamp(final)<max(timestamp(result),run['created_ns']):
        raise ValueError('Current role requires actual fresh child linkage and post-prepare completion')
    receipt_path=ref(workspace,record['completion']);receipt=read_json(receipt_path)
    try:attestation=json.loads(raw)
    except json.JSONDecodeError:raise ValueError('Role latest final must sign the exact completion receipt')
    if attestation.get('agent_id')!=record['agent_id'] or attestation.get('role_completion')!=record['completion']:
        raise ValueError('Actual child final does not sign this completion')
    if any(receipt.get(k)!=v for k,v in {'contract':'ssd-role-completion-v1','run_id':run['run_id'],
            'workspace':str(workspace),'sources':run['sources'],'role':role,'agent_id':record['agent_id'],
            'child_session_id':meta['id'],'parent_session_id':parent['id'],'prepared_ns':run['created_ns']}.items()):
        raise ValueError('Role completion is not bound to current run/source/role/child')
    if not run['created_ns']<=receipt.get('completed_ns',0)<=timestamp(final):raise ValueError('Completion chronology differs from actual final')
    if timestamp(call)<run['created_ns'] and receipt.get('bootstrap') is not True:
        raise ValueError('Pre-prepare role requires explicit auditable bootstrap')
    logged,_=events(record['child_log'])
    actual={event_digest(e):e for e in case_operations(logged,workspace,run['created_ns']) if timestamp(e)<=receipt['completed_ns']}
    if not receipt.get('operations') or any(i['event_sha256'] not in actual or actual[i['event_sha256']]['timestamp']!=i['timestamp'] for i in receipt['operations']):
        raise ValueError('Completion must retain actual post-prepare case tool events')
    if receipt.get('source_trace'):
        trace_path=ref(workspace,receipt['source_trace']);trace=read_json(trace_path)
        if trace.get('sources')!=run['sources']:raise ValueError('Role source trace changed')
        needle=str(inside(workspace,receipt['source_trace_used'],must_exist=False)).replace('\\','/').casefold()
        if not any(needle in log_text(e) for e in case_operations(logged,workspace)):raise ValueError('No actual source trace use')
    else:
        tools=[e for e in logged if e.get('type')=='response_item' and e.get('payload',{}).get('type') in {'function_call','custom_tool_call'}]
        if any(not any(s['path'].replace('\\','/').casefold() in log_text(e) or s['sha256'] in log_text(e) for e in tools) for s in run['sources']):
            raise ValueError('No actual current original use')
    if not isinstance(receipt.get('outputs'),dict) or not receipt['outputs']:raise ValueError('Actual output scope required')
    for name,sha in receipt['outputs'].items():
        path=inside(workspace,name)
        if check_outputs and digest(path)!=sha:raise ValueError('Role completed output changed: '+name)
    return {'call':call,'result':result,'parent':parent,'child':meta,'final':final,'receipt':receipt}


def dispatch(record,model,effort):
    logged,meta=events(record['parent_log'])
    calls=[e for e in logged if e.get('type')=='response_item' and e.get('payload',{}).get('call_id')==record['call_id'] and e['payload'].get('type')=='function_call']
    outputs=[e for e in logged if e.get('type')=='response_item' and e.get('payload',{}).get('call_id')==record['call_id'] and e['payload'].get('type')=='function_call_output']
    if len(calls)!=1 or len(outputs)!=1: raise ValueError('One actual spawn call and matching output required')
    call,result=calls[0],outputs[0]
    payload=call['payload']
    if payload.get('name','').split('.')[-1]!='spawn_agent': raise ValueError('Only actual explicit spawn accepted')
    args=json.loads(payload['arguments'])
    if args.get('model')!=model or args.get('reasoning_effort')!=effort or args.get('fork_turns')!='none':
        raise ValueError('Exact role model/effort/fork required; unavailable model cannot silently degrade')
    output=result['payload']['output']
    if isinstance(output,str): output=json.loads(output)
    if output.get('status') not in {None,'running'} or output.get('error') or output.get('task_name')!=record['agent_id']:
        raise ValueError('Actual successful spawn result must match agent identity')
    return call,result,meta,args


def child(record,parent,effort,model='gpt-6.1-sol'):
    logged,meta=events(record['child_log'])
    spawn=meta.get('source',{}).get('subagent',{}).get('thread_spawn',{})
    if meta['id']==parent['id'] or spawn.get('parent_thread_id')!=parent['id'] or spawn.get('agent_path')!=record['agent_id']:
        raise ValueError('Actual separate child identity and exact parent/agent linkage required')
    turns=[e['payload'] for e in logged if e.get('type')=='turn_context']
    if not turns or any(t.get('model')!=model or t.get('effort')!=effort for t in turns):
        raise ValueError('Real child runtime model differs from required role')
    finals=[e for e in logged if e.get('type')=='response_item' and e.get('payload',{}).get('type')=='message'
            and e['payload'].get('role')=='assistant'
            and (e['payload'].get('phase')=='final_answer' or e['payload'].get('channel')=='final')]
    if not finals: raise ValueError('Actual completed child final required')
    parts=finals[-1]['payload'].get('content',[])
    if not parts or any(not isinstance(p.get('text'),str) or p.get('encrypted_content') for p in parts):
        raise ValueError('Unreadable final cannot attest acceptance')
    raw=''.join(p['text'] for p in parts)
    raw=re.sub(r'\s*<oai-mem-citation>[\s\S]*?</oai-mem-citation>\s*$','',raw)
    return meta,finals[-1],raw


def admit(args):
    from ssdflow import audit
    report=audit(args,require_review=False)
    workspace,_,run=state(args.workspace)
    evidence=read_json(args.evidence)
    scope={k:v for k,v in evidence.items() if k not in {'review','model_dispatch'}}
    admission={'contract':'ssd-independent-ultra-v1','token':uuid.uuid4().hex,
               'run_id':run['run_id'],'workspace':str(workspace),'issued_ns':time.time_ns(),
               'snapshot':report['snapshot'],'scope':scope,'model':'gpt-6.1-sol','effort':'ultra'}
    if getattr(args,'expedited_auth',None):
        from expedited import validate
        authorization=read_json(no_links(args.expedited_auth))
        verified=validate(workspace,authorization)
        admission.update(route='original-expedited',model=verified['model'],effort=verified['effort'],
                         expedited_authorization=authorization,authorization_validation=verified)
    else:admission['route']='ordinary'
    # A revision receives a new immutable admission; never mutate an old review scope.
    path=workspace/'.ssd'/('review-admission-'+admission['token']+'.json')
    write_json(path,admission,exclusive=True)
    return {'path':path.relative_to(workspace).as_posix(),'sha256':digest(path),'token':admission['token']}


def review_route(workspace,admission):
    if admission.get('route','ordinary')=='ordinary':
        expected={'model':'gpt-6.1-sol','effort':'ultra'}
    elif admission.get('route')=='original-expedited':
        from expedited import validate
        verified=validate(workspace,admission['expedited_authorization'])
        if verified!=admission.get('authorization_validation'):raise ValueError('Frozen expedited scope authorization changed')
        expected={'model':'gpt-6-astra','effort':'low'}
    else:raise ValueError('Unknown review route')
    if any(admission.get(k)!=v for k,v in expected.items()):raise ValueError('Admission model cannot override exact authorized review route')
    return expected


def dispatch_binding(workspace,record,admission):
    route=review_route(workspace,admission)
    call,result,parent,args=dispatch(record,route['model'],route['effort'])
    if admission.get('route')=='original-expedited' and admission['authorization_validation'].get('parent_session_id')!=parent['id']:
        raise ValueError('Actual expedited dispatch parent differs from authorized human parent')
    if timestamp(call)<admission['issued_ns']: raise ValueError('Admission must precede real review dispatch')
    message=args.get('message','')
    encrypted=isinstance(message,str) and bool(re.fullmatch(r'gAAAA[A-Za-z0-9_=-]+',message))
    if not encrypted and not all(s in message for s in (admission['token'],admission['run_id'],str(workspace))):
        raise ValueError('Review dispatch must name admitted token/run/workspace')
    binding={'contract':'ssd-independent-ultra-v1','token':admission['token'],'run_id':admission['run_id'],
             'workspace':str(workspace),'parent_session_id':parent['id'],'call_id':record['call_id'],
             'dispatch_message_sha256':hashlib.sha256(message.encode()).hexdigest(),
             'dispatch_event_sha256':hashlib.sha256(json.dumps([call,result],ensure_ascii=False,sort_keys=True).encode()).hexdigest()}
    return binding,call,result,parent


def binding(args):
    workspace,_,_=state(args.workspace)
    spec=read_json(workspace/'.ssd/model-dispatch.json')
    from ssdflow import ref
    admission=read_json(ref(workspace,spec['review']['admission']))
    record={'parent_log':args.session_log,'call_id':args.call_id,'agent_id':spec['review']['agent_id']}
    return dispatch_binding(workspace,record,admission)[0]


def verify_visual(workspace,proof,expected,video_hash,seen_proofs=None):
    """Retain an already signed, byte-identical video's first actual visual review."""
    from ssdflow import ref
    visual=proof.get('video_visual',{})
    if visual.get('decision')!='pass':raise ValueError('Independent video visual pass required')
    inherited=visual.get('inherited_review')
    if inherited:
        path=ref(workspace,inherited['proof'])
        previous=read_json(path)
        history=set(seen_proofs or [])
        if digest(path) in history or len(history)>8:raise ValueError('Cyclic/overlong inherited visual chain')
        history.add(digest(path))
        if previous.get('decision')!='pass' or previous.get('snapshot',{}).get('系统材料/操作视频.mp4')!=video_hash:
            raise ValueError('Only unchanged actually accepted video can retain earlier review')
        record=inherited['dispatch']
        admission=read_json(ref(workspace,record['admission']))
        bound,call,result,parent=dispatch_binding(workspace,record,admission)
        route=review_route(workspace,admission)
        meta,final,raw=child(record,parent,route['effort'],route['model'])
        if not timestamp(call)<=timestamp({'timestamp':meta.get('timestamp')})<=timestamp(result):
            raise ValueError('Inherited visual reviewer must be exact admitted fresh ultra child')
        try: attestation=json.loads(raw)
        except json.JSONDecodeError:raise ValueError('Prior actual visual final unreadable')
        if (attestation.get('reviewer_agent_id')!=record['agent_id'] or previous.get('reviewer_agent_id')!=record['agent_id']
                or attestation.get('review_evidence_sha256')!=digest(path)
                or attestation.get('review_dispatch_binding')!=bound or previous.get('review_dispatch_binding')!=bound):
            raise ValueError('Prior actual reviewer final must sign exact retained visual proof')
        return verify_visual(workspace,previous,expected,video_hash,history)
    seen=visual.get('viewed',[])
    if {str(no_links(i['file'])):i['sha256'] for i in seen}!=expected:
        raise ValueError('First independent visual review must inspect every contact sheet/key original frame')


def verify_review(workspace,run,evidence,snapshot,timeline):
    from ssdflow import ref
    spec=read_json(ref(workspace,evidence['model_dispatch']))
    builds=spec.get('build',[])
    repairs=spec.get('repair',[])
    if not isinstance(builds,list) or not builds: raise ValueError('Actual high builder records required')
    agents=set(); sessions=set(); parents=set()
    completions=[];used_calls=set()
    for role,records,effort in [('build',builds,'high'),('repair',repairs,'ultra')]:
        for record in records:
            verified=verify_role_completion(workspace,run,record,role,check_outputs=False)
            call,result,parent,meta=verified['call'],verified['result'],verified['parent'],verified['child']
            key=(parent['id'],record['call_id'])
            if key in used_calls:raise ValueError('One actual role dispatch cannot satisfy multiple records')
            used_calls.add(key);completions.append(verified['receipt'])
            if record['agent_id'] in agents or meta['id'] in sessions: raise ValueError('Distinct role agents required')
            agents.add(record['agent_id']);sessions.add(meta['id']);parents.add(parent['id'])
    latest={}
    for receipt in sorted(completions,key=lambda r:r['completed_ns']):latest.update(receipt['outputs'])
    for name,sha in latest.items():
        if digest(inside(workspace,name))!=sha:raise ValueError('Latest signed role output changed: '+name)
    record=spec['review']
    admission=read_json(ref(workspace,record['admission']))
    if (admission.get('run_id')!=run['run_id'] or admission.get('workspace')!=str(workspace)
            or admission.get('snapshot')!=snapshot
            or admission.get('scope')!={k:v for k,v in evidence.items() if k not in {'review','model_dispatch'}}):
        raise ValueError('Current files/evidence differ from actual admitted review scope')
    binding,call,result,parent=dispatch_binding(workspace,record,admission)
    route=review_route(workspace,admission)
    meta,final,raw=child(record,parent,route['effort'],route['model'])
    created=timestamp({'timestamp':meta.get('timestamp')})
    if (record['agent_id'] in agents or meta['id'] in sessions or meta['id'] in parents
            or not timestamp(call)<=created<=timestamp(result) or timestamp(final)<timestamp(result)):
        raise ValueError('Review must be a fresh independent ultra child created by this admitted dispatch')
    proof_path=ref(workspace,evidence['review'])
    proof=read_json(proof_path)
    try: attestation=json.loads(raw)
    except json.JSONDecodeError: raise ValueError('Reviewer latest final must be complete JSON attestation')
    if (attestation.get('reviewer_agent_id')!=record['agent_id']
            or attestation.get('review_evidence_sha256')!=digest(proof_path)
            or attestation.get('review_dispatch_binding')!=binding):
        raise ValueError('Independent child latest final must sign exact proof SHA256 and real dispatch binding')
    if (proof.get('decision')!='pass' or proof.get('reviewer_agent_id')!=record['agent_id']
            or proof.get('run_id')!=run['run_id'] or proof.get('snapshot')!=snapshot
            or proof.get('review_dispatch_binding')!=binding):
        raise ValueError('Reviewer proof does not accept current exact delivery')
    required={'source_fidelity','algorithm','api','persistence','browser','export','data','source_package','video','lifecycle'}
    reviews=proof.get('reviews',[])
    if not required.issubset({r.get('kind') for r in reviews}) or any(r.get('decision')!='pass' or not r.get('evidence') for r in reviews):
        raise ValueError('Concrete independent findings required in every applicable quality category')
    expected={str(no_links(i['file'])):i['sha256'] for i in [*timeline['contact_sheets'],*timeline['interaction_frames'],
                                                        *[f for f in timeline['frames'] if f['type'] in {'first','last'}]]}
    verify_visual(workspace,proof,expected,snapshot['系统材料/操作视频.mp4'])
    return {'status':'verified','reviewer_agent_id':record['agent_id'],'proof_sha256':digest(proof_path)}
