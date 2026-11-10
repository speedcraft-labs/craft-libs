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
        observations=iter([(181,125),(600,400),(900,500)])
        class Control:
            def call(self,method):
                calls.append(method);clock[0],done=next(observations)
                return {'perf':{'renderQueue':0,'rendersInFlight':0,'pendingSlots':[]},'activity':[] if done==500 else [{'done':done,'total':500}],'tasks':[],'unsaved':None}
        with patch('lightcraft_real_app.time.monotonic',side_effect=lambda:clock[0]), patch('lightcraft_real_app.time.perf_counter_ns',side_effect=lambda:clock[0]*1_000_000_000), patch('lightcraft_real_app.time.sleep'):
            session_drain(Control(),record,'before-idle-quit',require_saved=True)
        self.assertEqual(record['samples'],original)
        self.assertEqual(record['background_drains'][0]['end_ns'],900_000_000_000)
        self.assertEqual(len(record['background_drains'][0]['progress']),2)
        self.assertEqual(calls,['ui.inspect']*3)

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
            def run(directory,provisional):
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
            def run(directory,provisional):
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
            def run(directory,provisional):
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


if __name__=='__main__': unittest.main()
