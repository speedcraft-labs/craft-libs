import copy
import importlib.util
import unittest
from lightcraft_session_report import validate_session, summarize


def fixture():
    return dict(launch_ns=10, interactive_ns=20, quit_request_ns=100, exit_ns=150, gpu_adapter='test GPU',
                samples=[dict(action='exposure', sent_ns=30, frame_ns=40, duration_ns=10, checked=True, frame_sha256='abc',warmup=False)])


class Boundaries(unittest.TestCase):
    def test_valid_session(self):
        validate_session(fixture())

    def test_launch_or_exit_inside_action_rejected(self):
        for sent,end,duration in [(10,40,30),(30,150,120),(30,40,60)]:
            s=fixture()
            s['samples'][0].update(sent_ns=sent,frame_ns=end,duration_ns=duration)
            with self.assertRaises(ValueError):
                validate_session(s)

    def test_early_frame_requires_exact_later_pixel_proof(self):
        s=fixture()
        proof=dict(method='verified-x11',frame_ns=40,verified_ns=50,rgb_sha256='abc',width=10,height=10,
                   candidates=[dict(ns=40,width=10,height=10,rgb_sha256='old-frame')])
        s['samples'][0]['evidence']={'capture':proof}
        with self.assertRaisesRegex(ValueError,'pixel proof'):validate_session(s)
        proof['candidates'].append(dict(ns=40,width=10,height=10,rgb_sha256='abc'))
        validate_session(s)
        proof['verified_ns']=151
        with self.assertRaises(ValueError):validate_session(s)

    def test_headless_retry_keeps_elapsed_time_and_failed_evidence(self):
        import tempfile
        from pathlib import Path
        from types import SimpleNamespace
        from unittest.mock import patch
        from lightcraft_real_app import session_frame
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);log=root/'app.log';log.write_text('')
            control=SimpleNamespace(session_log=log)
            def capture(control,path):
                end=50 if not log.read_text() else 80
                path.write_bytes(b'capture')
                control.last_capture_proof=dict(method='native-upper-bound',frame_ns=end,verified_ns=end,rgb_sha256=str(end),width=10,height=10,candidates=[])
                if end==50:log.write_text('rendering headlessly')
                return end,str(end)
            with patch('lightcraft_real_app.session_capture_once',side_effect=capture) as capture_mock:
                end,digest=session_frame(control,root/'frame.png')
            self.assertEqual(capture_mock.call_count,2)
            self.assertEqual((end,digest),(80,'80'))
            self.assertTrue((root/'frame.headless-attempt-0.png').exists())
            self.assertFalse(control.last_capture_proof['attempts'][0]['native'])
            s=fixture();s['samples'][0].update(frame_ns=end,duration_ns=end-30,frame_sha256=digest,evidence={'capture':control.last_capture_proof})
            validate_session(s)
            control.last_capture_proof['native']=False
            with self.assertRaisesRegex(ValueError,'headless'):validate_session(s)

    def test_retry_native_png_verifies_earlier_x11_frame(self):
        import tempfile
        from pathlib import Path
        from types import SimpleNamespace
        from unittest.mock import patch
        from lightcraft_real_app import session_frame
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);log=root/'app.log';log.write_text('')
            control=SimpleNamespace(session_log=log)
            def capture(control,path):
                first=not log.read_text();end=50 if first else 80;digest='headless' if first else 'result'
                path.write_bytes(b'capture')
                candidate=dict(ns=45 if first else 75,width=10,height=10,rgb_sha256='result')
                control.last_capture_proof=dict(method='verified-x11',frame_ns=end,verified_ns=end,rgb_sha256=digest,width=10,height=10,candidates=[candidate])
                if first:log.write_text('rendering headlessly')
                return end,digest
            with patch('lightcraft_real_app.session_capture_once',side_effect=capture):end,digest=session_frame(control,root/'frame.png')
            self.assertEqual((end,digest),(45,'result'))
            self.assertEqual(control.last_capture_proof['verified_ns'],80)
            s=fixture();s['samples'][0].update(frame_ns=end,duration_ns=end-30,frame_sha256=digest,evidence={'capture':control.last_capture_proof})
            validate_session(s)

    def test_tiers_cannot_be_inside_a_pruned_corpus_root(self):
        import json
        import tempfile
        from pathlib import Path
        from unittest.mock import patch
        from lightcraft_session_corpus import main
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            manifest=root/'manifest.toml'
            manifest.write_text('[[file]]\npath = "photo.arw"\n')
            tiers=root/'tiers.json'
            tiers.write_text(json.dumps({'typical':['photo.arw']}))
            argv=['corpus',str(manifest),str(root/'download'),str(tiers),'--out',str(root/'download/tiers')]
            with patch('sys.argv',argv), self.assertRaisesRegex(ValueError,'outside'):
                main()

    def test_grid_top_rejects_negative_rubber_band_offsets(self):
        from lightcraft_real_app import session_grid_at_top
        for offset in (None,-2006.448,-3023.768,100):
            self.assertFalse(session_grid_at_top({'scroll':{'grid':offset}}))
        self.assertTrue(session_grid_at_top({'scroll':{'grid':0.0}}))

    def test_long_background_prep_drains_without_changing_action_samples(self):
        from unittest.mock import patch
        from lightcraft_real_app import session_drain
        clock=[0];calls=[];record={'samples':copy.deepcopy(fixture()['samples'])}
        original=copy.deepcopy(record['samples'])
        observations=iter([(181,125),(600,400),(900,500),(901,500)])
        class Control:
            def call(self,method):
                calls.append(method);clock[0],done=next(observations)
                return {'perf':{'renderQueue':0,'rendersInFlight':0,'pendingSlots':[]},'activity':[] if done==500 else [{'done':done,'total':500}],'tasks':[],'unsaved':None}
        with patch('lightcraft_real_app.time.monotonic',side_effect=lambda:clock[0]), patch('lightcraft_real_app.time.perf_counter_ns',side_effect=lambda:clock[0]*1_000_000_000), patch('lightcraft_real_app.time.sleep'):
            session_drain(Control(),record,'before-idle-quit',require_saved=True)
        self.assertEqual(record['samples'],original)
        self.assertEqual(record['background_drains'][0]['end_ns'],901_000_000_000)
        self.assertEqual([p['activity'][0]['done'] for p in record['background_drains'][0]['progress'] if p['activity']],[125,400])
        self.assertEqual(calls,['ui.inspect']*4)

    def test_empty_activity_snapshot_waits_for_young_background_job(self):
        from unittest.mock import patch
        from lightcraft_real_app import session_drain
        clock=[0];observations=iter([(0,[]),(.6,[{'done':0,'total':500}]),(3,[]),(4,[])])
        class Control:
            def call(self,method):
                clock[0],activity=next(observations)
                return {'perf':{'renderQueue':0,'rendersInFlight':0,'pendingSlots':[]},'activity':activity,'tasks':[],'unsaved':None}
        record={}
        with patch('lightcraft_real_app.time.monotonic',side_effect=lambda:clock[0]), patch('lightcraft_real_app.time.perf_counter_ns',side_effect=lambda:round(clock[0]*1_000_000_000)), patch('lightcraft_real_app.time.sleep'):
            session_drain(Control(),record,'before-idle-quit',require_saved=True)
        self.assertEqual(record['background_drains'][0]['end_ns'],4_000_000_000)

    def test_empty_texture_queue_shape_is_a_list(self):
        from lightcraft_real_app import session_idle
        self.assertTrue(session_idle({'perf':{'renderQueue':0,'rendersInFlight':0,'pendingSlots':[]}}))
        self.assertFalse(session_idle({'perf':{'renderQueue':0,'rendersInFlight':0,'pendingSlots':['Main']}}))

    def test_unchecked_or_empty_gpu_rejected(self):
        s=fixture(); s['gpu_adapter']=None
        with self.assertRaises(ValueError): validate_session(s)
        s=fixture(); s['samples'][0]['checked']=False
        with self.assertRaises(ValueError): validate_session(s)

    @unittest.skipUnless(importlib.util.find_spec('PIL'), 'Pillow is required for real-app pixel checks')
    def test_noisy_jpeg_uses_lossless_export_at_identical_geometry(self):
        import random,tempfile
        from pathlib import Path
        from PIL import Image
        from lightcraft_session_report import check_export_pixels
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);source=Image.frombytes('RGB',(256,171),random.Random(313).randbytes(256*171*3))
            source.save(root/'source.png');source.save(root/'actual.jpg',quality=90,subsampling=0)
            session={'export_sample':str(root/'actual.jpg'),'export_oracle':str(root/'source.png'),'export_oracle_method':'png-export-same-geometry'}
            self.assertLess(max(check_export_pixels(session)['mean_rgb']),8)
            source.resize((256,172),Image.Resampling.BILINEAR).save(root/'wrong-geometry.png')
            session['export_oracle']=str(root/'wrong-geometry.png')
            with self.assertRaisesRegex(ValueError,'geometry'):check_export_pixels(session)
            session.pop('export_oracle_method')
            with self.assertRaisesRegex(ValueError,'MAE 8'):check_export_pixels(session)
            Image.new('RGB',source.size,(0,255,0)).save(root/'wrong-photo.png')
            session.update(export_oracle=str(root/'wrong-photo.png'),export_oracle_method='png-export-same-geometry')
            with self.assertRaisesRegex(ValueError,'MAE 8'):check_export_pixels(session)

    def test_exposure_requires_changed_photo_pixels(self):
        from lightcraft_session_report import verify_photo_change
        with self.assertRaisesRegex(ValueError,'photo pixels'):verify_photo_change('unchanged-photo','unchanged-photo')
        with self.assertRaises(ValueError):verify_photo_change('', 'new-photo')
        verify_photo_change('old-photo','new-photo')

    def test_foreign_gpu_process_rejects_publication(self):
        s=fixture();s['process_ids']=[123]
        s['gpu_processes_before']={'processes':[]}
        s['gpu_processes_after']={'processes':[{'pid':123,'name':'our exited app'}]}
        validate_session(s)
        s['gpu_processes_after']['processes'].append({'pid':456,'name':'other GPU test'})
        with self.assertRaisesRegex(ValueError,'foreign GPU'):validate_session(s)

    def test_gpu_admission_waits_in_30_second_polls_and_has_a_deadline(self):
        from lightcraft_real_app import session_gpu_admit
        foreign={'processes':[{'pid':456,'name':'unlocked-test'}]}
        clean={'processes':[]}
        clock=[0];sleeps=[];waits=[]
        def pause(seconds):sleeps.append(seconds);clock[0]+=seconds
        observations=iter([foreign,foreign,clean])
        admitted,provisional=session_gpu_admit(1800,observe=lambda:next(observations),pause=pause,now=lambda:clock[0],on_wait=waits.append)
        self.assertEqual((admitted,provisional),(clean,False))
        self.assertEqual(sleeps,[30,30])
        clock[0]=0;sleeps.clear()
        admitted,provisional=session_gpu_admit(1800,observe=lambda:foreign,pause=pause,now=lambda:clock[0])
        self.assertEqual((clock[0],len(sleeps),provisional),(1800,60,True))
        self.assertEqual(admitted,foreign)

    def test_gpu_contamination_discards_then_repeats_the_session(self):
        import tempfile
        from pathlib import Path
        from unittest.mock import patch
        from lightcraft_real_app import session_guarded_attempt
        clean={'processes':[]};foreign={'processes':[{'pid':456,'name':'unlocked-test'}]}
        class Watch:
            count=0
            def __init__(self):
                self.samples=[foreign if Watch.count==0 else clean];self.errors=[];Watch.count+=1
            def start(self):pass
            def stop(self):pass
        with tempfile.TemporaryDirectory() as tmp:
            report={};calls=[]
            def run(directory,provisional,on_started):
                calls.append((directory,provisional));directory.mkdir()
                return {'process_ids':[123]}
            with patch('lightcraft_real_app.session_gpu_admit',return_value=(clean,False)), patch('lightcraft_real_app.SessionGpuWatch',Watch), patch('lightcraft_real_app.session_gpu_processes',return_value=clean):
                accepted=session_guarded_attempt(report,lambda:None,Path('/our-app'),Path(tmp)/'session','typical','main',0,run)
            self.assertEqual(len(calls),2)
            self.assertNotEqual(calls[0][0],calls[1][0])
            self.assertEqual(report['discarded_sessions'][0]['gpu_foreign_processes'],foreign['processes'])
            self.assertEqual(accepted['gpu_status'],'clean')
            self.assertTrue((calls[0][0]/'discarded-session.json').exists())

    def test_transient_foreign_process_in_driver_after_snapshot_is_retained(self):
        import tempfile
        from pathlib import Path
        from unittest.mock import patch
        from lightcraft_real_app import session_guarded_attempt
        clean={'processes':[]};foreign={'processes':[{'pid':456,'name':'short-unlocked-test'}]}
        class Watch:
            samples=[clean];errors=[]
            def start(self):pass
            def stop(self):pass
        with tempfile.TemporaryDirectory() as tmp:
            report={};calls=[]
            def run(directory,provisional,on_started):
                calls.append(directory);directory.mkdir()
                return {'process_ids':[123],'gpu_processes_after':foreign if len(calls)==1 else clean}
            with patch('lightcraft_real_app.session_gpu_admit',return_value=(clean,False)), patch('lightcraft_real_app.SessionGpuWatch',Watch), patch('lightcraft_real_app.session_gpu_processes',return_value=clean):
                accepted=session_guarded_attempt(report,lambda:None,Path('/our-app'),Path(tmp)/'session','typical','main',0,run)
            discarded=report['discarded_sessions'][0]
            self.assertEqual(discarded['gpu_processes_driver_after'],foreign)
            self.assertEqual(discarded['gpu_foreign_processes'],foreign['processes'])
            self.assertEqual(accepted['gpu_status'],'clean')

    def test_shared_gpu_fallback_remains_labeled_provisional(self):
        import tempfile
        from pathlib import Path
        from unittest.mock import patch
        from lightcraft_real_app import session_guarded_attempt
        foreign={'processes':[{'pid':456,'name':'unlocked-test'}]}
        class Watch:
            samples=[foreign];errors=[]
            def start(self):pass
            def stop(self):pass
        with tempfile.TemporaryDirectory() as tmp:
            report={}
            def run(directory,provisional,on_started):
                self.assertTrue(provisional);directory.mkdir();return fixture()
            with patch('lightcraft_real_app.session_gpu_admit',return_value=(foreign,True)), patch('lightcraft_real_app.SessionGpuWatch',Watch), patch('lightcraft_real_app.session_gpu_processes',return_value=foreign):
                accepted=session_guarded_attempt(report,lambda:None,Path('/our-app'),Path(tmp)/'session','typical','main',0,run)
            self.assertEqual(report['provisional_tiers'],{'typical':['unlocked-test']})
            self.assertEqual(accepted['gpu_status'],'shared-provisional')
            validate_session(accepted)
            accepted['gpu_provisional']=False
            with self.assertRaisesRegex(ValueError,'foreign GPU'):validate_session(accepted)

    def test_gpu_ownership_is_by_pid_not_executable_name(self):
        from lightcraft_real_app import session_gpu_foreign
        snapshots=[{'processes':[{'pid':123,'name':'same-binary'},{'pid':456,'name':'same-binary'}]}]
        self.assertEqual(session_gpu_foreign(snapshots,[123]),[{'pid':456,'name':'same-binary'}])

    def test_control_startup_failure_is_not_discarded_as_gpu_contention(self):
        import tempfile
        from pathlib import Path
        from unittest.mock import patch
        from lightcraft_real_app import session_guarded_attempt, spawn
        clean={'processes':[]};own={'processes':[{'pid':123,'name':'our-failed-app'}]}
        class Watch:
            samples=[own];errors=[]
            def start(self):pass
            def stop(self):pass
        class FailedProcess:
            pid=123;returncode=-11
            def poll(self):return self.returncode
        with tempfile.TemporaryDirectory() as tmp:
            report={};directory=Path(tmp)/'session'
            def run(attempt,provisional,on_started):
                attempt.mkdir()
                return spawn(Path('/our-app'),attempt/'library',attempt/'profile',None,on_started=on_started)
            with patch('lightcraft_real_app.session_gpu_admit',return_value=(clean,False)), patch('lightcraft_real_app.SessionGpuWatch',Watch), patch('lightcraft_real_app.session_gpu_processes',return_value=clean), patch('lightcraft_real_app.subprocess.Popen',return_value=FailedProcess()):
                with self.assertRaisesRegex(RuntimeError,'startup with status -11'):
                    session_guarded_attempt(report,lambda:None,Path('/our-app'),directory,'typical','main',0,run)
            self.assertEqual(report['discarded_sessions'],[])
            self.assertEqual(len(report['failed_sessions']),1)
            self.assertEqual(report['failed_sessions'][0]['process_ids'],[123])
            self.assertEqual(report['failed_sessions'][0]['gpu_foreign_processes'],[])

    def test_pair_resume_preserves_samples_and_rejects_changed_workload(self):
        import json,tempfile
        from pathlib import Path
        from lightcraft_real_app import session_resume, session_comparison_complete
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'report.json'
            config=dict(payloads={'typical':'/raw'},sessions=10,warmups=2,pair=0)
            session=fixture();session.update(tier='typical',pair=0,side='point')
            prior=dict(schema='lightcraft-session-v1',config=config,binary_sha256={'point':'hash'},sessions=[session])
            path.write_text(json.dumps(prior))
            resumed=dict(config,pair=1,resume_report=str(path))
            self.assertEqual(session_resume(resumed,{'point':'hash'})['sessions'],[session])
            with self.assertRaisesRegex(ValueError,'binary hashes'):
                session_resume(resumed,{'point':'changed'})
            with self.assertRaisesRegex(ValueError,'workload'):
                session_resume(dict(resumed,warmups=0),{'point':'hash'})
            self.assertFalse(session_comparison_complete(config,[session]))
            all_sessions=[dict(tier='typical',pair=p,side=s) for p in range(10) for s in ('point','main','upstream')]
            self.assertTrue(session_comparison_complete(config,all_sessions))
            self.assertFalse(session_comparison_complete(config,all_sessions+[all_sessions[0]]))

    def test_session_invocation_runs_one_pair_and_keeps_prior_guard(self):
        import contextlib,io,json,tempfile
        from pathlib import Path
        from unittest.mock import patch
        from lightcraft_real_app import session_main, file_digest
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);binary=root/'app';binary.write_bytes(b'fake binary')
            config=dict(payloads={'typical':'/raw'},sessions=10,warmups=2,pair=0,measurement_method='pre-dispatch-v2',
                        revisions={s:dict(binary=str(binary),revision=s) for s in ('point','main','upstream')})
            prior_sessions=[dict(fixture(),tier='typical',pair=0,side=s) for s in config['revisions']]
            prior=root/'prior.json';prior.write_text(json.dumps(dict(schema='lightcraft-session-v1',config=config,
                sessions=prior_sessions,binary_sha256={s:file_digest(binary) for s in config['revisions']},
                harness_revision='frozen',driver_sha256=file_digest(Path(__file__).with_name('lightcraft_real_app.py')),guard={'contended':False},fingerprint={'machine':'test'})))
            config.update(pair=1,resume_report=str(prior))
            config_path=root/'config.json';config_path.write_text(json.dumps(config));calls=[]
            def guarded(report,checkpoint,binary,directory,tier,side,pair,run):
                calls.append((pair,side));return dict(fixture(),tier=tier,pair=pair,side=side)
            with patch('lightcraft_real_app.ensure_display',return_value=None), patch('lightcraft_real_app.session_guarded_attempt',side_effect=guarded), patch('lightcraft_session_report.check_pixels',return_value=[]), patch('lightcraft_session_report.summarize',return_value=[]), contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(session_main(['--config',str(config_path),'--out',str(root/'out')]),0)
            report=json.loads((root/'out'/'report.json').read_text())
            self.assertEqual(calls,[(1,'upstream'),(1,'main'),(1,'point')])
            self.assertEqual(len(report['sessions']),6)
            self.assertFalse(report['comparison_complete'])
            self.assertTrue(report['prior_acquisitions_passed'])
            self.assertEqual(report['prior_acquisitions'][0]['guard'],{'contended':False})

    def test_stable_ratio_resamples_sessions(self):
        from lightcraft_session_report import ACTIONS
        sessions=[]
        for side,factor in [('point',2),('main',1),('upstream',3)]:
            for pair in range(10):
                s=fixture(); s.update(side=side,tier='test',pair=pair,startup_library_ns=factor*10)
                s['samples']=[dict(copy.deepcopy(s['samples'][0]),action=a,frame_ns=30+factor*10,duration_ns=factor*10) for a in ACTIONS]
                sessions.append(s)
        rows=summarize(sessions)
        self.assertEqual(rows[0]['ci95'],[2,2])
        self.assertEqual(rows[0]['verdict'],'faster')
        sessions[0].update(gpu_provisional=True,gpu_tier_offenders=['earlier-offender-now-gone'])
        from lightcraft_session_report import markdown
        self.assertIn('PROVISIONAL',markdown(summarize(sessions)))
        self.assertIn('earlier-offender-now-gone',markdown(summarize(sessions)))

    def test_aa_gate_and_calibration_are_explicit(self):
        from lightcraft_session_report import ACTIONS, markdown, variance_components
        sessions=[]
        for side in ('point','main'):
            for pair in range(10):
                s=fixture();s.update(side=side,tier='test',pair=pair,startup_library_ns=10)
                s['samples']=[dict(copy.deepcopy(s['samples'][0]),action=a) for a in ACTIONS]
                sessions.append(s)
        uncalibrated=summarize(sessions,resamples=200)
        self.assertEqual(uncalibrated[0]['verdict'],'sensitivity uncalibrated')
        aa=summarize(sessions,resamples=200,aa=True)
        self.assertTrue(all(r['aa_pass'] for r in aa))
        calibrated=summarize(sessions,resamples=200,calibration={'rows':aa})
        self.assertEqual(calibrated[0]['verdict'],'no measurable change')
        self.assertIn('Minimum detectable effect %',markdown(calibrated))
        calibrated[0]['minimum_detectable_effect_pct']=None
        with self.assertRaisesRegex(ValueError,'MDE'):markdown(calibrated)
        self.assertIsNone(variance_components([[1],[2]])['within_log_sd'])
        self.assertGreater(variance_components([[1,1],[2,2]])['between_log_sd'],0)
        # A narrow interval excluding unity fails A/A, even with negligible variance.
        for s in sessions:
            if s['side']=='main':
                for x in s['samples']:x.update(frame_ns=41,duration_ns=11)
        self.assertFalse(summarize(sessions,resamples=200,aa=True)[0]['aa_pass'])

    def test_result_rejects_pre_dispatch_and_pre_completion_frames(self):
        from lightcraft_real_app import session_result
        from types import SimpleNamespace
        from pathlib import Path
        from unittest.mock import patch
        proof=dict(verified_ns=90,width=1,height=1,candidates=[dict(ns=n,rgb_sha256='result',width=1,height=1) for n in (20,40,60)])
        control=SimpleNamespace(last_capture_proof=proof)
        with patch('lightcraft_real_app.session_frame',return_value=(20,'result')):
            self.assertEqual(session_result(control,Path('unused'),30,not_before=50),(60,'result'))
        self.assertEqual(proof['frame_ns'],60)

    def test_slowdown_is_a_real_recorded_queue_delay_only_on_switch(self):
        from lightcraft_real_app import session_execute
        from unittest.mock import patch
        class Control:
            test_delay_ms=10
            armed_action='switch'
            last_sent_ns=0
            def call(self,method,params):
                self.last_sent_ns=41
                return 'reply'
        control=Control()
        with patch('lightcraft_real_app.time.perf_counter_ns',return_value=30), patch('lightcraft_real_app.time.sleep') as sleep:
            self.assertEqual(session_execute(control,'library.select'),'reply')
            sleep.assert_called_once_with(.01)
        self.assertEqual(control.last_sent_ns,30)
        self.assertEqual(control.last_test_delay['actual_delay_ns'],11)
        control.armed_action='import'
        with patch('lightcraft_real_app.time.sleep') as sleep:
            session_execute(control,'library.select')
            sleep.assert_not_called()

    def test_repeated_lifecycles_reject_overlap_and_false_durations(self):
        s=fixture()
        s['quit_samples']=[dict(sent_ns=100,exit_ns=150,duration_ns=50,exit_code=0),dict(sent_ns=250,exit_ns=300,duration_ns=50,exit_code=0)]
        s['startup_samples']=[dict(sent_ns=170,frame_ns=200,duration_ns=30,capture=dict(frame_ns=200,verified_ns=220,native=True))]
        validate_session(s)
        s['startup_samples'][0]['duration_ns']=20
        with self.assertRaisesRegex(ValueError,'duration'):validate_session(s)
        s['startup_samples'][0]['duration_ns']=30
        s['quit_samples'][1]['sent_ns']=210
        with self.assertRaisesRegex(ValueError,'overlap'):validate_session(s)

    def test_aa_rejects_different_commits_or_one_binary(self):
        from lightcraft_real_app import session_calibration
        config={'aa':True,'revisions':{'point':{'revision':'same','binary':'A'},'main':{'revision':'same','binary':'B'}}}
        self.assertIsNone(session_calibration(config))
        config['revisions']['main']['binary']='A'
        with self.assertRaisesRegex(ValueError,'separately built'):session_calibration(config)
        config['revisions']['main'].update(binary='B',revision='other')
        with self.assertRaisesRegex(ValueError,'same app commit'):session_calibration(config)

    def test_low_latency_transport_handles_fragmented_utf8_and_buffered_lines(self):
        import socket,json
        from lightcraft_real_app import Control
        with socket.socket() as listener:
            listener.bind(('127.0.0.1',0));listener.listen(1)
            with socket.create_connection(listener.getsockname()) as client:
                connection,_=listener.accept()
                with connection:
                    control=Control(client);control.low_latency=True
                    data='{"id":1,"result":"snowman ☃"}\n{"id":2}\n'.encode()
                    for start in range(0,len(data),3):connection.sendall(data[start:start+3])
                    self.assertEqual(json.loads(control.read_reply())['result'],'snowman ☃')
                    self.assertEqual(json.loads(control.read_reply())['id'],2)
                    control.reader.close()

    def test_incomplete_pair_count_cannot_claim_zero_mde_or_a_change(self):
        from lightcraft_session_report import ACTIONS
        sessions=[]
        for side,factor in [('point',2),('main',1)]:
            s=fixture();s.update(side=side,tier='test',pair=0,startup_library_ns=factor*10)
            s['samples']=[dict(copy.deepcopy(s['samples'][0]),action=a,frame_ns=30+factor*10,duration_ns=factor*10) for a in ACTIONS]
            sessions.append(s)
        row=summarize(sessions,resamples=20,aa=True)[0]
        self.assertEqual(row['verdict'],'insufficient paired sessions')
        self.assertIsNone(row['minimum_detectable_effect_pct'])
        self.assertFalse(row['aa_pass'])


if __name__=='__main__': unittest.main()
