/* Small private homepage over the existing article editor; no second app/runtime. */
(() => {
  const $ = s => document.querySelector(s), wb = window.workbench;
  const nav = {today:'showToday',articles:'showLibrary',ideas:'showIdeas',health:'showHealth',review:'showReview',editor:'showEditor'};
  let data = null, articles = [], recentId = '', activeView = 'today', operation = null, busy = false;
  const input = $('#ideaInput'), captureStatus = $('#captureStatus');
  const cacheKey = 'tang-desk-capture';
  try { input.value = localStorage.getItem(cacheKey) || ''; } catch (_) {}
  input.addEventListener('input', () => {operation = null; try {localStorage.setItem(cacheKey,input.value);} catch (_) {captureStatus.textContent='设备暂存不可用，请点击“先记下来”保存。';}});
  const node = (tag, text, className) => {const el=document.createElement(tag);if(text!==undefined) el.textContent=text;if(className) el.className=className;return el;};
  const date = t => new Date(t*1000).toLocaleString('zh-CN',{timeZone:'Asia/Shanghai',month:'numeric',day:'numeric',hour:'2-digit',minute:'2-digit',hour12:false});
  const duration = value => {if(value==null) return '—';const m=Math.floor(value*60);return `${Math.floor(m/60)}小时${m%60}分`;};
  function feedback(text,error=false){captureStatus.textContent=text;captureStatus.dataset.error=String(error);}
  function button(text,callback,style='quiet-button'){const b=node('button',text,style);b.type='button';b.addEventListener('click',callback);return b;}
  function dialog(title){const root=$('#dialogContent');root.replaceChildren(node('h2',title));$('#deskDialog').showModal();return root;}
  function errorDialog(error){const root=dialog('这一步暂时没有完成');root.append(node('p',error.message));}
  async function go(view){try {if(!wb.signedIn) throw new Error('请先登录你的工作台');await wb.go(view);}catch(error){errorDialog(error);}}
  Object.entries(nav).forEach(([view,id])=>{if(view!=='articles'&&view!=='editor') $('#'+id).addEventListener('click',()=>go(view));});
  $('#allIdeas').onclick=()=>go('ideas');$('#allArticles').onclick=()=>go('articles');$('#sleepDetails').onclick=()=>go('health');$('#backToday').onclick=()=>go('today');
  window.addEventListener('workbench-view',event=>{
    activeView=event.detail;
    Object.entries(nav).forEach(([v,id])=>{if(v===activeView) $('#'+id).setAttribute('aria-current','page');else $('#'+id).removeAttribute('aria-current');});
    $('#todayDesk').hidden=activeView!=='today';$('#deskDetail').hidden=!['ideas','health','review'].includes(activeView);
    if(data) renderDetail();
  });
  window.addEventListener('workbench-signedout',()=>{$('#deskPage').hidden=true;data=null;articles=[];$('#ideaCards').replaceChildren();$('#recentCover').removeAttribute('src');});
  window.addEventListener('workbench-ready',async()=>{
    try {await refresh();const query=new URLSearchParams(location.search);if(!query.has('article')&&!query.has('recover')) await go(['ideas','health','review','articles'].includes(query.get('view'))?query.get('view'):'today');}
    catch(error){feedback(error.message,true);if(!new URLSearchParams(location.search).has('article')) await go('today');$('#sleepSync').textContent='睡眠记录暂时读取失败';}
  });
  window.addEventListener('workbench-articles',event=>{articles=event.detail;renderRecent().catch(error=>{$('#recentEmpty').textContent=error.message;$('#recentEmpty').hidden=false;});});
  async function refresh(){data=await wb.request('/api/wellbeing');renderHealth();renderIdeas();renderDetail();}
  function renderHealth(){
    const latest=data.sleep[0],today=data.today;
    $('#sleepTotal').replaceChildren();
    if(latest){const m=Math.floor(latest.totalSleep*60);$('#sleepTotal').append(node('span',String(Math.floor(m/60))),node('small','小时'),node('span',String(m%60)),node('small','分'));$('#sleepLabel').textContent=latest.day===today?'最近一晚睡眠':latest.day+' 的睡眠';$('#sleepSync').textContent=`收到于 ${date(latest.received)}${latest.day!==today?' · 待新记录':''}`;}
    else {$('#sleepTotal').append(node('span','—'),node('small',' 等待同步'));$('#sleepSync').textContent='还没有收到睡眠记录';}
    $('#sleepChart').replaceChildren();
    for(let offset=6;offset>=0;offset--){const d=new Date(today+'T12:00:00+08:00');d.setUTCDate(d.getUTCDate()-offset);const day=d.toLocaleDateString('en-CA',{timeZone:'Asia/Shanghai'});const record=data.sleep.find(s=>s.day===day);const bar=node('div',undefined,'sleep-bar');bar.dataset.current=String(offset===0);bar.dataset.missing=String(!record);bar.title=day+' · '+(record?duration(record.totalSleep):'暂无记录');const line=node('i');line.style.height=(record?Math.max(3,Math.min(55,record.totalSleep/10*55)):2)+'px';bar.append(line,node('span',offset===0?'今天':d.toLocaleDateString('zh-CN',{timeZone:'Asia/Shanghai',weekday:'short'})));$('#sleepChart').append(bar);}
    const checkin=data.checkins.find(c=>c.day===today);
    document.querySelectorAll('[data-mood]').forEach(b=>b.setAttribute('aria-pressed',String(checkin?.mood===b.dataset.mood)));
    $('#careQuestion').textContent=checkin?.mood==='tired'?'今天有点累，就从一件小事开始。愿意记下现在的感受吗？':checkin?.mood==='good'?'有精神的一天。把脑海里那个想法，先留下一句吧。':latest?'睡眠记录到了。今天感觉怎么样？愿意留一句话吗？':'今天的你，感觉怎么样？留一句话给自己吧。';
  }
  document.querySelectorAll('[data-mood]').forEach(b=>b.addEventListener('click',async()=>{const buttons=[...document.querySelectorAll('[data-mood]')];buttons.forEach(x=>x.disabled=true);try {await wb.request('/api/checkin',{mood:b.dataset.mood});await refresh();showToast('今天的感受已保存');}catch(error){errorDialog(error);}finally{buttons.forEach(x=>x.disabled=false);}}));
  async function renderRecent(){
    const recent=articles.find(a=>!a.archived&&a.title!=='未命名文章');recentId=recent?.id||'';
    $('#recentTitle').textContent=recent?.title||'';$('#recentDigest').textContent=recent?.digest||'';$('#recentState').textContent=recent?(recent.wechat?'有微信导入记录':'工作台草稿'):'';$('#recentState').hidden=!recent;$('#continueArticle').hidden=!recent;$('#recentCover').hidden=true;$('#recentEmpty').hidden=!!recent;
    if(recent){const item=await wb.request('/api/articles?id='+encodeURIComponent(recent.id));if(recentId!==recent.id)return;const cover=item.document.cover;if(typeof cover==='string'&&/^data:image\/(png|jpeg);base64,/.test(cover)){$('#recentCover').src=cover;$('#recentCover').hidden=false;}}
  }
  $('#continueArticle').onclick=()=>recentId&&wb.openArticle(recentId).catch(errorDialog);
  function renderIdeas(){const ideas=data.notes.filter(n=>n.kind==='idea').slice(0,3);$('#ideaCards').replaceChildren();for(const item of ideas){const card=button('',()=>openNote(item),'idea-card');card.append(node('strong',item.text.split('\n')[0].slice(0,26)),node('span',item.text.slice(0,70)));$('#ideaCards').append(card);}if(!ideas.length)$('#ideaCards').append(node('div','不用先想好题目。随手留一句话，灵感就有了自己的位置。','empty-ideas'));}
  async function capture(asArticle){
    const text=input.value.trim();if(!text){input.focus();feedback('先写一句话就好。');return;}if(busy)return;
    busy=true;input.readOnly=true;$('#saveIdea').disabled=$('#startArticle').disabled=true;feedback(asArticle?'正在把原话放进文章…':'正在保存这个想法…');
    try{
      operation=operation||{id:crypto.randomUUID(),text,kind:'idea'};
      await wb.request('/api/notes',operation);
      if(asArticle){await wb.create({title:text.split('\n')[0].slice(0,36),markdown:text,theme:'spring',images:{}});showToast('原话已保存成文章，可以继续编辑或让小秋接着整理');}
      input.value='';operation=null;try{localStorage.removeItem(cacheKey);}catch(_){}feedback('已保存到书桌，随时可以接着写。');await refresh();
    }catch(error){feedback(error.message+'。文字已保留，请先核对保存结果。',true);}finally{busy=false;input.readOnly=false;$('#saveIdea').disabled=$('#startArticle').disabled=false;}
  }
  $('#captureForm').onsubmit=event=>{event.preventDefault();capture(false);};$('#startArticle').onclick=()=>capture(true);
  function openNote(item){const root=dialog(item.kind==='idea'?'把这个想法接着写':'那天留下的话');const p=node('p',item.text);p.style.whiteSpace='pre-wrap';root.append(p,node('p',date(item.created)));if(item.kind==='idea')root.append(button('放回书桌继续写',async()=>{input.value=item.text;input.dispatchEvent(new Event('input'));$('#deskDialog').close();await go('today');input.focus();},'desk-primary'));}
  function reflection(){
    const root=dialog('留一句话给今天');root.append(node('p','今天做了什么、哪里卡住了，或者只是现在的感受。写多少都可以。'));
    const text=node('textarea');text.setAttribute('aria-label','今天的回顾');text.placeholder='今天，我……';text.maxLength=50000;
    const storage='tang-desk-reflection';try{text.value=localStorage.getItem(storage)||'';}catch(_){}text.oninput=()=>{try{localStorage.setItem(storage,text.value);}catch(_){}};
    const status=node('p','','dialog-status');const id=crypto.randomUUID();let lockedText=null;
    const save=button('把今天留下来',async()=>{if(!text.value.trim()){text.focus();return;}save.disabled=true;text.readOnly=true;lockedText=text.value.trim();try{await wb.request('/api/notes',{id,kind:'reflection',text:lockedText});try{localStorage.removeItem(storage);}catch(_){}$('#deskDialog').close();await refresh();showToast('已留下今天的记录');}catch(error){status.textContent=error.message+'。文字已保留，请先核对。';}finally{save.disabled=false;text.readOnly=false;}},'desk-primary');
    const actions=node('div',undefined,'dialog-actions');actions.append(save);root.append(text,status,actions);text.focus();
  }
  $('#shareFeeling').onclick=reflection;$('#eveningReview').onclick=reflection;
  function renderDetail(){
    if(!data||!['ideas','health','review'].includes(activeView))return;
    const root=$('#detailContent');root.replaceChildren();$('#deskDetail').classList.toggle('ideas-wide',activeView==='ideas');$('#detailTitle').textContent={ideas:'灵感有了自己的连接',health:'身体的节奏',review:'慢慢留下，慢慢看见'}[activeView];$('#detailIntro').textContent={ideas:'从一个关键词，找回那句话、那段记忆，以及下一步想做的事。',health:'看看真实记录，也听听自己的感受。',review:'你的每天，不只有完成了多少事情。'}[activeView];
    if(activeView==='ideas'){
      window.renderIdeaLibrary(root,{onContinue:async item=>{if(input.value.trim()&&input.value.trim()!==item.text)await wb.request('/api/notes',{id:crypto.randomUUID(),kind:'idea',text:input.value.trim()});input.value=item.text;input.dispatchEvent(new Event('input'));await go('today');input.focus();}});
      return;
    }
    if(activeView==='health'){
      if(!data.sleep.length){root.append(node('p','还没有收到睡眠数据。点击上方“连接手机睡眠”，开始同步。','health-note'));return;}
      const table=node('table',undefined,'sleep-table'),head=node('thead'),tr=node('tr');['日期','总睡眠','核心','深度','REM'].forEach(t=>tr.append(node('th',t)));head.append(tr);const body=node('tbody');for(const s of data.sleep){const row=node('tr');[s.day,duration(s.totalSleep),duration(s.core),duration(s.deep),duration(s.rem)].forEach(t=>row.append(node('td',t)));body.append(row);}table.append(head,body);root.append(table,node('p','只显示已收到的记录。缺失日期不会记成零；睡眠分期来自手表估计，不用于诊断。','health-note'));return;
    }
    const kind=activeView==='ideas'?'idea':'reflection';
    if(kind==='reflection')root.append(button('写下今天的回顾',reflection,'desk-primary'));
    const list=node('div',undefined,'note-list');if(kind==='reflection')list.style.marginTop='22px';
    const notes=data.notes.filter(n=>n.kind===kind);for(const item of notes){const entry=node('article',undefined,'note-entry');entry.append(node('p',item.text),node('small',date(item.created)),button(kind==='idea'?'接着这个想法写 →':'查看记录 →',()=>openNote(item)));list.append(entry);}if(!notes.length)list.append(node('p',kind==='idea'?'书桌上的“先记下来”，会把你的想法收在这里。':'今天可以成为第一条记录。','empty-ideas'));
    root.append(list);
    if(kind==='reflection'&&data.checkins.length){const title=node('h2','你记录过的身体感受');title.style.marginTop='32px';root.append(title);for(const c of data.checkins)root.append(node('p',c.day+' · '+({good:'有精神',okay:'一般',tired:'有点累'}[c.mood]),'subtle'));}
  }
  $('#connectSleep').onclick=async()=>{
    const root=dialog('把睡眠带到你的书桌');root.append(node('p','在 iPhone 上登录这个工作台，再点下面的按钮，用 Health Auto Export 创建睡眠同步。只接收睡眠摘要，其他健康数据不会保存在这里。'));
    const status=node('p','正在准备连接…','dialog-status');root.append(status);
    try{const setup=await wb.request('/api/health/setup');const link=node('a','在 iPhone 上设置同步','desk-primary');link.href=setup.setup_url;root.insertBefore(link,status);status.textContent='在应用中确认已选“睡眠”、按天汇总，再执行一次手动同步。后台同步时间由 iPhone 决定。';root.append(button('已完成，刷新睡眠',async()=>{try{await refresh();status.textContent=data.sleep.length?'已读取到 '+data.sleep[0].day+' 的睡眠记录。':'还没有收到记录，请在手机里运行一次同步。';}catch(error){status.textContent=error.message;}}));}catch(error){status.textContent=error.message;}
  };
  const Recognition=window.SpeechRecognition||window.webkitSpeechRecognition;let recognition=null;
  $('#voiceCapture').onclick=()=>{
    if(!Recognition){feedback('可以使用键盘上的系统听写，把说的话直接输入这里。');input.focus();return;}
    if(recognition){recognition.stop();return;}
    const r=new Recognition();recognition=r;r.lang='zh-CN';r.interimResults=false;r.continuous=true;
    r.onresult=event=>{for(let i=event.resultIndex;i<event.results.length;i++){if(event.results[i].isFinal)input.value+=(input.value?'\n':'')+event.results[i][0].transcript;}input.dispatchEvent(new Event('input'));};
    r.onerror=()=>feedback('这次语音输入没有完成，文字仍保留。你也可以使用系统听写。',true);
    r.onend=()=>{recognition=null;$('#voiceCapture span').textContent='说个想法';};
    r.onstart=()=>{feedback('正在听，完成后再点一次话筒。');$('#voiceCapture span').textContent='结束录音';};
    try{r.start();}catch(_){recognition=null;feedback('语音暂时不可用，可以用系统听写输入。',true);}
  };
})();
