"""Transcrição local de áudio para o G.U.Y., sem serviço de reconhecimento online."""

from __future__ import annotations

import io
import importlib
import subprocess
import sys
import threading
import wave
from pathlib import Path


MODELO_DIR = Path(__file__).resolve().parent.parent / "models" / "faster-whisper-base"
REFERENCIA_VOZ = Path(__file__).resolve().parent.parent / "data" / "voz" / "referencia.wav"
MODELO_VOZ_PERSONALIZADA = "tts_models/multilingual/multi-dataset/xtts_v2"
PACOTE_VOZ_PERSONALIZADA = "coqui-tts==0.27.5"
LIMITE_AMOSTRA_BYTES = 5 * 1024 * 1024
_modelo = None
_modelo_tts = None
_trava_modelo = threading.Lock()
_trava_carregamento_tts = threading.Lock()
_trava_tts = threading.Lock()


class VozIndisponivel(RuntimeError):
    pass


def referencia_voz_disponivel():
    return REFERENCIA_VOZ.is_file()


def salvar_referencia_voz(audio):
    if not audio:
        raise ValueError("A gravação de voz está vazia.")
    if len(audio) > LIMITE_AMOSTRA_BYTES:
        raise ValueError("A gravação excede o limite de 5 MB.")
    try:
        leitor = wave.open(io.BytesIO(audio), "rb")
    except (wave.Error, EOFError) as erro:
        raise ValueError("A gravação precisa estar no formato WAV PCM.") from erro

    with leitor:
        if leitor.getnchannels() != 1 or leitor.getsampwidth() != 2:
            raise ValueError("A gravação precisa ser mono em PCM de 16 bits.")
        taxa = leitor.getframerate()
        if taxa < 8_000 or taxa > 48_000:
            raise ValueError("A taxa de áudio precisa estar entre 8 kHz e 48 kHz.")
        duracao = leitor.getnframes() / taxa
        if duracao < 5 or duracao > 30:
            raise ValueError("Grave entre 5 e 30 segundos de voz.")

    REFERENCIA_VOZ.parent.mkdir(parents=True, exist_ok=True)
    temporario = REFERENCIA_VOZ.with_suffix(".tmp")
    temporario.write_bytes(audio)
    temporario.replace(REFERENCIA_VOZ)


def remover_referencia_voz():
    REFERENCIA_VOZ.unlink(missing_ok=True)


def _obter_modelo():
    global _modelo
    try:
        from faster_whisper import WhisperModel
    except ImportError as erro:
        raise VozIndisponivel(
            "O componente de voz não está instalado. Execute scripts\\iniciar.bat para instalar as dependências."
        ) from erro
    with _trava_modelo:
        if _modelo is None:
            if not (MODELO_DIR / "model.bin").is_file():
                try:
                    from huggingface_hub import snapshot_download
                except ImportError as erro:
                    raise VozIndisponivel(
                        "O componente para baixar o modelo de voz não está "
                        "instalado. Atualize as dependências do G.U.Y."
                    ) from erro
                try:
                    snapshot_download(
                        repo_id="Systran/faster-whisper-base",
                        local_dir=str(MODELO_DIR),
                    )
                except Exception as erro:
                    raise VozIndisponivel(
                        "Não foi possível baixar o modelo de transcrição. "
                        "Confira a conexão com a internet e tente novamente."
                    ) from erro
            _modelo = WhisperModel(str(MODELO_DIR), device="cpu", compute_type="int8")
    return _modelo


