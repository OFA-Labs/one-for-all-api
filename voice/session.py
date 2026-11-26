"""One event loop owns each armed session and its cancellable response task."""
from __future__ import annotations

import asyncio
import math
import struct
import time
from collections import deque
from contextlib import suppress
from typing import Any
from uuid import uuid4
from ofa_execution.contracts import ExecutionError

from .audio import Capture, Playback
from .capabilities import CapabilityDispatcher, MissingCapability, ReasoningGate
from .config import Settings
from .contracts import ActionBridge, Emit, LlmProvider
from .intent import Action, Router
from .language import acknowledgement
from .replay import ReplayFeed
from .state import Machine, State
from .tts.ack_cache import AckCache


def rms(pcm: bytes) -> float:
    samples = struct.unpack("<" + "h" * (len(pcm) // 2), pcm)
    return math.sqrt(sum(x * x for x in samples) / max(1, len(samples)))


class Session:
    def __init__(self, settings: Settings, router: Router, stt: Any,
                 speech: Any, llm: LlmProvider | None, bridge: ActionBridge,
                 cache: AckCache, emit: Emit,
                 dispatcher: CapabilityDispatcher | None = None,
                 authorize=lambda: None) -> None:
        self.settings, self.router = settings, router
        self.stt, self.speech = stt, speech
        self.bridge, self.cache, self.emit = bridge, cache, emit
        self.reasoning = ReasoningGate(llm)
        self.dispatcher = dispatcher
        self.authorize = authorize
        self.machine = Machine()
        self.capture = Capture(settings.input_device, settings.input_rate)
        self.playback = Playback(settings.output_device)
        self.listener: asyncio.Task[None] | None = None
        self.response: asyncio.Task[None] | None = None
        self.decision_response: asyncio.Task[None] | None = None
        self.runtime = None
        self.feed: ReplayFeed | None = None
        self._mute_until = 0.0
        self._closing = False
        self._last_activity = time.monotonic()
        self._utterance_id = ""
        self._prompt_task = None
        self._prompt_id = None
        self._speech_generation = 0
        self.playback.on_event = emit

    def notify_task(self, payload):
        card=payload.get("approval") or payload.get("handoff") or payload.get("question")
        if not card or (payload.get("approval") or {}).get("decision") is not None:
            if self._prompt_task and not self._prompt_task.done():
                self._prompt_task.cancel()
                self.playback.interrupt()
            return
        if card["id"]==self._prompt_id: return
        self._prompt_id=card["id"]
        self.emit("question",{"text":"Review the exact pending action in OFA Desktop Integration. Approve or reject it there, or say yes or no."})
        if self.machine.state not in {State.THINKING,State.LISTENING}: return
        async def prompt():
            generation=self._speech_generation+1
            try:
                await self._say("Please review the action in OFA. Say yes to approve, or no to cancel.","en")
            finally:
                if not self._closing and self._speech_generation==generation and self.machine.state==State.SPEAKING: self.state(State.LISTENING)
        self._prompt_task=asyncio.create_task(prompt())

    def state(self, state: State) -> None:
        self.machine.transition(state)
        self.emit("state", {"state": state.value, "epoch": self.machine.epoch})

    async def toggle(self) -> None:
        if self.machine.state != State.IDLE:
            await self.close("caps_lock")
            return
        if not self.settings.consent:
            self.emit("error", {"code": "MIC_CONSENT_REQUIRED"})
            return
        try:
            self.authorize()
        except PermissionError:
            self.emit("error", {"code": "DESKTOP_CONNECTION_REQUIRED"})
            return
        self._closing = False
        self.state(State.ARMED)
        try:
            if hasattr(self.bridge, "resume"):
                self.bridge.resume()
            self.playback.start()
            self.capture.start()
            self.state(State.LISTENING)
            self._last_activity = time.monotonic()
            self.listener = asyncio.create_task(self._listen())
        except Exception:
            self.emit("error", {"code": "MIC_DENIED"})
            await self.close()

    async def interrupt(self) -> None:
        self.emit("barge_detected",{"utterance_id":self._utterance_id})
        self.playback.interrupt()
        if getattr(self.bridge,"pending",None):
            return  # Approval speech must not cancel the task it is deciding.
        if self.response and not self.response.done():
            self.bridge.stop()
            self.response.cancel()
            with suppress(asyncio.CancelledError):
                await self.response
            if hasattr(self.bridge, "resume") and not self._closing:
                self.bridge.resume()
        if self.machine.state in {State.THINKING, State.SPEAKING}:
            self.state(State.INTERRUPTED)
            self.state(State.LISTENING)

    async def _listen(self) -> None:
        pre: deque[bytes] = deque(maxlen=10)
        positives, quiet = 0, 0
        try:
            while not self._closing:
                pcm = await asyncio.wait_for(self.capture.read(), timeout=2)
                gated = (not self.settings.headphones and
                         (self.machine.state == State.SPEAKING or
                          time.monotonic() < self._mute_until))
                if gated:
                    pre.clear()
                    positives = 0
                    continue
                pre.append(pcm)
                voiced = rms(pcm) >= self.settings.rms_threshold
                positives = positives + 1 if voiced else 0
                if voiced:
                    self._last_activity = time.monotonic()
                if self.feed is None and positives >= 3:
                    await self.interrupt()
                    self.feed = ReplayFeed(int(self.settings.max_utterance_seconds * 48000))
                    for chunk in pre:
                        await self.feed.push(chunk)
                    quiet = 0
                    self._utterance_id = str(uuid4())
                    self.emit("utterance_started", {"utterance_id": self._utterance_id})
                    if getattr(self.bridge,"pending",None):
                        if self.decision_response and not self.decision_response.done(): self.decision_response.cancel()
                        self.decision_response=asyncio.create_task(self._respond(self.feed))
                    else:
                        self.response = asyncio.create_task(self._respond(self.feed))
                elif self.feed is not None:
                    await self.feed.push(pcm)
                    quiet = 0 if voiced else quiet + 20
                    if quiet >= self.settings.silence_ms:
                        self.emit("speech_end", {"utterance_id": self._utterance_id})
                        await self.feed.end()
                        self.feed = None
                        pre.clear()
                if (self.feed is None and not getattr(self.bridge,"pending",None) and self.machine.state == State.LISTENING and
                        time.monotonic() - self._last_activity > self.settings.idle_seconds):
                    await self.close("idle_timeout")
                    return
        except asyncio.CancelledError:
            raise
        except Exception:
            self.emit("error", {"code": "DEVICE_LOST"})
            await self.close("audio_error")

    async def _respond(self, feed: ReplayFeed, supplied=None) -> None:
        utterance = self._utterance_id or str(uuid4())
        try:
            final = supplied
            if supplied is None:
                async for result in self.stt.transcribe(feed):
                    self.emit("transcript", {"text": result.text, "final": result.final})
                    if result.final:
                        final = result
            if final is None or not final.text.strip():
                return
            self.emit("stt_final", {"utterance_id": utterance})
            self.authorize()
            intent = self.router.route(final.text)
            if intent.intent=="stop":
                await self.close("spoken_stop")
                return
            if self.runtime and self.bridge.pending:
                if not self.runtime.decide_voice(final.text,final.confidence):
                    self.emit("question",{"text":"Complete the current choice or human handoff in Desktop Integration first."})
                return
            self.state(State.THINKING)
            if intent.intent == "stop":
                await self.close("spoken_stop")
                return
            if intent.intent == "open_app":
                self.emit("launch_dispatch", {"utterance_id": utterance})
                verified = await self.bridge.open(intent.slots["app"], utterance)
                if not verified:
                    self.emit("error", {"code": "LAUNCH_NOT_VERIFIED"})
                    return
                self.emit("launch_verified", {"utterance_id": utterance})
                await self._ack(intent.language)
            elif intent.intent == "clarify":
                if intent.options and self.runtime: self.runtime.offer_choices(intent.options)
                message = "Please name one installed app or a website address."
                if intent.slots.get("suggestions"):
                    message = "Did you mean " + intent.slots["suggestions"] + "? Please repeat the full command."
                self.emit("question", {"text": message})
                await self._say(message, "en")
            elif intent.intent == "capabilities":
                self.emit("reply", {"text": "I can open connected apps and sites. More actions use connected capabilities."})
                await self._say("I can open installed apps and websites.", "en")
            elif intent.intent == "reason":
                if self.settings.command_only:
                    self.emit("question", {"text": "Content reasoning is disabled for this iteration."})
                    await self._say("OFA Engine is not connected yet.", "en")
                else:
                    await self._chat(intent.actions[0], intent.language)
            elif intent.intent == "routine":
                if self.dispatcher is None and len(intent.actions) == 1 and intent.actions[0].capability in {"website.open", "web.search"}:
                    action = intent.actions[0]
                    if await self.bridge.open_url(action.args["url"]):
                        text = "Sent the link to your default browser."
                        self.emit("url_dispatched", {"verification": "dispatch_only"})
                        self.emit("reply", {"text": text})
                        await self._say(text, "en")
                    else:
                        self.emit("error", {"code": "URL_DISPATCH_FAILED"})
                    return
                if self.dispatcher is None:
                    raise MissingCapability("The requested action pack is not connected")
                if self.settings.command_only and any(a.capability == "reason.generate" for a in intent.actions):
                    raise MissingCapability("Content reasoning is disabled for this iteration")
                if await self.dispatcher.execute(intent.actions, intent.language, utterance):
                    if intent.actions[-1].capability=="file.read":
                        text=self.dispatcher.bindings.get("generated_text","")
                        await self._say(text[:1000] or "The selected file is empty.",intent.language)
                    elif any(a.capability in {"website.open","web.search","browser.navigate"} for a in intent.actions):
                        await self._say("Sent the link to your selected browser.","en")
                    else:
                        await self._ack(intent.language)
                else:
                    self.emit("error", {"code": "ACTION_NOT_VERIFIED"})
        except MissingCapability as error:
            self.emit("question", {"text": str(error)})
            await self._say("That action is not connected yet.", "en")
        except ExecutionError as error:
            self.emit("error",{"code":error.code,"text":error.message})
            await self._say("I could not verify that action. Please check OFA.","en")
        except asyncio.CancelledError:
            raise
        except Exception:
            self.emit("error", {"code": "VOICE_REQUEST_FAILED"})
            await self.speech.earcon(self.playback)
            self._mute_until = time.monotonic() + 0.2
        finally:
            if asyncio.current_task() is not self.decision_response and not self._closing and self.machine.state in {State.THINKING, State.SPEAKING}:
                self.state(State.LISTENING)
                self._last_activity = time.monotonic()

    async def _ack(self, language: str) -> None:
        self._speech_generation+=1
        self.playback.mark("ack_first_sample",self._utterance_id)
        self.emit("reply", {"text": acknowledgement(language)})
        try:
            pcm = self.cache.get(language)
        except KeyError:
            if await self._say(acknowledgement(language), language, "ack_first_sample"):
                self.emit("ack_played", {})
            return
        self.state(State.SPEAKING)
        epoch = self.playback.epoch
        await self.playback.write(pcm, epoch)
        await self.playback.drained(epoch)
        self._mute_until = time.monotonic() + 0.2
        self.emit("ack_played", {})

    async def _say(self, text: str, language: str, sample_kind="playback_first_sample") -> bool:
        self._speech_generation+=1
        self.playback.mark(sample_kind,self._utterance_id)
        try:
            return bool(await self.speech.say(text, language, self.playback,
                                              lambda: self.state(State.SPEAKING)))
        finally:
            self._mute_until = time.monotonic() + 0.2

    async def _chat(self, action: Action, language: str) -> None:
        raise MissingCapability("OFA Engine is not implemented in this iteration")

    async def close(self, reason: str = "stop") -> None:
        if self._closing:
            return
        self._closing = True
        self.emit("voice_stopped", {"code": reason})
        self.bridge.stop()
        self.playback.interrupt()
        current = asyncio.current_task()
        for task in (self.listener, self.response, self.decision_response, self._prompt_task):
            if task and task is not current and not task.done():
                task.cancel()
        if self.feed:
            await self.feed.end()
            self.feed = None
        self.capture.close()
        self.playback.close()
        for task in (self.listener, self.response, self.decision_response, self._prompt_task):
            if task and task is not current:
                with suppress(asyncio.CancelledError):
                    await task
        if self.machine.state != State.IDLE:
            self.state(State.IDLE)

    async def submit_text(self,text):
        from .contracts import Transcript
        if self.machine.state==State.IDLE or self.feed is not None:
            self.emit("question",{"text":"Press Caps Lock to start, or finish the current utterance first."})
            return
        await self.interrupt()
        if getattr(self.bridge,"pending",None):
            self.decision_response=asyncio.create_task(self._respond(None,Transcript(text,True,None)))
        else:
            self.response=asyncio.create_task(self._respond(None,Transcript(text,True,None)))
