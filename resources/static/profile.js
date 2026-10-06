const form = document.querySelector('#profile-form');
const sources = document.querySelector('#sources');
const status = document.querySelector('#save-status');
const voice = document.querySelector('#voice');
const previewVoice = document.querySelector('#preview-voice');
const voiceConsent = document.querySelector('#voice-consent');
const customVoice = document.querySelector('#custom-voice');
const recordVoice = document.querySelector('#record-voice');
const stopVoice = document.querySelector('#stop-voice');
const deleteVoice = document.querySelector('#delete-voice');
const voiceSampleStatus = document.querySelector('#voice-sample-status');
let voiceRecorder = null;
let voiceChunks = [];
let voiceStream = null;
let voiceRecordingTimer = null;
let voiceReferenceAvailable = false;

function addSource(source = {}) {
  const row = document.createElement('div');
  row.className = 'source-row';
  row.innerHTML = `<input class="source-url" type="url" placeholder="https://exemplo.com" value="${escapeAttribute(source.url || '')}"><input class="source-description" type="text" maxlength="240" placeholder="Por que esta fonte importa?" value="${escapeAttribute(source.descricao || '')}"><button class="icon-button" type="button" aria-label="Remover fonte">×</button>`;
  row.querySelector('button').addEventListener('click', () => row.remove());
  sources.append(row);
}

function escapeAttribute(value) { return String(value).replaceAll('&', '&amp;').replaceAll('"', '&quot;').replaceAll('<', '&lt;'); }
function setSelected(select, value) { if ([...select.options].some(option => option.value === value)) select.value = value; }
function setVoiceSampleStatus(message, error = false) {
  voiceSampleStatus.textContent = message;
  voiceSampleStatus.classList.toggle('error', error);
}

function loadVoices(selected) {
  if (!('speechSynthesis' in window)) return;
  const available = speechSynthesis.getVoices();
  const current = voice.value || selected || '';
  voice.replaceChildren(new Option('Voz padrão do sistema', ''));
  available.forEach(item => voice.add(new Option(`${item.name} (${item.lang})`, item.name)));
  setSelected(voice, current);
}

async function loadProfile() {
  try {
    const response = await fetch('/api/perfil');
    if (!response.ok) throw new Error('Não foi possível carregar o perfil.');
    const profile = await response.json();
    document.querySelector('#profile-name').value = profile.nome || '';
    document.querySelector('#profile-username').value = profile.username || '';
    document.querySelector('#github-url').value = profile.github_url || '';
    document.querySelector('#profile-notes').value = profile.notas || '';
    (profile.fontes || []).forEach(addSource);
    const preferences = profile.preferencias || {};
    setSelected(document.querySelector('#tone'), preferences.tom);
    setSelected(document.querySelector('#concision'), preferences.concisao);
    setSelected(document.querySelector('#language'), preferences.idioma);
    document.querySelector('#speak-responses').checked = Boolean(preferences.falar_respostas);
    customVoice.checked = Boolean(preferences.usar_voz_personalizada && voiceReferenceAvailable);
    loadVoices(preferences.voz);
  } catch (error) { status.textContent = error.message; status.classList.add('error'); }
}

async function loadVoiceReference() {
  try {
    const response = await fetch('/api/voz/referencia');
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.detail || 'Não foi possível verificar a amostra de voz.');
    voiceReferenceAvailable = Boolean(data.disponivel);
    customVoice.disabled = !data.disponivel;
    deleteVoice.hidden = !data.disponivel;
    if (data.disponivel) {
      setVoiceSampleStatus('Amostra salva somente neste computador.');
    } else {
      customVoice.checked = false;
      setVoiceSampleStatus('Grave de 5 a 30 segundos de fala clara para criar sua voz.');
    }
  } catch (error) {
    voiceReferenceAvailable = false;
    customVoice.disabled = true;
    setVoiceSampleStatus(error.message, true);
  }
}

async function startVoiceRecording() {
  if (!voiceConsent.checked) {
    setVoiceSampleStatus('Confirme que a gravação é sua ou que você tem autorização.', true);
    return;
  }
  if (!window.MediaRecorder || !navigator.mediaDevices?.getUserMedia) {
    setVoiceSampleStatus('Este navegador não permite gravar uma amostra de voz.', true);
    return;
  }
  try {
    voiceStream = await navigator.mediaDevices.getUserMedia({ audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true } });
    const mimeType = MediaRecorder.isTypeSupported('audio/webm;codecs=opus') ? 'audio/webm;codecs=opus' : '';
    voiceChunks = [];
    voiceRecorder = new MediaRecorder(voiceStream, mimeType ? { mimeType } : undefined);
    voiceRecorder.ondataavailable = event => { if (event.data.size) voiceChunks.push(event.data); };
    voiceRecorder.onstop = saveVoiceRecording;
    voiceRecorder.start();
    recordVoice.hidden = true;
    stopVoice.hidden = false;
    setVoiceSampleStatus('Gravando… fale por pelo menos 5 segundos; a gravação para em 30 segundos.');
    voiceRecordingTimer = window.setTimeout(() => voiceRecorder?.stop(), 30_000);
  } catch (error) {
    setVoiceSampleStatus(error.name === 'NotAllowedError'
      ? 'Permita o microfone nas configurações do Windows e do Edge.'
      : 'Não foi possível acessar o microfone.', true);
  }
}

