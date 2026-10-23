"""Independent global software-only batch queue; no model calls or old queue access."""
import argparse
import contextlib
import ctypes
from ctypes import wintypes
import hashlib
import json
import os
from pathlib import Path
import re
import time
import uuid
from common import digest, no_links, read_json, write_json, state
from model_proof import events

ROOT=Path(r'E:\研发自动化\work\.ssd-control')
STAGES={'build','repair','review','capture','evidence'}


def identity(pid):
    if os.name!='nt':
        import subprocess
        r=subprocess.run(['ps','-p',str(pid),'-o','lstart='],capture_output=True,text=True,check=True)
        if not r.stdout.strip(): raise ValueError('Owner is not alive')
        return {'pid':pid,'created':r.stdout.strip()}
    k=ctypes.WinDLL('kernel32',use_last_error=True)
    k.OpenProcess.argtypes=[wintypes.DWORD,wintypes.BOOL,wintypes.DWORD];k.OpenProcess.restype=wintypes.HANDLE
    k.GetProcessTimes.argtypes=[wintypes.HANDLE]+[ctypes.POINTER(wintypes.FILETIME)]*4
    k.CloseHandle.argtypes=[wintypes.HANDLE]
    handle=k.OpenProcess(0x1000,False,pid)
    if not handle: raise ValueError('Owner PID is unavailable')
    try:
        slots=[wintypes.FILETIME() for _ in range(4)]
        if not k.GetProcessTimes(handle,*[ctypes.byref(v) for v in slots]): raise ValueError('Owner creation identity unavailable')
        return {'pid':pid,'created':(slots[0].dwHighDateTime<<32)|slots[0].dwLowDateTime}
    finally:k.CloseHandle(handle)


def capacity(log):
    logged,meta=events(log)
    if isinstance(meta.get('source'),dict) and meta['source'].get('subagent'):
        raise ValueError('A child cannot claim another parent runtime group')
    maximum=None
    for event in logged:
        payload=event.get('payload',{})
        kinds=payload.get('internal_chat_message_metadata_passthrough',{}).get('content_item_kinds',[])
        if payload.get('role')!='developer' or 'multi_agent.role_instructions' not in kinds: continue
        raw=''.join(p.get('text','') for p in payload.get('content',[]))
        match=re.search(r'There are (\d+) available concurrency slots',raw)
        if match: maximum=max(0,int(match[1])-1)
    if maximum is None: raise ValueError('Real platform concurrency declaration unavailable; do not invent capacity')
    return {'session_id':meta['id'],'worker_capacity':min(12,maximum),'session_log':str(no_links(log))}


def resources():
    if os.name!='nt': raise ValueError('This media resource admission is verified only on Windows')
    class Memory(ctypes.Structure):
        _fields_=[('length',wintypes.DWORD),('load',wintypes.DWORD)]+[(n,ctypes.c_ulonglong) for n in ('total_phys','avail_phys','total_page','avail_page','total_virtual','avail_virtual','extended')]
    mem=Memory();mem.length=ctypes.sizeof(mem)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(mem)): raise ValueError('Memory sample unavailable')
    def times():
        values=[wintypes.FILETIME() for _ in range(3)]
        if not ctypes.windll.kernel32.GetSystemTimes(*[ctypes.byref(v) for v in values]): raise ValueError('CPU sample unavailable')
        return [(v.dwHighDateTime<<32)|v.dwLowDateTime for v in values]
    before=times();time.sleep(.2);after=times()
    idle,kernel,user=[b-a for a,b in zip(before,after)]
    return {'available_mb':min(mem.avail_phys,mem.avail_page)//(1024*1024),
            'logical_cpu':os.cpu_count() or 1,'cpu_percent':100*(1-idle/max(1,kernel+user))}


