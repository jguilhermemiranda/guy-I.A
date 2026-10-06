import os
from pathlib import Path

import ollama
from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request
from werkzeug.exceptions import RequestEntityTooLarge
from werkzeug.utils import secure_filename

from .Guy import (
    BANCO_DIR,
    historicos,
    indexar_arquivo,
    normalizar_temperatura,
    obter_colecao,
    opcoes_modelo,
    processar_mensagem,
    remover_documento,
)
from .memoria import (
    adicionar_memoria,
    criar_banco_memoria,
    editar_memoria,
    listar_memorias,
    remover_memoria,
)


MODELO_GUY = "joaoguilhermeomiranda/guy"
MODELO_FEARTH = "joaoguilhermeomiranda/fearth"
AGENTES_VALIDOS = {"guy", "fearth", "debate"}

# O Guy continua usando seu histórico/RAG original em Guy.py.
historicos_fearth = {}
historicos_debate = {}

PROJECT_DIR = Path(__file__).resolve().parent.parent
RESOURCES_DIR = PROJECT_DIR / "resources"

app = Flask(
    __name__,
    template_folder=str(RESOURCES_DIR / "templates"),
    static_folder=str(RESOURCES_DIR / "static"),
)
app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024

load_dotenv()
USUARIO = {
    "id": "single-user",
    "username": os.environ.get("GUY_USERNAME", "usuario").strip() or "usuario",
    "tipo": "USER",
}
criar_banco_memoria()


def resposta_ollama(modelo, mensagens, temperatura=None, agente="guy"):
    resposta = ollama.chat(
        model=modelo,
        messages=mensagens,
        options=opcoes_modelo(agente, temperatura),
    )
    conteudo = resposta.get("message", {}).get("content", "").strip()
    if not conteudo:
        raise RuntimeError("O Ollama não retornou uma resposta.")
    return conteudo


def responder_fearth(usuario, mensagem, temperatura=None):
    username = usuario["username"]
    historico = historicos_fearth.setdefault(username, [])
    sistema = {
        "role": "system",
        "content": (
            "Você é Fearth, uma agente independente, analítica e respeitosa. "
            "Não concorde automaticamente: aponte premissas frágeis, riscos e "
            "alternativas quando fizer sentido. Responda em português do Brasil."
        ),
    }
    mensagens = [sistema, *historico[-12:], {"role": "user", "content": mensagem}]
    resposta = resposta_ollama(MODELO_FEARTH, mensagens, temperatura=temperatura, agente="fearth")
    historico.extend([
        {"role": "user", "content": mensagem},
        {"role": "assistant", "content": resposta},
    ])
    return resposta


def responder_debate(usuario, pergunta, temperatura=None):
    username = usuario["username"]
    historico = historicos_debate.setdefault(username, [])
    contexto = "\n\n".join(historico[-6:])
    base = f"Pergunta do usuário: {pergunta}"
    if contexto:
        base = f"Contexto de debates anteriores:\n{contexto}\n\n{base}"

    guy = resposta_ollama(MODELO_GUY, [
        {
            "role": "system",
            "content": "Você é Guy. Apresente uma posição inicial útil, objetiva e bem justificada em português do Brasil.",
        },
        {"role": "user", "content": base},
    ], temperatura=temperatura, agente="guy")
    fearth = resposta_ollama(MODELO_FEARTH, [
        {
            "role": "system",
            "content": "Você é Fearth, debatedora independente. Analise a pergunta e a posição de Guy. Conteste somente onde houver motivo e ofereça correções práticas. Responda em português do Brasil.",
        },
        {"role": "user", "content": f"{base}\n\nPosição inicial de Guy:\n{guy}"},
    ], temperatura=temperatura, agente="fearth")
    conclusao = resposta_ollama(MODELO_GUY, [
        {
            "role": "system",
            "content": "Você é o mediador final de um debate. Produza uma conclusão equilibrada, curta e acionável; reconheça incertezas e diga qual escolha faz mais sentido nas condições dadas. Responda em português do Brasil.",
        },
        {"role": "user", "content": f"Pergunta: {pergunta}\n\nGuy:\n{guy}\n\nFearth:\n{fearth}"},
    ], temperatura=temperatura, agente="guy")
    historico.extend([
        f"Usuário: {pergunta}",
        f"Guy: {guy}",
        f"Fearth: {fearth}",
        f"Conclusão: {conclusao}",
    ])
    return {"modo": "debate", "guy": guy, "fearth": fearth, "conclusao": conclusao}


