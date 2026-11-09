import copy
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

    def test_empty_texture_queue_shape_is_a_list(self):
        from lightcraft_real_app import session_idle
        self.assertTrue(session_idle({'perf':{'renderQueue':0,'rendersInFlight':0,'pendingSlots':[]}}))
        self.assertFalse(session_idle({'perf':{'renderQueue':0,'rendersInFlight':0,'pendingSlots':['Main']}}))

    def test_unchecked_or_empty_gpu_rejected(self):
        s=fixture(); s['gpu_adapter']=None
        with self.assertRaises(ValueError): validate_session(s)
        s=fixture(); s['samples'][0]['checked']=False
        with self.assertRaises(ValueError): validate_session(s)

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


if __name__=='__main__': unittest.main()