async function saveVoiceRecording() {
  window.clearTimeout(voiceRecordingTimer);
  voiceStream?.getTracks().forEach(track => track.stop());
  voiceStream = null;
  stopVoice.hidden = true;
  recordVoice.hidden = false;
  try {
    setVoiceSampleStatus('Preparando e salvando a amostra localmente…');
    const wav = await window.audioToWav(new Blob(voiceChunks, { type: voiceRecorder?.mimeType || 'audio/webm' }));
    const formData = new FormData();
    formData.append('audio', wav, 'minha-voz.wav');
    const response = await fetch('/api/voz/referencia', { method: 'POST', body: formData });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.detail || 'Não foi possível salvar a amostra.');
    voiceReferenceAvailable = true;
    customVoice.disabled = false;
    deleteVoice.hidden = false;
    setVoiceSampleStatus('Amostra salva neste computador. Você já pode ativar e testar a voz clonada.');
  } catch (error) {
    setVoiceSampleStatus(error.message, true);
  } finally {
    voiceRecorder = null;
    voiceChunks = [];
  }
}

async function removeVoiceReference() {
  if (!window.confirm('Apagar a amostra de voz salva neste computador?')) return;
  try {
    const response = await fetch('/api/voz/referencia', { method: 'DELETE' });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.detail || 'Não foi possível apagar a amostra.');
    voiceReferenceAvailable = false;
    customVoice.checked = false;
    customVoice.disabled = true;
    deleteVoice.hidden = true;
    setVoiceSampleStatus('Amostra apagada deste computador.');
  } catch (error) {
    setVoiceSampleStatus(error.message, true);
  }
}

async function previewCustomVoice() {
  status.classList.remove('error');
  status.textContent = 'Preparando a voz clonada; na primeira vez, o G.U.Y. instala o componente e baixa o modelo. Isso pode levar alguns minutos…';
  const response = await fetch('/api/voz/sintetizar', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      texto: 'Oi! Eu sou o Guy. Que bom conversar com você.',
      idioma: document.querySelector('#language').value
    })
  });
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    throw new Error(data.detail || 'Não foi possível gerar a prévia da voz.');
  }
  const audioUrl = URL.createObjectURL(await response.blob());
  const audio = new Audio(audioUrl);
  audio.onended = () => URL.revokeObjectURL(audioUrl);
  audio.onerror = () => URL.revokeObjectURL(audioUrl);
  try {
    await audio.play();
    status.textContent = 'Prévia da voz personalizada em reprodução.';
  } catch (error) {
    URL.revokeObjectURL(audioUrl);
    throw error;
  }
}

document.querySelector('#add-source').addEventListener('click', () => addSource());
if ('speechSynthesis' in window) speechSynthesis.onvoiceschanged = () => loadVoices();
recordVoice.addEventListener('click', startVoiceRecording);
stopVoice.addEventListener('click', () => voiceRecorder?.stop());
deleteVoice.addEventListener('click', removeVoiceReference);
voiceConsent.addEventListener('change', () => { recordVoice.disabled = !voiceConsent.checked; });
previewVoice.addEventListener('click', () => {
  status.classList.remove('error');
  if (customVoice.checked) {
    previewCustomVoice().catch(error => {
      status.textContent = error.message;
      status.classList.add('error');
    });
    return;
  }
  if (!('speechSynthesis' in window)) {
    status.textContent = 'A fala não está disponível neste navegador.';
    status.classList.add('error');
    return;
  }
  speechSynthesis.cancel();
  const utterance = new SpeechSynthesisUtterance(
    'Oi! Eu sou o Guy. Que bom conversar com você.'
  );
  utterance.lang = document.querySelector('#language').value || 'pt-BR';
  const selected = speechSynthesis.getVoices().find(item => item.name === voice.value);
  if (selected) utterance.voice = selected;
  speechSynthesis.speak(utterance);
});
form.addEventListener('submit', async event => {
  event.preventDefault();
  const fontes = [...sources.querySelectorAll('.source-row')].map(row => ({ url: row.querySelector('.source-url').value.trim(), descricao: row.querySelector('.source-description').value.trim() })).filter(item => item.url);
  const payload = { nome: document.querySelector('#profile-name').value.trim(), username: document.querySelector('#profile-username').value.trim(), github_url: document.querySelector('#github-url').value.trim(), notas: document.querySelector('#profile-notes').value.trim(), fontes, preferencias: { tom: document.querySelector('#tone').value, concisao: document.querySelector('#concision').value, idioma: document.querySelector('#language').value, voz: voice.value, usar_voz_personalizada: customVoice.checked, falar_respostas: document.querySelector('#speak-responses').checked } };
  status.classList.remove('error'); status.textContent = 'Salvando…';
  try {
    const response = await fetch('/api/perfil', { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.detail || 'Não foi possível salvar.');
    status.textContent = 'Preferências salvas.';
  } catch (error) { status.textContent = error.message; status.classList.add('error'); }
});
recordVoice.disabled = !voiceConsent.checked;
loadVoices();
(async () => {
  await loadVoiceReference();
  await loadProfile();
  if (!voiceReferenceAvailable) customVoice.checked = false;
})();
