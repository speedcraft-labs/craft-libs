#!/usr/bin/env python3
"""Generate pinned brush-only 315b configs for Agentbox."""
import hashlib
import json
from pathlib import Path

ROOT = Path('/jobs/work/speedcraft-labs/keep/315b-photocraft-threeway')
TARGET = Path('/jobs/work/speedcraft-labs/targets/315b/pinned')
DRIVER = Path('/jobs/work/speedcraft-labs/wt/315b-craft-libs/crates/journeys/scripts/photocraft_session.py')
PINS = {
    'a': ('74330157cb601573ae4523a95bb9132822fc3918', TARGET/'photocraft-a-mergebase'),
    'b': ('629049f550e5cad1c483fe800a66047cd02bf150', TARGET/'photocraft-b-fork-tip'),
    'c': ('e052eabf4be74612725400955d184f85d208c0f0', TARGET/'photocraft-c-upstream-tip'),
}
BIN_HASHES = {key: hashlib.sha256(binary.read_bytes()).hexdigest() for key, (_, binary) in PINS.items()}
PAYLOADS = {
    'typical': {'path':'/jobs/work/speedcraft-labs/keep/315-photocraft-latency/payloads/photocraft-typical-layered.psd','sha256':'ad14251fe3b44e3a1c95d28b6cdd1e5b577ead48912aa4e93cbaf1e8780f9b1d','dimensions':[4000,3000]},
    'heavy': {'path':'/jobs/work/speedcraft-labs/keep/315-photocraft-latency/payloads/photocraft-heavy-layered.psd','sha256':'64bcfcd57979b88b91c796bfc32389814cb50dfa4a1209c064a218477edf54fa','dimensions':[5000,4800]},
}
UI = {'window':{'width':1600,'height':1000},'update_later':[870,551],'canvas':[92,113,1128,843],'visibility_eye':[1332,610],'blend_dropdown':[1368,551],'blend_options':{'normal':[1388,583],'multiply':[1388,674]},'move_auto_select':[136,49]}
def side(role, build):
    revision, binary = PINS[build]
    return {'name':role,'role':role,'revision':revision,'binary':str(binary),'binary_sha256':BIN_HASHES[build]}
def base(acquisition, pair, tier, planned, sides, proof=False):
    return {'app':'photocraft','acquisition':acquisition,'pair':pair,'tier':tier,'planned_pairs':planned,'expected_driver_sha256':hashlib.sha256(DRIVER.read_bytes()).hexdigest(),'gpu_state':{'graphics_mhz':1350,'memory_mhz':7000},'payload':PAYLOADS[tier],'ui':UI,'sides':sides,'brush_only':True,'pixel_proof':proof,'capture_update_notice':proof,'source_pins':{'merge_base':PINS['a'][0],'fork_tip':PINS['b'][0],'upstream_tip':PINS['c'][0],'recorder':'crates/ui-egui/src/latency.rs sha256=0c5c15480a8ea911b24707a7001a743412d548b3f7fa93f503364ef7aec59653','recorder_commits':{'a':'936a9bb696ce2a957d240b8149051e9bbd7ffa6b','b':'79201e03d81b39df0e2a3c4a38cd21d9fbb80feb','c':'c14b9ae881d59b18c544c0d2a0facf62817ea5d0'},'craft_libs_driver_commit':'0d9528cb383f9e42c8e7cbf84feeb4a031228194','craft_libs_driver_sha256':hashlib.sha256(DRIVER.read_bytes()).hexdigest(),'upstream_recorder_patches':['photocraft-session-latency.patch','photocraft-session-frame-capture-and-dabs.patch','photocraft-session-point-frame-capture.patch','photocraft-session-frame-rgb-capture.patch','photocraft-session-upstream-dab-count.patch']}}
def write_campaign(name, tier, count, factory):
    folder=ROOT/'configs'/f'{name}-{tier}'
    folder.mkdir(parents=True,exist_ok=True)
    for pair in range(count):
        data=factory(pair)
        (folder/f'pair-{pair:02d}.json').write_text(json.dumps(data,indent=2)+'\n')
for tier in PAYLOADS:
    write_campaign('proof',tier,1,lambda pair:base(f'proof-{tier}',pair,tier,1,[side('a','a'),side('b','b'),side('c','c')],True))
    write_campaign('aa',tier,20,lambda pair:base(f'aa-{tier}',pair,tier,20,[side('a','b'),side('b','b')]))
    write_campaign('threeway',tier,10,lambda pair:base(f'threeway-{tier}',pair,tier,10,[side('a','a'),side('b','b'),side('c','c')]))
print('generated configs with driver sha256',hashlib.sha256(DRIVER.read_bytes()).hexdigest())
