"use strict";
const token = location.hash.slice(1);
history.replaceState(null, "", location.pathname);
const $ = id => document.getElementById(id);
const id = () => crypto.randomUUID();
async function api(path, body) {
  const r = await fetch('/api/' + path, {method:body?'POST':'GET',headers:{'Authorization':'Bearer '+token,'Content-Type':'application/json'},body:body?JSON.stringify(body):undefined});
  const result = await r.json(); if(!r.ok) throw new Error(JSON.stringify(result)); return result;
}
function button(label, action) {const b=document.createElement('button');b.textContent=label;b.onclick=()=>action().catch(showError);return b;}
function showError(e){$('error').textContent=e.message;}
function pre(value){const p=document.createElement('pre');p.textContent=JSON.stringify(value,null,2);return p;}
$('plan').value=JSON.stringify({title:'Native test pad',steps:[{operation:'app.open',target:{app:'OFA Test Pad'}},{operation:'window.observe',target:{app:'OFA Test Pad'}}]},null,2);
$('command').onsubmit=async e=>{e.preventDefault();try{$('error').textContent='';await api('commands',{command_id:id(),text:$('text').value});}catch(e){showError(e);}};
$('run-plan').onclick=async()=>{try{$('error').textContent='';await api('tasks',{command_id:id(),plan:JSON.parse($('plan').value)});}catch(e){showError(e);}};
$('stop').onclick=()=>api('control',{command_id:id(),action:'stop'}).catch(showError);
async function refresh(){
  try{
    const caps=await api('capabilities');$('connection').textContent=caps.stopped?'Execution stopped. Resume explicitly to run new tasks.':'Connected · deterministic execution · no AI provider';
    $('capabilities').textContent=JSON.stringify(caps,null,2);
    if(caps.stopped){$('connection').append(button('Resume local control',()=>api('control',{command_id:id(),action:'resume'})));}
    const tasks=await api('tasks');$('tasks').replaceChildren();
    for(const t of tasks.reverse()){
      const card=document.createElement('article');card.className='task';const h=document.createElement('h3');h.textContent=t.plan.title+' · '+t.state;card.append(h);
      const meta=document.createElement('p');meta.textContent=`Step ${Math.min(t.step+1,t.plan.steps.length)}/${t.plan.steps.length} · ${t.id}`;card.append(meta);
      for(const action of ['pause','resume','cancel'])card.append(button(action,()=>api(`tasks/${t.id}/control`,{command_id:id(),action})));
      if(t.approval && t.approval.decision===null){
        const a=t.approval;const title=document.createElement('h3');title.textContent='Approval required — exact action and fresh reading';card.append(title,pre({action:a.exact_action,reading:a.reading,reading_hash:a.reading_hash}));
        for(const approve of [true,false])card.append(button(approve?'Approve once':'Reject',()=>api(`tasks/${t.id}/decision`,{command_id:id(),approval_id:a.id,reading_hash:a.reading_hash,approve})));
      }
      if(t.question){card.append(pre(t.question));for(const option of t.question.options)card.append(button(option.label,()=>api(`tasks/${t.id}/answer`,{command_id:id(),question_id:t.question.id,option_id:option.id})));}
      if(t.handoff)card.append(button('Continue after human step',()=>api(`tasks/${t.id}/control`,{command_id:id(),action:'continue',handoff_id:t.handoff.id})));
      if(t.error)card.append(pre(t.error));
      const details=document.createElement('details');const summary=document.createElement('summary');summary.textContent='Observations, verified effects and event timeline';details.append(summary,pre({observation:t.observation,effects:t.effects,events:t.events}));card.append(details);
      if(t.observation?.frame){const img=document.createElement('img');img.src=t.observation.frame;img.alt='Consented target-window observation';card.append(img);}
      $('tasks').append(card);
    }
  }catch(e){$('connection').textContent='Local control unavailable. Reopen the launcher page if the token was lost.';showError(e);}
  setTimeout(refresh,300);
}
refresh();
