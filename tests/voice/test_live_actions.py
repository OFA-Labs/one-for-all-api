import asyncio
import hashlib
from pathlib import Path

import httpx
import pytest

from ofa_execution.config import App, LocalConfig
from ofa_execution.contracts import Evidence, ExecutionError, Expectation, Observation, Outcome, Plan, Step, Target
from ofa_execution.engine import Engine
from ofa_execution.files import FileHand
from ofa_execution.slack import SlackHand
from voice.bridge import EngineBridge
from voice.capabilities import CapabilityDispatcher, ReasoningGate
from voice.discovery import canonicalize
from voice.intent import Router
from voice.runtime import Runtime


class Store:
    def __init__(self): self.data={}
    def read(self): return self.data.copy()
    def write(self,value): self.data=value.copy()


class NativeDialog:
    def request_scope(self,kind,origin,answer): self.answer=answer


async def until(predicate):
    async with asyncio.timeout(3):
        while not predicate(): await asyncio.sleep(.01)


def test_catalog_preserves_real_ambiguity_but_merges_duplicate_installations(tmp_path):
    exe=tmp_path/'slack.exe'; exe.touch()
    result=canonicalize([App(name='Slack',executable=str(exe)),
        App(name='Slack',launch_kind='aumid',launch_identity='Slack.App_12345!App'),
        App(name='Photos',launch_kind='aumid',launch_identity='Microsoft.Windows.Photos_12345!App'),
        App(name='Photos',launch_kind='aumid',launch_identity='Microsoft.OneDrive.Photos_12345!App')])
    config=LocalConfig(apps=result)
    assert config.app('Slack').launch_kind=='aumid'
    assert config.app('Windows Photos').launch_identity.startswith('Microsoft.Windows.')
    router=Router([(alias,a.name) for a in result for alias in [a.name,*a.aliases]])
    intent=router.route('Open Photos')
    assert intent.intent=='clarify' and len(intent.options)==2 and not intent.actions


@pytest.mark.parametrize('name,binary',[('Git Bash','git-bash'),('A friendly app','powershell'),('Windows Security','SecHealthUI'),('helper','winget')])
def test_sensitive_alias_cannot_bypass_native_policy(tmp_path,name,binary):
    path=tmp_path/(binary+'.exe'); path.touch()
    with pytest.raises(ExecutionError): LocalConfig(apps=[App(name=name,executable=str(path))]).app(name)


def test_router_preserves_exact_content_url_and_search_query():
    router=Router({})
    assert router.route('Open https://example.com/MyReport.pdf?Key=AbC').actions[0].args['url'].endswith('/MyReport.pdf?Key=AbC')
    assert router.route('Search for Cats and Dogs on Google').actions[0].args['url'].endswith('q=Cats+and+Dogs')
    result=router.route('Write "Title\\nHello and Goodbye" to MyNotes.md')
    assert result.actions[0].args=={'text':'Title\nHello and Goodbye','filename':'MyNotes.md'}
    assert router.route('write Hello and Goodbye to MyNotes dot md').actions[0].args=={'text':'Hello and Goodbye','filename':'MyNotes.md'}
    assert router.route('read MyNotes dot m d').actions[0].args['filename']=='MyNotes.md'
    assert router.route('Write Hello to MyNotes dot md.').actions[0].args=={'text':'Hello','filename':'MyNotes.md'}
    assert router.route('open example dot com').actions[0].args['url']=='https://example.com'


def test_real_engine_file_write_approval_changed_reading_and_no_model(tmp_path):
    async def run():
        config=LocalConfig(read_roots=[str(tmp_path)],write_roots=[str(tmp_path)])
        engine=Engine(config,{'files':FileHand(config)},None)
        bridge=EngineBridge(engine)
        runtime=Runtime(config,bridge,Store(),NativeDialog(),asyncio.get_running_loop(),lambda:None,lambda *_:None)
        # Grant fixture folder through the same native callback seam, not a browser path.
        dialog=runtime.overlay
        runtime.request_scope('write_folder','http://127.0.0.1:3000'); dialog.answer(str(tmp_path))
        await asyncio.sleep(.01)
        reasoning=ReasoningGate(None)
        dispatcher=CapabilityDispatcher({'file.write_text':runtime.handle,'file.read':runtime.handle},reasoning)
        try:
            action=Router({}).route('write "Exact Case" to Notes.md').actions
            task=asyncio.create_task(dispatcher.execute(action,'en','write-one'))
            await until(lambda:bridge.pending is not None)
            old=bridge.pending.copy()
            assert not (tmp_path/'Notes.md').exists()
            (tmp_path/'Notes.md').write_text('Changed externally',encoding='utf-8')
            bridge.decide(old['task_id'],{'approval_id':old['approval']['id'],'reading_hash':old['approval']['reading_hash'],'approve':True})
            await until(lambda:bridge.pending and bridge.pending['approval']['id']!=old['approval']['id'])
            assert (tmp_path/'Notes.md').read_text()=='Changed externally'
            with pytest.raises(ExecutionError):
                bridge.decide(old['task_id'],{'approval_id':old['approval']['id'],'reading_hash':old['approval']['reading_hash'],'approve':True})
            card=bridge.pending
            bridge.decide(card['task_id'],{'approval_id':card['approval']['id'],'reading_hash':card['approval']['reading_hash'],'approve':True})
            assert await task
            assert (tmp_path/'Notes.md').read_text()=='Exact Case'
            assert dispatcher.bindings['artifact_path']==str(tmp_path/'Notes.md') and reasoning.calls==0
            assert await dispatcher.execute(Router({}).route('read Notes.md').actions,'en','read-one')
        finally: engine.close()
    asyncio.run(run())


