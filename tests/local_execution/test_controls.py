import threading
import time

import pytest

from ofa_execution.config import LocalConfig
from ofa_execution.contracts import Answer, Control, Decision, Evidence, ExecutionError, Expectation, Observation, Outcome, Plan, Step, Target, uid
from ofa_execution.engine import Engine
from ofa_execution.files import FileHand
from ofa_execution.planner import DeterministicPlanner
from ofa_execution.policy import Gate


def until(engine,task,predicate):
    deadline=time.monotonic()+3
    while time.monotonic()<deadline:
        snap=engine.snapshot(task)
        if predicate(snap):return snap
        time.sleep(.005)
    raise AssertionError(engine.snapshot(task))


class SlowHand:
    def __init__(self):self.started=threading.Event();self.inputs=[];self.count=0
    def capabilities(self):return {'operations':['file.write']}
    def observe(self,step):return Observation(surface='file',identity={'file':'owned-fixture'},facts={'state':self.count})
    def execute(self,step,before,checkpoint):
        self.started.set()
        for _ in range(200):
            checkpoint();self.inputs.append(time.monotonic());self.count+=1;time.sleep(.003)
        after=self.observe(step)
        return Outcome(status='verified',observation=after,evidence=[Evidence(tier='A',kind='readback',reading_hash=after.hash)])


def test_stop_suppresses_incremental_input_without_retry(tmp_path):
    cfg=LocalConfig(write_roots=[str(tmp_path)]);hand=SlowHand();engine=Engine(cfg,{'files':hand},DeterministicPlanner(cfg))
    try:
        step=Step(operation='file.write',target=Target(path=str(tmp_path/'x.txt')),text='x',expect=Expectation())
        task=engine.submit(uid(),Plan(title='stop',steps=[step]))['task_id']
        snap=until(engine,task,lambda s:s['state']=='approval');a=snap['approval']
        engine.decide(task,Decision(approval_id=a['id'],reading_hash=a['reading_hash'],approve=True))
        assert hand.started.wait(2)
        stopped=time.monotonic();engine.emergency_stop()
        final=until(engine,task,lambda s:s['state']=='unknown')
        assert len(hand.inputs)<200
        assert max(hand.inputs)-stopped<.25
        engine.control(None,Control(action='resume'))
        count=len(hand.inputs);time.sleep(.03)
        assert len(hand.inputs)==count
        assert list(final['effects'].values())[0]['state']=='unknown'
    finally:engine.close()


class QuestionHand:
    human=True
    def capabilities(self):return {}
    def observe(self,step):return Observation(surface='file',identity={'fixture':'question'},facts={})
    def validate_target(self,step,before):
        if not step.target.ref:raise ExecutionError('TARGET_AMBIGUOUS','Choose element',[{'id':'exact-ref','label':'Exact control'}])
    def execute(self,step,before,checkpoint):
        checkpoint();after=self.observe(step)
        return Outcome(status='verified',observation=after,evidence=[Evidence(tier='A',kind='fixture_readback',reading_hash=after.hash)])


def test_clarification_before_effect_and_explicit_answer(tmp_path):
    cfg=LocalConfig(read_roots=[str(tmp_path)]);hand=QuestionHand();engine=Engine(cfg,{'files':hand},DeterministicPlanner(cfg))
    try:
        task=engine.submit(uid(),Plan(title='question',steps=[Step(operation='file.read',target=Target(path=str(tmp_path/'x.txt')))]))['task_id']
        snap=until(engine,task,lambda s:s['state']=='question')
        assert snap['effects']=={}
        engine.answer(task,Answer(question_id=snap['question']['id'],option_id='exact-ref'))
        assert until(engine,task,lambda s:s['state']=='completed')['state']=='completed'
    finally:engine.close()