@contextlib.contextmanager
def locked(root):
    root=no_links(root);root.mkdir(parents=True,exist_ok=True)
    path=root/'mutation.lock'
    deadline=time.monotonic()+3
    while True:
        try:
            handle=path.open('x',encoding='utf-8');break
        except FileExistsError:
            if time.monotonic()>=deadline: raise ValueError('Queue lock busy; preserve live lock and resume later')
            time.sleep(.05)
    try:
        handle.write(str(os.getpid()));handle.close()
        file=root/'control.json'
        value=read_json(file) if file.exists() else {'schema_version':1,'batches':{},'queue':[],'turn':0,'lane_last':{},'last_group':{}}
        yield value
        pending=root/('control-'+uuid.uuid4().hex+'.pending')
        write_json(pending,value,exclusive=True);os.replace(pending,file)
    finally:
        if not handle.closed:handle.close()
        path.unlink()


def owner(batch,pid):
    if batch['owner']!=identity(pid): raise ValueError('Only the registered live owner may mutate this batch')


def runnable(control,entry,active):
    """Use the same case/run/source/authorization predicates before selection."""
    batch=control['batches'][entry['batch_id']]
    case=next(c for c in batch['cases'] if c['case_id']==entry['case_id'])
    if entry['state']!='waiting' or case['state'] not in {'ready','active'}:return False
    if any(a['workspace']==entry['workspace'] for a in active):return False
    try:
        if batch['owner']!=identity(batch['owner']['pid']):return False
        _,_,run=state(entry['workspace'])
        if run['run_id']!=case['run_id'] or any(digest(s['path'])!=s['sha256'] for s in run['sources']):return False
        if entry['stage']=='review' and case.get('expedited_authorization'):
            from expedited import validate
            verified=validate(entry['workspace'],case['expedited_authorization'])
            if verified!=case['expedited_authorization_binding'] or verified['parent_session_id']!=batch['group']['session_id']:return False
        return True
    except (ValueError,OSError,KeyError):return False


def register(root,batch_id,cases,authorization,pid,parent_log):
    if not re.fullmatch(r'[A-Za-z0-9_-]+',batch_id) or not str(authorization).strip(): raise ValueError('Stable batch id and explicit user authorization reference required')
    group=capacity(parent_log)
    entries=[]
    for case in cases:
        workspace,_,run=state(case['workspace'])
        if case['case_id']!=run['case_id']: raise ValueError('Case id differs from prepared run')
        entries.append({'case_id':run['case_id'],'title':run['title'],'workspace':str(workspace),
                        'source_key':hashlib.sha256(json.dumps(sorted(s['sha256'] for s in run['sources'])).encode()).hexdigest(),
                        'run_id':run['run_id'],'state':'ready'})
    if len({c['case_id'] for c in entries})!=len(entries): raise ValueError('Duplicate case id in batch')
    with locked(root) as control:
        if batch_id in control['batches']: raise ValueError('Existing batch; status and resume, never reset')
        old={c['source_key']:(bid,c['case_id']) for bid,b in control['batches'].items() for c in b['cases'] if c['state']!='duplicate'}
        for case in entries:
            if case['source_key'] in old:case.update(state='duplicate',duplicate_of=old[case['source_key']])
            else:old[case['source_key']]=(batch_id,case['case_id'])
        manifest_sha=hashlib.sha256(json.dumps([{k:c[k] for k in ('case_id','title','workspace','source_key','run_id')} for c in entries],sort_keys=True,ensure_ascii=False).encode()).hexdigest()
        control['batches'][batch_id]={'owner':identity(pid),'group':group,'authorization':authorization,'cases':entries,'case_manifest_sha256':manifest_sha,'registered_ns':time.time_ns()}
    return {'batch_id':batch_id,'cases':entries,'runtime':group}


