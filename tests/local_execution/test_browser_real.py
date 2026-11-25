"""Opt-in real browse integration; launched by tools/local_execution/browser-smoke.cjs."""
import os
import threading
import time
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer

import pytest

from ofa_execution.browser import BrowserHand
from ofa_execution.config import LocalConfig
from ofa_execution.contracts import Decision,Expectation,Plan,Step,Target,uid
from ofa_execution.engine import Engine
from ofa_execution.mcp import McpClient
from ofa_execution.planner import DeterministicPlanner


pytestmark=pytest.mark.skipif(not os.environ.get('OFA_BROWSE_BINARY'),reason='Run the isolated real-browser smoke script')


class Page(BaseHTTPRequestHandler):
    def do_GET(self):
        body=b'''<!doctype html><title>OFA browser test</title><h1>OFA owned fixture</h1><label for="message">Message</label><input id="message"><input type="hidden" name="context" value="safe-context"><button id="send" onclick="document.querySelector('p').textContent='Sent: '+document.querySelector('input').value">Send</button><p>Not sent</p>'''
        self.send_response(200);self.send_header('Content-Type','text/html');self.end_headers();self.wfile.write(body)
    def log_message(self,*args):pass


def test_real_browse_plan_park_commit_and_readback():
    server=ThreadingHTTPServer(('127.0.0.1',0),Page)
    threading.Thread(target=server.serve_forever,daemon=True).start()
    origin=f'http://127.0.0.1:{server.server_port}'
    cfg=LocalConfig(browser_command=[os.environ['OFA_BROWSE_BINARY'],'mcp'],fixture_origins=[origin])
    client=McpClient(cfg.browser_command,{'OPENCODE_BROWSER_PORT':os.environ['OPENCODE_BROWSER_PORT']})
    hand=BrowserHand(cfg,client);engine=Engine(cfg,{'browser':hand},DeterministicPlanner(cfg))
    try:
        status=client.call('status',{})
        assert status.get('connected'),status
        plan=Plan(title='Real browser deterministic fixture',allowed_origins=[origin],steps=[
            Step(operation='browser.open',url=origin+'/'),
            Step(operation='browser.fill',target=Target(name='Message',role='edit'),text='hello',expect=Expectation(kind='value',value='hello')),
            Step(operation='browser.click',target=Target(name='Send',role='button'),expect=Expectation(kind='text',value='Sent: hello'))])
        task=engine.submit(uid(),plan)['task_id'];decided=set();deadline=time.monotonic()+25
        while time.monotonic()<deadline:
            snap=engine.snapshot(task)
            if snap['state']=='approval' and snap['approval']['id'] not in decided:
                card=snap['approval'];decided.add(card['id'])
                assert any(e['extra'].get('hidden') for e in card['reading']['elements'])
                engine.decide(task,Decision(approval_id=card['id'],reading_hash=card['reading_hash'],approve=True))
            if snap['state'] in {'completed','failed','unknown'}:break
            time.sleep(.03)
        assert snap['state']=='completed',(snap['state'],snap['step'],snap['error'],client.last_error)
        assert len(decided)==2
        assert any(e['name']=='Sent: hello' for e in snap['observation']['elements'])
        assert len(hand.tabs)==1
        close=Step(operation='browser.close')
        assert hand.execute(close,hand.observe(close),lambda:None).status=='verified'
    finally:
        engine.close();hand.close();server.shutdown();server.server_close()
