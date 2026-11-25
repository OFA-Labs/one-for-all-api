/* Real pinned browse + unpacked extension in a disposable Chromium profile.
 * No personal browser profile, provider account or existing tab is touched.
 */
const fs=require('fs'),os=require('os'),path=require('path'),cp=require('child_process'),net=require('net'),crypto=require('crypto');
const root=path.resolve(__dirname,'../..');
let playwrightModule=process.env.OFA_PLAYWRIGHT_MODULE;
if(!playwrightModule){try{playwrightModule=require.resolve('playwright');}catch{playwrightModule=path.resolve(root,'../one-for-all-web/node_modules/playwright');}}
const playwright=require(playwrightModule);
const python=process.env.OFA_TEST_PYTHON || path.join(root,'.venv','Scripts','python.exe');
const binary=process.env.OFA_BROWSE_BINARY;
if(!binary)throw Error('Set OFA_BROWSE_BINARY to the locally installed pinned browse.exe; no secrets are required.');
const temporary=fs.mkdtempSync(path.join(os.tmpdir(),'ofa-browser-smoke-'));
let context,relay,pair,localServer;
function runPython(code,args=[]){return cp.spawnSync(python,['-c',code,...args],{cwd:root,encoding:'utf8',windowsHide:true});}
function freePort(){return new Promise(resolve=>{const s=net.createServer();s.listen(0,'127.0.0.1',()=>{const port=s.address().port;s.close(()=>resolve(port));});});}
async function main(){
  const download=runPython(`import sys,urllib.request,zipfile,io,hashlib,json\nfrom pathlib import Path\ndata=urllib.request.urlopen('https://anoma.ly/release/browse/extension/stable/chromium',timeout=30).read()\nassert hashlib.sha256(data).hexdigest()=='5527b8e2865068ebd4060c6274ce7633bc06e1d2080fd19974a1cf9c7a7fe18d', 'Reviewed extension digest changed'\nz=zipfile.ZipFile(io.BytesIO(data))\nmanifest=json.loads(z.read('manifest.json'))\nassert manifest['version']=='0.1.5', 'Extension version drift requires reviewed test update'\nroot=Path(sys.argv[1]).resolve()\nfor item in z.infolist():\n target=(root/item.filename).resolve()\n assert target.is_relative_to(root), 'ZIP path escape'\nz.extractall(root)\nprint('Extension 0.1.5 SHA256 '+hashlib.sha256(data).hexdigest())`,[path.join(temporary,'extension')]);
  if(download.status!==0)throw Error(download.stderr);console.log(download.stdout.trim());
  const port=await freePort();
  const env={...process.env,OPENCODE_BROWSER_PORT:String(port),OPENCODE_BROWSER_AUTO_UPDATE:'off',OPENCODE_BROWSER_TOOLS:'all'};
  let executable=process.env.OFA_CHROMIUM_EXECUTABLE;
  if(!executable && !fs.existsSync(playwright.chromium.executablePath())){
    const cache=path.join(process.env.LOCALAPPDATA,'ms-playwright');
    const installed=fs.readdirSync(cache).filter(n=>/^chromium-\d+$/.test(n)).sort((a,b)=>Number(b.split('-')[1])-Number(a.split('-')[1]));
    for(const name of installed){const candidate=path.join(cache,name,'chrome-win64','chrome.exe');if(fs.existsSync(candidate)){executable=candidate;break;}}
  }
  context=await playwright.chromium.launchPersistentContext(path.join(temporary,'profile'),{headless:false,executablePath:executable,args:[`--disable-extensions-except=${path.join(temporary,'extension')}`,`--load-extension=${path.join(temporary,'extension')}`]});
  console.log('Real Chromium:',context.browser().version());
  let worker=context.serviceWorkers()[0] || await context.waitForEvent('serviceworker',{timeout:15000});
  const extensionId=new URL(worker.url()).host;
  env.OPENCODE_BROWSER_EXTENSION_ORIGINS='chrome-extension://'+extensionId;
  relay=cp.spawn(binary,['serve'],{env,windowsHide:true,stdio:'ignore'});
  await new Promise(r=>setTimeout(r,500));
  const page=await context.newPage();await page.goto(`chrome-extension://${extensionId}/settings.html`);
  pair=cp.spawn(binary,['pair'],{env,windowsHide:true,stdio:['ignore','pipe','pipe']});
  const code=await new Promise((resolve,reject)=>{let text='';const timer=setTimeout(()=>reject(Error('Pairing challenge timeout')),12000);function receive(b){text+=b;const m=text.match(/Pairing code:\s*([A-Z0-9-]+)/);if(m){clearTimeout(timer);resolve(m[1]);}}pair.stdout.on('data',receive);pair.stderr.on('data',receive);});
  // No pairing code/credential is printed or written to the repository.
  const advanced=page.getByText('advanced',{exact:false});
  if(await advanced.count())await advanced.first().click().catch(()=>{});
  const address=page.getByLabel(/Relay address/i);
  if(await address.count())await address.fill('127.0.0.1:'+port);
  else await page.locator('input[placeholder*="localhost"],input[placeholder*="127.0.0.1"]').first().fill('127.0.0.1:'+port);
  await page.getByLabel(/Pairing code/i).fill(code);
  await page.getByRole('button',{name:'Connect',exact:true}).click();
  await Promise.race([new Promise((resolve,reject)=>pair.on('exit',code=>code===0?resolve():reject(Error('Local test pairing failed')))),new Promise((_,reject)=>setTimeout(()=>reject(Error('Pairing did not complete; check extension origin/relay compatibility')),12000))]).catch(async e=>{console.log('Pairing UI status:',(await page.locator('body').innerText()).slice(0,2200));throw e;});
  // Keep Playwright's event loop running while the independent MCP test acts.
  await new Promise((resolve,reject)=>{
    const test=cp.spawn(python,['-m','pytest','tests/local_execution/test_browser_real.py','-q'],{cwd:root,env:{...env,OFA_BROWSE_BINARY:binary},windowsHide:true});
    test.stdout.on('data',b=>process.stdout.write(b));test.stderr.on('data',b=>process.stderr.write(b));
    const timer=setTimeout(()=>{test.kill();reject(Error('Real browser test timeout'));},45000);
    test.on('exit',code=>{clearTimeout(timer);code===0?resolve():reject(Error('Real browser integration failed'));});
  });
  const uiPort=await freePort(),sessionCredential=crypto.randomBytes(48).toString('base64url');
  const sample=path.join(temporary,'sample.txt'),permissions=path.join(temporary,'permissions.json');
  fs.writeFileSync(sample,'before');fs.writeFileSync(permissions,JSON.stringify({read_roots:[temporary],write_roots:[temporary]}));
  localServer=cp.spawn(python,['-m','ofa_execution','--no-browser','--port',String(uiPort),'--config',permissions],{cwd:root,env:{...process.env,OFA_LOCAL_TOKEN:sessionCredential},windowsHide:true,stdio:'ignore'});
  const control=await context.newPage();const uiOrigin='http://127.0.0.1:'+uiPort;
  let ready=false;for(let i=0;i<40;i++){try{const r=await fetch(uiOrigin);if(r.ok){ready=true;break;}}catch{}await new Promise(r=>setTimeout(r,100));}
  if(!ready)throw Error('Local control UI readiness timeout');
  await control.goto(uiOrigin+'/#'+sessionCredential);
  await control.getByText('Connected · deterministic execution · no AI provider',{exact:true}).waitFor();
  const plan={title:'UI approved file test',steps:[{operation:'file.write',target:{path:sample},text:'after',expect:{kind:'file_text',value:'after'}}]};
  await control.locator('#plan').fill(JSON.stringify(plan));await control.getByRole('button',{name:'Run plan',exact:true}).click();
  await control.getByRole('button',{name:'Approve once',exact:true}).waitFor();
  if(fs.readFileSync(sample,'utf8')!=='before')throw Error('UI task mutated before approval');
  await control.getByRole('button',{name:'Approve once',exact:true}).click();
  await control.getByRole('heading',{name:'UI approved file test · completed',exact:true}).waitFor();
  if(fs.readFileSync(sample,'utf8')!=='after')throw Error('UI file result not verified');
  await control.getByRole('button',{name:'Emergency stop',exact:true}).click();
  await control.getByRole('button',{name:'Resume local control',exact:true}).waitFor();
  console.log('PASS: real local control UI, approval before mutation, verified progress, emergency stop.');
}
main().catch(e=>{console.error(e.message);process.exitCode=1;}).finally(async()=>{
  if(context)await context.close();
  for(const child of [pair,relay,localServer])if(child && child.exitCode===null)child.kill();
  const resolved=path.resolve(temporary),tmp=path.resolve(os.tmpdir());
  if(path.dirname(resolved)===tmp && path.basename(resolved).startsWith('ofa-browser-smoke-'))fs.rmSync(resolved,{recursive:true,force:true,maxRetries:4,retryDelay:300});
});
