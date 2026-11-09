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

    def test_empty_texture_queue_shape_is_a_list(self):
        from lightcraft_real_app import session_idle
        self.assertTrue(session_idle({'perf':{'renderQueue':0,'rendersInFlight':0,'pendingSlots':[]}}))
        self.assertFalse(session_idle({'perf':{'renderQueue':0,'rendersInFlight':0,'pendingSlots':['Main']}}))

    def test_unchecked_or_empty_gpu_rejected(self):
        s=fixture(); s['gpu_adapter']=None
        with self.assertRaises(ValueError): validate_session(s)
        s=fixture(); s['samples'][0]['checked']=False
        with self.assertRaises(ValueError): validate_session(s)

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
