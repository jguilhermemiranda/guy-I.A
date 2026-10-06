import sqlite3
import tempfile
import unittest
from pathlib import Path

from app import perfil


class PerfilTestCase(unittest.TestCase):
    def setUp(self):
        self.diretorio = tempfile.TemporaryDirectory()
        self.banco_original = perfil.BANCO_PERFIL
        perfil.BANCO_PERFIL = Path(self.diretorio.name) / "perfil.db"

    def tearDown(self):
        perfil.BANCO_PERFIL = self.banco_original
        self.diretorio.cleanup()

    def test_salva_identidade_e_inclui_no_contexto(self):
        salvo = perfil.atualizar_perfil(
            "usuario-local",
            {"nome": "João", "username": "@joao-dev"},
        )

        self.assertEqual(salvo["nome"], "João")
        self.assertEqual(salvo["username"], "@joao-dev")
        contexto = perfil.construir_contexto_perfil("usuario-local")
        self.assertIn("nome preferido: João", contexto)
        self.assertIn("nome de usuário: @joao-dev", contexto)

    def test_migra_banco_antigo_sem_perder_preferencias(self):
        with sqlite3.connect(perfil.BANCO_PERFIL) as conexao:
            conexao.execute("""
                CREATE TABLE perfis (
                    usuario_id TEXT PRIMARY KEY,
                    github_url TEXT NOT NULL DEFAULT '',
                    fontes TEXT NOT NULL DEFAULT '[]',
                    notas TEXT NOT NULL DEFAULT '',
                    preferencias TEXT NOT NULL DEFAULT '{}',
                    atualizado_em TEXT NOT NULL
                )
            """)
            conexao.execute(
                "INSERT INTO perfis VALUES (?, ?, ?, ?, ?, ?)",
                (
                    "usuario-local",
                    "https://github.com/joao",
                    "[]",
                    "Prefere exemplos",
                    '{"tom": "direto"}',
                    "2026-01-01T00:00:00",
                ),
            )

        perfil.criar_banco_perfil()
        carregado = perfil.obter_perfil("usuario-local")
        self.assertEqual(carregado["github_url"], "https://github.com/joao")
        self.assertEqual(carregado["notas"], "Prefere exemplos")
        self.assertEqual(carregado["preferencias"]["tom"], "direto")
        self.assertEqual(carregado["nome"], "")
        self.assertEqual(carregado["username"], "")


if __name__ == "__main__":
    unittest.main()
