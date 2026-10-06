import unittest
from unittest.mock import patch

from scripts import bootstrap


class BootstrapTestCase(unittest.TestCase):
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
