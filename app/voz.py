"""Transcrição local de áudio para o G.U.Y., sem serviço de reconhecimento online."""

from __future__ import annotations

import io
import importlib
from importlib import metadata
from contextlib import contextmanager
import subprocess
import sys
import threading
import wave
from pathlib import Path


MODELO_DIR = Path(__file__).resolve().parent.parent / "models" / "faster-whisper-base"
REFERENCIA_VOZ = Path(__file__).resolve().parent.parent / "data" / "voz" / "referencia.wav"
MODELO_VOZ_PERSONALIZADA = "tts_models/multilingual/multi-dataset/xtts_v2"
PACOTE_VOZ_PERSONALIZADA = "coqui-tts[codec]==0.27.5"
INDICE_PYTORCH_CPU = "https://download.pytorch.org/whl/cpu"
VERSAO_PYTORCH_AUDIO_CPU = "2.11.0"
PACOTE_TRANSFORMERS_COMPATIVEL = "transformers>=4.57,<5"
LIMITE_AMOSTRA_BYTES = 5 * 1024 * 1024
_modelo = None
_modelo_tts = None
_trava_modelo = threading.Lock()
_trava_carregamento_tts = threading.Lock()
_trava_preparacao_tts = threading.Lock()
_trava_tts = threading.Lock()


class VozIndisponivel(RuntimeError):
    pass


def _versao_pacote(nome):
    try:
        return metadata.version(nome)
    except metadata.PackageNotFoundError:
        return None


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


