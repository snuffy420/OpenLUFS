"""Concurrency, deterministic reports, cache sharing and cancellation contracts."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack
from pathlib import Path
from types import SimpleNamespace
import tempfile
import threading
import unittest
from unittest.mock import patch
from openlufs.parallel import run_tracks,worker_count
from openlufs.analysis_cache import AnalysisCache
from openlufs.batch import analyze_batch,process_batch,DiskBudget
from openlufs.engine import Cancelled
from openlufs.models import Settings
from test_audio import WORK,tone


class ParallelTests(unittest.TestCase):
    def setUp(self):
        WORK.mkdir(exist_ok=True);self.temp=tempfile.TemporaryDirectory(prefix='parallel-',dir=WORK)
        self.root=Path(self.temp.name);self.patches=ExitStack()
        self.patches.enter_context(patch('openlufs.parallel.os.cpu_count',return_value=8))
        self.patches.enter_context(patch('openlufs.parallel.available_memory',return_value=4*1024**3))

    def tearDown(self):self.patches.close();self.temp.cleanup()

    def test_workers_overlap_callbacks_are_serialized_and_results_ordered(self):
        barrier=threading.Barrier(2);lock=threading.Lock();active=0;maximum=0;callbacks=[]
        caller=threading.get_ident()
        def job(index,item,emit):
            nonlocal active,maximum
            with lock:active+=1;maximum=max(maximum,active)
            try:
                emit('Processing')
                if index<2:barrier.wait(3)
                return 'Complete',item
            finally:
                with lock:active-=1
        results=run_tracks(range(20),job,threading.Event(),lambda *args:callbacks.append(threading.get_ident()),workers=2)
        self.assertEqual(maximum,2);self.assertEqual([payload for _,_,payload in results],list(range(20)))
        self.assertEqual(set(callbacks),{caller})

    def test_failure_does_not_abort_other_tracks(self):
        def job(index,item,emit):
            if index==1:raise ValueError('Invalid test audio')
            return 'Complete',item
        outcomes=run_tracks(range(4),job,threading.Event(),workers=2)
        self.assertEqual([stage for _,stage,_ in outcomes],['Complete','Failed','Complete','Complete'])
        self.assertIn('Invalid test audio',outcomes[1][2])

    def test_cancellation_stops_submission_and_waits_for_active_cleanup(self):
        cancel=threading.Event();started=[];cleaned=[];seen=set();lock=threading.Lock()
        def job(index,item,emit):
            with lock:started.append(index)
            try:
                emit('Processing')
                if not cancel.wait(3):raise RuntimeError('Cancellation did not arrive')
                raise Cancelled()
            finally:
                with lock:cleaned.append(index)
        def callback(index,stage,payload):
            if stage=='Processing':
                seen.add(index)
                if len(seen)==2:cancel.set()
        outcomes=run_tracks(range(50),job,cancel,callback,workers=2)
        self.assertEqual(sorted(started),[0,1]);self.assertEqual(sorted(cleaned),[0,1])
        self.assertEqual([stage for _,stage,_ in outcomes],['Cancelled','Cancelled'])

    def test_callback_failure_cancels_and_joins_workers(self):
        cancel=threading.Event()
        def job(index,item,emit):
            emit('Processing');cancel.wait(3);raise Cancelled()
        def callback(*args):raise RuntimeError('Callback failed')
        with self.assertRaisesRegex(RuntimeError,'Callback failed'):
            run_tracks(range(10),job,cancel,callback,workers=2)
        self.assertTrue(cancel.is_set())

    def test_worker_policy_limits_cpu_memory_and_rejects_bad_values(self):
        self.assertEqual(worker_count(20),4)
        with patch('openlufs.parallel.os.cpu_count',return_value=2):self.assertEqual(worker_count(20),1)
        with patch('openlufs.parallel.available_memory',return_value=1024**3):self.assertEqual(worker_count(20,8),1)
        for value in [0,33,True,1.5]:
            with self.assertRaises(ValueError):worker_count(20,value)

    def test_duplicate_measurements_share_one_analysis_without_blocking_other_files(self):
        cache=AnalysisCache();source=self.root/'file.wav';source.write_bytes(b'unchanged')
        started=threading.Event();release=threading.Event();calls=[];measurement=object()
        def analyze(path):calls.append(path);started.set();release.wait(3);return measurement
        with ThreadPoolExecutor(max_workers=2) as pool:
            first=pool.submit(cache.measure,source,analyze);self.assertTrue(started.wait(3))
            second=pool.submit(cache.measure,source,analyze);release.set()
            self.assertIs(first.result(3),measurement);self.assertIs(second.result(3),measurement)
        self.assertEqual(len(calls),1)
        cache.clear();other=self.root/'other.wav';other.write_bytes(b'other')
        barrier=threading.Barrier(2)
        def together(path):barrier.wait(3);return measurement
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures=[pool.submit(cache.measure,path,together) for path in [source,other]]
            for future in futures:self.assertIs(future.result(3),measurement)

    def test_clearing_cache_does_not_restore_inflight_stale_entry(self):
        cache=AnalysisCache();source=self.root/'file.wav';source.write_bytes(b'unchanged')
        started=threading.Event();release=threading.Event()
        def analyze(path):started.set();release.wait(3);return object()
        with ThreadPoolExecutor(max_workers=1) as pool:
            future=pool.submit(cache.measure,source,analyze);self.assertTrue(started.wait(3))
            cache.clear();release.set();future.result(3)
        self.assertIsNone(cache.get(source))

    def test_real_batch_partial_failure_reuses_analysis_and_keeps_order(self):
        files=[self.root/f'{i}.wav' for i in range(3)]
        for source in files:tone(source,seconds=2)
        files[1].write_bytes(b'not audio')
        cache=AnalysisCache();cancel=threading.Event()
        measured,errors=analyze_batch(files,cancel,analysis_cache=cache,workers=2)
        self.assertEqual([index for index,_ in measured],[0,2]);self.assertEqual(len(errors),1)
        planned=[(source,self.root/'output'/source.name) for source in files]
        results,errors=process_batch(planned,Settings(-24,-1),cancel,analysis_cache=cache,workers=2)
        self.assertEqual([Path(result.source).name for result in results],['0.wav','2.wav'])
        self.assertEqual(len(errors),1)
        self.assertTrue(all(abs(result.after.integrated+24)<=.100001 for result in results))

    def test_real_parallel_cancellation_stops_subprocesses_and_cleans_exports(self):
        import subprocess
        from openlufs.engine import Engine
        sources=[self.root/f'cancel-{i}.wav' for i in range(4)]
        cache=AnalysisCache()
        for source in sources[:2]:
            tone(source,seconds=4);cache.measure(source,Engine().analyze)
        # Remaining sources are never submitted once the first pair is cancelled.
        cancel=threading.Event();started=threading.Event();lock=threading.Lock();processes=[];commands=[]
        real_popen=subprocess.Popen;real_run=Engine.run
        def slower(engine,arguments,executable=None):
            arguments=list(arguments)
            if any(str(argument).startswith('volume=') for argument in arguments):
                arguments.insert(arguments.index('-i'),'-re')
            return real_run(engine,arguments,executable)
        def capture(arguments,*args,**kwargs):
            process=real_popen(arguments,*args,**kwargs)
            if '-re' in arguments:
                with lock:
                    processes.append(process);commands.append(arguments)
                    if len(processes)==2:started.set()
            return process
        planned=[(source,self.root/'cancel-output'/source.name) for source in sources]
        with patch.object(Engine,'run',slower),patch('openlufs.engine.subprocess.Popen',side_effect=capture):
            with ThreadPoolExecutor(max_workers=1) as pool:
                future=pool.submit(process_batch,planned,Settings(-24,-1),cancel,None,cache,2)
                try:
                    self.assertTrue(started.wait(5),'Parallel render subprocesses did not start')
                finally:cancel.set()
                results,errors=future.result(5)
        self.assertEqual(results,[]);self.assertEqual(errors,[])
        self.assertEqual(len(processes),2)
        for command in commands:
            for index,argument in enumerate(command):
                if argument in {'-threads','-filter_threads','-filter_complex_threads'}:
                    self.assertEqual(command[index+1],'1')
        self.assertTrue(all(process.poll() is not None for process in processes))
        self.assertFalse(list((self.root/'cancel-output').iterdir()))

    def test_low_disk_space_is_reported_before_export(self):
        budget=DiskBudget();cancel=threading.Event()
        with patch('openlufs.batch.shutil.disk_usage',return_value=SimpleNamespace(free=80*1024**2)):
            with self.assertRaisesRegex(OSError,'Not enough free space'):
                with budget.reserve(self.root/'output.wav',32*1024**2,cancel):pass
        self.assertEqual(budget.reserved,{})


if __name__=='__main__':unittest.main()
