import time

import pytest
from fastapi.testclient import TestClient

from ofa_execution.api import create_app
from ofa_execution.config import LocalConfig
from ofa_execution.contracts import (Command, Control, Decision, Evidence, ExecutionError,
                                     Observation, Outcome, Plan, Step, Target, Expectation, uid)
from ofa_execution.engine import Engine
from ofa_execution.files import FileHand
from ofa_execution.planner import DeterministicPlanner, MockPlannerAdapter
from ofa_execution.policy import Gate


def wait(engine, task_id, states, timeout=3):
    end=time.monotonic()+timeout
    while time.monotonic()<end:
        snap=engine.snapshot(task_id)
        if snap['state'] in states:
            return snap
        time.sleep(.01)
    raise AssertionError(engine.snapshot(task_id))


@pytest.fixture
def local(tmp_path):
    cfg=LocalConfig(read_roots=[str(tmp_path)],write_roots=[str(tmp_path)])
    engine=Engine(cfg,{'files':FileHand(cfg)},DeterministicPlanner(cfg))
    yield engine,tmp_path
    engine.close()


def file_step(path,text):
    return Step(operation='file.write',target=Target(path=str(path)),text=text,
                expect=Expectation(kind='file_text',value=text))


def approve(engine, task_id, snapshot):
    card=snapshot['approval']
    return engine.decide(task_id,Decision(approval_id=card['id'],reading_hash=card['reading_hash'],approve=True))


def test_real_file_park_commit_verify(local):
    engine,folder=local
    path=folder/'sample.txt'
    task=engine.submit(uid(),Plan(title='write',steps=[file_step(path,'exact text')]))['task_id']
    snap=wait(engine,task,{'approval'})
    assert not path.exists()
    assert snap['approval']['exact_action']['text']=='exact text'
    approve(engine,task,snap)
    done=wait(engine,task,{'completed','failed','unknown'})
    assert done['state']=='completed',done
    assert path.read_text()=='exact text'
    assert list(done['effects'].values())[0]['state']=='verified'
    assert [e['sequence'] for e in done['events']]==list(range(1,done['last_sequence']+1))


def test_changed_reading_rebuilds_card(local):
    engine,folder=local
    path=folder/'sample.txt';path.write_text('before')
    task=engine.submit(uid(),Plan(title='changed',steps=[file_step(path,'after')]))['task_id']
    snap=wait(engine,task,{'approval'})
    path.write_text('human edit')
    approve(engine,task,snap)
    deadline=time.monotonic()+2
    while time.monotonic()<deadline:
        newer=engine.snapshot(task)
        if newer['approval'] and newer['approval']['id']!=snap['approval']['id']:
            break
        time.sleep(.01)
    assert path.read_text()=='human edit'
    assert newer['approval']['reading']['facts']['text']=='human edit'
    approve(engine,task,newer)
    assert wait(engine,task,{'completed'})['state']=='completed'


def test_reject_and_cancel_preserve_existing_file(local):
    engine,folder=local
    path=folder/'sample.txt';path.write_text('original')
    task=engine.submit(uid(),Plan(title='reject',steps=[file_step(path,'change')]))['task_id']
    snap=wait(engine,task,{'approval'});card=snap['approval']
    engine.decide(task,Decision(approval_id=card['id'],reading_hash=card['reading_hash'],approve=False))
    assert wait(engine,task,{'failed'})['error']['code']=='REJECTED'
    assert path.read_text()=='original'


def test_pause_rebuilds_approval_and_global_stop(local):
    engine,folder=local
    task=engine.submit(uid(),Plan(title='pause',steps=[file_step(folder/'a.txt','a')]))['task_id']
    snap=wait(engine,task,{'approval'})
    engine.emergency_stop()
    with pytest.raises(ExecutionError,match='Emergency stop'):
        engine.submit(uid(),Plan(title='blocked',steps=[file_step(folder/'b.txt','b')]))
    assert not (folder/'a.txt').exists()
    engine.control(None,Control(action='resume'))
    newer=wait(engine,task,{'approval'})
    deadline=time.monotonic()+2
    while newer['approval']['id']==snap['approval']['id'] and time.monotonic()<deadline:
        time.sleep(.01);newer=engine.snapshot(task)
    assert newer['approval']['id']!=snap['approval']['id']
    engine.control(task,Control(action='cancel'))
    assert wait(engine,task,{'cancelled'})['state']=='cancelled'


def test_command_idempotency_and_conflict(local):
    engine,folder=local
    plan=Plan(title='idempotent',steps=[file_step(folder/'sample.txt','x')]);key=uid()
    first=engine.submit(key,plan)
    assert engine.submit(key,plan)==first
    with pytest.raises(ExecutionError) as exc:
        engine.submit(key,Plan(title='other',steps=[file_step(folder/'sample.txt','y')]))
    assert exc.value.code=='COMMAND_ID_CONFLICT'


