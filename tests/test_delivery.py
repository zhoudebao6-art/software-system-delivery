"""Isolated invariant fixtures, NEVER production acceptance or fabricated session logs."""
import argparse
import csv
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import ssdflow as flow
import model_proof
import package_probe
import expedited
import batch_control
from common import digest,write_json,read_json


class DeliveryTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='ssd-unit-',dir=os.environ['TEMP'])
        self.root=Path(self.temp.name);self.work=self.root/'work';self.output=self.root/'staging'/'case-v1'
        self.source=self.root/'input.txt';self.source.write_text('Input definition',encoding='utf-8')
        self.args=argparse.Namespace(workspace=str(self.work),output=str(self.output),case_id='case-1',title='检测系统',
            source=[str(self.source)],staging_root=str(self.root/'staging'),delivery_root=str(self.root/'delivery'))
        self.run=flow.prepare(self.args)
        self.evidence={}

    def tearDown(self):self.temp.cleanup()

    def item(self,name,value):
        p=self.work/'evidence'/name
        if isinstance(value,str):p.parent.mkdir(exist_ok=True,parents=True);p.write_text(value,encoding='utf-8')
        else:write_json(p,value)
        return flow.make_ref(self.work,p)

    def fixture(self):
        code=self.work/'source'/'app.py';code.parent.mkdir();code.write_text('def value():\n    return 4 + 7\n',encoding='utf-8')
        manifest=self.work/'evidence'/'package.json';write_json(manifest,{'source_root':'source','files':['app.py']})
        flow.package(argparse.Namespace(workspace=str(self.work),manifest=str(manifest)))
        data=self.output/'系统材料'/'数据'/'记录.csv'
        with data.open('w',encoding='utf-8-sig',newline='') as stream:
            csv.writer(stream).writerows([['对象编号','时刻','状态','读数'],['OBJ_01','2026-10-16T00:00:00','正常','1.2500'],['OBJ_01','2026-10-16T00:00:01','异常','2.5000']])
        schema={'记录.csv':{'columns':{'对象编号':{'kind':'id','pattern':'OBJ_[0-9]{2}','meaning':'对象'},
                '时刻':{'kind':'timestamp','meaning':'时刻'},'状态':{'kind':'enum','values':['正常','异常'],'meaning':'状态'},
                '读数':{'kind':'number','unit':'mm','meaning':'读数'}},'primary_key_kind':'natural',
                'primary_key':['对象编号','时刻'],'effective_key':['对象编号','时刻'],'object_columns':['对象编号'],
                'time_column':'时刻','event_column':'状态'}}
        self.evidence['data_plan']=self.item('plan.json',{'export_schema':schema,'name_review':{'记录.csv':{
            'sha256':digest(data),'filename_checked':True,'columns_checked':True,'text_checked':True,'evidence':'Isolated unit fixture actual cells inspected'}},
            'baseline_metrics':{},'expansion_plan':{'generation_method':'Isolated deterministic test fixture only',
                'main_tables':{'记录.csv':{'target_effective_rows':2,'required_events':['正常','异常']}}}})
        self.evidence['source_trace']=self.item('trace.json',{'sources':self.run['sources'],
            'mappings':[dict(source_location='input paragraph 1',definition='deterministic addition',
                function='app.value',api='/value',persistence='test object',page='object view',export='record value',validation='unit fixture')],
            'conflicts':[]})
        self.evidence['provenance']=self.item('provenance.json',{'nature':'Isolated unit fixture, no external data',
            'sources':[{'url':'https://example.invalid/unit-fixture','license':'Unit fixture authorship',
                        'accessed_at':'2026-10-16','obtained':False,'restriction':'Deliberately no network in unit test'}],
            'validation':'Unit schema fixture only; not domain validation'})
        log=self.item('checks.log','Unit fixture assertions only\n')
        self.evidence['execution']=self.item('execution.json',{'run_id':self.run['run_id'],'checks':[
            {'kind':k,'command':'unit fixture only','exit_code':0,'summary':'Isolated test record only','log':log}
            for k in ('algorithm','api','persistence','browser','export','lifecycle')]})
        self.evidence['cleanup']=self.item('cleanup.json',{'status':'stopped','workspace':str(self.work),'remaining':[],'ports_still_listening':[]})
        self.evidence['package_probe']=self.item('probe.json',{'status':'completed','run_id':self.run['run_id'],
            'source_zip_sha256':digest(self.output/'系统材料'/'源代码.zip'),'cleanup':{'status':'stopped'},
            'checker_sha256':digest(flow.BASE/'scripts/package_probe.py'),'log':str(self.work/log['path']),'log_sha256':log['sha256'],
            'case_assertions':{'core_flow':'unit fixture only','checks':[{'kind':k,'name':'unit fixture','passed':True} for k in ('startup','core_flow')]}})
        video=self.output/'系统材料'/'操作视频.mp4';video.write_bytes(b'isolated fake media fixture, never a real video')
        events=[{'action':['click','fill','download'][i%3],'started':float(i*9),'completed':float(i*9+1),
                 'assertion':'unit fixture only'} for i in range(6)]
        self.evidence['recording']=self.item('recording.json',{'video_sha256':digest(video),'duration':61,
            'continuous_capture':True,'real_browser':True,'edited':False,'events':events})
        frame=self.work/'evidence'/'unit-frame.jpg';frame.write_bytes(b'isolated unit frame fixture')
        f={'file':str(frame),'sha256':digest(frame)}
        samples=[]
        for i in range(305):
            sample=frame.with_name('unit-sample-'+str(i)+'.jpg');sample.write_bytes(b'isolated unit sample fixture')
            samples.append({'file':str(sample),'sha256':digest(sample),'type':'uniform_sample','seconds':i/5})
        timeline={'video_sha256':digest(video),'duration':61,'sample_fps':5,'width':1920,'height':1080,'codec':'h264','fps':25,
            'decode_ok':True,'frames':samples+[{**f,'type':'first'},{**f,'type':'last'}],
            'interaction_frames':[f]*12,'contact_sheets':[f]}
        self.evidence['timeline']=self.item('timeline.json',timeline)
        path=self.work/'evidence'/'manifest.json';write_json(path,self.evidence)
        return argparse.Namespace(workspace=str(self.work),evidence=str(path))

    def test_no_word_chart_profile_inputs_pass(self):
        result=flow.audit(self.fixture(),require_review=False)
        self.assertEqual(result['status'],'inputs_ready');self.assertFalse(result['independent_review_verified'])
        self.assertFalse(any(k.endswith(('.docx','.png','.jpg')) for k in result['snapshot']))

    def test_missing_required_evidence_rejected(self):
        args=self.fixture()
        for key in ['source_trace','data_plan','provenance','execution','package_probe','cleanup','recording','timeline']:
            with self.subTest(key=key):
                value=dict(self.evidence);value.pop(key);write_json(args.evidence,value)
                with self.assertRaises((ValueError,KeyError)):flow.audit(args,require_review=False)

    def test_no_independent_proof_cannot_finalize(self):
        with self.assertRaises((ValueError,KeyError)):flow.finalize(self.fixture())

    def test_word_chart_mixed_delivery_rejected(self):
        args=self.fixture()
        for name in ('extra.docx','curve.png'):
            p=self.output/name;p.write_bytes(b'not allowed')
            with self.assertRaises(ValueError):flow.audit(args,require_review=False)
            p.unlink()

    def test_readme_and_external_paths_rejected(self):
        source=self.work/'source';source.mkdir()
        for name in ('README.md','read-me.txt'):
            (source/name).write_text('guide',encoding='utf-8')
            manifest=self.work/'list.json';write_json(manifest,{'source_root':'source','files':[name]})
            with self.assertRaises(ValueError):flow.package(argparse.Namespace(workspace=str(self.work),manifest=str(manifest)))
        write_json(manifest,{'source_root':'source','files':['../../input.txt']})
        with self.assertRaises(ValueError):flow.package(argparse.Namespace(workspace=str(self.work),manifest=str(manifest)))

    def test_clean_only_metadata_columns_preserves_values(self):
        source=self.work/'input.csv';target=self.work/'clean.csv'
        with source.open('w',encoding='utf-8-sig',newline='') as stream:
            csv.writer(stream).writerows([['数据来源','读数','生成时间','空值','生成数据'],['public','1.23000','2026-10-16','','true'],['source','-0.000','2026-10-17','NA','false']])
        before=source.read_bytes();receipt=flow.clean_csv(source,target)
        self.assertEqual(source.read_bytes(),before)
        with target.open(encoding='utf-8-sig',newline='') as stream:rows=list(csv.reader(stream))
        self.assertEqual(rows,[['读数','生成时间','空值'],['1.23000','2026-10-16',''],['-0.000','2026-10-17','NA']])
        self.assertEqual(receipt['removed_columns'],['数据来源','生成数据'])

    def test_zip_traversal_rejected_before_extract(self):
        archive=self.root/'bad.zip'
        with zipfile.ZipFile(archive,'w') as z:z.writestr('../outside.py','bad')
        dest=self.root/'unpack';dest.mkdir()
        with self.assertRaises(ValueError):package_probe.unpack(archive,dest)
        self.assertFalse(list(dest.iterdir()))

    def test_fake_workspace_log_rejected(self):
        fake=self.work/'fake.jsonl';fake.write_text('{}\n',encoding='utf-8')
        with self.assertRaises(ValueError):model_proof.events(fake)

    def test_parent_self_identity_rejected(self):
        parent={'id':'same'}
        with patch.object(model_proof,'events',return_value=([],{'id':'same','source':{}})):
            with self.assertRaises(ValueError):model_proof.child({'child_log':'unused','agent_id':'/root'},parent,'ultra')

    def test_expedited_only_whole_affirmative_scoped_command(self):
        for text in ('case-1加急','加急case-1','请case-1使用原加急模式','case-1采用Astra低思考'):
            self.assertTrue(expedited.simple_command(text,'case-1'),text)
        for text in ('快一点','case-1支持加急吗','如果批准，case-1加急','材料：case-1加急','不要case-1加急','case-2加急','case-1加急\n但需要批准'):
            self.assertFalse(expedited.simple_command(text,'case-1'),text)

    def test_ordinary_admission_rejects_lower_model(self):
        for model,effort in [('gpt-6-astra','low'),('gpt-6.1-sol','high')]:
            with self.assertRaises(ValueError):model_proof.review_route(self.work,{'route':'ordinary','model':model,'effort':effort})

    def test_expedited_missing_real_message_rejected(self):
        with patch.object(expedited,'events',return_value=([],{'id':'fixture-parent','source':'vscode'})):
            with self.assertRaises(ValueError):expedited.validate(self.work,{
                'run_id':self.run['run_id'],'workspace':str(self.work),'session_log':'not used',
                'statement':'case-1加急','scope_name':'case-1','user_message_sha256':'0'*64})

    def test_batch_dedup_and_ready_stage_fairness(self):
        root=self.root/'control'
        runtime={'session_id':'unit-controller','worker_capacity':1,'session_log':'isolated fixture only'}
        with patch.object(batch_control,'capacity',return_value=runtime):
            result=batch_control.register(root,'batch-1',[{'case_id':'case-1','workspace':str(self.work)}],'unit fixture only',os.getpid(),'not real dispatch evidence')
            duplicate=batch_control.register(root,'batch-2',[{'case_id':'case-1','workspace':str(self.work)}],'unit fixture only',os.getpid(),'not real dispatch evidence')
            self.assertEqual(duplicate['cases'][0]['state'],'duplicate')
            q1=batch_control.mutate(root,'batch-1',os.getpid(),'queue','case-1','build')
            q2=batch_control.mutate(root,'batch-1',os.getpid(),'queue','case-1','review')
            selected=batch_control.mutate(root,'batch-1',os.getpid(),'acquire',token=q1['token'])
            self.assertFalse(selected['acquired']);self.assertEqual(selected['selected']['token'],q2['token'])
            acquired=batch_control.mutate(root,'batch-1',os.getpid(),'acquire',token=q2['token'])
            self.assertTrue(acquired['acquired'])
            self.assertFalse(batch_control.mutate(root,'batch-1',os.getpid(),'acquire',token=q1['token'])['acquired'])

    def test_publication_atomic_and_no_overwrite(self):
        args=self.fixture();report=flow.audit(args,require_review=False)
        report['evidence']=flow.make_ref(self.work,args.evidence)
        write_json(self.work/'.ssd/finalize.json',report)
        # Mock is strictly limited to atomic filesystem behavior; no real acceptance is claimed.
        with patch.object(flow,'audit',return_value={'test_only':True}):
            result=flow.publish(argparse.Namespace(workspace=str(self.work),name='delivery-case'))
        self.assertFalse(self.output.exists());self.assertEqual(result['snapshot'],report['snapshot'])
        self.output.mkdir(parents=True)
        with self.assertRaises(ValueError):flow.publish(argparse.Namespace(workspace=str(self.work),name='delivery-case'))

    def test_real_isolated_package_probe_job(self):
        source=self.work/'source';source.mkdir();(source/'app.py').write_text('print(4 + 7)\n',encoding='utf-8')
        manifest=self.work/'list.json';write_json(manifest,{'source_root':'source','files':['app.py']})
        flow.package(argparse.Namespace(workspace=str(self.work),manifest=str(manifest)))
        probe=self.work/'evidence'/'probe_case.py';probe.parent.mkdir()
        probe.write_text('import os,json,subprocess,sys\nfrom pathlib import Path\nroot=Path(os.environ["SSD_PACKAGE_ROOT"])\np=subprocess.run([sys.executable,str(root/"app.py")],capture_output=True,text=True,check=True)\nassert p.stdout.strip()=="11"\nPath(os.environ["SSD_PACKAGE_RESULT"]).write_text(json.dumps({"core_flow":"real unpacked app addition fixture","checks":[{"kind":"startup","name":"unpacked app process ran","passed":True},{"kind":"core_flow","name":"actual returned 11","passed":True}]}),encoding="utf-8")\n',encoding='utf-8')
        report=package_probe.probe(self.work,probe,self.work/'evidence'/'real-probe.json',timeout=30)
        self.assertEqual(report['status'],'completed',report)
        self.assertEqual(report['cleanup']['status'],'stopped')
        self.assertEqual(report['cleanup']['remaining_pids'],[])


if __name__=='__main__':unittest.main(verbosity=2)
