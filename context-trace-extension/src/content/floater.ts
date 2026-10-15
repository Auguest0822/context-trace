// 浮窗主体：DOM 创建、事件、消息分发
// 三个 tab：捕获 / 提取 / 检索

import type { Conversation, CandidateMemory, SearchResult, SearchResponse } from '../shared/types'
import type { ExtMessage } from '../shared/messages'

const ROOT_ID = '__ct_root'
let currentConv: Conversation | null = null
let selectedMsgIds = new Set<string>()
let currentCandidates: CandidateMemory[] = []
let currentPreviewId: string | undefined // 契约两步提炼：preview 单号
let selectedCandidateIds = new Set<string>()

function ensureRoot(): HTMLElement {
  let root = document.getElementById(ROOT_ID)
  if (root) return root
  root = document.createElement('div')
  root.id = ROOT_ID
  document.documentElement.appendChild(root)
  return root
}

function renderSkeleton(root: HTMLElement) {
  root.innerHTML = `
    <button class="ct-fab" id="ct-fab">
      <span class="dot"></span>
      <span>言迹</span>
    </button>
    <div class="ct-panel" id="ct-panel" role="dialog" aria-label="言迹 ContextTrace">
      <div class="ct-panel-head">
        <div>
          <h4>言迹 ContextTrace</h4>
          <span class="src-pill" id="ct-source">未识别</span>
        </div>
        <button class="close" id="ct-close" aria-label="关闭">×</button>
      </div>
      <div class="ct-panel-tabs">
        <button class="ct-panel-tab active" data-tab="capture">捕获</button>
        <button class="ct-panel-tab" data-tab="extract">提取</button>
        <button class="ct-panel-tab" data-tab="ask">提问</button>
      </div>
      <div class="ct-panel-body" id="ct-body"></div>
    </div>
    <div class="ct-toast" id="ct-toast"></div>
  `
}

function bindGlobal(root: HTMLElement) {
  const fab = root.querySelector<HTMLButtonElement>('#ct-fab')!
  const panel = root.querySelector<HTMLDivElement>('#ct-panel')!
  const close = root.querySelector<HTMLButtonElement>('#ct-close')!
  fab.addEventListener('click', () => {
    panel.classList.toggle('open')
    if (panel.classList.contains('open') && !currentConv) {
      autoCapture()
    } else if (panel.classList.contains('open')) {
      renderCapture()
    }
  })
  close.addEventListener('click', () => panel.classList.remove('open'))

  // tab 切换
  root.querySelectorAll<HTMLButtonElement>('.ct-panel-tab').forEach((tab) => {
    tab.addEventListener('click', () => {
      root.querySelectorAll('.ct-panel-tab').forEach((t) => t.classList.remove('active'))
      tab.classList.add('active')
      const which = tab.dataset.tab
      if (which === 'capture') renderCapture()
      if (which === 'extract') renderExtract()
      if (which === 'ask') renderAsk()
    })
  })
}

// —— Toast —— //
let toastTimer: number | undefined
function toast(text: string) {
  const el = document.getElementById('ct-toast')
  if (!el) return
  el.textContent = text
  el.classList.add('show')
  window.clearTimeout(toastTimer)
  toastTimer = window.setTimeout(() => el.classList.remove('show'), 1800)
}

// —— 发送消息给 background —— //
async function send<T extends ExtMessage, R = any>(msg: T): Promise<R> {
  return chrome.runtime.sendMessage(msg)
}

// —— 抓取对话 —— //
async function autoCapture() {
  const body = document.getElementById('ct-body')!
  body.innerHTML = `<div class="ct-loading">正在抓取当前页面对话</div>`
  try {
    const resp = await send({ type: 'CT_CAPTURE_PAGE', tabId: -1, url: location.href })
    if (resp?.error) {
      body.innerHTML = `<div class="ct-empty">抓取失败：${escapeHtml(resp.error)}<br/><br/>本页面可能不被支持，可手动去 <a href="#" id="ct-open-side">打开侧边栏</a>。</div>`
      bindOpenSide(body)
      return
    }
    currentConv = resp.conversation as Conversation | null
    renderCapture()
  } catch (e) {
    body.innerHTML = `<div class="ct-empty">抓取失败：${escapeHtml(String((e as Error).message))}</div>`
  }
}

