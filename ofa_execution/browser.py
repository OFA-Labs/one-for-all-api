"""Pinned browse MCP adapter. Public callers cannot supply scripts or raw tools.

Fixed isolated-world collectors below are code, not instructions from page text.
The local threat boundary is OFA's authenticated adapter, not upstream browse.
Production extension-side policy/pairing hardening remains a separate milestone.
"""
from __future__ import annotations

import time
from urllib.parse import urlsplit

from .contracts import Evidence, ExecutionError, NotDispatched, Observation, Outcome
from .verification import verify


# Reads the page, open shadow roots and same-origin frames. Frames from another
# origin are never entered; they make the reading incomplete. A closed shadow root
# cannot be detected from a page script.
COLLECT = r"""async (unused, arg) => {
  const max=Math.min(Math.max(Number(arg?.max_elements)||300,1),1000);
  const state = globalThis.__ofaLocalRead ||= {doc:crypto.randomUUID(), ids:new WeakMap(), nodes:new Map(), next:0};
  state.listening ||= new WeakSet();
  const all=[];
  let frames=0, skipped=false, captcha=false;
  const walk=(root,prefix,dx,dy)=>{
    const doc=root.nodeType===9?root:null;
    if(doc&&!state.listening.has(doc)){
      for(const name of ['pointerdown','keydown'])doc.addEventListener(name,e=>{if(e.isTrusted)state.userDriving=true;},true);
      state.listening.add(doc);
    }
    captcha ||= !!root.querySelector('[class*=captcha],[id*=captcha]');
    for(const el of root.querySelectorAll('*')){
      if(el.matches('a,button,input,textarea,select,[role],h1,h2,p,label')) all.push({el,prefix,dx,dy});
      if(el.shadowRoot) walk(el.shadowRoot,prefix,dx,dy);
      if(el.tagName==='IFRAME'||el.tagName==='FRAME'){
        let inner=null;
        try{inner=el.contentDocument;}catch{}
        if(inner&&inner.documentElement){
          const r=el.getBoundingClientRect();
          walk(inner,prefix+'frame:'+(++frames)+'/',dx+r.left+el.clientLeft,dy+r.top+el.clientTop);
        } else skipped=true;
      }
    }
  };
  walk(document,'',0,0);
  const clean=text=>String(text||'').replace(/\s+/g,' ').trim();
  const accessibleName=el=>{
    const scope=el.getRootNode();
    const referenced=clean((el.getAttribute('aria-labelledby')||'').split(/\s+/).filter(Boolean)
      .map(id=>scope.getElementById?.(id)?.textContent||'').join(' '));
    if(referenced) return [referenced,'aria-labelledby'];
    for(const [source,text] of [['aria-label',el.getAttribute('aria-label')],
        ['label',[...(el.labels||[])].map(l=>l.textContent).join(' ')],['content',el.innerText],['name-attribute',el.name]])
      if(clean(text)) return [clean(text),source];
    return ['','none'];
  };
  const elements=[];
  for(const {el,prefix,dx,dy} of all.slice(0,max)) {
    const protectedField=el.type==='password'||el.autocomplete==='one-time-code';
    const sensitive=protectedField||/token|csrf|secret|auth/i.test(el.name||'');
    let id=state.ids.get(el); if(!id){id=state.doc+':'+(++state.next);state.ids.set(el,id);}
    const ref=prefix+id;
    state.nodes.set(ref,el);
    const role=el.getAttribute('role')||(el.tagName==='A'?'link':el.tagName==='BUTTON'?'button':
      /INPUT|TEXTAREA/.test(el.tagName)?'edit':el.tagName.toLowerCase());
    const [name,nameSource]=accessibleName(el);
    let value=protectedField?null:('value' in el?String(el.value):null);
    let commitment=null;
    if(sensitive && !protectedField && value!==null) {
      commitment=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',new TextEncoder().encode(value)))).map(x=>x.toString(16).padStart(2,'0')).join('');
      value='[masked security metadata]';
    }
    const r=el.getBoundingClientRect();
    elements.push({ref,name:protectedField?'[protected]':name.slice(0,500),role,
      value:value===null?null:value.slice(0,16384),protected:protectedField,enabled:!el.disabled,
      bounds:[Math.round(r.left+dx),Math.round(r.top+dy),Math.round(r.right+dx),Math.round(r.bottom+dy)],
      extra:{href:el.href||null,hidden:el.type==='hidden',type:el.type||null,commitment,
        name_source:protectedField?'protected':nameSource}});
  }
  return {surface:'browser',identity:{document:state.doc},elements,
    complete:all.length<=max&&!skipped,
    facts:{url:location.href,title:document.title,user_driving:!!state.userDriving,human_required:!!state.userDriving||elements.some(e=>e.protected)||captcha}};
}"""