def test_typed_command_retry_uses_original_input_not_generated_step_ids(local):
    engine,folder=local
    path=folder/'read.txt';path.write_text('fixture')
    command=Command(command_id=uid(),text='read file '+str(path))
    first=engine.command(command)
    assert engine.command(command)==first
    assert len(engine.tasks)==1
    with pytest.raises(ExecutionError) as exc:
        engine.command(command.model_copy(update={'text':'read file '+str(folder/'other.txt')}))
    assert exc.value.code=='COMMAND_ID_CONFLICT'


@pytest.mark.parametrize('damage',['signature','reuse','reading','action','epoch','restart'])
def test_signed_token_rejects_invalid_grants(local,damage):
    engine,folder=local;gate=engine.gate;step=file_step(folder/'x.txt','x')
    reading=engine.hands['files'].observe(step)
    token=gate.sign('task',step,reading,0)
    if damage=='signature':token=token[:-1]+('a' if token[-1]!='a' else 'b')
    if damage=='reuse':gate.consume(token,'task',step,reading,0)
    if damage=='reading':reading.facts['text']='different'
    if damage=='action':step.text='other'
    if damage=='restart':gate=Gate(engine.config)
    with pytest.raises(ExecutionError):gate.consume(token,'task',step,reading,1 if damage=='epoch' else 0)


def test_expired_token(local):
    engine,folder=local
    cfg=engine.config.model_copy(update={'approval_seconds':.01})
    gate=Gate(cfg);step=file_step(folder/'x.txt','x');reading=engine.hands['files'].observe(step)
    token=gate.sign('task',step,reading,0);time.sleep(.02)
    with pytest.raises(ExecutionError) as exc:gate.consume(token,'task',step,reading,0)
    assert exc.value.code=='TOKEN_EXPIRED'


def test_local_auth_origin_host_and_extra_fields(local):
    engine,_=local;secret='test-fixture-only-'+'x'*48
    with TestClient(create_app(engine,secret)) as client:
        assert client.get('/api/capabilities').status_code==401
        headers={'Authorization':'Bearer '+secret}
        assert client.get('/api/capabilities',headers=headers).status_code==200
        assert client.get('/api/capabilities',headers={**headers,'Origin':'https://evil.invalid'}).status_code==403
        assert client.get('/api/capabilities',headers={**headers,'Host':'evil.invalid'}).status_code==403
        assert client.post('/api/commands',headers=headers,json={'text':'anything','code':'arbitrary script'}).status_code==422


def test_path_escape_missing_and_no_provider_requirements(local,tmp_path):
    engine,folder=local
    with pytest.raises(ExecutionError):engine.config.file(str(folder.parent/'outside.txt'),True)
    with pytest.raises(ExecutionError):engine.hands['files'].observe(Step(operation='file.read',target=Target(path=str(folder/'missing.txt'))))
    with pytest.raises(ExecutionError) as exc:engine.command(Command(text='review my code intelligently'))
    assert exc.value.code=='UNSUPPORTED_COMMAND'
    assert engine.capabilities()['planner']=='deterministic_only'


def test_mock_multistep_plan_is_execution_not_reasoning(local):
    engine,folder=local
    plan=Plan(title='fixture',steps=[file_step(folder/'first.txt','one'),file_step(folder/'second.txt','two')])
    engine.planner=MockPlannerAdapter({'fixture':plan})
    task=engine.command(Command(text='fixture'))['task_id']
    assert engine.snapshot(task)['plan']['source']=='mock_planner'
    approve(engine,task,wait(engine,task,{'approval'}))
    deadline=time.monotonic()+2
    while time.monotonic()<deadline:
        snap=engine.snapshot(task)
        if snap['state']=='approval' and snap['step']==1:break
        time.sleep(.01)
    assert (folder/'first.txt').read_text()=='one'
    assert not (folder/'second.txt').exists()
    approve(engine,task,snap)
    assert wait(engine,task,{'completed'})['state']=='completed'


class LostReplyHand:
    count=0
    def capabilities(self):return {'operations':['file.write']}
    def observe(self,step):return Observation(surface='file',identity={'file':'fixture'},facts={'version':'1'})
    def execute(self,step,before,checkpoint):
        checkpoint();self.count+=1
        raise ExecutionError('DISCONNECTED','Lost after the actual effect.')


def test_commit_disconnect_unknown_never_retried(local):
    engine,folder=local;hand=LostReplyHand();engine.hands['files']=hand
    task=engine.submit(uid(),Plan(title='lost',steps=[file_step(folder/'x.txt','x')]))['task_id']
    approve(engine,task,wait(engine,task,{'approval'}))
    assert wait(engine,task,{'unknown'})['state']=='unknown'
    engine.control(task,Control(action='resume'))
    assert hand.count==1
