"""Regression fixtures for confirmed F01-F08. Never business acceptance."""
import argparse
import json
import os
from pathlib import Path
import sys
import time
import unittest
from unittest.mock import patch
import uuid
import zipfile
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import ssdflow as flow
import model_proof as model
import batch_control as batch
import process_guard as guard
from media_job import Job,launch_suspended
from common import digest,read_json,write_json
import test_delivery

REAL_STALE={'parent_log':r'C:\Users\Administrator\.codex\sessions\2026\10\16\rollout-2026-10-16T09-09-32-01a14241-d132-7441-934f-17a61f154463.jsonl',
 'call_id':'call_8db73754e8614e699b0de5856288b8e1','agent_id':'/root/skill_build',
 'child_log':r'C:\Users\Administrator\.codex\sessions\2026\10\16\rollout-2026-10-16T09-16-58-01a14248-a02e-7560-b391-93c0377cc933.jsonl'}
RESULTS={}


class RepairTests(unittest.TestCase):
    def setUp(self):
        self.f=test_delivery.DeliveryTests();self.f.setUp()
        self.work,self.run,self.root=self.f.work,self.f.run,self.f.root
    def tearDown(self):self.f.tearDown()

    def test_windows_allowlist_same_canonical_names_and_alias_rejection(self):
        args=self.f.fixture()
        file=self.work/'source/backend/app.py';file.parent.mkdir();file.write_text('print(11)\n',encoding='utf8')
        manifest=self.work/'evidence/backslash.json'
        write_json(manifest,{'source_root':'source','files':['backend\\app.py']})
        packed=flow.package(argparse.Namespace(workspace=str(self.work),manifest=str(manifest)))
        probe=self.work/self.f.evidence['package_probe']['path'];v=read_json(probe);v['source_zip_sha256']=packed['sha256'];write_json(probe,v)
        self.f.evidence['package_probe']=flow.make_ref(self.work,probe);write_json(args.evidence,self.f.evidence)
        with zipfile.ZipFile(self.f.output/'系统材料/源代码.zip') as z:self.assertEqual(z.namelist(),['backend/app.py'])
        self.assertEqual(list(packed['members']),['backend/app.py'])
        self.assertEqual(flow.audit(args,False)['status'],'inputs_ready')
        write_json(manifest,{'source_root':'source','files':['backend\\app.py','backend/app.py']})
        with self.assertRaises(ValueError):flow.package(argparse.Namespace(workspace=str(self.work),manifest=str(manifest)))
        RESULTS['F06']={'canonical_member':'backend/app.py','audit':'inputs_ready','alias_duplicate':'rejected'}

    def test_completed_csv_reuses_original_fact_and_rejects_changed_bytes(self):
        args=self.f.fixture()
        with patch.object(flow,'audit_csv_exports',wraps=flow.audit_csv_exports) as full:
            first=flow.audit(args,False)
            plan=self.work/self.f.evidence['data_plan']['path'];write_json(plan,{'new_algorithm_plan':'not a revalidation of completed CSV'})
            self.f.evidence['data_plan']=flow.make_ref(self.work,plan);write_json(args.evidence,self.f.evidence)
            second=flow.audit(args,False)
            self.assertEqual(full.call_count,1);self.assertTrue(second['data']['reused'])
            data=self.f.output/'系统材料/数据/记录.csv'
            data.write_bytes(data.read_bytes().replace(b'1.2500',b'9.2500'))
            with self.assertRaisesRegex(ValueError,'Completed CSV changed'):flow.audit(args,False)
            self.assertEqual(full.call_count,1)
        RESULTS['F07']={'unchanged_audits':2,'full_csv_calls':1,'later_plan_change':'original_fact_reused','changed_csv':'rejected'}

    def test_publish_recovers_after_rename_before_receipt_and_no_overwrite(self):
        args=self.f.fixture();final=flow.audit(args,False);write_json(self.work/'.ssd/finalize.json',final)
        original=flow.write_json
        def interrupted(path,value,exclusive=False):
            if Path(path).name=='publish.json':raise OSError('Isolated injected receipt interruption after rename')
            return original(path,value,exclusive)
        publish_args=argparse.Namespace(workspace=str(self.work),name='recovery-case')
        with patch.object(flow,'audit',return_value={'filesystem_fixture_only':True}),patch.object(flow,'write_json',side_effect=interrupted):
            with self.assertRaises(OSError):flow.publish(publish_args)
        self.assertFalse(self.f.output.exists());self.assertTrue((self.work/'.ssd/publish-intent.json').is_file())
        recovered=flow.publish(publish_args)
        self.assertTrue(recovered['recovered_from_intent']);self.assertEqual(recovered['snapshot'],final['snapshot'])
        self.assertEqual(flow.publish(publish_args),recovered)
        with self.assertRaises(ValueError):flow.publish(argparse.Namespace(workspace=str(self.work),name='other-case'))
        target=Path(recovered['published'])/'系统材料/数据/记录.csv';target.write_bytes(target.read_bytes()+b'bad')
        with self.assertRaises(ValueError):flow.publish(publish_args)
        RESULTS['F08']={'injected_gap':'rename_succeeded_receipt_missing','resume':'recovered_exact_original_intent','repeated_resume':'idempotent','changed_target':'rejected'}

    def test_expedited_parent_must_match_dispatch(self):
        admission={'route':'original-expedited','authorization_validation':{'parent_session_id':'authorized-parent'},'issued_ns':0}
        with patch.object(model,'review_route',return_value={'model':'gpt-6-astra','effort':'low'}),patch.object(model,'dispatch',return_value=({}, {}, {'id':'other-parent'},{})):
            with self.assertRaisesRegex(ValueError,'authorized human parent'):model.dispatch_binding(self.work,{},admission)
        RESULTS['F04']={'cross_parent_dispatch':'rejected','scope':'unit boundary fixture, no real expedited authorization claimed'}

    def prepared_other(self,name):
        source=self.root/(name+'.txt');source.write_text(name,encoding='utf8')
        args=argparse.Namespace(workspace=str(self.root/name),output=str(self.root/'staging'/name),case_id=name,title=name,
            source=[str(source)],staging_root=str(self.root/'staging'),delivery_root=str(self.root/'delivery'))
        return flow.prepare(args)

    def test_ready_excludes_active_case_and_changed_source(self):
        other=self.prepared_other('other');invalid=self.prepared_other('invalid');control=self.root/'control'
        runtime={'session_id':'unit-controller','worker_capacity':3,'session_log':'mocked-capacity-only'}
        with patch.object(batch,'capacity',return_value=runtime):
            batch.register(control,'fair',[{'case_id':r['case_id'],'workspace':r['workspace']} for r in [self.run,other,invalid]],'unit fixture only',os.getpid(),'mock')
            a=batch.mutate(control,'fair',os.getpid(),'queue',self.run['case_id'],'build')
            self.assertTrue(batch.mutate(control,'fair',os.getpid(),'acquire',token=a['token'])['acquired'])
            blocked=batch.mutate(control,'fair',os.getpid(),'queue',self.run['case_id'],'review')
            invalid_q=batch.mutate(control,'fair',os.getpid(),'queue',invalid['case_id'],'review')
            Path(invalid['sources'][0]['path']).write_text('changed',encoding='utf8')
            b=batch.mutate(control,'fair',os.getpid(),'queue',other['case_id'],'build')
            self.assertTrue(batch.mutate(control,'fair',os.getpid(),'acquire',token=b['token'])['acquired'])
            self.assertEqual(batch.mutate(control,'fair',os.getpid(),'acquire',token=blocked['token'])['reason'],'same_case_active_stage')
        RESULTS['F05']={'active_A_build':'retained','waiting_A_review':'ineligible','changed_source_review':'ineligible','B_build':'acquired'}

    def test_stale_real_final_rejected_for_new_run_and_ticket(self):
        # Read genuine current session files. Never fabricate or modify logs.
        if not Path(REAL_STALE['child_log']).exists():self.skipTest('Specific genuine regression session unavailable on this host')
        with self.assertRaisesRegex(ValueError,'post-prepare completion'):
            model.verify_role_completion(self.work,self.run,REAL_STALE,'build')
        control=self.root/'real-stale-control'
        batch.register(control,'stale',[{'case_id':self.run['case_id'],'workspace':str(self.work)}],'isolated regression only',os.getpid(),REAL_STALE['parent_log'])
        q=batch.mutate(control,'stale',os.getpid(),'queue',self.run['case_id'],'build')
        self.assertTrue(batch.mutate(control,'stale',os.getpid(),'acquire',token=q['token'])['acquired'])
        for _ in range(2):
            with self.assertRaisesRegex(ValueError,'original acquired ticket'):
                batch.mutate(control,'stale',os.getpid(),'release',token=q['token'],value=REAL_STALE)
        self.assertEqual(read_json(control/'control.json')['queue'][0]['state'],'active')
        RESULTS['F03_real']={'record':REAL_STALE,'old_real_final_new_run':'rejected','release_attempts':2,'active_ticket':'retained'}

    def test_one_dispatch_cannot_release_two_tickets(self):
        # Unit fixture isolates the replay ledger after real identity verification.
        control=self.root/'replay';runtime={'session_id':'fixture','worker_capacity':3,'session_log':'fixture'}
        value={'parent_log':'fixture','call_id':'one-real-call-placeholder','agent_id':'fixture'}
        with patch.object(batch,'capacity',return_value=runtime):
            batch.register(control,'one',[{'case_id':self.run['case_id'],'workspace':str(self.work)}],'fixture only',os.getpid(),'fixture')
            with patch.object(model,'dispatch',return_value=({}, {}, {'id':'fixture'},{})),patch.object(model,'timestamp',return_value=10**30),patch.object(model,'verify_role_completion',return_value={}):
                first=batch.mutate(control,'one',os.getpid(),'queue',self.run['case_id'],'build')
                batch.mutate(control,'one',os.getpid(),'acquire',token=first['token'])
                batch.mutate(control,'one',os.getpid(),'release',token=first['token'],value=value)
                second=batch.mutate(control,'one',os.getpid(),'queue',self.run['case_id'],'build')
                batch.mutate(control,'one',os.getpid(),'acquire',token=second['token'])
                with self.assertRaisesRegex(ValueError,'already consumed'):
                    batch.mutate(control,'one',os.getpid(),'release',token=second['token'],value=value)
        RESULTS['F03_replay']={'first_release':'completed_in_unit_fixture','second_ticket_same_call':'rejected','scope':'ledger mechanics only, not real completion acceptance'}

    def with_own_job(self,args,action):
        job=Job('Local\\SSDRepair-'+uuid.uuid4().hex);info=None
        try:
            info=launch_suspended(job,args,dict(os.environ));job.k.ResumeThread(info.thread)
            return action(job,info)
        finally:
            job.close()
            if info:
                job.k.WaitForSingleObject(info.process,5000);job.k.CloseHandle(info.thread);job.k.CloseHandle(info.process)

    def test_real_read_command_refused_without_termination(self):
        def action(job,info):
            with self.assertRaisesRegex(ValueError,'live registered case ancestor'):guard.register(self.work,info.pid)
            self.assertIn(info.pid,job.pids())
            RESULTS['F02']={'pid':info.pid,'register':'rejected','own_process_after_rejection':'alive','cleanup':'own_job_finally_only'}
        self.with_own_job([sys.executable,'-c','import time;time.sleep(90)',str(self.work)],action)

    def test_real_unregistered_descendant_tree_stopped(self):
        server=self.work/'server.py';pids=self.work/'pids.json'
        child_code='import subprocess,sys,time,json;from pathlib import Path;p=subprocess.Popen([sys.executable,"-c","import time;time.sleep(90)"]);Path(sys.argv[1]).write_text(json.dumps([__import__("os").getpid(),p.pid]));time.sleep(90)'
        server.write_text('import subprocess,sys,time\nsubprocess.Popen([sys.executable,"-c",'+repr(child_code)+','+repr(str(pids))+'])\ntime.sleep(90)\n',encoding='utf8')
        def action(job,info):
            deadline=time.monotonic()+8
            while not pids.exists() and time.monotonic()<deadline:time.sleep(.05)
            self.assertTrue(pids.exists());children=read_json(pids)
            registered=guard.register(self.work,info.pid)
            receipt=guard.stop(self.work);members=job.pids()
            self.assertEqual(receipt['status'],'stopped',receipt);self.assertEqual(members,[])
            self.assertTrue(set(children).issubset({p['pid'] for p in receipt['processes']}))
            RESULTS['F01']={'root':registered,'children':children,'receipt':receipt,'actual_own_job_members_after_stop':members,'scope':'Only this test unique Job, no unrelated process touched'}
        self.with_own_job([sys.executable,str(server)],action)


if __name__=='__main__':
    result=unittest.main(verbosity=2,exit=False)
    destination=Path(r'E:\研发自动化\skill-evidence\repair-probes.json')
    write_json(destination,{'scope':'Repair regression evidence only, no independent/business pass',
        'checked_ns':time.time_ns(),'results':RESULTS,'tests_run':result.result.testsRun,
        'successful':result.result.wasSuccessful(),'cache':{k:os.environ.get(k) for k in ('TEMP','TMP','TMPDIR','PYTHONPYCACHEPREFIX')}})
    sys.exit(0 if result.result.wasSuccessful() else 1)
