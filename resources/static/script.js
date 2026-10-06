const messages = document.querySelector('#messages');
const input = document.querySelector('#message');
const send = document.querySelector('#send');
const newChat = document.querySelector('#new-chat');
const addKnowledge = document.querySelector('#add-knowledge');
const knowledgeDialog = document.querySelector('#knowledge-dialog');
const knowledgeAddFile = document.querySelector('#knowledge-add-file');
const knowledgeClose = document.querySelector('#knowledge-close');
const knowledgeFile = document.querySelector('#knowledge-file');
const knowledgeStatus = document.querySelector('#knowledge-status');
const knowledgeFiles = document.querySelector('#knowledge-files');
const selector = document.querySelector('#agent-selector');
const selectorButton = document.querySelector('#agent-selector-button');
const menu = document.querySelector('#agent-menu');
const title = document.querySelector('#conversation-title');
const temperatureSlider = document.querySelector('#temperature-slider');
const temperatureValue = document.querySelector('#temperature-value');
const DEFAULT_TEMPERATURE = 0.2;

const agents = {
  guy: { name: 'Guy', description: 'Agente principal', avatar: '/static/img/guy.png', heading: 'Fala, Guy aqui. 👋', text: 'Manda a pergunta, projeto ou problema.<br>Vamos descobrir juntos.', css: 'guy' },
  fearth: { name: 'Fearth', description: 'Agente independente', avatar: '/static/img/fearth.png', heading: 'Fearth aqui. 🪶', text: 'Pode mandar. Vou analisar, questionar<br>e dar minha própria opinião.', css: 'fearth' },
  debate: { name: 'Debate', description: 'Guy × Fearth', avatar: null, heading: 'Guy × Fearth. ⚔️', text: 'Mande um tema. Os dois vão argumentar,<br>confrontar os pontos e chegar a uma conclusão.', css: 'debate' }
};
let currentAgent = localStorage.getItem('guy_agente') || 'guy';
if (!agents[currentAgent]) currentAgent = 'guy';

function getTemperatureValue() {
  const value = Number(temperatureSlider?.value ?? DEFAULT_TEMPERATURE);
  if (!Number.isFinite(value)) return DEFAULT_TEMPERATURE;
  return Math.min(1, Math.max(0, value));
}

function updateTemperatureLabel() {
  if (!temperatureSlider || !temperatureValue) return;
  const value = getTemperatureValue();
  temperatureValue.textContent = value.toFixed(2);
  localStorage.setItem('guy_temperature', String(value));
}

const storedTemperature = Number(localStorage.getItem('guy_temperature'));
if (temperatureSlider) {
  const initialValue = Number.isFinite(storedTemperature) ? storedTemperature : DEFAULT_TEMPERATURE;
  temperatureSlider.value = String(Math.min(1, Math.max(0, initialValue)));
  updateTemperatureLabel();
}

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

function setKnowledgeStatus(message, error = false) {
  knowledgeStatus.textContent = message;
  knowledgeStatus.classList.toggle('error', error);
}

async function loadKnowledgeFiles() {
  knowledgeFiles.replaceChildren();
  const loading = document.createElement('p');
  loading.className = 'knowledge-empty';
  loading.textContent = 'Carregando arquivos...';
  knowledgeFiles.append(loading);

  try {
    const response = await fetch('/api/conhecimento/arquivos');
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.detail || 'Não foi possível carregar os arquivos.');
    if (!Array.isArray(data.arquivos)) throw new Error('A resposta da base de conhecimento é inválida.');

    knowledgeFiles.replaceChildren();
    if (!data.arquivos.length) {
      const empty = document.createElement('p');
      empty.className = 'knowledge-empty';
      empty.textContent = 'Nenhum arquivo na base ainda.';
      knowledgeFiles.append(empty);
      return;
    }

    data.arquivos.forEach(file => {
      const row = document.createElement('div');
      row.className = 'knowledge-file-row';

      const details = document.createElement('div');
      details.className = 'knowledge-file-details';
      const name = document.createElement('strong');
      name.textContent = file.nome;
      const path = document.createElement('small');
      path.textContent = file.caminho;
      details.append(name, path);

      const remove = document.createElement('button');
      remove.className = 'knowledge-remove-button';
      remove.type = 'button';
      remove.textContent = 'Remover';
      remove.setAttribute('aria-label', `Remover ${file.nome} da base`);
      remove.addEventListener('click', () => removeKnowledgeFile(file, remove));

      row.append(details, remove);
      knowledgeFiles.append(row);
    });
  } catch (error) {
    knowledgeFiles.replaceChildren();
    setKnowledgeStatus(error.message, true);
  }
}

