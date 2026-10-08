const form = document.querySelector('#debate-config-form');
const configPanel = document.querySelector('#debate-config-panel');
const sessionPanel = document.querySelector('#debate-session-panel');
const errorPanel = document.querySelector('#debate-form-error');
const startButton = document.querySelector('#debate-start');
const researchToggle = document.querySelector('#debate-research');
const researchNote = document.querySelector('#debate-research-note');
const historyList = document.querySelector('#debate-history-list');
const transcript = document.querySelector('#debate-transcript');
const summaryText = document.querySelector('#debate-summary-text');
const summaryError = document.querySelector('#debate-summary-error');
const participantList = document.querySelector('#debate-participants');
const firstSpeaker = document.querySelector('#debate-first');
const addSideButton = document.querySelector('#debate-add-side');
let activeSession = null;
let displayedSessionId = null;
let pollTimer = null;

function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = String(text);
  return node;
}

async function requestJson(url, options = {}) {
  const response = await fetch(url, options);
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.detail || 'A solicitação do debate falhou.');
  return data;
}

function formConfiguration() {
  const participants = [...participantList.querySelectorAll('.debate-participant')]
    .map((row, index) => ({
      id: `lado_${index + 1}`,
      nome: row.querySelector('[data-field="nome"]').value.trim(),
      posicao: row.querySelector('[data-field="posicao"]').value.trim(),
      modelo: row.querySelector('[data-field="modelo"]').value
    }));
  return {
    tema: document.querySelector('#debate-theme').value.trim(),
    rodadas: Number(document.querySelector('#debate-rounds').value),
    participante_inicial: firstSpeaker.value,
    participantes,
    regras: document.querySelector('#debate-rules').value.trim(),
    permite_mudar_posicao: document.querySelector('#debate-change-position').checked,
    limite_palavras_por_fala: Number(document.querySelector('#debate-words').value),
    pesquisa: researchToggle.checked
  };
}

function rebuildFirstSpeakerOptions(selectedId) {
  const rows = [...participantList.querySelectorAll('.debate-participant')];
  firstSpeaker.replaceChildren();
  rows.forEach((row, index) => {
    const id = `lado_${index + 1}`;
    const label = row.querySelector('[data-field="nome"]').value.trim() || `Lado ${index + 1}`;
    const option = el('option', '', label);
    option.value = id;
    firstSpeaker.append(option);
  });
  if (rows.some((_row, index) => `lado_${index + 1}` === selectedId)) {
    firstSpeaker.value = selectedId;
  }
}

function addParticipant(values = {}) {
  const row = el('fieldset', 'debate-participant');
  const index = participantList.querySelectorAll('.debate-participant').length + 1;
  const legend = el('legend', '', `Lado ${index}`);
  const nameLabel = el('label', '', 'Nome do lado');
  const name = el('input');
  name.required = true;
  name.maxLength = 80;
  name.placeholder = `Ex.: Lado ${index}`;
  name.value = values.nome || '';
  name.dataset.field = 'nome';
  nameLabel.append(name);

  const positionLabel = el('label', '', 'Posição defendida');
  const position = el('input');
  position.required = true;
  position.maxLength = 500;
  position.placeholder = 'Defina a posição deste lado';
  position.value = values.posicao || '';
  position.dataset.field = 'posicao';
  positionLabel.append(position);

  const modelLabel = el('label', '', 'Modelo que representa este lado');
  const model = el('select');
  model.dataset.field = 'modelo';
  for (const [value, label] of [['guy', 'Guy'], ['fearth', 'Fearth']]) {
    const option = el('option', '', label);
    option.value = value;
    model.append(option);
  }
  model.value = values.modelo || (index % 2 ? 'guy' : 'fearth');
  modelLabel.append(model);

  const remove = el('button', 'button-secondary', 'Remover lado');
  remove.type = 'button';
  remove.addEventListener('click', () => {
    const rows = [...participantList.querySelectorAll('.debate-participant')];
    if (rows.length <= 2) return;
    const selectedRow = rows[firstSpeaker.selectedIndex];
    row.remove();
    [...participantList.querySelectorAll('.debate-participant')].forEach((item, itemIndex) => {
      item.querySelector('legend').textContent = `Lado ${itemIndex + 1}`;
    });
    rebuildFirstSpeakerOptions();
    const remainingRows = [...participantList.querySelectorAll('.debate-participant')];
    const selectedIndex = remainingRows.indexOf(selectedRow);
    if (selectedIndex >= 0) firstSpeaker.selectedIndex = selectedIndex;
    updateStartEnabled();
  });

  name.addEventListener('input', () => {
    const oldFirst = firstSpeaker.value;
    legend.textContent = name.value.trim() || `Lado ${index}`;
    rebuildFirstSpeakerOptions(oldFirst);
  });
  row.append(legend, nameLabel, positionLabel, modelLabel, remove);
  participantList.append(row);
  rebuildFirstSpeakerOptions();
}

