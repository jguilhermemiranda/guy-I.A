import io
import subprocess
import sys
import tempfile
import unittest
import wave
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import Mock, patch

import numpy

from app import voz


def wav_de_teste(duracao=5):
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as arquivo:
        arquivo.setnchannels(1)
        arquivo.setsampwidth(2)
        arquivo.setframerate(16_000)
        arquivo.writeframes(b"\x00\x00" * (16_000 * duracao))
    return buffer.getvalue()


class VozTestCase(unittest.TestCase):
    def setUp(self):
        self.diretorio = tempfile.TemporaryDirectory()
        self.referencia_original = voz.REFERENCIA_VOZ
        self.modelo_original = voz._modelo
        voz.REFERENCIA_VOZ = Path(self.diretorio.name) / "referencia.wav"

    def tearDown(self):
        voz.REFERENCIA_VOZ = self.referencia_original
        voz._modelo = self.modelo_original
        self.diretorio.cleanup()

    def test_salva_amostra_wav_validada(self):
        voz.salvar_referencia_voz(wav_de_teste())
        self.assertTrue(voz.referencia_voz_disponivel())
        self.assertEqual(voz.REFERENCIA_VOZ.read_bytes(), wav_de_teste())

    def test_rejeita_amostra_curta(self):
        with self.assertRaisesRegex(ValueError, "entre 5 e 30 segundos"):
            voz.salvar_referencia_voz(wav_de_teste(duracao=4))

    def test_gera_wav_com_modelo_local(self):
        referencia = wav_de_teste()
        voz.REFERENCIA_VOZ.write_bytes(referencia)
        modelo = SimpleNamespace(
            synthesizer=SimpleNamespace(output_sample_rate=24_000),
            tts=lambda **_kwargs: numpy.array([0.0, 0.5, -0.5], dtype=numpy.float32),
        )
        with patch.object(voz, "_obter_modelo_tts", return_value=modelo):
            resultado = voz.sintetizar_wav("Olá, Guy!", idioma="pt")

        with wave.open(io.BytesIO(resultado), "rb") as audio:
            self.assertEqual(audio.getnchannels(), 1)
            self.assertEqual(audio.getsampwidth(), 2)
            self.assertEqual(audio.getframerate(), 24_000)
            self.assertEqual(audio.getnframes(), 3)

    def test_le_amostra_pcm_sem_chamar_torchcodec_e_restaura_loader(self):
        import torch
        import torchaudio
        from TTS.tts.models.xtts import load_audio

        voz.REFERENCIA_VOZ.parent.mkdir(parents=True, exist_ok=True)
        with wave.open(str(voz.REFERENCIA_VOZ), "wb") as arquivo:
            arquivo.setnchannels(1)
            arquivo.setsampwidth(2)
            arquivo.setframerate(16_000)
            arquivo.writeframes(numpy.zeros(80_000, dtype=numpy.int16).tobytes())

        carregador_original = torchaudio.load
        with voz._usar_carregador_wav_sem_torchcodec():
            audio = load_audio(str(voz.REFERENCIA_VOZ), 16_000)

        self.assertEqual(tuple(audio.shape), (1, 80_000))
        self.assertTrue(torch.allclose(
            audio,
            torch.zeros((1, 80_000), dtype=torch.float32),
        ))
        self.assertIs(torchaudio.load, carregador_original)

    def test_informa_modulo_python_ausente_na_importacao_do_tts(self):
        with (
            patch.object(voz, "_modelo_tts", None),
            patch.object(
                voz.importlib,
                "import_module",
                side_effect=voz.VozIndisponivel(
                    "Falta o módulo Python 'trainer'."
                ),
            ),
            patch.object(voz, "_versao_pacote", return_value=None),
        ):
            with self.assertRaisesRegex(voz.VozIndisponivel, "módulo Python 'trainer'"):
                voz._obter_modelo_tts()

    def test_repara_importacao_tts_incompleta_automaticamente(self):
        modulo = ModuleType("TTS.api")
        ausente = ModuleNotFoundError("No module named 'trainer'", name="trainer")
        with (
            patch.object(
                voz.importlib,
                "import_module",
                side_effect=[ausente, modulo],
            ),
            patch.object(voz, "_versao_pacote", return_value=None),
            patch.object(voz.subprocess, "run") as executar_instalacao,
            patch.object(voz.importlib, "invalidate_caches"),
        ):
            resultado = voz.preparar_dependencia_voz()

        self.assertIs(resultado, modulo)
        executar_instalacao.assert_called_once()
        self.assertEqual(
            executar_instalacao.call_args.args[0][-1],
            "coqui-tts[codec]==0.27.5",
        )

    def test_prepara_par_cpu_compativel_antes_de_importar_o_tts(self):
        modulo_tts = ModuleType("TTS.api")
        with (
            patch.object(
                voz,
                "_versao_pacote",
                side_effect=["2.14.1+cpu", None],
            ),
            patch.object(voz, "garantir_transformers_compativel"),
            patch.object(voz, "instalar_torchaudio_compativel") as instalar,
            patch.object(voz.importlib, "import_module", return_value=modulo_tts),
        ):
            resultado = voz._importar_api_tts()

        self.assertIs(resultado, modulo_tts)

        instalar.assert_called_once_with()

    def test_rebaixa_transformers_5_para_versao_compativel_com_xtts(self):
        with (
            patch.object(voz, "_versao_pacote", return_value="5.19.0"),
            patch.object(voz.subprocess, "run") as instalar,
        ):
            voz.garantir_transformers_compativel()

        instalar.assert_called_once_with(
            [
                sys.executable,
                "-m",
                "pip",
                "install",
                "--disable-pip-version-check",
                "--upgrade",
                "transformers>=4.57,<5",
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=1_800,
        )

    def test_instala_torch_e_torchaudio_em_versoes_compativeis(self):
        with (
            patch.object(
                voz,
                "_versao_pacote",
                side_effect=[
                    "2.14.1+cpu",
                    "2.11.0+cpu",
                    "2.11.0+cpu",
                ],
            ),
            patch.object(voz.subprocess, "run") as instalar,
            patch.object(voz.importlib, "invalidate_caches"),
        ):
            voz.instalar_torchaudio_compativel()

        instalar.assert_called_once_with(
            [
                sys.executable,
                "-m",
                "pip",
                "install",
                "--disable-pip-version-check",
                "--no-deps",
                "--force-reinstall",
                "--index-url",
                voz.INDICE_PYTORCH_CPU,
                "torch==2.11.0+cpu",
                "torchaudio==2.11.0+cpu",
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=1_800,
        )

    def test_mostra_detalhe_do_pip_quando_instalacao_falha(self):
        falha = subprocess.CalledProcessError(
            1,
            ["pip", "install"],
            stderr="ERROR: No matching distribution found",
        )
        with (
            patch.object(voz, "_versao_pacote", return_value="2.14.1+cpu"),
            patch.object(voz.subprocess, "run", side_effect=falha),
            self.assertRaisesRegex(
                voz.VozIndisponivel,
                "No matching distribution found",
            ),
        ):
            voz.instalar_torchaudio_compativel()

    def test_baixa_modelo_de_transcricao_no_primeiro_uso(self):
        diretorio_modelo = Path(self.diretorio.name) / "modelo"
        modelo = object()
        download = Mock()
        whisper = ModuleType("faster_whisper")
        whisper.WhisperModel = lambda *_args, **_kwargs: modelo
        huggingface = ModuleType("huggingface_hub")
        huggingface.snapshot_download = download
        with (
            patch.object(voz, "_modelo", None),
            patch.object(voz, "MODELO_DIR", diretorio_modelo),
            patch.dict(sys.modules, {
                "faster_whisper": whisper,
                "huggingface_hub": huggingface,
            }),
        ):
            carregado = voz._obter_modelo()

        self.assertIs(carregado, modelo)
        download.assert_called_once_with(
            repo_id="Systran/faster-whisper-base",
            local_dir=str(diretorio_modelo),
        )


if __name__ == "__main__":
    unittest.main()