def _obter_modelo_tts():
    global _modelo_tts
    with _trava_carregamento_tts:
        if _modelo_tts is not None:
            return _modelo_tts
        try:
            modulo_tts = importlib.import_module("TTS.api")
        except ModuleNotFoundError as erro:
            if erro.name != "TTS":
                raise VozIndisponivel(
                    "O componente de voz está incompleto. Verifique a instalação "
                    "do Python e tente novamente."
                ) from erro
            try:
                subprocess.run(
                    [
                        sys.executable,
                        "-m",
                        "pip",
                        "install",
                        "--disable-pip-version-check",
                        PACOTE_VOZ_PERSONALIZADA,
                    ],
                    check=True,
                    capture_output=True,
                    text=True,
                    timeout=1_800,
                )
            except subprocess.TimeoutExpired as erro:
                raise VozIndisponivel(
                    "A instalação da voz demorou mais de 30 minutos. Confira a "
                    "conexão e tente novamente."
                ) from erro
            except subprocess.CalledProcessError as erro:
                detalhe = (erro.stderr or erro.stdout or "").strip()[-1_000:]
                raise VozIndisponivel(
                    "Não foi possível instalar automaticamente o componente de "
                    f"voz. {detalhe or 'Confira a conexão e tente novamente.'}"
                ) from erro
            except OSError as erro:
                raise VozIndisponivel(
                    "Não foi possível iniciar a instalação automática da voz."
                ) from erro
            importlib.invalidate_caches()
            try:
                modulo_tts = importlib.import_module("TTS.api")
            except ImportError as erro:
                raise VozIndisponivel(
                    "O componente de voz foi instalado, mas não pôde ser carregado. "
                    "Reinicie o G.U.Y. e tente novamente."
                ) from erro
        try:
            _modelo_tts = modulo_tts.TTS(
                model_name=MODELO_VOZ_PERSONALIZADA,
                progress_bar=False,
                gpu=False,
            )
        except Exception as erro:
            raise VozIndisponivel(
                "Não foi possível preparar o modelo local de voz. "
                "Confira a conexão para baixar o modelo e tente novamente."
            ) from erro
    return _modelo_tts


def transcrever_wav(audio):
    """Recebe um WAV PCM mono e devolve texto pelo Whisper executado localmente."""
    if not audio:
        raise ValueError("O áudio está vazio.")
    try:
        leitor = wave.open(io.BytesIO(audio), "rb")
    except wave.Error as erro:
        raise ValueError("O áudio precisa estar no formato WAV PCM.") from erro

    with leitor:
        if leitor.getnchannels() != 1 or leitor.getsampwidth() != 2:
            raise ValueError("O áudio precisa ser mono em PCM de 16 bits.")
        taxa = leitor.getframerate()
        if taxa < 8_000 or taxa > 48_000:
            raise ValueError("A taxa de áudio não é compatível com a transcrição local.")
        import numpy
        amostras = numpy.frombuffer(
            leitor.readframes(leitor.getnframes()), dtype=numpy.int16
        ).astype(numpy.float32) / 32768.0
    segmentos, _ = _obter_modelo().transcribe(
        amostras,
        language="pt",
        beam_size=5,
        vad_filter=True,
        condition_on_previous_text=False,
    )
    return " ".join(segmento.text.strip() for segmento in segmentos).strip()


def sintetizar_wav(texto, idioma="pt"):
    if not referencia_voz_disponivel():
        raise VozIndisponivel(
            "Grave e salve uma amostra da sua voz em Perfil e preferências antes de ativar a clonagem."
        )
    texto = str(texto or "").strip()
    if not texto:
        raise ValueError("O texto para falar está vazio.")
    if len(texto) > 4_000:
        raise ValueError("O texto excede o limite de 4.000 caracteres.")
    try:
        import numpy
    except ImportError as erro:
        raise VozIndisponivel(
            "O componente numérico da voz não está instalado. Execute scripts\\iniciar.bat."
        ) from erro

    with _trava_tts:
        modelo = _obter_modelo_tts()
        amostras = modelo.tts(
            text=texto,
            speaker_wav=str(REFERENCIA_VOZ),
            language=idioma,
        )

    amostras_pcm = numpy.asarray(amostras, dtype=numpy.float32)
    amostras_pcm = numpy.clip(amostras_pcm, -1.0, 1.0)
    audio_pcm = (amostras_pcm * 32767).astype(numpy.int16).tobytes()
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as gravador:
        gravador.setnchannels(1)
        gravador.setsampwidth(2)
        gravador.setframerate(int(modelo.synthesizer.output_sample_rate))
        gravador.writeframes(audio_pcm)
    return buffer.getvalue()