function bindOpenSide(scope: HTMLElement) {
  const a = scope.querySelector<HTMLAnchorElement>('#ct-open-side')
  if (!a) return
  a.addEventListener('click', async (e) => {
    e.preventDefault()
    try {
      const tabId = (await chrome.tabs?.getCurrent?.())?.id
      if (tabId != null) {
        await (chrome as any).sidePanel?.open?.({ tabId })
      } else {
        window.open(chrome.runtime.getURL('sidepanel.html'), '_blank')
      }
    } catch {
      window.open(chrome.runtime.getURL('sidepanel.html'), '_blank')
    }
  })
}

// —— 渲染：捕获 —— //
function renderCapture() {
  const body = document.getElementById('ct-body')!
  const srcPill = document.getElementById('ct-source')!
  if (!currentConv) {
    body.innerHTML = `<div class="ct-empty">未抓到对话。点击 <a href="#" id="ct-recap">重新抓取</a></div>`
    srcPill.textContent = '未识别'
    body.querySelector('#ct-recap')?.addEventListener('click', (e) => {
      e.preventDefault()
      autoCapture()
    })
    return
  }
  srcPill.textContent = currentConv.source
  if (selectedMsgIds.size === 0) {
    // 默认勾选前 2 条 user + 2 条 assistant
    currentConv.messages.slice(0, 4).forEach((m) => selectedMsgIds.add(m.id))
  }
  body.innerHTML = `
    <div class="ct-summary">
      <b>${escapeHtml(currentConv.title)}</b><br/>
      共 ${currentConv.messages.length} 条消息，来源 ${escapeHtml(currentConv.source)}
    </div>
    <div class="ct-msg-list" id="ct-msg-list">
      ${currentConv.messages.map((m, i) => `
        <label class="ct-msg ${selectedMsgIds.has(m.id) ? 'checked' : ''}">
          <input type="checkbox" data-id="${m.id}" ${selectedMsgIds.has(m.id) ? 'checked' : ''}/>
          <span class="role ${m.role}">${m.role === 'user' ? '我' : currentConv!.source}</span>
          <span class="text">${escapeHtml(m.text)}</span>
        </label>
      `).join('')}
    </div>
  `
  body.querySelectorAll<HTMLInputElement>('input[type=checkbox]').forEach((cb) => {
    cb.addEventListener('change', () => {
      const id = cb.dataset.id!
      if (cb.checked) selectedMsgIds.add(id)
      else selectedMsgIds.delete(id)
      cb.closest('.ct-msg')?.classList.toggle('checked', cb.checked)
    })
  })

  // 底部
  const foot = document.createElement('div')
  foot.className = 'ct-foot'
  foot.innerHTML = `
    <span class="count">已选 ${selectedMsgIds.size} 条</span>
    <button class="ct-btn" id="ct-recap">重新抓取</button>
    <button class="ct-btn primary" id="ct-to-extract">提取记忆 →</button>
  `
  body.appendChild(foot)
  foot.querySelector('#ct-recap')!.addEventListener('click', autoCapture)
  foot.querySelector('#ct-to-extract')!.addEventListener('click', () => {
    document.querySelector('.ct-panel-tab[data-tab=extract]')?.dispatchEvent(new Event('click'))
  })
}

