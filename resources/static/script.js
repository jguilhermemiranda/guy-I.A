const messages = document.querySelector('#messages');
const input = document.querySelector('#message');
const send = document.querySelector('#send');
const newChat = document.querySelector('#new-chat');
const addKnowledge = document.querySelector('#add-knowledge');
const knowledgeFile = document.querySelector('#knowledge-file');
const knowledgeStatus = document.querySelector('#knowledge-status');
const selector = document.querySelector('#agent-selector');
const selectorButton = document.querySelector('#agent-selector-button');
const menu = document.querySelector('#agent-menu');
const title = document.querySelector('#conversation-title');

const agents = {
  guy: { name: 'Guy', description: 'Agente principal', avatar: '/static/img/guy.png', heading: 'Fala, Guy aqui. 👋', text: 'Manda a pergunta, projeto ou problema.<br>Vamos descobrir juntos.', css: 'guy' },
  fearth: { name: 'Fearth', description: 'Agente independente', avatar: '/static/img/fearth.png', heading: 'Fearth aqui. 🪶', text: 'Pode mandar. Vou analisar, questionar<br>e dar minha própria opinião.', css: 'fearth' },
  debate: { name: 'Debate', description: 'Guy × Fearth', avatar: null, heading: 'Guy × Fearth. ⚔️', text: 'Mande um tema. Os dois vão argumentar,<br>confrontar os pontos e chegar a uma conclusão.', css: 'debate' }
};
let currentAgent = localStorage.getItem('guy_agente') || 'guy';
if (!agents[currentAgent]) currentAgent = 'guy';

function scrollToBottom() { messages.scrollTop = messages.scrollHeight; }
function escapeHtml(value) { const el = document.createElement('div'); el.textContent = String(value || ''); return el.innerHTML; }
function toText(value) { return escapeHtml(value).replace(/\n/g, '<br>'); }

function updateAgentInterface() {
  const agent = agents[currentAgent];
  document.querySelector('#agent-name').textContent = agent.name;
  document.querySelector('#agent-description').textContent = agent.description;
  selectorButton.className = `agent-selector-button ${agent.css}`;
  const avatar = document.querySelector('#agent-avatar');
  if (agent.avatar) { avatar.src = agent.avatar; avatar.alt = agent.name; avatar.hidden = false; }
  else { avatar.hidden = true; }
  document.querySelectorAll('.agent-option').forEach(option => option.classList.toggle('active', option.dataset.agent === currentAgent));
}

function showWelcome() {
  const agent = agents[currentAgent];
  const icon = agent.avatar ? `<img src="${agent.avatar}" alt="${agent.name}">` : '<span class="mode-icon large">⚔️</span>';
  messages.innerHTML = `<div class="welcome" id="welcome"><div class="welcome-icon ${agent.css}">${icon}</div><h1>${agent.heading}</h1><p>${agent.text}</p></div>`;
}

function addMessage(text, type, agent = currentAgent) {
  const data = agents[agent] || agents.guy;
  const avatar = type === 'user' ? '<span>👤</span>' : data.avatar ? `<img src="${data.avatar}" alt="${data.name}">` : '<span>⚔️</span>';
  messages.insertAdjacentHTML('beforeend', `<article class="message ${type} ${data.css}"><div class="message-avatar">${avatar}</div><div class="message-body">${type === 'assistant' ? `<span class="message-name">${data.name}</span>` : ''}<div class="message-content">${toText(text)}</div></div></article>`);
  scrollToBottom();
}