@app.route("/")
@app.route("/inicio")
def inicio():
    return render_template("index.html")


@app.route("/chat", methods=["POST"])
def chat():
    dados = request.get_json(silent=True)
    if not isinstance(dados, dict):
        return jsonify({"detail": "JSON inválido."}), 400

    mensagem = str(dados.get("mensagem", "")).strip()
    agente = str(dados.get("agente", "guy")).lower().strip()
    temperatura = dados.get("temperatura")
    temperatura = normalizar_temperatura(temperatura, 0.2)
    if not mensagem:
        return jsonify({"detail": "A mensagem não pode estar vazia."}), 400
    if agente not in AGENTES_VALIDOS:
        return jsonify({"detail": "Agente inválido."}), 400

    try:
        if agente == "debate":
            return jsonify(responder_debate(USUARIO, mensagem, temperatura=temperatura))
        if agente == "fearth":
            return jsonify({
                "modo": "simples",
                "agente": "fearth",
                "resposta": responder_fearth(USUARIO, mensagem, temperatura=temperatura),
            })

        return jsonify({
            "modo": "simples",
            "agente": "guy",
            "resposta": processar_mensagem(USUARIO, mensagem, temperatura=temperatura),
        })
    except Exception as erro:
        app.logger.exception("Erro no chat: %s", erro)
        return jsonify({"detail": "Erro ao processar mensagem."}), 500


@app.route("/nova-conversa", methods=["POST"])
def nova_conversa():
    username = USUARIO["username"]
    historicos[username] = []
    historicos_fearth.pop(username, None)
    historicos_debate.pop(username, None)
    return jsonify({"sucesso": True})


@app.route("/api/conhecimento/arquivos", methods=["POST"])
def api_adicionar_arquivo_conhecimento():
    arquivo = request.files.get("arquivo")
    if not arquivo or not arquivo.filename:
        return jsonify({"detail": "Selecione um arquivo para adicionar."}), 400

    nome_arquivo = secure_filename(arquivo.filename)
    extensao = Path(nome_arquivo).suffix.lower()
    if not nome_arquivo or extensao not in {".pdf", ".txt", ".md"}:
        return jsonify({"detail": "Use um arquivo PDF, TXT ou MD."}), 400

    BANCO_DIR.mkdir(parents=True, exist_ok=True)
    caminho = BANCO_DIR / nome_arquivo
    if caminho.exists():
        return jsonify({
            "detail": "Já existe um arquivo com esse nome na base de conhecimento."
        }), 409

    arquivo.save(caminho)
    if caminho.stat().st_size == 0:
        caminho.unlink()
        return jsonify({"detail": "O arquivo selecionado está vazio."}), 400

    colecao = None
    try:
        colecao = obter_colecao()
        trechos_indexados = indexar_arquivo(
            colecao,
            caminho,
            fail_on_error=True,
        )
        if not trechos_indexados:
            caminho.unlink()
            return jsonify({
                "detail": "Não foi possível extrair conteúdo para indexar. Verifique o arquivo e tente novamente."
            }), 422
    except Exception as erro:
        if colecao is not None:
            remover_documento(colecao, caminho)
        caminho.unlink(missing_ok=True)
        app.logger.exception("Erro ao indexar arquivo de conhecimento: %s", erro)
        return jsonify({"detail": "Não foi possível adicionar o arquivo à base de conhecimento."}), 500

    return jsonify({
        "sucesso": True,
        "arquivo": nome_arquivo,
        "trechos_indexados": trechos_indexados,
    }), 201


