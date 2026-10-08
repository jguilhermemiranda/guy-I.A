import importlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app import Guy, debate, memoria, perfil

_INICIALIZACAO_TEMPORARIA = tempfile.TemporaryDirectory()
_BANCO_MEMORIA_ORIGINAL = memoria.BANCO_MEMORIA
_BANCO_PERFIL_ORIGINAL = perfil.BANCO_PERFIL
_BANCO_DEBATES_ORIGINAL = debate.BANCO_DEBATES
memoria.BANCO_MEMORIA = Path(_INICIALIZACAO_TEMPORARIA.name) / "memorias.db"
perfil.BANCO_PERFIL = Path(_INICIALIZACAO_TEMPORARIA.name) / "perfil.db"
debate.BANCO_DEBATES = Path(_INICIALIZACAO_TEMPORARIA.name) / "debates.db"
try:
    api = importlib.import_module("app.api")
finally:
    memoria.BANCO_MEMORIA = _BANCO_MEMORIA_ORIGINAL
    perfil.BANCO_PERFIL = _BANCO_PERFIL_ORIGINAL
    debate.BANCO_DEBATES = _BANCO_DEBATES_ORIGINAL
    _INICIALIZACAO_TEMPORARIA.cleanup()


class ContextoTestCase(unittest.TestCase):
    def test_on_nao_leva_newton_para_pergunta_de_motor(self):
        historico = []
        for _ in range(3):
            historico.extend([
                {"role": "user", "content": "Explique a segunda lei de Newton"},
                {"role": "assistant", "content": "A segunda lei de Newton relaciona força e aceleração."},
            ])

        montagem = Guy.montar_prompt_contexto(
            "Como funciona a partida de um motor?",
            historico,
            "",
            modo=True,
        )

        self.assertNotIn("Newton", montagem["prompt"])
        self.assertIn("Como funciona a partida de um motor?", montagem["prompt"])

    def test_on_preserva_o_turno_anterior_para_follow_up(self):
        historico = [
            {"role": "user", "content": "Explique a segunda lei de Newton"},
            {"role": "assistant", "content": "A força resultante é massa vezes aceleração."},
        ]

        montagem = Guy.montar_prompt_contexto(
            "Dê um exemplo disso.",
            historico,
            "",
            modo=True,
        )

        self.assertIn("segunda lei de Newton", montagem["prompt"])
        self.assertIn("massa vezes aceleração", montagem["prompt"])

    def test_off_nao_injeta_historico_nem_contexto_adicional(self):
        montagem = Guy.montar_prompt_contexto(
            "Explique motores.",
            [{"role": "user", "content": "A pergunta antiga secreta"}],
            "Preferência durável: respostas em português.",
            modo=False,
            contexto_adicional={"RAG": "Conteúdo antigo da base."},
        )

        self.assertNotIn("pergunta antiga secreta", montagem["prompt"])
        self.assertNotIn("Conteúdo antigo da base.", montagem["prompt"])
        self.assertIn("Preferência durável", montagem["prompt"])
        self.assertIn("<<<INÍCIO>>>\nExplique motores.", montagem["prompt"])
        self.assertEqual(montagem["historico"], [])

    def test_repeticoes_nao_aumentam_a_relevancia_ou_o_contexto(self):
        turno = [
            {"role": "user", "content": "Explique a segunda lei de Newton"},
            {"role": "assistant", "content": "Newton relaciona força, massa e aceleração."},
        ]
        uma_vez = Guy.montar_prompt_contexto(
            "Explique a segunda lei de Newton", turno, "", modo=True
        )
        repetido = Guy.montar_prompt_contexto(
            "Explique a segunda lei de Newton", turno * 3, "", modo=True
        )

        self.assertEqual(uma_vez["historico_texto"], repetido["historico_texto"])
        self.assertEqual(
            [d["score"] for d in uma_vez["decisoes"] if d["incluido"]],
            [d["score"] for d in repetido["decisoes"] if d["incluido"]],
        )
        self.assertTrue(any("turno repetido" in d["motivo"] for d in repetido["decisoes"]))

    def test_preferencia_persiste_e_controla_a_montagem(self):
        with tempfile.TemporaryDirectory() as pasta:
            with (
                patch.object(perfil, "BANCO_PERFIL", Path(pasta) / "perfil.db"),
                patch.object(api, "USUARIO", {"username": "context-test"}),
            ):
                cliente = api.app.test_client()
                atualizada = cliente.put(
                    "/api/perfil",
                    json={"preferencias": {"contexto_habilitado": False}},
                )
                carregado = cliente.get("/api/perfil").get_json()
                montagem = Guy.montar_prompt_contexto(
                    "Pergunta atual",
                    [{"role": "user", "content": "Turno anterior"}],
                    "",
                    modo=carregado["preferencias"]["contexto_habilitado"],
                )

        self.assertEqual(atualizada.status_code, 200)
        self.assertFalse(carregado["preferencias"]["contexto_habilitado"])
        self.assertNotIn("Turno anterior", montagem["prompt"])

    def test_chat_e_fearth_usam_o_montador_comum(self):
        usuario = {"username": "montador-test", "tipo": "USER"}
        perfil_padrao = perfil._perfil_padrao(usuario["username"])

        with (
            patch.object(Guy, "historicos", {usuario["username"]: []}),
            patch.object(Guy, "obter_perfil", return_value=perfil_padrao),
            patch.object(Guy, "construir_contexto_memoria", return_value=""),
            patch.object(Guy, "salvar_memorias_relevantes"),
            patch.object(Guy.ollama, "chat", return_value={"message": {"content": "resposta"}}) as guy_chat,
            patch.object(Guy, "montar_prompt_contexto", wraps=Guy.montar_prompt_contexto) as guy_montador,
        ):
            Guy.processar_mensagem(usuario, "Pergunta atual", contexto_habilitado=False)
        self.assertEqual(guy_montador.call_count, 1)
        self.assertEqual(guy_chat.call_args.kwargs["messages"][0]["role"], "system")
        self.assertIn("responda", guy_chat.call_args.kwargs["messages"][0]["content"].lower())
        self.assertIn(
            "<<<INÍCIO>>>\nPergunta atual",
            guy_chat.call_args.kwargs["messages"][1]["content"],
        )

        with (
            patch.object(api, "historicos_fearth", {usuario["username"]: []}),
            patch.object(api, "obter_perfil", return_value=perfil_padrao),
            patch.object(api, "construir_contexto_memoria", return_value=""),
            patch.object(api, "resposta_ollama", return_value="resposta") as fearth_chat,
            patch.object(api, "montar_prompt_contexto", wraps=api.montar_prompt_contexto) as fearth_montador,
        ):
            api.responder_fearth(usuario, "Pergunta atual", contexto_habilitado=False)
        self.assertEqual(fearth_montador.call_count, 1)
        self.assertEqual(fearth_chat.call_args.args[1][0]["role"], "system")
        self.assertIn("Fearth", fearth_chat.call_args.args[1][0]["content"])

        with patch.object(api, "USUARIO", usuario):
            resposta = api.app.test_client().post(
                "/chat",
                json={"mensagem": "Pergunta atual", "agente": "debate"},
            )
        self.assertEqual(resposta.status_code, 409)
        self.assertIn("Debate estruturado", resposta.get_json()["detail"])

    def test_rota_chat_aplica_preferencia_persistida(self):
        perfil_usuario = perfil._perfil_padrao("chat-context-test")
        perfil_usuario["preferencias"]["contexto_habilitado"] = False
        with (
            patch.object(api, "USUARIO", {"username": "chat-context-test"}),
            patch.object(api, "obter_perfil", return_value=perfil_usuario),
            patch.object(api, "responder_fearth", return_value="resposta") as responder,
        ):
            resposta = api.app.test_client().post(
                "/chat",
                json={"mensagem": "Pergunta atual", "agente": "fearth"},
            )

        self.assertEqual(resposta.status_code, 200)
        self.assertFalse(responder.call_args.kwargs["contexto_habilitado"])

    def test_nova_conversa_limpa_so_historicos_e_preserva_memoria(self):
        with tempfile.TemporaryDirectory() as pasta:
            with (
                patch.object(memoria, "BANCO_MEMORIA", Path(pasta) / "memorias.db"),
                patch.object(api, "USUARIO", {"username": "nova-conversa-test"}),
            ):
                memoria.criar_banco_memoria()
                memoria.adicionar_memoria(
                    api.USUARIO["username"],
                    "Preferência durável.",
                    categoria="preferencia",
                )
                api.historicos[api.USUARIO["username"]] = [{"role": "user", "content": "antigo"}]
                api.historicos_fearth[api.USUARIO["username"]] = [{"role": "user", "content": "antigo"}]

                resposta = api.app.test_client().post("/nova-conversa")

                self.assertEqual(resposta.status_code, 200)
                self.assertEqual(api.historicos[api.USUARIO["username"]], [])
                self.assertNotIn(api.USUARIO["username"], api.historicos_fearth)
                self.assertEqual(
                    memoria.buscar_memorias(api.USUARIO["username"])[0][2],
                    "Preferência durável.",
                )


if __name__ == "__main__":
    unittest.main()
