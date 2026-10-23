"""Execute an admitted media command in its own Windows Job before any child code runs."""
import argparse
import ctypes
from ctypes import wintypes
import json
import os
import time
import uuid
from common import digest,inside,no_links,read_json,state,write_json
from batch_control import ROOT,identity,owner,mutate
from media_job import Job,launch_suspended,job_pids


def run(workspace,batch_id,token,owner_pid,receipt,args,timeout):
    workspace,_,run=state(workspace)
    receipt=inside(workspace,receipt,must_exist=False)
    if receipt.exists() or not args or not 0<timeout<=3600:raise ValueError('Fresh receipt, command and bounded timeout required')
    control=read_json(ROOT/'control.json');batch=control['batches'][batch_id];owner(batch,owner_pid)
    q=next(q for q in control['queue'] if q['token']==token and q['batch_id']==batch_id)
    if q['state']!='active' or q['stage'] not in {'capture','evidence'} or q['workspace']!=str(workspace):
        raise ValueError('Actual admitted media token/workspace required')
    name='Local\\SSDMediaInvocation-'+uuid.uuid4().hex
    job=Job(name);info=None;code=None;timed_out=False;bound=False
    report={'run_id':run['run_id'],'workspace':str(workspace),'batch_id':batch_id,'token':token,
            'job_name':name,'args':args,'started_ns':time.time_ns(),'status':'starting'}
    write_json(receipt,report,exclusive=True)
    try:
        info=launch_suspended(job,args,dict(os.environ))
        mutate(ROOT,batch_id,owner_pid,'bind-runtime',token=token,value={'pid':info.pid,'job_name':name,'command':args})
        bound=True;report['pid']=info.pid;report['identity']=identity(info.pid)
        if job.k.ResumeThread(info.thread)==0xffffffff:raise ctypes.WinError(ctypes.get_last_error())
        deadline=time.monotonic()+timeout
        while True:
            result=job.k.WaitForSingleObject(info.process,100)
            if result==0:
                value=wintypes.DWORD()
                if not job.k.GetExitCodeProcess(info.process,ctypes.byref(value)):raise ctypes.WinError(ctypes.get_last_error())
                code=int(value.value);break
            if result!=258:raise ValueError('Exact owned process wait failed')
            if time.monotonic()>=deadline:timed_out=True;break
    except BaseException as error:
        report['error']=str(error)
        raise
    finally:
        job.close() # Only this invocation and its descendants; also on interrupt/failure.
        if info:
            job.k.WaitForSingleObject(info.process,5000)
            job.k.CloseHandle(info.thread);job.k.CloseHandle(info.process)
        remaining=job_pids(name)
        deadline=time.monotonic()+5
        while remaining and time.monotonic()<deadline:
            time.sleep(.05);remaining=job_pids(name)
        report.update(exit_code=code,timed_out=timed_out,finished_ns=time.time_ns(),remaining_pids=remaining,
                      status='completed' if code==0 and not timed_out and not remaining else 'failed')
        write_json(receipt,report)
        if bound and not remaining:
            mutate(ROOT,batch_id,owner_pid,'release',token=token,
                   value={'receipt':receipt.relative_to(workspace).as_posix(),'sha256':digest(receipt),'media_status':report['status']})
    return report


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for k in ('workspace','batch-id','token','receipt'):p.add_argument('--'+k,required=True)
    p.add_argument('--owner-pid',type=int,required=True);p.add_argument('--timeout',type=float,default=600)
    p.add_argument('command',nargs=argparse.REMAINDER);a=p.parse_args()
    try:
        command=a.command[1:] if a.command[:1]==['--'] else a.command
        report=run(a.workspace,a.batch_id,a.token,a.owner_pid,a.receipt,command,a.timeout)
        print(json.dumps({'status':report['status'],'receipt':a.receipt,'remaining_pids':report['remaining_pids']},ensure_ascii=False))
        return 0 if report['status']=='completed' else 2
    except (ValueError,OSError,KeyError,TypeError,StopIteration) as error:
        print(json.dumps({'status':'blocked','error':str(error)},ensure_ascii=False));return 2


if __name__=='__main__':raise SystemExit(main())