async function removeKnowledgeFile(file, button) {
  if (!window.confirm(`Remover "${file.nome}" da base de conhecimento?`)) return;
  button.disabled = true;

  try {
    const response = await fetch('/api/conhecimento/arquivos', {
      method: 'DELETE',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ caminho: file.caminho })
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.detail || 'Não foi possível remover o arquivo.');
    setKnowledgeStatus(`${data.arquivo} removido da base.`);
    await loadKnowledgeFiles();
  } catch (error) {
    setKnowledgeStatus(error.message, true);
    button.disabled = false;
  }
}

async function sendMessage() {
  const text = input.value.trim();
  if (!text || send.disabled) return;
  document.querySelector('#welcome')?.remove();
  addMessage(text, 'user');
  input.value = ''; autoGrow(); setLoading(true);
  try {
    const response = await fetch('/chat', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ mensagem: text, agente: currentAgent, temperatura: getTemperatureValue() }) });
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
temperatureSlider?.addEventListener('input', updateTemperatureLabel);
input.addEventListener('input', autoGrow);
input.addEventListener('keydown', event => { if (event.key === 'Enter' && !event.shiftKey) { event.preventDefault(); sendMessage(); } });
newChat?.addEventListener('click', async () => { if (send.disabled) return; newChat.disabled = true; try { const response = await fetch('/nova-conversa', { method: 'POST', headers: { 'Content-Type': 'application/json' } }); if (!response.ok) throw new Error('Não foi possível iniciar uma nova conversa.'); showWelcome(); if (title) title.textContent = 'Nova conversa'; } catch (error) { addMessage(`Erro: ${error.message}`, 'assistant'); } finally { newChat.disabled = false; input.focus(); } });
addKnowledge?.addEventListener('click', () => {
  knowledgeDialog.classList.remove('hidden');
  setKnowledgeStatus('');
  loadKnowledgeFiles();
});
knowledgeAddFile?.addEventListener('click', () => knowledgeFile?.click());
knowledgeClose?.addEventListener('click', () => knowledgeDialog.classList.add('hidden'));
knowledgeDialog?.querySelector('[data-close-knowledge]')?.addEventListener('click', () => knowledgeDialog.classList.add('hidden'));
document.addEventListener('keydown', event => {
  if (event.key === 'Escape') knowledgeDialog.classList.add('hidden');
});
knowledgeFile?.addEventListener('change', async () => {
  const file = knowledgeFile.files?.[0];
  if (!file) return;

  knowledgeAddFile.disabled = true;
  setKnowledgeStatus(`Adicionando ${file.name}...`);

  try {
    const formData = new FormData();
    formData.append('arquivo', file);
    const response = await fetch('/api/conhecimento/arquivos', { method: 'POST', body: formData });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.detail || 'Não foi possível adicionar o arquivo.');
    setKnowledgeStatus(`${data.arquivo} adicionado à base (${data.trechos_indexados} trechos).`);
    await loadKnowledgeFiles();
  } catch (error) {
    setKnowledgeStatus(error.message, true);
  } finally {
    knowledgeFile.value = '';
    knowledgeAddFile.disabled = false;
  }
});
updateAgentInterface(); input.focus();