"""CPU-only scheduling checks; never starts an app or takes a benchmark lock."""
import importlib.util,json
from pathlib import Path
k=Path(__file__).parent;spec=importlib.util.spec_from_file_location('operator_pairs',k/'run-pairs.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
c={'sessions':10,'sides':['point','main'],'single_side_acquisitions':True};plan=list(m.acquisition_plan(c,[]))
assert len(plan)==20 and len({tag for pair,sides,tag in plan})==20
assert [(pair,next(iter(sides))) for pair,sides,tag in plan[:8]]==[(0,'point'),(0,'main'),(1,'main'),(1,'point'),(2,'point'),(2,'main'),(3,'main'),(3,'point')]
assert list(m.acquisition_plan(c,[{'pair':0,'side':'point'}]))[0][1]=={'main'}
assert list(m.acquisition_plan(c,[{'pair':0,'side':'main'},{'pair':0,'side':'point'}]))[0][0]==1
ordinary=dict(c,single_side_acquisitions=False);assert len(list(m.acquisition_plan(ordinary,[])))==10 and all(sides=={'point','main'} and tag==str(pair) for pair,sides,tag in m.acquisition_plan(ordinary,[]))
u=dict(c,sides=['point','main','upstream'],acquisition_sides=['upstream']);assert all(sides=={'upstream'} for pair,sides,tag in m.acquisition_plan(u,[]))
print('Six scheduling checks pass: balanced AB/BA, unique acquisitions, resumable missing build, completed-pair skip, original paired mode, upstream-only mode.')