ACT = r"""(unused, arg) => {
  const state=globalThis.__ofaLocalRead, el=state?.nodes.get(arg.ref);
  if(!el||!el.isConnected) throw new Error('STALE_REF');
  if(state.userDriving)throw new Error('USER_TAKEOVER');
  if(el.type==='password'||el.autocomplete==='one-time-code') throw new Error('HUMAN_REQUIRED');
  if(arg.operation==='browser.click') {el.click();return true;}
  if(arg.operation==='browser.fill') {
    if(!/INPUT|TEXTAREA/.test(el.tagName)||el.type==='hidden')throw new Error('UNSUPPORTED_CONTROL');
    const view=el.ownerDocument.defaultView;
    const proto=el.tagName==='INPUT'?view.HTMLInputElement.prototype:view.HTMLTextAreaElement.prototype;
    Object.getOwnPropertyDescriptor(proto,'value').set.call(el,arg.text);
    el.dispatchEvent(new view.Event('input',{bubbles:true}));el.dispatchEvent(new view.Event('change',{bubbles:true}));return true;
  }
  if(arg.operation==='browser.scroll'){el.scrollBy(0,arg.direction==='up'?-300:300);return true;}
  throw new Error('UNSUPPORTED_OPERATION');
}"""


# Would a person's click land on this element? Two box readings 50 ms apart, then
# a composed-tree hit test at its centre. Scroll positions are put back, so the
# approved reading and the readback after dispatch stay comparable.
PREFLIGHT = r"""async (unused, arg) => {
  const el=globalThis.__ofaLocalRead?.nodes.get(arg.ref);
  if(!el||!el.isConnected) return {found:false};
  const box=()=>{const r=el.getBoundingClientRect();return [r.left,r.top,r.width,r.height].map(Math.round).join()};
  const first=box();
  await new Promise(done=>setTimeout(done,50));
  const stable=el.isConnected&&first===box();
  const saved=[], views=[];
  for(let n=el;n;){
    if(n.nodeType===1) saved.push([n,n.scrollLeft,n.scrollTop]);
    if(n.nodeType===9){const view=n.defaultView;views.push([view,view.scrollX,view.scrollY]);n=view.frameElement;}
    else n=n.parentNode||n.host;
  }
  el.scrollIntoView({block:'center',inline:'center',behavior:'instant'});
  const lands=(target,x,y)=>{
    let top=target.ownerDocument.elementFromPoint(x,y);
    while(top&&top.shadowRoot){const inner=top.shadowRoot.elementFromPoint(x,y);if(!inner||inner===top)break;top=inner;}
    for(let n=top;n;n=n.assignedSlot||n.parentNode||n.host) if(n===target||(n.tagName==='LABEL'&&n.control===target))return true;
    return false;
  };
  const r=el.getClientRects()[0];
  let hit=false;
  if(r&&r.width>0&&r.height>0){
    let x=r.left+r.width/2, y=r.top+r.height/2, target=el;
    hit=lands(target,x,y);
    while(hit){
      const frame=target.ownerDocument.defaultView.frameElement;
      if(!frame)break;
      const box=frame.getBoundingClientRect();
      x+=box.left+frame.clientLeft; y+=box.top+frame.clientTop; target=frame;
      hit=lands(target,x,y);
    }
  }
  for(const [n,left,top] of saved) if(n.scrollLeft!==left||n.scrollTop!==top) n.scrollTo({left,top,behavior:'instant'});
  for(const [view,left,top] of views) view.scrollTo({left,top,behavior:'instant'});
  return {found:true,stable,hit_target:hit};
}"""

