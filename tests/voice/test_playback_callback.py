import asyncio
from types import SimpleNamespace
import pytest
from voice.audio import Playback


def test_callback_marks_actual_nonzero_output_and_interrupt_silence(monkeypatch):
    class Stream:
        latency=0
        def __init__(self,**kwargs): self.callback=kwargs['callback']; self.finished=kwargs['finished_callback']
        def start(self): pass
        def abort(self): self.finished()
        def close(self): pass
    monkeypatch.setattr('voice.audio.sd.RawOutputStream',Stream)
    async def run():
        events=[]; playback=Playback(None); playback.on_event=lambda kind,payload:events.append((kind,payload))
        playback.start(); playback.mark('ack_first_sample','u1')
        timing=SimpleNamespace(outputBufferDacTime=123.0)
        out=bytearray(960)
        playback._stream.callback(out,480,timing,None)
        await asyncio.sleep(0)
        assert not events  # Opening output does not mean an acknowledgement played.
        await playback.write(b'\x01\x00'*480,playback.epoch)
        playback._stream.callback(out,480,timing,None)
        await asyncio.sleep(0)
        assert events[0][0]=='ack_first_sample' and events[0][1]['measurement']=='output_callback_estimate'
        old=playback.epoch
        await playback.write(b'\x02\x00'*480,old)
        playback.interrupt()
        playback._stream.callback(out,480,timing,None)
        await asyncio.sleep(0)
        assert not any(out) and events[-1][0]=='playback_silent'
        with pytest.raises(asyncio.CancelledError): await playback.write(b'\x01\x00',old)
        old_stream=playback._stream
        playback.close(); playback.start()
        old_stream.finished()  # Late callback from the closed device cannot poison the new stream.
        assert not playback._failed
        playback._stream.finished()
        await asyncio.sleep(0)
        with pytest.raises(RuntimeError,match='OUTPUT_DEVICE_LOST'): await playback.drained(playback.epoch)
        playback.close()
    asyncio.run(run())
