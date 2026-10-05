/* The same article API is used by the editor and the owner's AI assistant. */
(() => {
  const $ = selector => document.querySelector(selector);
  const editor = $('.shell'), home = $('#libraryPage'), tools = $('#articleTools');
  const status = $('#cloudSaveStatus'), message = $('#libraryMessage');
  const browserDraft = localStorage.getItem(draftKey);
  let current = null, items = [], loading = false, dirty = false, conflict = false;
  let timer, saving = null, signedIn = false, generation = 0;
  const date = value => new Date(value * 1000).toLocaleString('zh-CN', {hour12:false});

  async function request(path, body) {
    const response = await fetch(apiPath(path), body === undefined ? {} : {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body)});
    const result = await response.json();
    if (!response.ok) {
      const error = new Error(result.error || '暂时无法连接工作台');
      error.status = response.status;
      throw error;
    }
    return result;
  }

  function documentState() {
    return {title:titleInput.value.trim() || '未命名文章', byline:bylineInput.value, markdown:markdownInput.value,
      theme:activeTheme, author:$('#draftAuthor').value, digest:$('#draftDigest').value,
      cover:coverDataUrl, cover_meta:coverMeta, images:Object.fromEntries(imageAssets), wechat:current?.document.wechat || null};
  }

  function switchView(edit) {
    $('#deskPage').hidden = true;
    editor.hidden = !edit; tools.hidden = !edit; home.hidden = edit;
    $('#showEditor').disabled = !current;
    $('#showEditor').hidden = !current;
    $('#saveArticle').hidden = !edit;
    window.dispatchEvent(new CustomEvent('workbench-view', {detail:edit ? 'editor' : 'articles'}));
    window.scrollTo(0, 0);
  }

  function showError(error) {
    status.textContent = error.message;
    if (error.status === 401) {
      signedIn = false; $('#ownerLogin').hidden = false;
      window.dispatchEvent(new CustomEvent('workbench-signedout'));
      message.textContent = '登录后可查看自己的历史文章。其他访客看不到你的草稿。';
    }
  }

  function drawList() {
    const search = $('#articleSearch').value.trim().toLocaleLowerCase();
    const filter = $('#articleFilter').value;
    const visible = items.filter(item => item.title.toLocaleLowerCase().includes(search) &&
      (filter === 'all' || (filter === 'archived' ? item.archived : filter === 'wechat' ? !item.archived && item.wechat : !item.archived)));
    $('#articleList').replaceChildren();
    for (const item of visible) {
      const button = document.createElement('button'); button.type = 'button';
      const state = document.createElement('small');
      state.textContent = item.archived ? '已归档' : item.wechat ? '已送微信草稿箱' : '工作台草稿';
      const title = document.createElement('h2'); title.textContent = item.title;
      const description = document.createElement('p'); description.textContent = item.digest;
      const updated = document.createElement('p'); updated.textContent = `${date(item.updated)} · 第 ${item.revision} 版`;
      button.append(state, title, description, updated);
      button.addEventListener('click', () => openArticle(item.id).catch(showError));
      $('#articleList').append(button);
    }
    message.textContent = visible.length ? `${visible.length} 篇文章，内容和历史版本保存在网站。` : '这里还没有文章。可以新建，也可以让 AI 把聊好的稿件保存进来。';
  }

  async function refresh() {
    if (!signedIn) return;
    items = (await request('/api/articles')).articles;
    drawList();
    window.dispatchEvent(new CustomEvent('workbench-articles', {detail:items}));
  }

  async function historyList() {
    if (!current?.revision) return;
    const id = current.id;
    const result = await request('/api/versions?id=' + encodeURIComponent(id));
    if (current?.id !== id) return;
    $('#versionSelect').replaceChildren(new Option('选择历史版本', ''));
    for (const version of result.versions) $('#versionSelect').add(new Option(`第 ${version.revision} 版 · ${date(version.updated)} · ${version.source}`, version.revision));
    $('#articleVersion').textContent = `第 ${current.revision} 版${current.document.wechat ? ' · 已送微信' : ' · 工作台草稿'}`;
    $('#archiveArticle').textContent = current.archived ? '取消归档' : '归档文章';
  }

  function applyDocument(item) {
    loading = true;
    current = item; conflict = false; dirty = false;
    const doc = item.document;
    titleInput.value = doc.title || ''; bylineInput.value = doc.byline || '';
    markdownInput.value = doc.markdown || ''; activeTheme = themes[doc.theme] ? doc.theme : 'editorial';
    $('#draftAuthor').value = doc.author || ''; $('#draftDigest').value = doc.digest || '';
    window.loadSavedCover(doc.cover, doc.cover_meta);
    imageAssets.clear(); for (const [key,value] of Object.entries(doc.images || {})) imageAssets.set(key,value);
    draftButton.disabled = false; draftButton.textContent = doc.wechat ? '再次导入一份' : '导入公众号草稿';
    draftResult.textContent = '每次点击都会新建一份微信草稿，不覆盖旧稿，也不会正式发布。';
    if (!renderEditorArticle(false)) { article.innerHTML = ''; $('#previewTitle').textContent = doc.title || '未命名文章'; $('#previewByline').textContent = doc.byline || ''; }
    saveEditorState();
    updateCoverPreview();
    loading = false;
    localStorage.setItem('tang-active-article', item.id);
    status.textContent = item.revision ? '已从网站载入' : '新文章尚未保存';
    switchView(true);
  }

  async function save(source = '网页微调') {
    clearTimeout(timer);
    if (!current || !signedIn || loading) return;
    if (saving) { await saving; return dirty ? save(source) : current; }
    if (!dirty && current.revision) return current;
    let before = generation;
    const payload = {id:current.id, revision:current.revision, archived:current.archived, source, document:documentState()};
    status.textContent = '正在保存到网站…';
    saving = (async () => {
      let result, copied = false;
      try {
        result = await request('/api/articles', payload);
      } catch (error) {
        if (error.status !== 409) throw error;
        // Preserve the latest local edits as a new article; never overwrite the other writer.
        current = {...current, id:crypto.randomUUID(), revision:0, archived:false, document:{...current.document, wechat:source === '已送微信草稿箱' ? current.document.wechat : null}};
        before = generation;
        status.textContent = '另一处已有更新，正在为你另存一份…';
        history.replaceState(null, '', location.pathname + '?article=' + encodeURIComponent(current.id));
        localStorage.setItem('tang-active-article', current.id);
        const copy = {id:current.id, revision:0, archived:false, source:'版本冲突，保留当前修改另存', document:documentState()};
        try { sessionStorage.setItem('tang-editor-recovery', JSON.stringify(copy)); } catch (_) { }
        result = await request('/api/articles', copy);
        copied = true;
      }
      current = result; dirty = generation !== before;
      window.coverSaved?.(result.document.cover);
      conflict = false;
      if (!dirty) sessionStorage.removeItem('tang-editor-recovery');
      status.textContent = dirty ? '还有新修改待保存' : copied ? '已另存一份，原文章保持不变' : `已保存 · ${new Date().toLocaleTimeString('zh-CN',{hour12:false})}`;
      if (copied) showToast('你的修改已另存为新文章，可以继续送到微信草稿箱');
      return result;
    })().catch(error => {
      window.coverSaveFailed?.(error.message);
      dirty = true; conflict = error.status === 409; showError(error); throw error;
    }).finally(() => { saving = null; });
    await saving;
    await refresh(); await historyList();
    if (dirty && !conflict) return save(source);
    return current;
  }

  window.scheduleArticleSave = () => {
    if (loading || !current) return;
    generation++; dirty = true;
    try { sessionStorage.setItem('tang-editor-recovery', JSON.stringify({id:current.id, revision:current.revision, document:documentState()})); } catch (_) { /* Server save still proceeds if browser storage is full. */ }
    status.textContent = '有修改，正在准备保存…';
    clearTimeout(timer);
    timer = setTimeout(() => save().catch(showError), 1000);
  };
  window.saveCurrentArticle = async () => {
    if (!signedIn) throw new Error('请先登录自己的文章工作台');
    if (!current) throw new Error('请先从文章库选择或新建文章');
    return save();
  };
  window.recordWechatReceipt = async receipt => {
    current.document.wechat = {...receipt, sent_at:Date.now() / 1000};
    dirty = true; generation++; await save('已送微信草稿箱');
  };

  async function openArticle(id) {
    if (dirty) await save();
    const item = await request('/api/articles?id=' + encodeURIComponent(id));
    applyDocument(item);
    history.replaceState(null, '', location.pathname + '?article=' + encodeURIComponent(id));
    await historyList();
  }

  async function create(document) {
    if (!signedIn) throw new Error('请先登录自己的文章工作台');
    if (dirty) await save();
    applyDocument({id:crypto.randomUUID(), revision:0, archived:false, document:document || {title:'未命名文章', markdown:'', theme:activeTheme, author:'唐泽龙', byline:'唐泽龙'}});
    history.replaceState(null, '', location.pathname + '?article=' + encodeURIComponent(current.id));
    dirty = true; generation++; await save('新建文章');
    return current;
  }

  window.workbench = {request, openArticle, create, get signedIn() {return signedIn;},
    async go(view) {
      if (dirty) await save();
      if (view === 'articles') {switchView(false); await refresh();}
      else {
        editor.hidden = tools.hidden = home.hidden = true;
        $('#deskPage').hidden = false; $('#saveArticle').hidden = true;
        window.dispatchEvent(new CustomEvent('workbench-view', {detail:view}));
      }
      history.replaceState(null, '', location.pathname + (view === 'today' ? '' : '?view=' + view));
      window.scrollTo(0, 0);
    }
  };

  $('#newArticle').addEventListener('click', () => create().catch(showError));
  $('#saveArticle').addEventListener('click', () => save().catch(showError));
  $('#showLibrary').addEventListener('click', () => window.workbench.go('articles').catch(showError));
  $('#showEditor').addEventListener('click', () => {if(current){switchView(true);history.replaceState(null,'',location.pathname+'?article='+encodeURIComponent(current.id));}});
  $('#refreshLibrary').addEventListener('click', () => refresh().catch(showError));
  $('#articleSearch').addEventListener('input', drawList); $('#articleFilter').addEventListener('change', drawList);
  $('#archiveArticle').addEventListener('click', async () => {try {current.archived = !current.archived; dirty = true; generation++; await save('归档状态调整'); switchView(false);} catch(error){showError(error);} });
  $('#restoreVersion').addEventListener('click', async () => {
    const revision = $('#versionSelect').value;
    if (!revision || !current || !confirm('把所选版本恢复为新版本？现有版本仍保留在历史中。')) return;
    try {
      if (dirty) await save();
      const old = await request(`/api/articles?id=${encodeURIComponent(current.id)}&revision=${revision}`);
      applyDocument({...current, document:old.document}); dirty = true; generation++;
      await save(`恢复第 ${revision} 版`);
    } catch(error) { showError(error); }
  });
  $('#copyForPolish').addEventListener('click', async () => {try {await navigator.clipboard.writeText(markdownInput.value); showToast('正文已复制；润色后贴回正文框，再更新预览');}catch(error){showToast('复制失败，请在正文框内手动复制');} });
  let recoverable = null;
  try { recoverable = JSON.parse(browserDraft || 'null'); } catch (_) { /* Keep malformed local data untouched. */ }
  $('#recoverBrowserDraft').hidden = !recoverable?.markdown;
  $('#recoverBrowserDraft').addEventListener('click', () => create(recoverable).catch(showError));
  window.addEventListener('beforeunload', event => {if(dirty || saving){event.preventDefault();event.returnValue='';} });

  async function initialize() {
    const result = await request('/api/wechat/status');
    signedIn = result.authenticated; canUseApi = true;
    $('#ownerLogin').hidden = signedIn;
    if (!signedIn) {status.textContent = '请登录自己的文章库'; return;}
    status.textContent = '文章库已连接';
    if (new URLSearchParams(location.search).get('next') === 'flow') {
      const section = ['#assessment','#result','#history','#compare','#source'].includes(location.hash) ? location.hash : '';
      location.replace('/flow/' + section);
      return;
    }
    await refresh();
    window.dispatchEvent(new CustomEvent('workbench-ready'));
    if (new URLSearchParams(location.search).get('recover') === '1' && recoverable?.markdown) {
      const oldId = localStorage.getItem('tang-active-article');
      const old = items.some(item => item.id === oldId) ? await request('/api/articles?id=' + encodeURIComponent(oldId)) : null;
      await create({...old?.document, ...recoverable, wechat:null});
      showToast('浏览器暂存的文字已另存为新文章；旧页面可以留着核对图片');
      return;
    }
    const selected = new URLSearchParams(location.search).get('article');
    let pending = null;
    try { pending = JSON.parse(sessionStorage.getItem('tang-editor-recovery') || 'null'); } catch (_) { }
    if (pending && pending.id === selected) {
      applyDocument({id:pending.id, revision:pending.revision, archived:false, document:pending.document});
      dirty = true; generation++; await save('恢复当前页面未保存的修改');
    } else if (selected) await openArticle(selected);
  }
  $('#ownerLogin').addEventListener('submit', async event => {
    event.preventDefault();
    try {await request('/api/session', {code:$('#loginCode').value.trim()});$('#loginCode').value='';await initialize();}catch(error){showError(error);}
  });
  switchView(false);
  (async () => {
    if (location.hash.startsWith('#login=')) {
      const code = decodeURIComponent(location.hash.slice(7));
      history.replaceState(null,'',location.pathname + location.search);
      await request('/api/session', {code});
    }
    await initialize();
  })().catch(showError);
})();