function updateStartEnabled() {
  startButton.disabled = !form.checkValidity();
}

function makeButton(label, action, options = {}) {
  const button = el('button', options.primary ? 'button-primary' : 'button-secondary', label);
  button.type = 'button';
  button.disabled = Boolean(options.disabled);
  if (options.title) button.title = options.title;
  if (options.confirm) {
    button.addEventListener('click', () => {
      if (window.confirm(options.confirm)) void command(action);
    });
  } else {
    button.addEventListener('click', () => void command(action));
  }
  return button;
}

async function command(action) {
  if (!displayedSessionId) return;
  setError('');
  try {
    await requestJson(`/api/debate/${encodeURIComponent(displayedSessionId)}/${action}`, {
      method: 'POST'
    });
    await refresh();
  } catch (error) {
    setError(error.message);
  }
}

function setError(message) {
  errorPanel.textContent = message;
  errorPanel.hidden = !message;
}

function renderHistory(sessions) {
  historyList.replaceChildren();
  const history = sessions.filter(item => ['ENCERRADA', 'CANCELADA'].includes(item.status));
  if (!history.length) {
    historyList.append(el('p', 'settings-help', 'Ainda não há debates concluídos.'));
    return;
  }
  history.forEach(item => {
    const button = el('button', 'debate-history-item');
    button.type = 'button';
    button.append(
      el('strong', '', item.tema),
      el('small', '', `${item.status} · ${item.rodadas_realizadas}/${item.rodadas_total} rodadas`)
    );
    button.addEventListener('click', () => {
      displayedSessionId = item.id;
      void loadSession(item.id);
    });
    historyList.append(button);
  });
}

function renderTranscript(session) {
  const wasNearBottom = transcript.scrollHeight - transcript.scrollTop - transcript.clientHeight < 80;
  const participants = session.participantes || [
    { id: 'guy', nome: 'Guy', modelo: 'guy' },
    { id: 'fearth', nome: 'Fearth', modelo: 'fearth' }
  ];
  const byId = new Map(participants.map(item => [item.id, item]));
  transcript.replaceChildren();
  let currentRound = null;
  for (const turn of session.turnos) {
    if (currentRound !== turn.rodada) {
      currentRound = turn.rodada;
      transcript.append(el('h2', 'debate-round-heading', `RODADA ${turn.rodada}`));
    }
    const speaker = byId.get(turn.falante) || { nome: turn.falante, modelo: '' };
    const card = el('article', `debate-turn ${speaker.modelo}`);
    const heading = el('header', 'debate-turn-heading');
    heading.append(
      el('span', 'debate-turn-icon', speaker.nome.slice(0, 1).toUpperCase()),
      el('strong', '', speaker.nome)
    );
    card.append(heading, el('p', 'debate-turn-text', turn.texto));
    if (turn.fontes?.length) {
      const sources = el('details', 'debate-sources');
      sources.append(el('summary', '', 'Fontes consultadas / pesquisa'));
      turn.fontes.forEach(source => {
        const sourceRow = el('p', 'debate-source');
        if (source.erro) {
          sourceRow.textContent = source.erro;
        } else {
          const title = source.title || source.titulo || 'Resultado sem título';
          const url = source.href || source.url || '';
          const accessed = source.acessado_em || '';
          sourceRow.textContent = `${title}${url ? ` — ${url}` : ''}${accessed ? ` · acesso: ${accessed}` : ''}`;
        }
        sources.append(sourceRow);
      });
      card.append(sources);
    }
    transcript.append(card);
  }
  if (wasNearBottom) transcript.scrollTop = transcript.scrollHeight;
}

function renderControls(session, readOnly) {
  const controls = document.querySelector('#debate-controls');
  controls.replaceChildren();
  if (readOnly) {
    controls.append(el('p', 'settings-help', 'Visualização somente leitura.'));
    return;
  }
  const busy = ['EM_ANDAMENTO', 'GERANDO_RESUMO'].includes(session.status);
  if (session.status === 'EM_ANDAMENTO') {
    controls.append(makeButton('Pausar após esta fala', 'pausar'));
  }
  if (session.status === 'PAUSADA') {
    controls.append(makeButton('Continuar', 'continuar', { primary: true }));
  }
  if (session.status === 'ERRO') {
    controls.append(makeButton('Tentar esta fala novamente', 'tentar-novamente', { primary: true }));
  }
  if (session.status === 'ENCERRADA' && session.resumo_status === 'ERRO') {
    controls.append(makeButton('Tentar resumo novamente', 'tentar-resumo', { primary: true }));
  }
  if (['EM_ANDAMENTO', 'PAUSADA', 'ERRO'].includes(session.status)) {
    controls.append(makeButton(
      'Interromper geração',
      'interromper',
      { disabled: true, title: 'Indisponível: a chamada síncrona do Ollama não pode ser abortada.' }
    ));
    controls.append(makeButton('Encerrar e resumir', 'encerrar'));
    controls.append(makeButton(
      'Cancelar sessão',
      'cancelar',
      { confirm: 'Cancelar este debate sem gerar resumo? A sessão será mantida no histórico.' }
    ));
  }
  if (busy) controls.setAttribute('aria-busy', 'true');
  else controls.removeAttribute('aria-busy');
}