def instalar_torchaudio_compativel():
    versao_torch_instalada = _versao_pacote("torch")
    if versao_torch_instalada is None:
        raise VozIndisponivel(
            "O PyTorch não está instalado no ambiente da voz."
        )

    pacotes = [f"torchaudio=={VERSAO_PYTORCH_AUDIO_CPU}+cpu"]
    if versao_torch_instalada != f"{VERSAO_PYTORCH_AUDIO_CPU}+cpu":
        pacotes.insert(0, f"torch=={VERSAO_PYTORCH_AUDIO_CPU}+cpu")

    print(
        "G.U.Y.: instalando o par compatível de áudio para CPU "
        f"(PyTorch {VERSAO_PYTORCH_AUDIO_CPU})...",
        flush=True,
    )
    try:
        subprocess.run(
            [
                sys.executable,
                "-m",
                "pip",
                "install",
                "--disable-pip-version-check",
                "--no-deps",
                "--force-reinstall",
                "--index-url",
                INDICE_PYTORCH_CPU,
                *pacotes,
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=1_800,
        )
    except subprocess.TimeoutExpired as erro:
        raise VozIndisponivel(
            "A instalação do par torch/torchaudio excedeu 30 minutos. "
            "Confira a conexão e abra o G.U.Y. novamente."
        ) from erro
    except subprocess.CalledProcessError as erro:
        detalhe = "\n".join(
            saida.strip()
            for saida in (erro.stdout, erro.stderr)
            if saida and saida.strip()
        )
        if detalhe:
            detalhe = f" Detalhe do pip: {detalhe[-1_200:]}"
        raise VozIndisponivel(
            "Não foi possível instalar o par torch/torchaudio "
            f"{VERSAO_PYTORCH_AUDIO_CPU}+cpu.{detalhe}"
        ) from erro
    except OSError as erro:
        raise VozIndisponivel(
            f"Não foi possível iniciar a instalação de torchaudio: {erro}"
        ) from erro

    versao_torch = _versao_pacote("torch")
    versao_audio = _versao_pacote("torchaudio")
    versoes_esperadas = (
        f"{VERSAO_PYTORCH_AUDIO_CPU}+cpu",
        f"{VERSAO_PYTORCH_AUDIO_CPU}+cpu",
    )
    if (versao_torch, versao_audio) != versoes_esperadas:
        raise VozIndisponivel(
            "A instalação terminou, mas as versões de torch e torchaudio "
            "não correspondem ao par esperado "
            f"{versoes_esperadas[0]}: "
            f"{versao_torch or 'ausente'} e {versao_audio or 'ausente'}."
        )
    importlib.invalidate_caches()

    return None


def garantir_transformers_compativel():
    versao = _versao_pacote("transformers")
    partes = versao.split(".") if versao else []
    if len(partes) < 2 or not all(parte.isdigit() for parte in partes[:2]):
        return
    versao_numerica = tuple(int(parte) for parte in partes[:2])
    if (4, 57) <= versao_numerica < (5, 0):
        return

    print(
        "G.U.Y.: ajustando Transformers para a versão compatível com XTTS...",
        flush=True,
    )
    try:
        subprocess.run(
            [
                sys.executable,
                "-m",
                "pip",
                "install",
                "--disable-pip-version-check",
                "--upgrade",
                PACOTE_TRANSFORMERS_COMPATIVEL,
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=1_800,
        )
    except subprocess.TimeoutExpired as erro:
        raise VozIndisponivel(
            "O ajuste de Transformers excedeu 30 minutos. Confira a conexão "
            "e abra o G.U.Y. novamente."
        ) from erro
    except subprocess.CalledProcessError as erro:
        detalhe = "\n".join(
            saida.strip()
            for saida in (erro.stdout, erro.stderr)
            if saida and saida.strip()
        )
        if detalhe:
            detalhe = f" Detalhe do pip: {detalhe[-1_200:]}"
        raise VozIndisponivel(
            "Não foi possível instalar Transformers compatível com XTTS."
            f"{detalhe}"
        ) from erro
    except OSError as erro:
        raise VozIndisponivel(
            f"Não foi possível iniciar o ajuste de Transformers: {erro}"
        ) from erro


def _importar_api_tts():
    garantir_transformers_compativel()

    versao_torch = _versao_pacote("torch")
    versao_audio = _versao_pacote("torchaudio")
    if versao_torch and (
        versao_audio is None
        or versao_audio != versao_torch
    ):
        instalar_torchaudio_compativel()

    return importlib.import_module("TTS.api")


def preparar_dependencia_voz():
    """Garante que TTS.api possa ser importado no Python que roda o aplicativo."""
    with _trava_preparacao_tts:
        try:
            return _importar_api_tts()
        except ModuleNotFoundError as erro:
            modulo_faltante = erro.name or "desconhecido"
        except ImportError as erro:
            modulo_faltante = str(erro)

        print(
            "G.U.Y.: preparando automaticamente o componente da voz "
            f"personalizada (módulo ausente: {modulo_faltante})...",
            flush=True,
        )
        try:
            subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "pip",
                    "install",
                    "--disable-pip-version-check",
                    "--upgrade",
                    PACOTE_VOZ_PERSONALIZADA,
                ],
                check=True,
                timeout=1_800,
            )
        except subprocess.TimeoutExpired as erro:
            raise VozIndisponivel(
                "A preparação da voz excedeu 30 minutos. Confira a conexão "
                "e abra o G.U.Y. novamente para tentar outra vez."
            ) from erro
        except subprocess.CalledProcessError as erro:
            raise VozIndisponivel(
                "O instalador automático da voz falhou. Confira a conexão e "
                "as mensagens do instalador no terminal."
            ) from erro
        except OSError as erro:
            raise VozIndisponivel(
                f"Não foi possível iniciar o instalador da voz: {erro}"
            ) from erro

        importlib.invalidate_caches()
        try:
            return _importar_api_tts()
        except ImportError as erro:
            raise VozIndisponivel(
                "A instalação terminou, mas TTS.api ainda não pode ser "
                f"importado com {sys.executable}: {erro}"
            ) from erro


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
            modulo_tts = preparar_dependencia_voz()
        except VozIndisponivel:
            raise
        except ImportError as erro:
            raise VozIndisponivel(
                "Não foi possível importar TTS.api. "
                f"Detalhe: {erro}"
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
                "Confira a conexão para baixar o modelo e tente novamente. "
                f"Detalhe técnico: {erro}"
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


@contextmanager
def _usar_carregador_wav_sem_torchcodec():
    import numpy
    import torch
    import torchaudio

    carregar_original = torchaudio.load

    def carregar_audio(origem, *args, **kwargs):
        try:
            caminho = Path(origem).resolve()
        except (TypeError, OSError, ValueError):
            return carregar_original(origem, *args, **kwargs)
        if caminho != REFERENCIA_VOZ.resolve():
            return carregar_original(origem, *args, **kwargs)

        try:
            with wave.open(str(caminho), "rb") as leitor:
                if leitor.getcomptype() != "NONE" or leitor.getsampwidth() != 2:
                    raise VozIndisponivel(
                        "A amostra salva precisa continuar em WAV PCM de 16 bits."
                    )
                canais = leitor.getnchannels()
                taxa = leitor.getframerate()
                dados = leitor.readframes(leitor.getnframes())
        except (wave.Error, EOFError, OSError) as erro:
            raise VozIndisponivel(
                f"Não foi possível ler a amostra WAV salva: {erro}"
            ) from erro

        audio = numpy.frombuffer(dados, dtype=numpy.int16)
        audio = audio.reshape(-1, canais).T.astype(numpy.float32) / 32768.0
        return torch.from_numpy(audio.copy()), taxa

    torchaudio.load = carregar_audio
    try:
        yield
    finally:
        torchaudio.load = carregar_original


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
        with _usar_carregador_wav_sem_torchcodec():
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