def test_disconnect_invalidates_pending_native_scope_callback(tmp_path):
    async def run():
        config=LocalConfig()
        runtime=Runtime(config,None,Store(),NativeDialog(),asyncio.get_running_loop(),lambda:None,lambda *_:None)
        runtime.request_scope('write_folder','http://127.0.0.1:3000')
        runtime.revoke()
        runtime.overlay.answer(str(tmp_path))
        await asyncio.sleep(.01)
        assert not config.write_roots
    asyncio.run(run())


def slack_fixture(tmp_path, mode='success'):
    path=tmp_path/'review.md'; path.write_text('# Exact review\n',encoding='utf-8')
    calls=[]
    def handler(request):
        calls.append(request)
        if request.url.path.endswith('auth.test'):
            return httpx.Response(200,json={'ok':True,'team_id':'T123ABC456','team':'Local fixture'})
        if request.url.path.endswith('files.getUploadURLExternal'):
            return httpx.Response(200,json={'ok':True,'file_id':'F123ABC456','upload_url':'https://files.slack.com/upload/v1/fake' if mode!='unsafe' else 'https://attacker.example/upload/v1/fake'})
        if request.url.path.startswith('/upload/'):
            assert 'authorization' not in request.headers
            assert request.content==path.read_bytes()
            return httpx.Response(200,text='OK')
        if request.url.path.endswith('files.completeUploadExternal'):
            if mode=='lost_reply': raise httpx.ReadTimeout('mock lost reply',request=request)
            return httpx.Response(200,json={'ok':True,'files':[{'id':'F123ABC456'}]})
        assert request.url.path.endswith('files.info')
        return httpx.Response(200,json={'ok':True,'file':{'id':'F123ABC456','size':path.stat().st_size,'shares':{'private':{'G123ABC456':[{'ts':'1.2'}]}}}})
    config=LocalConfig(read_roots=[str(tmp_path)])
    hand=SlackHand(config,'local-test-token',['G123ABC456'],httpx.MockTransport(handler))
    step=Step(operation='slack.send_file',target=Target(path=str(path),destination='G123ABC456'),expect=Expectation())
    return hand,step,calls,path


def test_slack_protocol_exact_bytes_and_channel_readback_locally(tmp_path):
    hand,step,calls,path=slack_fixture(tmp_path)
    try:
        reading=hand.observe(step)
        assert reading.facts['sha256']==hashlib.sha256(path.read_bytes()).hexdigest()
        result=hand.execute(step,reading,lambda:None)
        assert result.status=='verified' and result.evidence[0].kind=='slack_file_share_readback'
        assert len(calls)==5
    finally: hand.close()


def test_slack_lost_completion_reply_never_retries_mutation(tmp_path):
    hand,step,calls,_=slack_fixture(tmp_path,'lost_reply')
    try:
        assert hand.execute(step,hand.observe(step),lambda:None).status=='unknown'
        assert sum(r.url.path.endswith('files.completeUploadExternal') for r in calls)==1
        assert len(calls)==4
    finally: hand.close()


def test_slack_refuses_changed_file_and_untrusted_upload_host(tmp_path):
    hand,step,calls,path=slack_fixture(tmp_path,'unsafe')
    try:
        reading=hand.observe(step)
        calls.clear()
        path.write_text('changed',encoding='utf-8')
        with pytest.raises(ExecutionError,match='changed'): hand.execute(step,reading,lambda:None)
        assert not calls
        with pytest.raises(ExecutionError,match='untrusted'): hand.execute(step,hand.observe(step),lambda:None)
        assert len(calls)==1
    finally: hand.close()


def test_stop_during_real_engine_approval_prevents_file_write(tmp_path):
    async def run():
        config=LocalConfig(write_roots=[str(tmp_path)])
        engine=Engine(config,{'files':FileHand(config)},None)
        bridge=EngineBridge(engine)
        try:
            path=tmp_path/'stopped.md'
            task=asyncio.create_task(bridge.execute(Step(operation='file.write',target=Target(path=str(path)),text='Never write',expect=Expectation()),'stop-test'))
            await until(lambda:bridge.pending is not None)
            bridge.stop(); task.cancel()
            await asyncio.gather(task,return_exceptions=True)
            bridge.resume(); await asyncio.sleep(.05)
            assert not path.exists()
        finally: engine.close()
    asyncio.run(run())