function renderSession(session, readOnly = false) {
  activeSession = readOnly ? activeSession : session;
  displayedSessionId = session.id;
  configPanel.hidden = !readOnly && !['ENCERRADA', 'CANCELADA'].includes(session.status);
  if (readOnly) configPanel.hidden = true;
  sessionPanel.hidden = false;

  document.querySelector('#debate-session-theme').textContent = session.tema;
  document.querySelector('#debate-round-label').textContent =
    `Rodada ${session.rodada_atual} / ${session.rodadas_total} · ${session.rodadas_realizadas} realizadas`;
  const participants = session.participantes || [
    { id: 'guy', nome: 'Guy', posicao: session.posicao_guy },
    { id: 'fearth', nome: 'Fearth', posicao: session.posicao_fearth }
  ];
  const sides = document.querySelector('#debate-sides');
  sides.replaceChildren();
  participants.forEach((participant, index) => {
    if (index) sides.append(el('span', 'debate-side-separator', 'vs.'));
    const side = el('div', 'debate-side');
    side.append(el('strong', '', participant.nome), el('p', '', participant.posicao));
    sides.append(side);
  });
  document.querySelector('#debate-session-status').textContent =
    session.pausar_depois ? 'PAUSANDO após a fala atual' : session.status;
  document.querySelector('#debate-current-speaker').textContent =
    session.falante_atual && !readOnly
      ? `Falando agora: ${(participants.find(item => item.id === session.falante_atual)?.nome || session.falante_atual)}`
      : session.fala_em_andamento && !readOnly
        ? `Falando agora: ${participants.find(item => item.id === session.falante_atual)?.nome || '…'}`
        : '';
  renderTranscript(session);
  renderControls(session, readOnly);

  const summaryPanel = document.querySelector('#debate-summary-panel');
  const summaryFailed = session.status === 'ENCERRADA' && session.resumo_status === 'ERRO';
  summaryPanel.hidden = !session.resumo && !summaryFailed;
  summaryText.textContent = session.resumo || '';
  summaryError.textContent = summaryFailed
    ? `${session.erro || 'Resumo indisponível.'} Você pode tentar novamente.`
    : '';
}

async function loadSession(id) {
  try {
    const session = await requestJson(`/api/debate/${encodeURIComponent(id)}`);
    renderSession(session, ['ENCERRADA', 'CANCELADA'].includes(session.status));
  } catch (error) {
    setError(error.message);
  }
}

async function refresh() {
  try {
    const state = await requestJson('/api/debate');
    renderHistory(state.sessoes || []);
    if (state.pesquisa_disponivel) {
      researchToggle.disabled = false;
      researchNote.textContent = 'Pesquisa web disponível; até uma consulta por fala.';
      document.querySelector('#debate-search-capability').textContent = 'Pesquisa web disponível.';
    } else {
      researchToggle.disabled = true;
      researchToggle.checked = false;
      researchNote.textContent = 'Pesquisa indisponível nesta instalação.';
      document.querySelector('#debate-search-capability').textContent = 'Pesquisa indisponível.';
    }
    if (state.sessao_ativa) {
      renderSession(state.sessao_ativa);
    } else if (!activeSession || ['ENCERRADA', 'CANCELADA'].includes(activeSession.status)) {
      activeSession = null;
      displayedSessionId = null;
      sessionPanel.hidden = true;
      configPanel.hidden = false;
    }
    if (pollTimer) window.clearTimeout(pollTimer);
    if (state.sessao_ativa && ['EM_ANDAMENTO', 'GERANDO_RESUMO'].includes(state.sessao_ativa.status)) {
      pollTimer = window.setTimeout(refresh, 1200);
    }
  } catch (error) {
    setError(error.message);
  }
}

form.addEventListener('input', updateStartEnabled);
form.addEventListener('change', updateStartEnabled);
addSideButton.addEventListener('click', () => {
  addParticipant();
  updateStartEnabled();
});
form.addEventListener('submit', async event => {
  event.preventDefault();
  if (!form.reportValidity()) return;
  startButton.disabled = true;
  setError('');
  try {
    const key = window.crypto?.randomUUID
      ? window.crypto.randomUUID()
      : `${Date.now()}-${Math.random().toString(16).slice(2)}`;
    const session = await requestJson('/api/debate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'Idempotency-Key': key },
      body: JSON.stringify(formConfiguration())
    });
    activeSession = session;
    renderSession(session);
    await refresh();
  } catch (error) {
    setError(error.message);
  } finally {
    addParticipant({ nome: 'Guy', modelo: 'guy' });
    addParticipant({ nome: 'Fearth', modelo: 'fearth' });
    updateStartEnabled();
  }
});

updateStartEnabled();
void refresh();
