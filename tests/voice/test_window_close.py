"""Owned Win32 fixture: no personal window or unsaved document is closed."""
import os
import sys
import time
import pytest
from ofa_execution.config import App, LocalConfig
from ofa_execution.contracts import Plan, Step, Target, Expectation, Decision, Control, uid
from ofa_execution.engine import Engine
from ofa_execution.windows import DesktopHand

pytestmark=pytest.mark.skipif(os.name!='nt' or os.getenv('OFA_INTERACTIVE_TESTS')!='1',reason='Set OFA_INTERACTIVE_TESTS=1 in an interactive Windows session')


@pytest.mark.parametrize('unsaved',[False,True])
def test_safe_close_requires_approval_and_preserves_unsaved_work(unsaved):
    cfg=LocalConfig(apps=[App(name='Owned Close Pad',executable=getattr(sys,'_base_executable',sys.executable),
        arguments=['-m','ofa_execution.testpad']+(['--unsaved'] if unsaved else []),window_title='OFA Execution Test Pad')])
    hand=DesktopHand(cfg); engine=Engine(cfg,{'desktop':hand},None)
    task=engine.submit(uid(),Plan(title='Close fixture',steps=[Step(operation='app.open',target=Target(app='Owned Close Pad')),
        *[Step(operation=operation,target=Target(app='Owned Close Pad')) for operation in ('window.minimize','window.restore','window.maximize','window.restore','window.focus')],
        Step(operation='window.close',target=Target(app='Owned Close Pad'),expect=Expectation())]))['task_id']
    try:
        deadline=time.monotonic()+15
        while time.monotonic()<deadline:
            snap=engine.snapshot(task)
            if snap['state']=='approval': break
            if snap['state'] in {'failed','unknown'}: pytest.fail(str(snap['error']))
            time.sleep(.02)
        assert snap['state']=='approval'
        assert hand.owned_processes[0].poll() is None
        card=snap['approval']
        engine.decide(task,Decision(approval_id=card['id'],reading_hash=card['reading_hash'],approve=True))
        deadline=time.monotonic()+7
        while time.monotonic()<deadline:
            snap=engine.snapshot(task)
            if snap['state'] in {'completed','handoff','unknown','failed'}: break
            time.sleep(.02)
        assert snap['state']==('handoff' if unsaved else 'completed'),snap['error']
        if unsaved:
            assert hand.owned_processes[0].poll() is None
            assert snap['effects'] and all(e['state']=='unknown' for e in snap['effects'].values())
            engine.control(task,Control(action='cancel'))
    finally:
        engine.close()
        for process in hand.owned_processes:
            if process.poll() is None: process.terminate(); process.wait(timeout=3)
