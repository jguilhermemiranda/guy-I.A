import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from scripts import bootstrap


class BootstrapTestCase(unittest.TestCase):
    def test_nao_instala_tts_se_usuario_nao_tem_amostra(self):
        with (
            patch.object(bootstrap, "REFERENCIA_VOZ", Path("nao-existe.wav")),
            patch.object(bootstrap, "executar") as executar,
        ):
            bootstrap.garantir_dependencia_voz()

        executar.assert_not_called()

    def test_repara_tts_antes_de_iniciar_se_importacao_falhar(self):
        sucesso = SimpleNamespace(returncode=0, stderr="", stdout="")
        with (
            patch.object(
                bootstrap,
                "REFERENCIA_VOZ",
                SimpleNamespace(is_file=lambda: True),
            ),
            patch.object(bootstrap, "verificar_importacao_voz", return_value=sucesso) as verificar,
        ):
            bootstrap.garantir_dependencia_voz()

        verificar.assert_called_once()

    def test_mostra_erro_real_se_reparo_do_tts_falhar(self):
        falha = SimpleNamespace(returncode=1, stderr="No module named torch", stdout="")
        with (
            patch.object(
                bootstrap,
                "REFERENCIA_VOZ",
                SimpleNamespace(is_file=lambda: True),
            ),
            patch.object(bootstrap, "verificar_importacao_voz", return_value=falha),
            self.assertRaisesRegex(bootstrap.PreparacaoFalhou, "No module named torch"),
        ):
            bootstrap.garantir_dependencia_voz()

    def test_puxa_somente_modelos_ausentes(self):
        instalados = {
            "joaoguilhermeomiranda/guy",
            "nomic-embed-text",
        }
        with (
            patch.object(bootstrap, "listar_modelos", return_value=instalados),
            patch.object(bootstrap, "executar") as executar,
        ):
            bootstrap.garantir_modelos_ollama("ollama.exe")

        executar.assert_called_once_with([
            "ollama.exe",
            "pull",
            "joaoguilhermeomiranda/fearth",
        ])

    def test_nao_rebaixa_modelos_ja_instalados(self):
        with (
            patch.object(
                bootstrap,
                "listar_modelos",
                return_value={modelo.split(":")[0] for modelo in bootstrap.MODELOS_OLLAMA},
            ),
            patch.object(bootstrap, "executar") as executar,
        ):
            bootstrap.garantir_modelos_ollama("ollama.exe")

        executar.assert_not_called()


if __name__ == "__main__":
    unittest.main()