function addDebate(data) {
  const guy = data.guy || 'Guy não conseguiu responder.';
  const fearth = data.fearth || 'Fearth não conseguiu responder.';
  const conclusion = data.conclusao || 'Não foi possível gerar a conclusão.';
  messages.insertAdjacentHTML('beforeend', `
    <section class="debate-result">
      <div class="debate-heading"><span>⚔️</span> Debate</div>
      <article class="debate-card guy"><div class="message-avatar"><img src="/static/img/guy.png" alt="Guy"></div><div><span class="message-name">Guy</span><p>${toText(guy)}</p></div></article>
      <article class="debate-card fearth"><div class="message-avatar"><img src="/static/img/fearth.png" alt="Fearth"></div><div><span class="message-name">Fearth · contraponto</span><p>${toText(fearth)}</p></div></article>
      <article class="conclusion"><span>⚔️ CONCLUSÃO DO DEBATE</span><p>${toText(conclusion)}</p></article>
    </section>`);
  scrollToBottom();
}

function setLoading(loading) { send.disabled = loading; input.disabled = loading; selectorButton.disabled = loading; }
function autoGrow() { input.style.height = 'auto'; input.style.height = `${Math.min(input.scrollHeight, 170)}px`; }

async function sendMessage() {
  const text = input.value.trim();
  if (!text || send.disabled) return;
  document.querySelector('#welcome')?.remove();
  addMessage(text, 'user');
  input.value = ''; autoGrow(); setLoading(true);
  try {
    const response = await fetch('/chat', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ mensagem: text, agente: currentAgent }) });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.detail || data.erro || 'Não foi possível processar a mensagem.');
    if (data.modo === 'debate') addDebate(data);
    else addMessage(data.resposta, 'assistant', data.agente || currentAgent);
  } catch (error) { addMessage(`Erro: ${error.message}`, 'assistant', currentAgent); }
  finally { setLoading(false); input.focus(); }
}

selectorButton.addEventListener('click', event => { event.stopPropagation(); const open = menu.classList.toggle('open'); selectorButton.setAttribute('aria-expanded', String(open)); });
document.querySelectorAll('.agent-option').forEach(option => option.addEventListener('click', () => { if (send.disabled) return; currentAgent = option.dataset.agent; localStorage.setItem('guy_agente', currentAgent); menu.classList.remove('open'); selectorButton.setAttribute('aria-expanded', 'false'); updateAgentInterface(); showWelcome(); input.value = ''; autoGrow(); input.focus(); }));
document.addEventListener('click', event => { if (!selector.contains(event.target)) { menu.classList.remove('open'); selectorButton.setAttribute('aria-expanded', 'false'); } });
send.addEventListener('click', sendMessage);
input.addEventListener('input', autoGrow);
input.addEventListener('keydown', event => { if (event.key === 'Enter' && !event.shiftKey) { event.preventDefault(); sendMessage(); } });
newChat?.addEventListener('click', async () => { if (send.disabled) return; newChat.disabled = true; try { const response = await fetch('/nova-conversa', { method: 'POST', headers: { 'Content-Type': 'application/json' } }); if (!response.ok) throw new Error('Não foi possível iniciar uma nova conversa.'); showWelcome(); if (title) title.textContent = 'Nova conversa'; } catch (error) { addMessage(`Erro: ${error.message}`, 'assistant'); } finally { newChat.disabled = false; input.focus(); } });
addKnowledge?.addEventListener('click', () => knowledgeFile?.click());
knowledgeFile?.addEventListener('change', async () => {
  const file = knowledgeFile.files?.[0];
  if (!file) return;

  addKnowledge.disabled = true;
  knowledgeStatus.textContent = `Adicionando ${file.name}...`;
  knowledgeStatus.classList.remove('error');

  try {
    const formData = new FormData();
    formData.append('arquivo', file);
    const response = await fetch('/api/conhecimento/arquivos', { method: 'POST', body: formData });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.detail || 'Não foi possível adicionar o arquivo.');
    knowledgeStatus.textContent = `${data.arquivo} adicionado à base (${data.trechos_indexados} trechos).`;
  } catch (error) {
    knowledgeStatus.textContent = error.message;
    knowledgeStatus.classList.add('error');
  } finally {
    knowledgeFile.value = '';
    addKnowledge.disabled = false;
  }
});
updateAgentInterface(); input.focus();