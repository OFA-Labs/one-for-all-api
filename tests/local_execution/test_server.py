"""Real loopback launcher smoke in an isolated process, no credentials logged."""
import http.client
import json
import os
import secrets
import socket
import subprocess
import sys
import time


def test_real_local_launcher_and_authenticated_http():
    sock=socket.socket();sock.bind(('127.0.0.1',0));port=sock.getsockname()[1];sock.close()
    token=secrets.token_urlsafe(48)
    child=subprocess.Popen([sys.executable,'-m','ofa_execution','--no-browser','--port',str(port)],
                           env={**os.environ,'OFA_LOCAL_TOKEN':token},stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
                           creationflags=0x08000000 if os.name=='nt' else 0)
    try:
        deadline=time.monotonic()+10
        while time.monotonic()<deadline:
            try:
                connection=http.client.HTTPConnection('127.0.0.1',port,timeout=1)
                connection.request('GET','/api/capabilities',headers={'Authorization':'Bearer '+token})
                response=connection.getresponse();body=response.read()
                if response.status==200:break
            except OSError:
                pass
            if child.poll() is not None:raise AssertionError('Local launcher exited before readiness')
            time.sleep(.05)
        else:raise AssertionError('Local launcher readiness timeout')
        assert json.loads(body)['planner']=='deterministic_only'
        assert token.encode() not in body
        connection.close()
        connection=http.client.HTTPConnection('127.0.0.1',port,timeout=2)
        connection.request('GET','/api/capabilities')
        response=connection.getresponse();assert response.status==401
        response.read();connection.close()
    finally:
        if child.poll() is None:child.terminate();child.wait(timeout=5)
