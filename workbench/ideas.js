/* Explicit keyword-to-quote links; original notes never change. */
(() => {
  const element=(tag,text,cls)=>{const el=document.createElement(tag);if(text!==undefined)el.textContent=text;if(cls)el.className=cls;return el;};
  const key=word=>word.normalize('NFC').trim().toLowerCase();
  const date=time=>new Date(time*1000).toLocaleString('zh-CN',{timeZone:'Asia/Shanghai',month:'numeric',day:'numeric',hour:'2-digit',minute:'2-digit',hour12:false});
  const action=(text,callback,cls='quiet-button')=>{const b=element('button',text,cls);b.type='button';b.onclick=callback;return b;};
  const sourceLink=item=>{const label=item.source_label||'查看来源对话';if(!item.source_url)return element('span',item.source_label||'来源待补充','idea-source');const a=element('a',label+' ↗','idea-source');a.href=item.source_url;a.target='_blank';a.rel='noopener noreferrer';return a;};
  const svgElement=(tag,attrs={})=>{const el=document.createElementNS('http://www.w3.org/2000/svg',tag);for(const [k,v] of Object.entries(attrs))el.setAttribute(k,v);return el;};

  window.renderIdeaLibrary=async(root,{onContinue})=>{
    const state=root.ideaState||(root.ideaState={query:'',keyword:'',selected:'',positions:new Map(),zoom:1,pan:{x:0,y:0}});
    const requestId=Symbol();root.ideaRequest=requestId;
    root.replaceChildren(element('p','正在把灵感和关键词连起来…','subtle'));
    let ideas=[],savedKeywords=[];
    async function load(){const response=await window.workbench.request('/api/ideas');ideas=response.ideas;savedKeywords=response.keywords||[];}
    try{await load();}catch(error){root.replaceChildren(element('p',error.message,'idea-error'));return;}
    if(root.ideaRequest!==requestId||!root.isConnected||document.querySelector('#deskDetail').hidden||!document.querySelector('#deskDetail').classList.contains('ideas-wide'))return;
    root.replaceChildren();
    const toolbar=element('div',undefined,'idea-toolbar');const search=element('input');search.type='search';search.placeholder='找一个词，或你说过的一句话…';search.setAttribute('aria-label','搜索灵感和关键词');search.value=state.query;
    const info=element('span','','subtle');const create=action('＋ 记个灵感',()=>editNew(),'desk-primary');toolbar.append(search,info,create);
    const layout=element('div',undefined,'ideas-layout'),left=element('section',undefined,'idea-originals'),side=element('aside',undefined,'ideas-side');left.setAttribute('aria-label','你的原话');
    const filter=element('div',undefined,'idea-filter'),cards=element('div',undefined,'idea-quote-list');left.append(filter,cards);
    const tagsPanel=element('section',undefined,'keyword-panel'),tagsHead=element('div',undefined,'section-heading'),tags=element('div',undefined,'keyword-cloud');tagsHead.append(element('h2','从关键词开始'),action('看全部',()=>{state.keyword='';state.selected='';draw();},'text-button'));tagsPanel.append(tagsHead,element('p','先记一个词也可以，原话和关联以后再补。','subtle'));
    const keywordForm=element('form',undefined,'keyword-capture'),keywordInput=element('input'),keywordSave=element('button','记下关键词','desk-primary'),keywordStatus=element('p','','keyword-status');
    keywordInput.id='newKeyword';keywordInput.placeholder='输入关键词，按回车记下';keywordInput.setAttribute('aria-label','新增关键词');keywordInput.maxLength=40;keywordInput.required=true;keywordSave.type='submit';keywordStatus.setAttribute('role','status');keywordStatus.setAttribute('aria-live','polite');keywordForm.append(keywordInput,keywordSave);const keywordActions=element('div',undefined,'keyword-actions');tagsPanel.append(keywordForm,keywordStatus,tags,keywordActions);
    keywordForm.onsubmit=async event=>{event.preventDefault();const value=keywordInput.value.trim();if(!value){keywordInput.focus();return;}keywordInput.readOnly=true;keywordSave.disabled=true;keywordStatus.textContent='正在记下…';try{const result=await window.workbench.request('/api/keywords',{keyword:value});await load();state.query=search.value='';state.keyword=result.key;state.selected='';keywordInput.value='';keywordStatus.textContent=`已记下「${result.label}」，现在或以后都可以关联原话。`;draw();}catch(error){keywordStatus.textContent=error.message+'，输入已保留。';}finally{keywordSave.disabled=false;keywordInput.readOnly=false;keywordInput.focus();}};
    const graphPanel=element('section',undefined,'idea-graph-panel'),graphHead=element('div',undefined,'section-heading'),graph=element('div',undefined,'idea-graph'),graphNote=element('p','','graph-note');graphHead.append(element('h2','灵感关系图'));graphPanel.append(graphHead,graph,graphNote);
    const detail=element('section',undefined,'idea-connection-detail');side.append(tagsPanel,graphPanel,detail);layout.append(left,side);root.append(toolbar,layout);
    let visible=[];
    function matches(item){return !state.query||[item.text,...item.keywords,item.context,item.next_step,item.source_label].join('\n').toLowerCase().includes(state.query.toLowerCase());}
    function chooseKeyword(word){state.keyword=state.keyword===key(word)?'':key(word);state.selected='';draw();}
    function chooseNote(id){state.selected=state.selected===id?'':id;state.keyword='';draw();}
    search.oninput=()=>{state.query=search.value;state.keyword='';state.selected='';draw();};
    function draw(){
      visible=ideas.filter(matches);const filtered=visible.filter(i=>!state.keyword||i.keywords.some(w=>key(w)===state.keyword));
      info.textContent=`${ideas.length} 条原话`;cards.replaceChildren();filter.replaceChildren();
      if(state.keyword){filter.append(element('span',`“${state.keyword}” · ${filtered.length} 条关联原话`),action('清除筛选',()=>{state.keyword='';draw();},'text-button'));}
      else filter.append(element('span',state.query?`找到 ${filtered.length} 条原话`:'原话留在这里，关联可以慢慢补。'));
      for(const item of filtered){
        const card=element('article',undefined,'idea-quote');card.dataset.id=item.id;card.classList.toggle('selected',state.selected===item.id);
        const quote=element('blockquote',item.text);const label=element('div',undefined,'idea-quote-top');label.append(element('span','我的原话'),action('定位到图谱',()=>chooseNote(item.id),'text-button'));
        const chips=element('div',undefined,'idea-quote-keywords');for(const word of item.keywords){const b=action('# '+word,()=>chooseKeyword(word),'keyword-chip');b.setAttribute('aria-pressed',String(state.keyword===key(word)));chips.append(b);}if(!item.keywords.length)chips.append(element('span','还没有关键词，随时可以补上。','subtle'));
        const origin=element('div',undefined,'idea-origin-line');origin.append(element('time',date(item.created)),sourceLink(item));
        const actions=element('div',undefined,'idea-quote-actions');actions.append(action('整理关联',()=>editLinks(item),'text-button'),action('接着这个想法写 →',async()=>{try{await onContinue(item);}catch(error){showError(error);}},'quiet-button'));
        card.append(label,quote,chips,origin,actions);cards.append(card);
      }
      if(!filtered.length)cards.append(element('p',state.keyword?'这个关键词已经留下了，想起相关的人、事或一句话时，再来补充就好。':ideas.length?'没有匹配的原话，换个词试试。':'看见了什么、想到了谁，都可以从一句原话开始。','empty-ideas'));
      const counts=new Map(savedKeywords.filter(w=>!state.query||w.label.toLowerCase().includes(state.query.toLowerCase())).map(w=>[w.key,{label:w.label,count:0}]));for(const item of visible)for(const word of item.keywords){const k=key(word);const old=counts.get(k)||{label:word,count:0};old.count++;counts.set(k,old);}
      tags.replaceChildren();for(const [k,v] of [...counts].sort((a,b)=>b[1].count-a[1].count)){const chip=action(v.label+' · '+(v.count||'待关联'),()=>chooseKeyword(v.label),'keyword-chip');chip.setAttribute('aria-pressed',String(state.keyword===k));tags.append(chip);}if(!counts.size)tags.append(element('p','在上方记下第一个关键词，它会出现在这里和图谱里。','subtle'));
      keywordActions.replaceChildren();if(state.keyword){const word=counts.get(state.keyword)?.label||state.keyword;keywordActions.append(action('关联已有原话',()=>linkKeyword(word),'quiet-button'),action('给这个词补一句话',()=>editNew(word),'text-button'));}
      const selected=ideas.find(i=>i.id===state.selected);detail.replaceChildren();
      if(selected){detail.append(element('h2','这句话的来路与去向'));for(const [label,value] of [['当时看见 / 想起',selected.context],['提炼成关键词',selected.keywords.join(' · ')],['我说过的话',selected.text],['以后想做',selected.next_step]]){const block=element('div',undefined,'idea-chain-step');block.append(element('small',label),element('p',value||'还没有补充'));detail.append(block);}detail.append(sourceLink(selected),action('补充 / 修改关联',()=>editLinks(selected),'quiet-button'));}
      else if(state.keyword){const word=counts.get(state.keyword)?.label||state.keyword;detail.append(element('h2','关键词 · '+word),element('p',`${filtered.length} 条关联原话。可以先存词，再慢慢找回记忆。`,'subtle'));}
      else detail.append(element('h2','让思考有迹可循'),element('p','原句是根，关键词是路标。共享一个词的想法会连起来；选中原句，还能找回当时的场景和未来想做的事。','subtle'));
      renderGraph(visible);
    }
    function showError(error){const dialog=document.querySelector('#deskDialog'),content=document.querySelector('#dialogContent');content.replaceChildren(element('h2','这一步暂时没有完成'),element('p',error.message));dialog.showModal();}
    function editNew(keyword=''){
      const dialog=document.querySelector('#deskDialog'),content=document.querySelector('#dialogContent');content.replaceChildren(element('h2','先把想法留下来'),element('p',keyword?'这句原话会关联到「'+keyword+'」。':'想到什么就记什么，关键词可以稍后和小秋一起整理。'));
      const text=element('textarea');text.setAttribute('aria-label','新的灵感原话');text.maxLength=50000;const status=element('p','','dialog-status');const id=crypto.randomUUID();
      const save=action(keyword?'保存并关联':'保存这句原话',async()=>{if(!text.value.trim()){text.focus();return;}save.disabled=true;text.readOnly=true;try{await window.workbench.request('/api/notes',{id,kind:'idea',text:text.value});if(keyword)await window.workbench.request('/api/ideas',{id,revision:0,keywords:[keyword],source:'zelong/网页整理'});await load();state.query=search.value='';state.keyword='';state.selected=id;dialog.close();draw();}catch(error){status.textContent=error.message+'。文字已保留，请先核对保存结果。';}finally{save.disabled=false;text.readOnly=false;}},'desk-primary');const actions=element('div',undefined,'dialog-actions');actions.append(save);content.append(text,status,actions);dialog.showModal();text.focus();
    }
    function linkKeyword(word){
      const dialog=document.querySelector('#deskDialog'),content=document.querySelector('#dialogContent');content.replaceChildren(element('h2','把「'+word+'」连到原话'));
      if(!ideas.length){content.append(element('p','还没有原话。先给这个词补一句话吧。'),action('写一句原话',()=>{dialog.close();editNew(word);},'desk-primary'));dialog.showModal();return;}
      const select=element('select');select.setAttribute('aria-label','选择要关联的原话');select.append(new Option('选择一条原话…',''));for(const item of ideas)select.append(new Option(item.text.slice(0,80),item.id));const status=element('p','','dialog-status');
      const save=action('保存这条关联',async()=>{const item=ideas.find(i=>i.id===select.value);if(!item){select.focus();status.textContent='请先选一条原话。';return;}save.disabled=true;select.disabled=true;try{const body={id:item.id,revision:item.revision,keywords:[...item.keywords],context:item.context,next_step:item.next_step,source_label:item.source_label,source_url:item.source_url,source:'zelong/网页整理'};if(!body.keywords.some(k=>key(k)===key(word)))body.keywords.push(word);await window.workbench.request('/api/ideas',body);await load();state.keyword=key(word);state.selected='';dialog.close();draw();}catch(error){status.textContent=error.message+'；选择已保留。';}finally{save.disabled=false;select.disabled=false;}},'desk-primary');content.append(element('p','原句和已有关键词都保留，只增加这一条连接。'),select,status,save);dialog.showModal();
    }
    function editLinks(item){
      const dialog=document.querySelector('#deskDialog'),content=document.querySelector('#dialogContent');content.replaceChildren(element('h2','把这句话连起来'),element('blockquote',item.text,'link-original'));
      const form=element('form',undefined,'idea-link-form'),fields={};
      for(const [name,label,placeholder,multi] of [['keywords','关键词','例如：低门槛创作，长期迭代',false],['context','当时看见了什么 / 想起了谁','记下真实的场景、人物或记忆，暂时想不起来可以留空。',true],['next_step','以后想做什么','这个想法，让你联想到的下一步。',true],['source_label','来自哪段对话 / 哪份资料','例如：和小秋聊创作工作台',false],['source_url','来源链接（可选）','网页链接或 codex://threads/…',false]]){
        const id='idea-link-'+name;const field=element(multi?'textarea':'input');field.id=id;field.name=name;field.placeholder=placeholder;field.value=name==='keywords'?item.keywords.join('，'):item[name]||'';if(multi)field.rows=3;field.maxLength={keywords:1400,context:10000,next_step:10000,source_label:200,source_url:2000}[name];const labelEl=element('label',label);labelEl.htmlFor=id;form.append(labelEl,field);fields[name]=field;
      }
      const status=element('p','原句会原样保留，只更新这些关联。','dialog-status'),cache='tang-idea-links:'+item.id;
      try{const draft=JSON.parse(localStorage.getItem(cache)||'null');if(draft&&draft.revision===item.revision){for(const k in fields)fields[k].value=draft[k];status.textContent='已找回上次未保存的整理。原句保持不变。';}}catch(_){}
      form.oninput=()=>{try{localStorage.setItem(cache,JSON.stringify({revision:item.revision,...Object.fromEntries(Object.entries(fields).map(([k,v])=>[k,v.value]))}));}catch(_){}};
      const save=element('button','保存关联','desk-primary');save.type='submit';const actions=element('div',undefined,'dialog-actions');actions.append(save);form.append(status,actions);
      form.onsubmit=async event=>{event.preventDefault();save.disabled=true;const body={id:item.id,revision:item.revision,source:'zelong/网页整理'};for(const name in fields)body[name]=name==='keywords'?fields[name].value.split(/[，,、;；\n]+/).map(s=>s.trim()).filter(Boolean):fields[name].value;Object.values(fields).forEach(f=>f.readOnly=true);try{await window.workbench.request('/api/ideas',body);try{localStorage.removeItem(cache);}catch(_){}await load();state.selected=item.id;state.keyword='';dialog.close();draw();}catch(error){status.textContent=error.message+'；本次输入保留在这里。';}finally{save.disabled=false;Object.values(fields).forEach(f=>f.readOnly=false);}};
      content.append(form);dialog.showModal();fields.keywords.focus();
    }
    function renderGraph(items){
      graph.replaceChildren();const nodes=new Map(),edges=[];
      function add(id,label,type){if(!nodes.has(id)){const pos=state.positions.get(id);nodes.set(id,{id,label,type,x:pos?.x,y:pos?.y,degree:0});}return nodes.get(id);}
      function link(a,b){edges.push([a,b]);a.degree++;b.degree++;}
      for(const word of savedKeywords){if(!state.query||word.label.toLowerCase().includes(state.query.toLowerCase()))add('k:'+word.key,word.label,'keyword');}
      for(const item of items){const quote=add('n:'+item.id,item.text.slice(0,12)+(item.text.length>12?'…':''),'quote');quote.noteId=item.id;
        for(const word of item.keywords)link(quote,add('k:'+key(word),word,'keyword'));
        if(item.source_label||item.source_url)link(quote,add('s:'+(item.source_url||item.source_label),item.source_label||'来源对话','source'));
        if(item.context){const memory=add('m:'+item.id,item.context.slice(0,11)+'…','memory');memory.noteId=item.id;link(quote,memory);}
        if(item.next_step){const next=add('f:'+item.id,item.next_step.slice(0,11)+'…','future');next.noteId=item.id;link(quote,next);}
      }
      const all=[...nodes.values()];
      if(!all.length){graph.append(element('p','第一条灵感，会成为这里的第一个节点。','empty-graph'));graphNote.textContent='原句、关键词和来源，都会在这里连起来。';return;}
      const W=620,H=420,needsLayout=all.some(n=>n.x===undefined);
      all.forEach((n,i)=>{if(n.x===undefined){const angle=i*2.39996,r=all.length===1?0:Math.sqrt((i+1)/all.length)*165;n.x=W/2+Math.cos(angle)*r*1.3;n.y=H/2+Math.sin(angle)*r;}});
      // ponytail: pairwise layout fits a personal graph; use quadtree forces if thousands of nodes become slow.
      for(let turn=0;needsLayout&&turn<55;turn++){
        for(let i=0;i<all.length;i++)for(let j=i+1;j<all.length;j++){const a=all[i],b=all[j];let dx=a.x-b.x,dy=a.y-b.y;const d=Math.max(1,Math.hypot(dx,dy)),push=Math.min(12,3200/(d*d)+Math.max(0,83-d)*.16);if(!dx&&!dy){dx=1;dy=.5;}a.x+=dx/d*push;a.y+=dy/d*push;b.x-=dx/d*push;b.y-=dy/d*push;}
        for(const [a,b] of edges){const dx=b.x-a.x,dy=b.y-a.y,d=Math.max(1,Math.hypot(dx,dy)),pull=(d-150)*.02;a.x+=dx/d*pull;a.y+=dy/d*pull;b.x-=dx/d*pull;b.y-=dy/d*pull;}
        for(const n of all){n.x=Math.max(80,Math.min(W-80,n.x+(W/2-n.x)*.003));n.y=Math.max(45,Math.min(H-45,n.y+(H/2-n.y)*.003));}
      }
      const svg=svgElement('svg',{viewBox:`0 0 ${W} ${H}`,role:'group','aria-label':'可交互灵感关系图，点击节点关联原句，拖动移动，使用加减按钮缩放',tabindex:'0'}),group=svgElement('g');svg.append(group);
      const lines=edges.map(([a,b])=>{const line=svgElement('line',{'class':'graph-edge'});group.append(line);return {a,b,line};});
      for(const n of all){const g=svgElement('g',{'class':'graph-node '+n.type,tabindex:'0',role:'button','aria-label':n.type==='keyword'?'关键词 '+n.label:'查看关联 '+n.label});g.dataset.node=n.id;n.el=g;g.append(svgElement('circle',{r:24,'class':'graph-hit'}));const radius=n.type==='keyword'?Math.min(15,8+n.degree*1.4):7;g.append(svgElement('circle',{r:radius}));const label=svgElement('text',{x:0,y:radius+22,'text-anchor':'middle'});const limit=n.type==='keyword'?12:n.type==='quote'?7:n.type==='source'?9:5;label.textContent=n.label.length>limit?n.label.slice(0,limit)+'…':n.label;const title=svgElement('title');title.textContent=n.label;g.append(label,title);group.append(g);g.onkeydown=event=>{if(event.key==='Enter'||event.key===' '){event.preventDefault();selectNode(n);}};g.onpointerenter=()=>highlight(n.id);g.onpointerleave=()=>highlight();}
      function selectNode(n){if(n.type==='keyword')chooseKeyword(n.label);else if(n.noteId)chooseNote(n.noteId);else{state.keyword='';state.selected='';const matchesSource=items.filter(i=>'s:'+(i.source_url||i.source_label)===n.id);detail.replaceChildren(element('h2',n.label),element('p',`${matchesSource.length} 条原话来自这里。`,'subtle'));if(matchesSource[0])detail.append(sourceLink(matchesSource[0]));highlight(n.id);}}
      function highlight(id){id=id||(state.selected?'n:'+state.selected:state.keyword?'k:'+state.keyword:'');const related=new Set([id]);edges.forEach(([a,b])=>{if(a.id===id)related.add(b.id);if(b.id===id)related.add(a.id);});all.forEach(n=>{n.el.classList.toggle('dim',!!id&&!related.has(n.id));n.el.classList.toggle('active',n.id===id);});lines.forEach(({a,b,line})=>line.classList.toggle('active',a.id===id||b.id===id));}
      function paint(){group.setAttribute('transform',`translate(${state.pan.x} ${state.pan.y}) scale(${state.zoom})`);all.forEach(n=>{n.el.setAttribute('transform',`translate(${n.x} ${n.y})`);state.positions.set(n.id,{x:n.x,y:n.y});});lines.forEach(({a,b,line})=>{line.setAttribute('x1',a.x);line.setAttribute('y1',a.y);line.setAttribute('x2',b.x);line.setAttribute('y2',b.y);});}
      function zoom(factor){const z=Math.max(.45,Math.min(3,state.zoom*factor)),ratio=z/state.zoom;state.pan.x=W/2-(W/2-state.pan.x)*ratio;state.pan.y=H/2-(H/2-state.pan.y)*ratio;state.zoom=z;paint();}
      const controls=element('div',undefined,'graph-controls');controls.append(action('＋',()=>zoom(1.2),'graph-control'),action('−',()=>zoom(1/1.2),'graph-control'),action('复位',()=>{state.zoom=1;state.pan={x:0,y:0};paint();},'graph-control'));controls.children[0].setAttribute('aria-label','放大关系图');controls.children[1].setAttribute('aria-label','缩小关系图');
      const point=event=>new DOMPoint(event.clientX,event.clientY).matrixTransform(svg.getScreenCTM().inverse());let drag=null;
      svg.onpointerdown=event=>{if(event.button!==0)return;const p=point(event),id=event.target.closest('[data-node]')?.dataset.node;drag={id,p,last:p,moved:false};svg.setPointerCapture(event.pointerId);};
      svg.onpointermove=event=>{if(!drag)return;const p=point(event),dx=p.x-drag.last.x,dy=p.y-drag.last.y;if(Math.hypot(p.x-drag.p.x,p.y-drag.p.y)>4)drag.moved=true;if(drag.id){const n=nodes.get(drag.id);n.x+=dx/state.zoom;n.y+=dy/state.zoom;}else{state.pan.x+=dx;state.pan.y+=dy;}drag.last=p;paint();};
      svg.onpointerup=event=>{if(!drag)return;const d=drag;drag=null;if(svg.hasPointerCapture(event.pointerId))svg.releasePointerCapture(event.pointerId);if(!d.moved&&d.id)selectNode(nodes.get(d.id));};svg.onpointercancel=()=>{drag=null;};
      svg.addEventListener('wheel',event=>{event.preventDefault();zoom(event.deltaY<0?1.08:1/1.08);},{passive:false});
      svg.onkeydown=event=>{if(event.key==='+'||event.key==='='){event.preventDefault();zoom(1.2);}if(event.key==='-'){event.preventDefault();zoom(1/1.2);}};
      const legend=element('div',undefined,'graph-legend');[['keyword','关键词'],['quote','原句'],['source','对话 / 来源'],['future','记忆 / 下一步']].forEach(([type,text])=>legend.append(element('span',text,type)));
      graph.append(controls,svg,legend);graphNote.textContent=`${all.length} 个节点 · ${edges.length} 条有依据的连接。拖动节点或空白处，滚轮缩放。`;paint();highlight();
    }
    draw();
  };
})();