# Seconds before each pre-dispatch attempt. The dispatch itself is never repeated.
RETRY_WAITS = (0, 0.02, 0.1, 0.1, 0.5)
RETRYABLE = {"HIT_TARGET_INTERCEPTED", "ELEMENT_UNSTABLE"}


class BrowserHand:
    def __init__(self, config, client=None):
        self.config, self.client = config, client
        self.tabs: dict[str, str] = {}
        self.last_tab: str | None = None

    def _client(self):
        if self.client is None:
            from .mcp import McpClient
            self.client = McpClient(self.config.browser_command)
        return self.client

    def capabilities(self):
        return {"hand": "browser", "backend": "browse_mcp", "configured": bool(self.config.browser_command or self.client),
                "operations": ["browser.open", "browser.observe", "browser.click", "browser.fill", "browser.scroll", "browser.close"],
                "screenshots": {"available": False, "reason": "local_masking_not_configured"},
                "pairing_required": True, "arbitrary_scripts": False, "live_reasoning": False}

    def _tab(self, step):
        tab = step.target.tab or self.last_tab
        if tab is None or str(tab) not in self.tabs:
            raise ExecutionError("TAB_NOT_OWNED", "This session can only control its own OFA tabs.")
        return str(tab)

    @staticmethod
    def _tool_tab(tab):
        # Upstream distinguishes numeric tab IDs from user-chosen string slugs.
        return int(tab) if str(tab).isdigit() else tab

    @staticmethod
    def _unwrap(value):
        # browse eval returns its value directly; execute wrappers may add result.
        if isinstance(value, dict) and "result" in value and "surface" not in value:
            return value["result"]
        return value

    def observe(self, step):
        if step.operation == "browser.open":
            return Observation(surface="browser", identity={"new_tab": True}, facts={"url": step.url})
        tab = self._tab(step)
        result = self._unwrap(self._client().call("eval", {"tab": self._tool_tab(tab), "expression": COLLECT,
                                                           "arg": {"max_elements": self.config.max_elements}}))
        if not isinstance(result, dict) or result.get("surface") != "browser":
            raise ExecutionError("BROWSER_SCHEMA_CHANGED", "Browser collector did not return the expected reading.")
        reading = Observation.model_validate(result)
        reading.identity["tab"] = tab
        p = urlsplit(reading.facts["url"])
        if f"{p.scheme}://{p.netloc.lower()}" != self.tabs[tab]:
            raise ExecutionError("ORIGIN_CHANGED", "Browser left the frozen tab origin; human assistance is required.")
        return reading

    def _target(self, step, before):
        matches = [e for e in before.elements if not e.protected and e.enabled and
                   not e.extra.get("hidden") and e.bounds and e.bounds[2]>e.bounds[0] and e.bounds[3]>e.bounds[1] and
                   (e.ref == step.target.ref if step.target.ref else
                    (step.target.name is None or e.name.casefold() == step.target.name.casefold()) and
                    (step.target.role is None or e.role.casefold() == step.target.role.casefold()))]
        if len(matches) != 1:
            raise ExecutionError("TARGET_AMBIGUOUS" if matches else "TARGET_NOT_FOUND", "Select an exact structural browser element; no blind click.",
                                 [{"id": e.ref, "label": f"{e.role}: {e.name}"} for e in matches[:20]])
        element = matches[0]
        if element.extra.get("href"):
            p = urlsplit(element.extra["href"])
            if f"{p.scheme}://{p.netloc.lower()}" != self.tabs[self._tab(step)]:
                raise ExecutionError("ORIGIN_NOT_ALLOWED", "Cross-origin links require another explicitly planned open step.")
        return element

    def validate_target(self, step, before):
        if step.operation in {"browser.click", "browser.fill", "browser.scroll"} and not before.facts.get("human_required"):
            self._target(step, before)

    def after_handoff(self, step):
        self._client().call("eval", {"tab": self._tool_tab(self._tab(step)),
                                     "expression": "() => { if(globalThis.__ofaLocalRead) globalThis.__ofaLocalRead.userDriving=false; return true; }"})

    def execute(self, step, before, checkpoint):
        checkpoint()
        client = self._client()
        if step.operation == "browser.open":
            p = urlsplit(step.url)
            origin = f"{p.scheme}://{p.netloc.lower()}"
            result = client.call("navigate", {"url": step.url, "group": "ONE FOR ALL — local",
                                              "allowedOrigins": [origin], "keepOpen": True,
                                              "timeout": 5000, "waitUntil": "load"})
            tab = str(result["tab"])
            self.tabs[tab], self.last_tab = origin, tab
            observe = step.model_copy(deep=True)
            observe.operation, observe.target.tab = "browser.observe", tab
            after = self.observe(observe)
            good = after.facts["url"] == step.url
            return Outcome(status="verified" if good else "unknown", observation=after,
                           evidence=[Evidence(tier="A", kind="fresh_tab_url", reading_hash=after.hash)])
        tab = self._tab(step)
        if step.operation == "browser.close":
            client.call("tabs", {"action": "close", "tab": self._tool_tab(tab)})
            self.tabs.pop(tab)
            result = client.call("tabs", {})
            # Tool success alone is not verification. Re-read owned tab list.
            gone = tab not in {str(t.get("id", t.get("tab"))) for t in result.get("tabs", [])}
            after = Observation(surface="browser", identity={"tab": tab}, facts={"closed": gone})
            return Outcome(status="verified" if gone else "unknown", observation=after,
                           evidence=[Evidence(tier="A", kind="tab_list_readback", reading_hash=after.hash)])
        if step.operation in {"browser.observe", "browser.screenshot"}:
            after = self.observe(step)
            if step.operation == "browser.screenshot":
                # No raw screenshot escape through upstream. Future redaction
                # adapter can supply frames; current unsupported case is honest.
                raise ExecutionError("SCREENSHOT_REDACTION_REQUIRED", "Browser frames are unavailable until local masking is configured; structural observations work.")
            return Outcome(status="verified", observation=after,
                           evidence=[Evidence(tier="A", kind="fresh_dom", reading_hash=after.hash)])
        element = self._ready(step, before, checkpoint)
        checkpoint()
        # One fixed synchronous operation; no queued human-paced type macro.
        client.call("eval", {"tab": self._tool_tab(tab), "expression": ACT,
                             "arg": {"operation": step.operation, "ref": element.ref,
                                     "text": step.text, "direction": step.direction}})
        return verify(step, before, self.observe(step))

    def _ready(self, step, before, checkpoint):
        """Everything that happens before dispatch; only this part may be retried."""
        for attempt, wait in enumerate(RETRY_WAITS, 1):
            time.sleep(wait)
            checkpoint()
            try:
                fresh = self.observe(step)
                if fresh.hash != before.hash:
                    raise ExecutionError("READING_CHANGED", "Browser state changed after approval.")
                element = self._target(step, fresh)
                if step.operation in {"browser.click", "browser.fill"}:
                    self._preflight(step, element)
                return element
            except ExecutionError as exc:
                if exc.code in {"HELD", "CANCELLED"}:
                    raise
                if exc.code not in RETRYABLE or attempt == len(RETRY_WAITS):
                    raise NotDispatched(exc.code, exc.message, exc.options) from exc

    def _preflight(self, step, element):
        result = self._unwrap(self._client().call("eval", {"tab": self._tool_tab(self._tab(step)),
                                                           "expression": PREFLIGHT, "arg": {"ref": element.ref}}))
        if not isinstance(result, dict) or "found" not in result:
            raise ExecutionError("BROWSER_SCHEMA_CHANGED", "Browser pre-flight did not return the expected reading.")
        if not result["found"]:
            raise ExecutionError("TARGET_NOT_FOUND", "The element left the page before it could be used.")
        if result.get("stable") is not True:
            raise ExecutionError("ELEMENT_UNSTABLE", "The element is still moving; nothing was sent.")
        if result.get("hit_target") is not True:
            raise ExecutionError("HIT_TARGET_INTERCEPTED",
                                 "Something is covering the element, such as a banner or dialog; nothing was sent.")

    def close(self):
        if self.client:
            self.client.close()