def test_first_approval_decision_wins_under_race(tmp_path):
    cfg=LocalConfig(write_roots=[str(tmp_path)]);engine=Engine(cfg,{'files':FileHand(cfg)},DeterministicPlanner(cfg))
    try:
        task=engine.submit(uid(),Plan(title='race',steps=[Step(operation='file.write',target=Target(path=str(tmp_path/'x.txt')),text='x',expect=Expectation(kind='file_text',value='x'))]))['task_id']
        a=until(engine,task,lambda s:s['state']=='approval')['approval'];results=[];barrier=threading.Barrier(3)
        def decide(value):
            barrier.wait()
            try:engine.decide(task,Decision(approval_id=a['id'],reading_hash=a['reading_hash'],approve=value));results.append('accepted')
            except ExecutionError as e:results.append(e.code)
        threads=[threading.Thread(target=decide,args=(v,)) for v in [True,False]]
        for thread in threads:thread.start()
        barrier.wait()
        for thread in threads:thread.join()
        assert results.count('accepted')==1
        assert set(results)-{'accepted'} <= {'ALREADY_DECIDED','APPROVAL_STALE'}
    finally:engine.close()


def test_url_scope_private_network_and_unknown_fields(monkeypatch):
    origin='https://allowed.invalid';cfg=LocalConfig(allowed_origins=[origin]);gate=Gate(cfg)
    plan=Plan(title='url',allowed_origins=[origin],steps=[Step(operation='browser.open',url=origin)])
    monkeypatch.setattr('socket.getaddrinfo',lambda *a:[(2,1,6,'',('127.0.0.1',443))])
    with pytest.raises(ExecutionError) as e:gate.screen(plan)
    assert e.value.code=='PRIVATE_NETWORK_DENIED'
    with pytest.raises(ExecutionError):gate.url('file:///private',plan)
    with pytest.raises(ExecutionError):gate.url('https://unplanned.invalid',plan)
    with pytest.raises(ValueError):Step.model_validate({'operation':'browser.click','script':'forbidden'})


def test_queue_and_plan_are_bounded_and_frozen(tmp_path):
    cfg=LocalConfig(write_roots=[str(tmp_path)]);engine=Engine(cfg,{'files':FileHand(cfg)},DeterministicPlanner(cfg))
    try:
        plan=Plan(title='original',steps=[Step(operation='file.write',target=Target(path=str(tmp_path/'x.txt')),text='original',expect=Expectation())])
        first=engine.submit(uid(),plan)['task_id'];until(engine,first,lambda s:s['state']=='approval')
        plan.steps[0].text='untrusted alteration'
        assert engine.snapshot(first)['plan']['steps'][0]['text']=='original'
        for _ in range(3):engine.submit(uid(),plan)
        with pytest.raises(ExecutionError) as e:engine.submit(uid(),plan)
        assert e.value.code=='QUEUE_FULL'
    finally:engine.close()


class HandoffHand:
    human=True
    reads=0
    def capabilities(self):return {}
    def observe(self,step):
        self.reads+=1
        return Observation(surface='file',identity={'fixture':'handoff'},facts={'human_required':self.human})
    def after_handoff(self,step):self.human=False
    def execute(self,step,before,checkpoint):
        checkpoint();after=self.observe(step)
        return Outcome(status='verified',observation=after,evidence=[Evidence(tier='A',kind='fresh_fixture',reading_hash=after.hash)])


def test_explicit_handoff_continue_rereads_current_state(tmp_path):
    cfg=LocalConfig(read_roots=[str(tmp_path)]);hand=HandoffHand();engine=Engine(cfg,{'files':hand},DeterministicPlanner(cfg))
    try:
        task=engine.submit(uid(),Plan(title='handoff',steps=[Step(operation='file.read',target=Target(path=str(tmp_path/'fixture.txt')))]))['task_id']
        snap=until(engine,task,lambda s:s['state']=='handoff');reads=hand.reads
        with pytest.raises(ExecutionError):engine.control(task,Control(action='continue',handoff_id='wrong'))
        assert hand.reads==reads
        engine.control(task,Control(action='continue',handoff_id=snap['handoff']['id']))
        assert until(engine,task,lambda s:s['state']=='completed')['state']=='completed'
        assert hand.reads>reads
    finally:engine.close()
