"""Bounded native audio callbacks with epoch-based cancellation."""
from __future__ import annotations

import asyncio
import threading

import numpy as np
import sounddevice as sd
from scipy.signal import firwin, lfilter


class Capture:
    def __init__(self, device: int | None, rate: int = 24000) -> None:
        self.device = device
        self.rate = rate
        self.queue: asyncio.Queue[bytes | Exception] = asyncio.Queue(30)
        self._slots = threading.BoundedSemaphore(30)
        self._stream: sd.RawInputStream | None = None
        self._active = False
        self._generation = 0
        self._overflow = threading.Event()
        self._filter = firwin(63, 10500, fs=48000)
        self._history = np.zeros(62)

    def _deliver(self, item: bytes | Exception, generation: int) -> None:
        self._slots.release()
        if not self._active or generation != self._generation:
            return
        if self._overflow.is_set():
            self._overflow.clear()
            item = RuntimeError("CAPTURE_OVERFLOW")
        if self.queue.full():
            self.queue.get_nowait()
            item = RuntimeError("CAPTURE_OVERFLOW")
        self.queue.put_nowait(item)

    def start(self) -> None:
        loop = asyncio.get_running_loop()
        if self.rate == 24000:
            try:
                sd.check_input_settings(device=self.device, samplerate=24000, channels=1, dtype="int16")
            except sd.PortAudioError:
                sd.check_input_settings(device=self.device, samplerate=48000, channels=1, dtype="int16")
                self.rate = 48000
        self._history = np.zeros(62)
        self._generation += 1
        generation = self._generation
        self._overflow.clear()
        self._active = True

        def callback(data: object, frames: int, timing: object, status: object) -> None:
            if not self._active:
                return
            if not self._slots.acquire(blocking=False):
                self._overflow.set()
                return
            item = RuntimeError("CAPTURE_OVERFLOW") if status else bytes(data)
            loop.call_soon_threadsafe(self._deliver, item, generation)

        self._stream = sd.RawInputStream(
            samplerate=self.rate, blocksize=self.rate // 50,
            channels=1, dtype="int16", device=self.device, callback=callback,
        )
        self._stream.start()

    async def read(self) -> bytes:
        item = await self.queue.get()
        if isinstance(item, Exception):
            raise item
        if self.rate == 24000:
            return item
        source = np.frombuffer(item, dtype="<i2").astype(np.float64)
        filtered, self._history = lfilter(
            self._filter, [1.0], source, zi=self._history
        )
        return np.clip(filtered[::2], -32768, 32767).astype("<i2").tobytes()

    def close(self) -> None:
        self._active = False
        self._generation += 1
        if self._stream:
            self._stream.abort()
            self._stream.close()
            self._stream = None
        while not self.queue.empty():
            self.queue.get_nowait()


class Playback:
    def __init__(self, device: int | None) -> None:
        self.device = device
        self._pcm = bytearray()
        self._lock = threading.Lock()
        self._epoch = 0
        self._stream: sd.RawOutputStream | None = None
        self.last_dac = 0.0
        self.on_event = lambda *_: None
        self._marker = None
        self._silence = None
        self._loop = None
        self._failed = False
        self._closing = True
        self.marker = None
        self._stream_generation = 0

    def mark(self, kind, utterance_id):
        with self._lock:
            self._marker=(kind,utterance_id)
            self.marker=self._marker

    def start(self) -> None:
        self._loop=asyncio.get_running_loop()
        self._stream_generation+=1
        generation=self._stream_generation
        self._failed=False
        self._closing=False
        def finished():
            if not self._closing and generation==self._stream_generation:
                self._failed=True
                self._loop.call_soon_threadsafe(self.on_event,"error",{"code":"OUTPUT_DEVICE_LOST"})
        def callback(out: object, frames: int, timing: object, status: object) -> None:
            needed = frames * 2
            if generation!=self._stream_generation:
                out[:]=bytes(needed)
                return
            with self._lock:
                chunk = bytes(self._pcm[:needed])
                del self._pcm[:needed]
                marker=self._marker if chunk and any(chunk) else None
                if marker: self._marker=None
                silence=self._silence if not chunk else None
                if silence is not None: self._silence=None
                epoch=self._epoch
            out[:] = chunk + bytes(needed - len(chunk))
            if chunk:
                self.last_dac = float(timing.outputBufferDacTime)
            if marker and self._loop:
                self._loop.call_soon_threadsafe(self.on_event,marker[0],{"utterance_id":marker[1],"epoch":epoch,"dac_time":float(timing.outputBufferDacTime),"measurement":"output_callback_estimate"})
            if silence is not None and self._loop:
                self._loop.call_soon_threadsafe(self.on_event,"playback_silent",{"epoch":silence,"dac_time":float(timing.outputBufferDacTime),"measurement":"output_callback_estimate"})

        self._stream = sd.RawOutputStream(
            samplerate=24000, blocksize=480, channels=1, dtype="int16",
            device=self.device, callback=callback, finished_callback=finished, latency="low",
        )
        self._stream.start()

    async def write(self, pcm: bytes, epoch: int) -> None:
        if len(pcm) % 2:
            raise ValueError("Odd-length PCM")
        for start in range(0, len(pcm), 960):
            while True:
                if self._failed: raise RuntimeError("OUTPUT_DEVICE_LOST")
                with self._lock:
                    if epoch != self._epoch:
                        raise asyncio.CancelledError
                    if len(self._pcm) < 19200:
                        self._pcm.extend(pcm[start:start + 960])
                        break
                await asyncio.sleep(0.005)

    async def drained(self, epoch: int) -> None:
        deadline=asyncio.get_running_loop().time()+30
        while True:
            if self._failed or asyncio.get_running_loop().time()>deadline:
                raise RuntimeError("OUTPUT_DEVICE_LOST")
            with self._lock:
                if epoch != self._epoch:
                    raise asyncio.CancelledError
                if not self._pcm:
                    break
            await asyncio.sleep(0.005)
        latency = float(self._stream.latency) if self._stream else 0.0
        await asyncio.sleep(latency + 0.02)

    def interrupt(self) -> int:
        with self._lock:
            self._epoch += 1
            self._pcm.clear()
            self._marker=None
            self._silence=self._epoch
            return self._epoch

    @property
    def epoch(self) -> int:
        return self._epoch

    def close(self) -> None:
        self._closing=True
        self._stream_generation+=1
        self.interrupt()
        if self._stream:
            self._stream.abort()
            self._stream.close()
            self._stream = None
