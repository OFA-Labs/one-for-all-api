"""Real UIA/SendInput integration against an owned disposable Win32 app."""
import os
import sys
import time
import ctypes

import pytest

from ofa_execution.config import App, LocalConfig
from ofa_execution.contracts import Control, Decision, Expectation, Plan, Step, Target, uid
from ofa_execution.engine import Engine
from ofa_execution.planner import DeterministicPlanner
from ofa_execution.windows import DesktopHand
from ofa_execution.takeover import TakeoverMonitor
from ofa_execution.hotkey import StopHotkey
from ofa_execution.windows import Input,KeyInput


pytestmark=pytest.mark.skipif(os.name!='nt',reason='Real Windows interactive session required')


def test_real_native_multistep_approval_input_and_readback():
    from ofa_execution.windows import user
    cfg=LocalConfig(apps=[App(name='OFA Test Pad',executable=getattr(sys,'_base_executable',sys.executable),
                              arguments=['-m','ofa_execution.testpad'],window_title='OFA Execution Test Pad',
                              writable=True,capture=True)])
    hand=DesktopHand(cfg);engine=Engine(cfg,{'desktop':hand},DeterministicPlanner(cfg))
    monitor=TakeoverMonitor(lambda:hand.active_window,engine.user_takeover).start()
    app=Target(app='OFA Test Pad')
    try:
        assert monitor.available,'Target-window takeover hook could not be installed'
        plan=Plan(title='Real native execution fixture',steps=[
            Step(operation='app.open',target=app),
            Step(operation='window.minimize',target=app),
            Step(operation='window.restore',target=app),
            Step(operation='window.focus',target=app),
            Step(operation='desktop.fill',target=Target(app='OFA Test Pad',role='edit'),text='hello',expect=Expectation(kind='value',value='hello')),
            Step(operation='desktop.type',target=Target(app='OFA Test Pad',role='edit'),text='!',expect=Expectation(kind='value',value='!hello')),
            Step(operation='desktop.click',target=Target(app='OFA Test Pad',name='Apply',role='button'),expect=Expectation(kind='text',value='Result: !hello')),
            Step(operation='desktop.screenshot',target=app)])
        task=engine.submit(uid(),plan)['task_id'];approved=set();deadline=time.monotonic()+25
        while time.monotonic()<deadline:
            snap=engine.snapshot(task)
            if snap['state']=='approval' and snap['approval']['id'] not in approved:
                card=snap['approval'];approved.add(card['id'])
                engine.decide(task,Decision(approval_id=card['id'],reading_hash=card['reading_hash'],approve=True))
            if snap['state'] in {'completed','failed','unknown'}:break
            time.sleep(.03)
        assert snap['state']=='completed',(snap['state'],snap['step'],snap['error'],[(e['name'],e['value']) for e in (snap['observation'] or {}).get('elements',[])])
        assert len(approved)==3
        assert snap['observation']['frame'].startswith('data:image/bmp;base64,')
        assert all(e['state']=='verified' for e in snap['effects'].values())
        assert any('Result: !hello' in e['name'] for e in snap['observation']['elements'])
        # Actual untagged Windows input in our own fixture, not a personal app.
        follow=engine.submit(uid(),Plan(title='takeover fixture',steps=[Step(operation='desktop.fill',target=Target(app='OFA Test Pad',role='edit'),text='must not execute',expect=Expectation(kind='value',value='must not execute'))]))['task_id']
        deadline=time.monotonic()+3
        while engine.snapshot(follow)['state']!='approval' and time.monotonic()<deadline:time.sleep(.01)
        events=(Input*2)(Input(type=1,ki=KeyInput(0,ord('x'),4,0,0)),Input(type=1,ki=KeyInput(0,ord('x'),6,0,0)))
        start=time.monotonic();assert user.SendInput(2,events,ctypes.sizeof(Input))==2
        deadline=start+2
        while engine.snapshot(follow)['state']!='paused' and time.monotonic()<deadline:time.sleep(.005)
        paused=engine.snapshot(follow)
        assert paused['state']=='paused',paused['state']
        assert time.monotonic()-start<.25
        assert paused['effects']=={}
        assert any(e['type']=='user_takeover' for e in paused['events'])
        engine.control(follow,Control(action='cancel'))
        hotkey=StopHotkey(engine.emergency_stop).start()
        try:
            assert hotkey.available,'Default stop hotkey is unavailable on this test machine'
            ctypes.windll.user32.PostThreadMessageW(hotkey.thread_id,0x0312,0x4F46,0)
            deadline=time.monotonic()+2
            while not engine.capabilities()['stopped'] and time.monotonic()<deadline:time.sleep(.005)
            assert engine.capabilities()['stopped']
        finally:hotkey.close()
    finally:
        monitor.close()
        engine.close()
        for process in hand.owned_processes:
            if process.poll() is None:
                process.terminate();process.wait(timeout=3)


def test_real_protected_uia_field_hands_off_without_read_or_type():
    cfg=LocalConfig(apps=[App(name='OFA Protected Pad',executable=getattr(sys,'_base_executable',sys.executable),arguments=['-m','ofa_execution.testpad','--protected'],window_title='OFA Execution Test Pad',writable=True,capture=True)])
    hand=DesktopHand(cfg);engine=Engine(cfg,{'desktop':hand},DeterministicPlanner(cfg))
    try:
        task=engine.submit(uid(),Plan(title='Protected field fixture',steps=[Step(operation='app.open',target=Target(app='OFA Protected Pad')),Step(operation='desktop.fill',target=Target(app='OFA Protected Pad',role='edit'),text='must not be typed',expect=Expectation(kind='value',value='must not be typed'))]))['task_id']
        deadline=time.monotonic()+10
        while time.monotonic()<deadline:
            snap=engine.snapshot(task)
            if snap['state'] in {'handoff','failed','unknown'}:break
            time.sleep(.02)
        assert snap['state']=='handoff',(snap['state'],snap['error'])
        protected=[e for e in snap['observation']['elements'] if e['protected']]
        assert protected and all(e['value'] is None and e['name']=='[protected]' for e in protected)
        assert not snap['effects']
        assert snap['observation']['frame'] is None
        engine.control(task,Control(action='cancel'))
    finally:
        engine.close()
        for process in hand.owned_processes:
            if process.poll() is None:process.terminate();process.wait(timeout=3)
