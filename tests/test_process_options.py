"""F02 attached Python option regressions; only owned isolated Windows Jobs."""
import os
from pathlib import Path
import subprocess
import sys
import time
import unittest
from unittest.mock import MagicMock,patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import process_guard as guard
import test_delivery
import test_repair

RESULTS={}

class ProcessOptionTests(unittest.TestCase):
    def setUp(self):
        self.f=test_delivery.DeliveryTests();self.f.setUp()
        self.work,self.root=self.f.work,self.f.root
        self.helper=self.work/'helper.py'
        self.marker=self.work/'actual-script-started.txt'
        self.helper.write_text('from pathlib import Path\nimport time\nPath(__file__).with_name("actual-script-started.txt").write_text("executed")\ntime.sleep(300)\n',encoding='utf8')
    def tearDown(self):self.f.tearDown()

    def owned(self,options):
        return guard.background_entry_owned(self.work,{'name':'python.exe',
            'command':subprocess.list2cmdline([sys.executable,*options,str(self.helper)])})

    def test_python_options_script_position(self):
        for options in (['-cimport time;time.sleep(300)'],['-mssd_probe_sleep'],
                        ['-Icimport time;time.sleep(300)'],['-Imssd_probe_sleep'],
                        ['-BuIcimport time;time.sleep(300)'],['-Z'],['--unknown'],['-']):
            with self.subTest(options=options):self.assertFalse(self.owned(options))
        for options in ([],['-B','-u'],['-Bu'],['-I','-B'],['-X','dev','-W','ignore'],
                        ['-Xdev','-Wignore'],['-BWignore','-Xdev'],['--']):
            with self.subTest(options=options):self.assertTrue(self.owned(options))
        for options in (['-W'],['-X']):
            self.assertIsNone(guard.python_script_argument(options))

    def test_retained_handle_failed_termination_requires_actual_exit(self):
        for signals,exited in [([0,0],True),([258],False)]:
            with self.subTest(exited=exited):
                kernel=MagicMock();handle=object()
                kernel.TerminateProcess.return_value=False
                kernel.WaitForSingleObject.side_effect=signals
                with patch.object(guard,'retain_exact',return_value=(kernel,handle)):
                    if exited:guard.terminate_exact({'unit_boundary':'retained handle race only'})
                    else:
                        with self.assertRaisesRegex(ValueError,'termination failed'):
                            guard.terminate_exact({'unit_boundary':'retained handle race only'})
                kernel.CloseHandle.assert_called_once_with(handle)

    def test_real_attached_code_and_cluster_refused_and_untouched(self):
        outcomes=[]
        for mode in ['-cimport time;time.sleep(300)','-Icimport time;time.sleep(300)']:
            def action(job,info):
                rows=guard.inventory();row=next(r for r in rows if r['pid']==info.pid)
                self.assertFalse(guard.background_entry_owned(self.work,row))
                with self.assertRaisesRegex(ValueError,'live registered case ancestor'):guard.register(self.work,info.pid)
                self.assertIn(info.pid,job.pids());self.assertFalse(self.marker.exists())
                self.assertFalse((self.work/'.ssd/processes.json').exists())
                outcomes.append({'mode':mode,'pid':info.pid,'register':'rejected',
                    'process_after_rejection':'alive','fake_script_executed':False})
            test_repair.RepairTests.with_own_job(self,[sys.executable,mode,str(self.helper)],action)
        RESULTS['attached_code']=outcomes

    def test_real_attached_module_refused_and_untouched(self):
        lib=self.root/'module-library';lib.mkdir()
        (lib/'ssd_probe_sleep.py').write_text('import time\ntime.sleep(300)\n',encoding='utf8')
        def action(job,info):
            row=next(r for r in guard.inventory() if r['pid']==info.pid)
            self.assertFalse(guard.background_entry_owned(self.work,row))
            with self.assertRaisesRegex(ValueError,'live registered case ancestor'):guard.register(self.work,info.pid)
            self.assertIn(info.pid,job.pids());self.assertFalse(self.marker.exists())
            RESULTS['attached_module']={'mode':'-mssd_probe_sleep','pid':info.pid,'register':'rejected',
                'process_after_rejection':'alive','fake_script_executed':False}
        with patch.dict(os.environ,{'PYTHONPATH':str(lib)}):
            test_repair.RepairTests.with_own_job(self,[sys.executable,'-mssd_probe_sleep',str(self.helper)],action)

    def test_real_normal_flags_script_registered_and_stopped(self):
        def action(job,info):
            deadline=time.monotonic()+8
            while not self.marker.exists() and time.monotonic()<deadline:time.sleep(.05)
            self.assertTrue(self.marker.exists())
            row=next(r for r in guard.inventory() if r['pid']==info.pid)
            self.assertTrue(guard.background_entry_owned(self.work,row))
            registered=guard.register(self.work,info.pid);receipt=guard.stop(self.work)
            self.assertEqual(receipt['status'],'stopped',receipt);self.assertEqual(job.pids(),[])
            RESULTS['normal_script']={'argv_options':['-Bu','-X','dev','-Wignore'],'registered':registered,
                'actual_script_executed':True,'cleanup':receipt,'actual_own_job_members_after_stop':[]}
        test_repair.RepairTests.with_own_job(self,[sys.executable,'-Bu','-X','dev','-Wignore',str(self.helper)],action)

if __name__=='__main__':
    from common import write_json
    result=unittest.main(verbosity=2,exit=False)
    write_json(Path(os.environ.get('SSD_F02_PROBE_REPORT',r'E:\研发自动化\skill-evidence\repair-f02-probes.json')),{
        'scope':'F02 targeted isolated Windows Job regression only; no independent/business pass',
        'tests_run':result.result.testsRun,'successful':result.result.wasSuccessful(),'results':RESULTS,
        'cache':{k:os.environ.get(k) for k in ('TEMP','TMP','TMPDIR','PYTHONPYCACHEPREFIX')}})
    sys.exit(0 if result.result.wasSuccessful() else 1)