// —— 渲染：提取 —— //
function renderExtract() {
  const body = document.getElementById('ct-body')!
  if (!currentConv) {
    body.innerHTML = `<div class="ct-empty">先到「捕获」页抓取一次对话。</div>`
    return
  }
  if (!currentCandidates.length) {
    body.innerHTML = `<div class="ct-loading">队长正在提炼记忆</div>`
    send({
      type: 'CT_EXTRACT',
      payload: {
        conversationId: currentConv.id,
        source: currentConv.source,
        selectedMessageIds: Array.from(selectedMsgIds)
      }
    }).then((resp: any) => {
      currentCandidates = resp.candidates || []
      currentPreviewId = resp.previewId // 契约两步提炼：preview 单号，提交时回传
      selectedCandidateIds = new Set(currentCandidates.map((c) => c.id))
      renderExtract()
    })
    return
  }
  body.innerHTML = `
    <div class="ct-summary">
      基于选中的 <b>${selectedMsgIds.size}</b> 条消息，队长提炼出 <b>${currentCandidates.length}</b> 条候选记忆。请勾选要保存到记忆库的条目。
    </div>
    ${currentCandidates.map((c) => `
      <div class="ct-candidate ${selectedCandidateIds.has(c.id) ? 'checked' : ''}">
        <div class="head">
          <input type="checkbox" data-id="${c.id}" ${selectedCandidateIds.has(c.id) ? 'checked' : ''}/>
          <span class="cat ${c.category}">${c.category}</span>
        </div>
        <textarea data-id="${c.id}">${escapeHtml(c.content)}</textarea>
      </div>
    `).join('')}
  `
  body.querySelectorAll<HTMLInputElement>('input[type=checkbox]').forEach((cb) => {
    cb.addEventListener('change', () => {
      const id = cb.dataset.id!
      if (cb.checked) selectedCandidateIds.add(id)
      else selectedCandidateIds.delete(id)
      cb.closest('.ct-candidate')?.classList.toggle('checked', cb.checked)
    })
  })
  body.querySelectorAll<HTMLTextAreaElement>('textarea').forEach((ta) => {
    ta.addEventListener('input', () => {
      const id = ta.dataset.id!
      const c = currentCandidates.find((x) => x.id === id)
      if (c) c.content = ta.value
    })
  })

  const foot = document.createElement('div')
  foot.className = 'ct-foot'
  foot.innerHTML = `
    <span class="count">已选 ${selectedCandidateIds.size} / ${currentCandidates.length} 条</span>
    <button class="ct-btn" id="ct-reset">重选</button>
    <button class="ct-btn primary" id="ct-save">保存到记忆库</button>
  `
  body.appendChild(foot)
  foot.querySelector('#ct-reset')!.addEventListener('click', () => {
    currentCandidates = []
    renderExtract()
  })
  foot.querySelector('#ct-save')!.addEventListener('click', async () => {
    if (!selectedCandidateIds.size) {
      toast('请先勾选要保存的记忆')
      return
    }
    const chosen = currentCandidates
      .filter((c) => selectedCandidateIds.has(c.id))
      .map((c) => ({ ...c, content: c.content })) // 已经是最新值
    await send({
      type: 'CT_SAVE',
      payload: { candidates: chosen, conversationId: currentConv!.id, previewId: currentPreviewId }
    })
    toast(`已保存 ${chosen.length} 条到记忆库`)
    currentCandidates = []
    currentPreviewId = undefined
    selectedCandidateIds = new Set()
    renderExtract()
  })
}

// —— 渲染：提问 —— //
function renderAsk() {
  const body = document.getElementById('ct-body')!
  if (body.dataset.inited === '1') return
  body.dataset.inited = '1'
  body.innerHTML = `
    <div class="ct-qa">
      <div class="qbox">
        <input id="ct-q" type="text" placeholder="把问题发给队长，TA 会用记忆库回答"/>
        <button class="ct-btn primary" id="ct-ask-btn">问</button>
      </div>
      <div id="ct-ask-out"></div>
    </div>
  `
  const input = body.querySelector<HTMLInputElement>('#ct-q')!
  const askBtn = body.querySelector<HTMLButtonElement>('#ct-ask-btn')!
  const out = body.querySelector<HTMLDivElement>('#ct-ask-out')!
  const go = async () => {
    const q = input.value.trim()
    if (!q) return
    out.innerHTML = `<div class="ct-loading">队长正在查阅记忆库</div>`
    const resp = (await send({ type: 'CT_SEARCH', payload: { question: q } })) as SearchResponse
    const ans = (await send({ type: 'CT_ASK_CAPTAIN', payload: { question: q, memories: resp } })) as { answer: string }
    renderAskResult(out, q, resp, ans.answer)
  }
  askBtn.addEventListener('click', go)
  input.addEventListener('keydown', (e) => { if (e.key === 'Enter') go() })
}

function renderAskResult(scope: HTMLElement, q: string, resp: SearchResponse, answer: string) {
  scope.innerHTML = `
    <div class="ct-summary"><b>问：</b>${escapeHtml(q)}</div>
    ${answer ? `<div class="ct-result">${escapeHtml(answer)}</div>` : ''}
    ${resp.results.length ? `<div class="ct-summary" style="margin-top:10px">记忆来源（${resp.results.length}）</div>` + resp.results.map((r) => `
      <div class="ct-result">
        <div class="title">${escapeHtml(r.title)}</div>
        ${escapeHtml(r.content)}
        <div class="meta">${escapeHtml(r.source)} · ${escapeHtml(r.conversation)} · ${escapeHtml(r.time)} · ${r.matchedBy.join(' / ')}</div>
      </div>
    `).join('') : ''}
  `
}

function escapeHtml(s: string): string {
  return s
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
}

// —— 入口：content script 启动时挂浮窗 —— //
export function mountFloater() {
  const root = ensureRoot()
  renderSkeleton(root)
  bindGlobal(root)
}

export function handleContentMessage(msg: ExtMessage) {
  if (msg.type === 'CT_PICK_CONVERSATION') {
    return { conversation: currentConv }
  }
}
