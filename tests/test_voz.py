import io
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

    def test_instala_componente_automaticamente_na_primeira_sintese(self):
        modelo = SimpleNamespace(
            synthesizer=SimpleNamespace(output_sample_rate=24_000),
            tts=lambda **_kwargs: numpy.array([0.25], dtype=numpy.float32),
        )
        modulo = ModuleType("TTS.api")
        modulo.TTS = lambda **_kwargs: modelo
        ausente = ModuleNotFoundError("No module named 'TTS'", name="TTS")
        with (
            patch.object(voz, "_modelo_tts", None),
            patch.object(
                voz.importlib,
                "import_module",
                side_effect=[ausente, modulo],
            ),
            patch.object(voz.subprocess, "run") as executar_instalacao,
            patch.object(voz.importlib, "invalidate_caches"),
        ):
            carregado = voz._obter_modelo_tts()

        self.assertIs(carregado, modelo)
        executar_instalacao.assert_called_once()
        self.assertIn(voz.PACOTE_VOZ_PERSONALIZADA, executar_instalacao.call_args.args[0])

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
