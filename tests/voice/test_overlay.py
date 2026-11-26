import json
import os
import struct
from pathlib import Path

import pytest


def test_popup_text_requires_armed_session_and_reuses_verified_router():
    import asyncio
    from voice.config import Settings
    from voice.intent import Router
    from voice.session import Session
    from voice.state import State

    class Bridge:
        pending=None
        calls=[]
        async def open(self,name,command_id): self.calls.append(name); return True
        def stop(self): pass

    class NoStt:
        def transcribe(self,feed): raise AssertionError('Typed input must not open STT')

    async def run():
        bridge=Bridge()
        session=Session(Settings(),Router({'whatsapp':'WhatsApp'}),NoStt(),None,None,bridge,None,lambda *_:None)
        await session.submit_text('Open WhatsApp')
        assert session.machine.state==State.IDLE and not bridge.calls
        session.state(State.ARMED); session.state(State.LISTENING)
        async def ack(language): pass
        session._ack=ack
        await session.submit_text('Open WhatsApp'); await session.response
        assert bridge.calls==['WhatsApp'] and session.machine.state==State.LISTENING
        assert session.capture._stream is None
    asyncio.run(run())


def test_liquid_orb_asset_is_packaged_as_a_high_dpi_animation():
    assets=Path(__file__).parents[2]/'voice/assets'
    data=(assets/'liquid-orb.gif').read_bytes()
    assert data[:6] in (b'GIF87a',b'GIF89a')
    assert struct.unpack('<HH',data[6:10])==(240,240)
    meta=json.loads((assets/'orb.json').read_text())
    assert meta['frames']>1 and meta['playback_rate']==3


def test_consent_cards_use_concise_explicit_copy():
    from voice.overlay import SCOPE_LABELS, pairing_prompt

    title, lines = pairing_prompt('http://127.0.0.1:3000', 'ABC123')
    assert title == 'Connect this computer?'
    assert 'http://127.0.0.1:3000' in lines[0]
    assert any('ABC123' in line for line in lines)
    assert all(len(line) < 120 for line in lines)
    assert set(SCOPE_LABELS) == {
        'windows', 'read_folder', 'write_folder', 'register_app',
        'startup_on', 'startup_off',
    }
    assert all(len(body) <= 2 for _, body in SCOPE_LABELS.values())


@pytest.mark.skipif(os.getenv('OFA_INTERACTIVE_TESTS')!='1',reason='Owned Tk surface needs an interactive desktop')
def test_native_panel_animates_handles_input_and_hides_on_idle():
    from voice.overlay import Overlay
    panel=Overlay(lambda:None)
    sent=[]
    panel.callbacks['send']=sent.append
    try:
        panel.emit('LISTENING'); panel.pump(); panel.root.update()
        first=panel.frame_index
        panel._animate()
        assert panel.visible and panel.frame_index!=first
        panel.entry.delete(0,'end'); panel.entry.insert(0,'Open WhatsApp')
        panel._submit(None)
        assert sent==['Open WhatsApp'] and panel.entry.get()==''
        assert panel.canvas.find_withtag('Stop microphone')
        assert panel.canvas.find_withtag('Interrupt speech')
        panel.emit('IDLE'); panel.pump()
        assert not panel.visible and panel.root.state()=='withdrawn'
    finally:
        panel.root.destroy()