@app.route("/api/conhecimento/arquivos", methods=["GET"])
def api_listar_arquivos_conhecimento():
    if not BANCO_DIR.exists():
        return jsonify({"arquivos": []})

    arquivos = []
    for caminho in sorted(BANCO_DIR.rglob("*")):
        if caminho.is_file() and caminho.suffix.lower() in {".pdf", ".txt", ".md"}:
            arquivos.append({
                "caminho": caminho.relative_to(BANCO_DIR).as_posix(),
                "nome": caminho.name,
                "tamanho": caminho.stat().st_size,
            })
    return jsonify({"arquivos": arquivos})


@app.route("/api/conhecimento/arquivos", methods=["DELETE"])
def api_remover_arquivo_conhecimento():
    dados = request.get_json(silent=True)
    if not isinstance(dados, dict):
        return jsonify({"detail": "JSON inválido."}), 400

    caminho_relativo = str(dados.get("caminho", "")).strip()
    if not caminho_relativo:
        return jsonify({"detail": "Selecione um arquivo para remover."}), 400

    try:
        raiz = BANCO_DIR.resolve()
        caminho = (raiz / Path(caminho_relativo)).resolve()
        caminho.relative_to(raiz)
    except (OSError, RuntimeError, ValueError):
        return jsonify({"detail": "Caminho de arquivo inválido."}), 400

    if caminho.suffix.lower() not in {".pdf", ".txt", ".md"} or not caminho.is_file():
        return jsonify({"detail": "Arquivo não encontrado na base de conhecimento."}), 404

    try:
        colecao = obter_colecao()
        remover_documento(colecao, caminho)
        caminho.unlink()
    except Exception as erro:
        app.logger.exception("Erro ao remover arquivo de conhecimento: %s", erro)
        return jsonify({"detail": "Não foi possível remover o arquivo da base de conhecimento."}), 500

    return jsonify({"sucesso": True, "arquivo": caminho.name})


@app.route("/memorias")
def memorias():
    return render_template("memorias.html")


@app.route("/api/memorias", methods=["GET"])
def api_listar_memorias():
    resultado = []
    for memoria in listar_memorias(USUARIO["username"]):
        resultado.append({
            "id": memoria[0],
            "categoria": memoria[1],
            "memoria": memoria[2],
            "importancia": memoria[3],
            "criado_em": memoria[4],
        })
    return jsonify({"memorias": resultado})


def dados_memoria():
    dados = request.get_json(silent=True)
    if not isinstance(dados, dict):
        return None, (jsonify({"detail": "JSON inválido."}), 400)

    memoria = str(dados.get("memoria", "")).strip()
    categoria = str(dados.get("categoria", "geral")).strip()
    if not memoria:
        return None, (jsonify({"detail": "A memória não pode estar vazia."}), 400)

    try:
        importancia = int(dados.get("importancia", 1))
    except (TypeError, ValueError):
        importancia = 1
    return (memoria, categoria, max(1, min(importancia, 5))), None


@app.route("/api/memorias", methods=["POST"])
def api_adicionar_memoria():
    valores, erro = dados_memoria()
    if erro:
        return erro
    memoria, categoria, importancia = valores
    adicionada = adicionar_memoria(USUARIO["username"], memoria, categoria, importancia)
    return jsonify({"sucesso": True, "adicionada": adicionada})


@app.route("/api/memorias/<int:memoria_id>", methods=["PUT"])
def api_editar_memoria(memoria_id):
    valores, erro = dados_memoria()
    if erro:
        return erro
    memoria, categoria, importancia = valores
    alterada = editar_memoria(USUARIO["username"], memoria_id, memoria, categoria, importancia)
    if not alterada:
        return jsonify({"detail": "Memória não encontrada."}), 404
    return jsonify({"sucesso": True})


@app.route("/api/memorias/<int:memoria_id>", methods=["DELETE"])
def api_remover_memoria(memoria_id):
    removida = remover_memoria(USUARIO["username"], memoria_id)
    if not removida:
        return jsonify({"detail": "Memória não encontrada."}), 404
    return jsonify({"sucesso": True})


@app.errorhandler(RequestEntityTooLarge)
def arquivo_grande_demais(_erro):
    return jsonify({"detail": "O arquivo excede o limite de 50 MB."}), 413


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)