def mutate(root,batch_id,pid,action,case_id=None,stage=None,token=None,value=None):
    with locked(root) as control:
        batch=control['batches'][batch_id]
        if action=='recover-owner':
            try: old_live=identity(batch['owner']['pid'])==batch['owner']
            except (ValueError,OSError):old_live=False
            if old_live:raise ValueError('Original owner still live; no stealing active owner')
            if not value or not value.get('parent_log') or not value.get('reason'):raise ValueError('Actual new controller log and recovery reason required')
            group=capacity(value['parent_log'])
            if any(q['state']=='active' and q['batch_id']==batch_id for q in control['queue']) and group['session_id']!=batch['group']['session_id']:
                raise ValueError('Unknown active ownership retained; recover original parent or prove cleanup first')
            batch.setdefault('owner_history',[]).append({'previous':batch['owner'],'reason':value['reason'],'at_ns':time.time_ns()})
            batch.update(owner=identity(pid),group=group);return batch
        owner(batch,pid)
        case=next((c for c in batch['cases'] if c['case_id']==case_id),None) if case_id else None
        if action=='expedite':
            if not case or not value:raise ValueError('Current case and real human authorization record required')
            from expedited import validate
            verified=validate(case['workspace'],value)
            if verified['parent_session_id']!=batch['group']['session_id']:raise ValueError('Expedited user authorization belongs to another controller parent')
            case['expedited_authorization']=value
            case['expedited_authorization_binding']=verified
            for entry in control['queue']:
                if entry['batch_id']==batch_id and entry['case_id']==case_id and entry['state']=='waiting':
                    entry['priority']=10
            return {'case_id':case_id,'authorization':verified,'active_retained':True}
        if action=='queue':
            if not case or stage not in STAGES or case['state'] not in {'ready','active'}: raise ValueError('Runnable case and supported stage required')
            old=next((q for q in control['queue'] if q['batch_id']==batch_id and q['case_id']==case_id and q['stage']==stage and q['state'] in {'waiting','active'}),None)
            if old:return old
            q={'batch_id':batch_id,'case_id':case_id,'workspace':case['workspace'],'stage':stage,'token':uuid.uuid4().hex,
               'submitted_ns':max(time.time_ns(),max((e['submitted_ns'] for e in control['queue']),default=0)+1),
               'state':'waiting','priority':10 if case.get('expedited_authorization') else 0,'group':batch['group']['session_id']}
            control['queue'].append(q);return q
        if action=='block':
            if not case or not value or not value.get('reason') or not value.get('resume_when'): raise ValueError('Concrete block reason and release condition required')
            if any(q['state']=='active' and q['case_id']==case_id and q['batch_id']==batch_id for q in control['queue']): raise ValueError('Finish real active work before blocking')
            case.update(state='blocked',block=value);return case
        if action=='resume':
            if not case or case['state']!='blocked': raise ValueError('Only blocked cases resume')
            case.update(state='ready');return case
        if action=='complete':
            if not case:raise ValueError('Unknown case')
            workspace=no_links(case['workspace']);receipt=read_json(workspace/'.ssd/publish.json')
            from ssdflow import tree
            if receipt['run_id']!=case['run_id'] or receipt['snapshot']!=tree(receipt['published']): raise ValueError('Current real published receipt required')
            if any(q['state']=='active' and q['case_id']==case_id and q['batch_id']==batch_id for q in control['queue']): raise ValueError('Release actual work before complete')
            case.update(state='delivered',receipt_sha256=digest(workspace/'.ssd/publish.json'));return case
        q=next(q for q in control['queue'] if q['token']==token and q['batch_id']==batch_id)
        if action=='acquire':
            if q['state']!='waiting':raise ValueError('Acquire original waiting token only')
            active=[e for e in control['queue'] if e['state']=='active']
            current_case=next(c for c in batch['cases'] if c['case_id']==q['case_id'])
            if current_case['state'] not in {'ready','active'}:raise ValueError('Case is blocked/delivered/duplicate')
            _,_,current_run=state(q['workspace'])
            if current_run['run_id']!=current_case['run_id'] or any(digest(s['path'])!=s['sha256'] for s in current_run['sources']):raise ValueError('Prepared run or source changed; preserve waiting token')
            if q['stage']=='review':
                if current_case.get('expedited_authorization'):
                    from expedited import validate
                    verified=validate(q['workspace'],current_case['expedited_authorization'])
                    if verified!=current_case['expedited_authorization_binding']:raise ValueError('Current expedited authorization changed')
                    if verified['parent_session_id']!=batch['group']['session_id']:raise ValueError('Expedited dispatch group differs from authorized human parent')
                    q['review_route']=verified
                else:q['review_route']={'route':'ordinary','model':'gpt-6.1-sol','effort':'ultra'}
            if any(e['workspace']==q['workspace'] for e in active):
                return {'acquired':False,'reason':'same_case_active_stage'}
            if q['stage'] in {'capture','evidence'}:
                media=[e for e in active if e['stage'] in {'capture','evidence'}]
                if any(e['workspace']==q['workspace'] for e in media):return {'acquired':False,'reason':'workspace_media_active'}
                if q['stage']=='evidence':
                    if media:return {'acquired':False,'reason':'media_busy'}
                else:
                    if any(e['stage']=='evidence' for e in media) or any(e['state']=='waiting' and e['stage']=='evidence' for e in control['queue']): return {'acquired':False,'reason':'evidence_drain'}
                    count=len(media)+1;sample=resources()
                    if count>4 or sample['available_mb']<4096+2048*(count-1) or sample['logical_cpu']<4*count+2 or sample['cpu_percent']>85:
                        return {'acquired':False,'reason':'resources_wait','sample':sample}
                    q['resources']=sample
            else:
                models=[e for e in active if e['stage'] not in {'capture','evidence'}]
                # Re-read the real latest platform declaration; an arbitrary CLI capacity is never used.
                verified=capacity(batch['group']['session_log']);batch['group']=verified
                if len(models)>=12 or sum(e['group']==q['group'] for e in models)>=verified['worker_capacity']:
                    return {'acquired':False,'reason':'actual_model_capacity'}
                ready=[]
                for e in control['queue']:
                    b=control['batches'][e['batch_id']]
                    c=next(c for c in b['cases'] if c['case_id']==e['case_id'])
                    if e['stage'] in {'capture','evidence'} or not runnable(control,e,active):continue
                    try:
                        if b['owner']!=identity(b['owner']['pid']):continue
                        cap=capacity(b['group']['session_log'])['worker_capacity']
                    except (ValueError,OSError):continue
                    if sum(a['group']==e['group'] for a in models)>=cap:continue
                    ready.append(e)
                def order(e):
                    lane=e['stage'];aged=time.time_ns()-e['submitted_ns']>=300_000_000_000
                    initial={'review':0,'repair':1,'build':2}[lane]
                    last_high=control.get('last_high',{}).get(lane,False)
                    high=e.get('priority',0)>=10
                    return (control['lane_last'].get(lane,0),initial if control['lane_last'].get(lane,0)==0 else 0,
                            not aged, high==last_high,control['last_group'].get(e['group'],0),e['submitted_ns'])
                selected=min(ready,key=order) if ready else None
                if selected is not q:return {'acquired':False,'reason':'fair_ready_selection','selected':selected}
                control['turn']+=1;control['lane_last'][q['stage']]=control['turn'];control['last_group'][q['group']]=control['turn']
                control.setdefault('last_high',{})[q['stage']]=q.get('priority',0)>=10
            q.update(state='active',acquired_ns=time.time_ns())
            next(c for c in batch['cases'] if c['case_id']==q['case_id'])['state']='active'
            return {'acquired':True,**q}
        if action=='bind-runtime':
            if q['state']!='active' or not value or not value.get('pid'):raise ValueError('Active runtime identity required')
            if q['stage'] in {'capture','evidence'}:
                from media_job import job_pids
                if not value.get('job_name') or value['pid'] not in job_pids(value['job_name']):raise ValueError('Real media PID must already belong to its unique job')
            q['runtime']={**value,'identity':identity(value['pid'])};return q
        if action=='release':
            if q['state']!='active':raise ValueError('Release original active only')
            if q['stage'] in {'capture','evidence'}:
                runtime=q.get('runtime')
                if not runtime or not runtime.get('job_name'):raise ValueError('No real media Job binding; retain cleanup_pending')
                from media_job import job_pids
                if job_pids(runtime['job_name']):raise ValueError('Media Job still has live members')
            else:
                if not value:raise ValueError('Actual completed model dispatch record required')
                from model_proof import dispatch,child,timestamp,verify_role_completion,dispatch_binding
                route=q.get('review_route',{'model':'gpt-6.1-sol','effort':'high' if q['stage']=='build' else 'ultra'})
                effort=route['effort']
                call,result,parent,_=dispatch(value,route['model'],effort)
                if parent['id']!=q['group']:raise ValueError('Actual model belongs to another controller group')
                if timestamp(call)<q['acquired_ns']:raise ValueError('Actual dispatch must follow this original acquired ticket; no retroactive admission')
                replay={'parent_session_id':parent['id'],'call_id':value['call_id']}
                if any(e.get('model_call')==replay for e in control['queue']):raise ValueError('Actual model dispatch already consumed by another ticket')
                workspace,_,run=state(q['workspace'])
                if q['stage'] in {'build','repair'}:
                    verify_role_completion(workspace,run,value,q['stage'])
                else:
                    from ssdflow import ref
                    admission=read_json(ref(workspace,value['admission']))
                    if admission.get('run_id')!=run['run_id'] or admission.get('workspace')!=str(workspace):raise ValueError('Review release requires this run admission')
                    binding,_,_,_=dispatch_binding(workspace,value,admission)
                    _,final,raw=child(value,parent,effort,route['model'])
                    try:attestation=json.loads(raw)
                    except json.JSONDecodeError:raise ValueError('Review latest final must sign actual current binding')
                    if (timestamp(final)<timestamp(result) or attestation.get('reviewer_agent_id')!=value['agent_id']
                            or attestation.get('review_dispatch_binding')!=binding
                            or not re.fullmatch(r'[0-9a-f]{64}',attestation.get('review_evidence_sha256',''))):
                        raise ValueError('Actual reviewer final does not complete this current dispatch')
                q['model_call']=replay
            q.update(state='completed',finished_ns=time.time_ns(),result=value)
            next(c for c in batch['cases'] if c['case_id']==q['case_id'])['state']='ready'
            return q
        raise ValueError('Unsupported mutation')


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=['register','status','queue','acquire','bind-runtime','release','block','resume','complete','recover-owner','expedite'])
    p.add_argument('--batch-id',required=True);p.add_argument('--pid',type=int);p.add_argument('--case-id');p.add_argument('--stage');p.add_argument('--token');p.add_argument('--value');p.add_argument('--cases');p.add_argument('--authorization');p.add_argument('--parent-log')
    a=p.parse_args()
    try:
        if a.action=='status':
            c=read_json(ROOT/'control.json');result={'batch':c['batches'][a.batch_id],'queue':[q for q in c['queue'] if q['batch_id']==a.batch_id]}
        elif a.action=='register':result=register(ROOT,a.batch_id,read_json(a.cases),a.authorization,a.pid,a.parent_log)
        else:result=mutate(ROOT,a.batch_id,a.pid,a.action,a.case_id,a.stage,a.token,read_json(a.value) if a.value else None)
        print(json.dumps(result,ensure_ascii=False,indent=2));return 0
    except (ValueError,OSError,KeyError,TypeError,StopIteration) as error:
        print(json.dumps({'status':'blocked','error':str(error)},ensure_ascii=False));return 2


if __name__=='__main__':raise SystemExit(main())
