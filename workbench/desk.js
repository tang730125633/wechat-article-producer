/* Small private homepage over the existing article editor; no second app/runtime. */
(() => {
  const $ = s => document.querySelector(s), wb = window.workbench;
  const nav = {today:'showToday',articles:'showLibrary',ideas:'showIdeas',health:'showHealth',review:'showReview',editor:'showEditor'};
  let data = null, articles = [], recentId = '', activeView = 'today', operation = null, busy = false;
  let healthRequest=null,healthReadFailed=false,lastHealthFetch=0,healthPeriod='today';
  const input = $('#ideaInput'), captureStatus = $('#captureStatus');
  const cacheKey = 'tang-desk-capture';
  try { input.value = localStorage.getItem(cacheKey) || ''; } catch (_) {}
  input.addEventListener('input', () => {operation = null; try {localStorage.setItem(cacheKey,input.value);} catch (_) {captureStatus.textContent='设备暂存不可用，请点击“先记下来”保存。';}});
  const node = (tag, text, className) => {const el=document.createElement(tag);if(text!==undefined) el.textContent=text;if(className) el.className=className;return el;};
  const date = t => new Date(t*1000).toLocaleString('zh-CN',{timeZone:'Asia/Shanghai',month:'numeric',day:'numeric',hour:'2-digit',minute:'2-digit',hour12:false});
  const duration = value => {if(value==null) return '—';const m=Math.floor(value*60+1e-6);return `${Math.floor(m/60)}小时${m%60}分`;};
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
    if(activeView==='health') refreshHealth().catch(()=>{});
  });
  window.addEventListener('workbench-signedout',()=>{$('#deskPage').hidden=true;data=null;articles=[];$('#ideaCards').replaceChildren();$('#recentCover').removeAttribute('src');});
  window.addEventListener('workbench-ready',async()=>{
    try {await refresh();const query=new URLSearchParams(location.search);if(!query.has('article')&&!query.has('recover')) await go(['ideas','health','review','articles'].includes(query.get('view'))?query.get('view'):'today');}
    catch(error){feedback(error.message,true);if(!new URLSearchParams(location.search).has('article')) await go('today');$('#sleepSync').textContent='睡眠记录暂时读取失败';}
  });
  window.addEventListener('workbench-articles',event=>{articles=event.detail;renderRecent().catch(error=>{$('#recentEmpty').textContent=error.message;$('#recentEmpty').hidden=false;});});
  async function refresh(){data=await wb.request('/api/wellbeing');healthReadFailed=false;renderHealth();renderIdeas();renderDetail();}
  async function refreshHealth(force=false){
    if(!wb.signedIn||document.hidden||healthRequest||(!force&&Date.now()-lastHealthFetch<15000))return healthRequest;
    lastHealthFetch=Date.now();
    healthRequest=(async()=>{try{const health=await wb.request('/api/health');if(!data)return;Object.assign(data,health);healthReadFailed=false;renderHealth();if(activeView==='health'&&!$('#deskDialog').open)renderDetail();}catch(error){healthReadFailed=true;$('#sleepSync').textContent='页面暂时无法取到更新，保留上次记录';if(data&&activeView==='health'&&!$('#deskDialog').open)renderDetail();throw error;}finally{healthRequest=null;}})();
    return healthRequest;
  }
  setInterval(()=>refreshHealth().catch(()=>{}),60000);
  document.addEventListener('visibilitychange',()=>{if(!document.hidden)refreshHealth(true).catch(()=>{});});
  window.addEventListener('focus',()=>refreshHealth().catch(()=>{}));
  function syncInfo(){
    const sources=(data.sync?.sources||[]).filter(s=>s.source!=='manual'&&(data.sync?.primary!=='iphone'||s.source.startsWith('iphone'))).sort((a,b)=>b.checked-a.checked);
    const source=sources.find(s=>s.status==='ok'&&Date.now()/1000-s.checked<=Math.max(1800,s.interval*2.5))||sources[0];
    const status=healthReadFailed?'error':data.sync?.status||'unconfigured';
    const title={ok:'自动同步运行中',error:'同步需要留意',delayed:'同步已超过预期时间',unconfigured:'还没有自动同步通路'}[status];
    return {source,status,title};
  }

  let sleepOpener = '';
  $('#deskDialog').addEventListener('close',()=>{
    const modal=$('#deskDialog');if(!modal.classList.contains('sleep-dialog'))return;
    modal.classList.remove('sleep-dialog');modal.removeAttribute('aria-label');delete $('#dialogContent').dataset.sleepDay;
    if(sleepOpener)document.getElementById(sleepOpener)?.focus();
  });
  function sleepTime(value, day){
    if(!value)return '—';
    const normalized=typeof value==='number'?value*1000:value.replace(/^(\d{4}-\d{2}-\d{2}) /,'$1T').replace(/ ([+-]\d{2})(\d{2})$/,'$1:$2');
    const d=new Date(normalized);if(!Number.isFinite(d.getTime()))return '—';
    const dayKey=d.toLocaleDateString('en-CA',{timeZone:'Asia/Shanghai'});
    const time=d.toLocaleTimeString('zh-CN',{timeZone:'Asia/Shanghai',hour:'2-digit',minute:'2-digit',hour12:false});
    return (day&&dayKey!==day?dayKey.slice(5).replace('-','/')+' ':'')+time;
  }
  const stageNames={awake:'清醒',rem:'快速动眼（REM）',core:'核心睡眠',deep:'深度睡眠',asleep:'未分期睡眠',inBed:'卧床'};
  function openSleepDay(day){
    sleepOpener=document.activeElement?.id||'';
    dialog('睡眠详情');$('#deskDialog').classList.add('sleep-dialog');$('#deskDialog').setAttribute('aria-label','睡眠详情');
    renderSleepDay(day);
  }
  function renderSleepDay(day){
    const root=$('#dialogContent'),record=data.sleep.find(r=>r.day===day);root.replaceChildren(node('h2','睡眠详情'));root.dataset.sleepDay=day;
    if(!record){root.append(node('p','这一天还没有收到睡眠记录。'));return;}
    const records=[...data.sleep].sort((a,b)=>b.day.localeCompare(a.day)),idx=records.findIndex(r=>r.day===day);
    const nav=node('div',undefined,'sleep-detail-nav'),choose=node('select');choose.id='sleep-detail-date';choose.setAttribute('aria-label','选择睡眠日期');
    for(const item of records){const option=node('option',item.day);option.value=item.day;choose.append(option);}choose.value=day;
    const move=target=>{renderSleepDay(target);$('#sleep-detail-date').focus();};choose.onchange=()=>move(choose.value);
    const prev=button('‹',()=>move(records[idx+1].day),'sleep-date-arrow');prev.disabled=idx===records.length-1;prev.setAttribute('aria-label','上一条睡眠记录');
    const next=button('›',()=>move(records[idx-1].day),'sleep-date-arrow');next.disabled=idx===0;next.setAttribute('aria-label','下一条睡眠记录');nav.append(prev,choose,next);root.append(nav);
    const total=node('section',undefined,'sleep-detail-total');total.append(node('small','睡眠时间'),node('strong',duration(record.totalSleep)));
    const previous=records[idx+1];if(previous){const minutes=Math.round((record.totalSleep-previous.totalSleep)*60);total.append(node('span',`比 ${previous.day.slice(5).replace('-','/')} ${minutes<0?'少':'多'} ${Math.abs(minutes)} 分钟`));}root.append(total);
    const times=node('div',undefined,'sleep-detail-times');for(const [label,key] of [['入睡','sleepStart'],['起床','sleepEnd']]){const card=node('div');card.append(node('span',label),node('strong',sleepTime(record[key],day)));times.append(card);}root.append(times);
    const chart=node('section',undefined,'sleep-timeline');chart.append(node('h3','这一晚的睡眠阶段'),node('p','正在读取分期明细…','sleep-detail-note'));root.append(chart);
    const stageList=node('div',undefined,'sleep-detail-stages'),values={};
    for(const key of ['awake','rem','core','deep']){const row=node('div',undefined,'sleep-detail-stage');row.dataset.stage=key;const label=node('span',stageNames[key]);const value=node('strong',record[key]==null?'尚未同步':duration(record[key]));values[key]=value;row.append(label,value);stageList.append(row);}root.append(stageList);
    if(record.inBed>0){const bed=node('p','已记录卧床时间 '+duration(record.inBed),'sleep-detail-note');root.append(bed);}
    const signals=node('section',undefined,'sleep-detail-signals');signals.append(node('h3','当天的身体记录'));
    const grid=node('div',undefined,'sleep-signal-grid');
    for(const [key,label,unit,digits] of [['heart_rate','日均心率','次/分',0],['respiratory_rate','日均呼吸频率','次/分',1],['heart_rate_variability','日均 HRV','毫秒',1],['apple_sleeping_wrist_temperature','睡眠腕温','°C',1]]){
      const metric=(data.metrics||[]).find(m=>m.day===day&&m.name===key),card=node('div');card.append(node('span',label),node('strong',metric?Number(metric.value).toLocaleString('zh-CN',{maximumFractionDigits:digits}):'—'),node('small',metric?unit:'尚未收到'));
      if(metric&&key==='heart_rate')card.append(node('small',`当天范围 ${Math.round(metric.min)}–${Math.round(metric.max)}`));grid.append(card);
    }
    signals.append(grid,node('p','心率、呼吸和 HRV 是当天汇总，不是整晚专属测量。','sleep-detail-note'));root.append(signals);
    root.append(node('p','睡眠汇总更新于 '+date(record.received)+'。分期来自设备记录，用于了解自己的变化。','sleep-detail-note'));
    wb.request('/api/health/sleep?day='+encodeURIComponent(day)).then(detail=>{
      if(!$('#deskDialog').open||root.dataset.sleepDay!==day)return;
      renderSleepTimeline(chart,detail,record,values);
    }).catch(()=>{
      if(root.dataset.sleepDay!==day)return;
      chart.replaceChildren(node('h3','这一晚的睡眠阶段'),node('p','分期明细暂时没有取到，汇总记录仍然保留。','sleep-detail-note'),button('重新读取',()=>renderSleepDay(day),'quiet-button'));
    });
  }
  function renderSleepTimeline(root,detail,record,values){
    root.replaceChildren(node('h3','这一晚的睡眠阶段'));
    const segments=detail.segments||[],window=detail.window;
    if(!segments.length||!window){
      root.append(node('p','这晚目前只有每日汇总，尚未收到逐段时间轴。下面仍可查看已同步的分期时长。','sleep-detail-note'));
      const composition=node('div',undefined,'sleep-composition'),sum=['rem','core','deep'].reduce((n,k)=>n+(record[k]||0),0);
      for(const key of ['rem','core','deep'])if(record[key]>0&&sum){const piece=node('span');piece.dataset.stage=key;piece.style.flexGrow=String(record[key]);piece.title=stageNames[key]+' '+duration(record[key]);composition.append(piece);}root.append(composition);
      const setup=button('连接睡眠分期明细',()=>{$('#deskDialog').close();$('#connectSleep').click();},'text-button');root.append(setup);return;
    }
    const sources=[...new Set(segments.map(s=>s.source))].sort((a,b)=>segments.filter(s=>s.source===b&&['rem','core','deep'].includes(s.stage)).length-segments.filter(s=>s.source===a&&['rem','core','deep'].includes(s.stage)).length);
    const sourceLabel=node('p',sources[0]||'手机同步的睡眠分期','sleep-detail-note'),canvas=node('div'),more=node('details',undefined,'sleep-segment-list');
    let selected=sources[0];root.append(sourceLabel);
    if(sources.length>1){const select=node('select');select.setAttribute('aria-label','选择睡眠分期来源');for(const source of sources){const option=node('option',source||'未提供来源');option.value=source;select.append(option);}select.onchange=()=>{selected=select.value;sourceLabel.textContent=selected||'未提供来源';draw();};root.append(select);}root.append(canvas,more);
    function merged(rows){const out=[];for(const r of [...rows].sort((a,b)=>a.start-b.start)){const last=out.at(-1);if(last&&r.start<=last.end)last.end=Math.max(last.end,r.end);else out.push({...r});}return out;}
    function draw(){
      const rows=segments.filter(s=>s.source===selected),span=window.end-window.start;canvas.replaceChildren();more.replaceChildren(node('summary','查看 '+rows.length+' 段原始明细'));
      const keys=['awake','rem','core','deep'];if(rows.some(s=>s.stage==='asleep'))keys.push('asleep');
      for(const key of keys){const lane=node('div',undefined,'sleep-timeline-lane'),track=node('div',undefined,'sleep-lane-track');lane.dataset.stage=key;lane.append(node('span',key==='rem'?'REM':stageNames[key]));const parts=merged(rows.filter(s=>s.stage===key));
        for(const part of parts){const bar=node('span',undefined,'sleep-piece');bar.style.left=((part.start-window.start)/span*100)+'%';bar.style.width=((part.end-part.start)/span*100)+'%';bar.title=stageNames[key]+' '+sleepTime(part.start)+'–'+sleepTime(part.end);track.append(bar);}lane.append(track);canvas.append(lane);
        if(key==='awake'&&values.awake&&record.awake==null){const seconds=parts.reduce((n,r)=>n+r.end-r.start,0);values.awake.textContent=parts.length?duration(seconds/3600):'未记录到清醒片段';}
      }
      const axis=node('div',undefined,'sleep-timeline-axis');for(let i=0;i<4;i++)axis.append(node('span',sleepTime(window.start+span*i/3)));canvas.append(axis);
      const table=node('table'),body=node('tbody');for(const part of rows){const tr=node('tr');for(const text of [stageNames[part.stage],sleepTime(part.start)+'–'+sleepTime(part.end),duration((part.end-part.start)/3600)])tr.append(node('td',text));body.append(tr);}table.append(body);more.append(table);
    }
    draw();root.append(node('p','时间轴来自实际分期片段；留白表示该时间段未收到对应记录。明细更新于 '+date(detail.received)+'。','sleep-detail-note'));
  }

  function renderHealthDetail(root){
    const latest=data.sleep[0],sync=syncInfo(),source=sync.source;
    const control=node('div',undefined,'health-live-heading');const badge=node('span',sync.title,'health-live-badge');badge.dataset.state=sync.status;
    control.append(badge,button('刷新显示',async()=>{try{await refreshHealth(true);}catch(_){showToast('暂时无法连接，正在保留上次记录');}},'quiet-button'));root.append(control);
    const top=node('div',undefined,'health-summary-grid'),night=node('section',undefined,'health-night-card'),connection=node('section',undefined,'health-connection-card');
    night.append(node('small',latest?latest.day+' · 最近收到的睡眠':'等待第一晚睡眠'),node('h2',latest?duration(latest.totalSleep):'还没有记录'));
    if(latest){const stages=node('div',undefined,'sleep-stages');stages.setAttribute('aria-label','睡眠分期');const legend=node('div',undefined,'sleep-stage-labels');const total=['core','deep','rem'].reduce((sum,k)=>sum+(latest[k]||0),0);for(const [k,label] of [['core','核心'],['deep','深度'],['rem','REM']]){if(latest[k]==null)continue;const segment=node('span',undefined,k);segment.style.flexGrow=String(latest[k]);segment.title=label+' '+duration(latest[k]);if(total)stages.append(segment);const item=node('p');item.className=k;item.append(node('span',label),node('strong',duration(latest[k])));legend.append(item);}night.append(stages,legend);if(latest.day!==data.today)night.append(node('p','今天的新记录还没有到，当前展示的是 '+latest.day+'。','health-pending'));}
    else night.append(node('p','新记录到达后，这里会自动显示。','subtle'));
    connection.append(node('h2','数据正在怎么更新'),node('p',source?(source.source==='mac-bridge'?'经 Mac 自动同步':'iPhone 自动直传'):'暂未接通自动同步','health-channel'));
    const times=node('dl',undefined,'health-sync-times');const add=(a,b)=>{times.append(node('dt',a),node('dd',b));};
    add('最近检查',source?date(source.checked):'尚无自动检查');add('最近成功',source?.success?date(source.success):'尚未成功');
    const changed=Math.max(0,...[...data.sleep,...(data.metrics||[]),...(data.workouts||[])].map(s=>s.received||0));add('内容实际变化',changed?date(changed):'还没有新内容');add(source?.source.startsWith('iphone')?'期望同步间隔':'检查周期',source?`每 ${Math.round(source.interval/60)} 分钟`:'等待配置');
    connection.append(times,node('p','页面打开时每分钟自动刷新；切回来也会立即检查。','subtle'));
    if(source?.source.startsWith('iphone'))connection.append(node('p','数据由 iPhone 直接上传；Mac 只负责看网页。手机锁屏及 iOS 后台调度会影响上传时机。','health-dependency'));
    for(const [channel,label] of [['iphone','手机健康指标'],['iphone-workouts','手机训练记录'],['iphone-sleep','手机睡眠明细']]){const receipt=(data.sync?.sources||[]).find(s=>s.source===channel);connection.append(node('p',label+'：'+(receipt?.success?'收到于 '+date(receipt.success):'尚未收到直传'),'health-channel-receipt'));}
    if(source?.source==='mac-bridge')connection.append(node('p','Mac 休眠或关机时暂停，恢复后继续。手机直传接通后可不依赖 Mac。','health-dependency'));
    if(sync.status==='error'||sync.status==='delayed'){const errors={source_unavailable:'Mac 上的健康服务暂时无法读取。',source_rejected:'健康服务拒绝了读取，请检查应用授权。',invalid_source_data:'健康服务返回的数据暂时无法解析。',no_records:'上游尚未返回新的睡眠记录。'};connection.append(node('p',healthReadFailed?'网页暂时联系不上服务器；这里保留的是上次状态。':sync.status==='delayed'?(data.sync?.primary==='iphone'?'较久没有收到手机上传。请解锁 iPhone，检查健康导出应用的运行记录。':'很久没有收到自动检查了，请确认 Mac 在线、健康服务仍在运行。'):errors[source?.error]||'这轮同步没有成功，历史记录已保留。','health-pending'));}
    if(latest)night.append(button('查看这晚详情 →',()=>openSleepDay(latest.day),'text-button'));
    connection.append(button('手机直传设置',()=>$('#connectSleep').click(),'text-button'));top.append(night,connection);root.append(top);renderMovement(root);
    const week=node('section',undefined,'health-week-card');const heading=node('div',undefined,'section-heading');heading.append(node('h2','最近七天，身体的节奏'));
    const bars=node('div',undefined,'health-week-bars'),records=[];
    for(let i=6;i>=0;i--){const d=new Date(data.today+'T12:00:00+08:00');d.setUTCDate(d.getUTCDate()-i);const day=d.toLocaleDateString('en-CA',{timeZone:'Asia/Shanghai'}),record=data.sleep.find(s=>s.day===day);if(record)records.push(record);const col=button('',()=>openSleepDay(day),'health-day-column');col.id='sleep-week-'+day;col.disabled=!record;col.setAttribute('aria-label',day+' · '+(record?duration(record.totalSleep)+'，查看睡眠详情':'未收到睡眠记录'));col.dataset.missing=String(!record);const area=node('span',undefined,'health-bar-area'),bar=node('i');bar.style.height=record?Math.max(3,Math.min(100,record.totalSleep/12*100))+'%':'2px';area.append(bar);col.append(node('strong',record?duration(record.totalSleep):'未收到'),area,node('span',day.slice(5).replace('-','/')));bars.append(col);}
    heading.append(node('span',`已收到 ${records.length} / 7 天`,'subtle'));week.append(heading,bars);
    let insight='先积累真实记录。缺失日期留空，不记成零，也不凭一晚给你打分。';
    if(records.length>=3){const recent=records[records.length-1],previous=records.slice(0,-1),avg=previous.reduce((sum,r)=>sum+r.totalSleep,0)/previous.length,diff=Math.round((recent.totalSleep-avg)*60);insight=`最近这晚比前 ${previous.length} 晚的平均时长${diff<0?'少':'多'} ${Math.abs(diff)} 分钟。今天的感受，也值得一起记下来。`;}
    week.append(node('p',insight,'health-insight'),button('记下今天的感受',reflection,'quiet-button'));root.append(week);
    if(data.sleep.length){const section=node('details',undefined,'health-history');section.append(node('summary','查看每日记录与睡眠分期'));const table=node('table',undefined,'sleep-table'),head=node('thead'),tr=node('tr');['日期','总睡眠','核心','深度','REM'].forEach(t=>tr.append(node('th',t)));head.append(tr);const body=node('tbody');for(const s of data.sleep){const row=node('tr');[s.day,duration(s.totalSleep),duration(s.core),duration(s.deep),duration(s.rem)].forEach(t=>row.append(node('td',t)));body.append(row);}table.append(head,body);section.append(table);root.append(section);}
    root.append(node('p','睡眠分期来自手表估计，不用于诊断。数据检查、数据变化和你的身体感受分别记录。','health-note'));
  }
  function renderMovement(root){
    const metrics=data.metrics||[],workouts=data.workouts||[];
    const yesterday=new Date(data.today+'T12:00:00+08:00');yesterday.setUTCDate(yesterday.getUTCDate()-1);const yesterdayKey=yesterday.toLocaleDateString('en-CA',{timeZone:'Asia/Shanghai'});
    const get=(name,day)=>metrics.find(m=>m.name===name&&m.day===day);
    const format=(value,digits=0)=>Number(value).toLocaleString('zh-CN',{maximumFractionDigits:digits});
    const overview=node('section',undefined,'health-morning');overview.append(node('h2','先看看最近的自己'));
    const latest=data.sleep[0],previous=data.sleep[1],sentences=[];
    if(latest&&previous){const diff=Math.round((latest.totalSleep-previous.totalSleep)*60);sentences.push(`${latest.day} 的睡眠比上一条记录${diff>=0?'多':'少'}约 ${Math.abs(diff)} 分钟。`);}
    const steps=get('step_count',yesterdayKey),exercise=get('apple_exercise_time',yesterdayKey);
    sentences.push(`昨天（${yesterdayKey}）${steps?'已记录 '+format(steps.value)+' 步':'步数尚未收到'}${exercise?'，锻炼 '+format(exercise.value)+' 分钟':''}。`);
    overview.append(node('p',sentences.join(' ')),button('记下今天的状态',reflection,'quiet-button'));root.append(overview);
    const activity=node('section',undefined,'health-activity'),heading=node('div',undefined,'section-heading'),period=node('div',undefined,'health-period');
    for(const [value,label] of [['today','今天'],['yesterday','昨天']]){const b=button(label,()=>{healthPeriod=value;renderDetail();},'quiet-button');b.setAttribute('aria-pressed',String(healthPeriod===value));period.append(b);}
    heading.append(node('h2','日常活动'),period);activity.append(heading);
    const day=healthPeriod==='today'?data.today:yesterdayKey;activity.append(node('p',day+' · 已同步的累计记录，不把缺失记成零。','subtle'));
    const tiles=node('div',undefined,'health-metric-grid');
    for(const [name,label,unit,digits] of [['step_count','步数','步',0],['active_energy','活动热量','千卡',0],['apple_exercise_time','锻炼时间','分钟',0],['apple_stand_hour','站立小时','小时',0],['walking_running_distance','步行与跑步','公里',2],['cycling_distance','骑行距离','公里',2],['flights_climbed','爬楼','层',0],['time_in_daylight','日光下的时间','分钟',0]]){
      const item=get(name,day),tile=node('article',undefined,'health-metric-card');tile.append(node('span',label),node('strong',item?format(item.value,digits):'—'),node('small',item?unit+' · 接收于 '+date(item.received):'尚未收到这项记录'));tiles.append(tile);
    }
    activity.append(tiles);root.append(activity);
    const vitals=node('section',undefined,'health-vitals');vitals.append(node('h2','身体信号'),node('p','展示已收到的测量或当日汇总，不代表此刻的实时读数。','subtle'));
    const vitalGrid=node('div',undefined,'health-metric-grid');
    for(const [name,label,unit,digits] of [['resting_heart_rate','静息心率','次/分',0],['heart_rate','平均心率','次/分',0],['heart_rate_variability','心率变异性 HRV','毫秒',1],['respiratory_rate','平均呼吸频率','次/分',1],['apple_sleeping_wrist_temperature','睡眠腕温','°C',1],['vo2_max','有氧适能估算','ml/(kg·min)',1]]){
      const item=metrics.find(m=>m.name===name),tile=node('article',undefined,'health-metric-card');tile.append(node('span',label),node('strong',item?format(item.value,digits):'—'),node('small',item?unit+' · '+item.day:'尚未收到'));
      if(item?.name==='heart_rate')tile.append(node('small',`当天范围 ${format(item.min)}–${format(item.max)} 次/分`));vitalGrid.append(tile);
    }
    vitals.append(vitalGrid);root.append(vitals);
    const training=node('section',undefined,'health-workouts');training.append(node('h2','最近的训练'),node('p','训练单独展示，不会再叠加到上面的活动热量中。','subtle'));
    const names={'Traditional Strength Training':'传统力量训练','Functional Strength Training':'功能性力量训练','Running':'跑步','Walking':'步行','Cycling':'骑行','Yoga':'瑜伽','Swimming':'游泳','High Intensity Interval Training':'高强度间歇训练'};
    if(!workouts.length)training.append(node('p','暂未收到训练记录。日常活动与记录成一场训练是两类数据。','empty-ideas'));
    for(const w of workouts.slice(0,10)){const card=node('article',undefined,'health-workout-card');const info=node('div');info.append(node('h3',names[w.name]||w.name),node('p',date(w.start)+(w.source?' · '+w.source:''),'subtle'));const values=node('div',undefined,'workout-values');values.append(node('strong',format(w.duration_seconds/60,1)+' 分钟'));if(w.energy_kcal!=null)values.append(node('span',format(w.energy_kcal)+' 千卡'));if(w.distance_km!=null)values.append(node('span',format(w.distance_km,2)+' 公里'));card.append(info,values);training.append(card);}root.append(training);
  }
  function renderHealth(){
    const latest=data.sleep[0],today=data.today;
    $('#sleepTotal').replaceChildren();
    if(latest){const m=Math.floor(latest.totalSleep*60+1e-6);$('#sleepTotal').append(node('span',String(Math.floor(m/60))),node('small','小时'),node('span',String(m%60)),node('small','分'));$('#sleepLabel').textContent=latest.day===today?'最近一晚睡眠':latest.day+' 的睡眠';$('#sleepSync').textContent=`收到于 ${date(latest.received)}${latest.day!==today?' · 待新记录':''}`;}
    else {$('#sleepTotal').append(node('span','—'),node('small',' 等待同步'));$('#sleepSync').textContent='还没有收到睡眠记录';}
    $('#sleepChart').replaceChildren();
    for(let offset=6;offset>=0;offset--){const d=new Date(today+'T12:00:00+08:00');d.setUTCDate(d.getUTCDate()-offset);const day=d.toLocaleDateString('en-CA',{timeZone:'Asia/Shanghai'});const record=data.sleep.find(s=>s.day===day);const bar=button('',()=>openSleepDay(day),'sleep-bar');bar.id='sleep-mini-'+day;bar.disabled=!record;bar.setAttribute('aria-label',day+' · '+(record?duration(record.totalSleep)+'，查看睡眠详情':'未收到睡眠记录'));bar.dataset.current=String(offset===0);bar.dataset.missing=String(!record);bar.title=day+' · '+(record?duration(record.totalSleep):'暂无记录');const line=node('i');line.style.height=(record?Math.max(3,Math.min(55,record.totalSleep/10*55)):2)+'px';bar.append(line,node('span',offset===0?'今天':d.toLocaleDateString('zh-CN',{timeZone:'Asia/Shanghai',weekday:'short'})));$('#sleepChart').append(bar);}
    const sync=syncInfo();const recordText=latest?'记录 '+latest.day:'暂无睡眠记录';$('#sleepSync').textContent=sync.source?`${recordText} · ${sync.status==='ok'?'自动同步':sync.title} · 检查于 ${date(sync.source.checked)}`:`${recordText} · 尚未接通自动同步`;$('#sleepSync').dataset.state=sync.status;
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
    if(activeView==='health'){renderHealthDetail(root);return;}
    const kind=activeView==='ideas'?'idea':'reflection';
    if(kind==='reflection')root.append(button('写下今天的回顾',reflection,'desk-primary'));
    const list=node('div',undefined,'note-list');if(kind==='reflection')list.style.marginTop='22px';
    const notes=data.notes.filter(n=>n.kind===kind);for(const item of notes){const entry=node('article',undefined,'note-entry');entry.append(node('p',item.text),node('small',date(item.created)),button(kind==='idea'?'接着这个想法写 →':'查看记录 →',()=>openNote(item)));list.append(entry);}if(!notes.length)list.append(node('p',kind==='idea'?'书桌上的“先记下来”，会把你的想法收在这里。':'今天可以成为第一条记录。','empty-ideas'));
    root.append(list);
    if(kind==='reflection'&&data.checkins.length){const title=node('h2','你记录过的身体感受');title.style.marginTop='32px';root.append(title);for(const c of data.checkins)root.append(node('p',c.day+' · '+({good:'有精神',okay:'一般',tired:'有点累'}[c.mood]),'subtle'));}
  }
  $('#connectSleep').onclick=async()=>{
    const root=dialog('让 iPhone 直接上传');root.append(node('p','请在 iPhone Safari 中打开本页。健康指标、训练记录和睡眠分期分别同步；只添加尚未接通的项目，上传不经过 Mac。'));
    const status=node('p','正在准备手机配置…','dialog-status');root.append(status);
    try{
      for(const [kind,channel,label] of [['metrics','iphone','① 设置健康指标直传'],['workouts','iphone-workouts','② 设置训练记录直传'],['sleep','iphone-sleep','③ 设置睡眠分期明细']]){
        const receipt=(data.sync?.sources||[]).find(s=>s.source===channel);
        if(receipt?.success){root.insertBefore(node('p',label+'：已收到手机上传。以后请在 Health Auto Export 中管理现有自动化。'),status);continue;}
        const setup=await wb.request('/api/health/setup?kind='+kind);const link=node('a',label,'desk-primary');link.href=setup.setup_url;link.style.margin='8px 0';root.insertBefore(link,status);
      }
      status.textContent='在 Health Auto Export 中确认配置并分别执行一次“手动导出”。不要重复创建同名自动化。手机锁屏时健康读取受限；配置完成不等于上传已成功。';
      root.append(button('已执行上传，核对接收结果',async()=>{try{await refresh();const got=(data.sync?.sources||[]).filter(s=>s.source.startsWith('iphone')&&s.success);status.textContent=got.length===3?'三项手机直传均有成功回执。':'已收到 '+got.length+' / 3 项手机直传，请核对未完成项目。';}catch(error){status.textContent=error.message;}}));
    }catch(error){status.textContent=error.message;}
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
