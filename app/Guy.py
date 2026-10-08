from pathlib import Path
import hashlib
import json
import logging
import re
import unicodedata
from urllib.parse import urlparse

import chromadb
import ollama
import requests

from bs4 import BeautifulSoup
from pypdf import PdfReader

try:
    from ddgs import DDGS
except ImportError:
    DDGS = None

from .memoria import (
    adicionar_memoria,
    construir_contexto_memoria
)
from .perfil import construir_contexto_perfil, instrucao_preferencias, obter_perfil

VERMELHO = "\033[91m"
AMARELO = "\033[93m"
VERDE = "\033[92m"
CIANO = "\033[96m"
ROXO = "\033[95m"
RESET = "\033[0m"

BASE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = BASE_DIR.parent
DATA_DIR = PROJECT_DIR / "data"
BANCO_DIR = DATA_DIR / "knowledge"
CHROMA_DIR = DATA_DIR / "chroma_db"

MODELO_GUY = "joaoguilhermeomiranda/guy"
MODELO_FEARTH = "joaoguilhermeomiranda/fearth"
MODELO_EMBEDDING = "nomic-embed-text"

COLECAO = "guy_conhecimento"
CONFIGURACAO_CONTEXTO = {
    "historico_limite": 4,
    "limiar_relevancia": 0.25,
    "limiar_duplicacao": 0.8,
}

TAMANHO_CHUNK = 1200
SOBREPOSICAO = 200
LIMIAR_RELEVANCIA = 0.45

RESULTADOS_BUSCA = 10
RESULTADOS_WEB = 10

TEMPO_MAXIMO_PAGINA = 20
MAX_CHARS_PAGINA = 9000

USER_AGENT = (
    "Mozilla/5.0 "
    "(Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 "
    "(KHTML, like Gecko) "
    "Chrome/151.0 Safari/537.36"
)

historicos = {}
_LOGGER = logging.getLogger(__name__)

TEMPERATURA_PADRAO_GUY = 0.2
TEMPERATURA_PADRAO_FEARTH = 0.1


def normalizar_temperatura(temperatura, padrao):
    try:
        valor = float(temperatura)
    except (TypeError, ValueError):
        return float(padrao)

    valor = max(0.0, min(1.0, valor))
    return float(valor)


def opcoes_modelo(agente="guy", temperatura=None):
    padrao = TEMPERATURA_PADRAO_FEARTH if agente == "fearth" else TEMPERATURA_PADRAO_GUY
    temperatura_final = normalizar_temperatura(temperatura, padrao)

    if agente == "fearth":
        return {
            "temperature": temperatura_final,
            "top_p": 0.7,
            "seed": 42
        }

    return {
        "temperature": temperatura_final,
        "top_p": 0.8,
        "seed": 42
    }


def ler_pdf(caminho):
    try:
        leitor = PdfReader(str(caminho))
    except Exception as erro:
        print(f"{VERMELHO}Erro ao abrir PDF: {erro}{RESET}")
        return ""

    paginas = []

    for numero, pagina in enumerate(leitor.pages, start=1):
        try:
            texto = pagina.extract_text() or ""

            if texto.strip():
                paginas.append(f"[Página {numero}]\n{texto}")
        except Exception as erro:
            print(f"{VERMELHO}Erro na página {numero}: {erro}{RESET}")

    return "\n\n".join(paginas)


def ler_arquivo(caminho):
    extensao = caminho.suffix.lower()

    if extensao == ".pdf":
        return ler_pdf(caminho)

    if extensao in [".txt", ".md"]:
        try:
            return caminho.read_text(
                encoding="utf-8",
                errors="ignore"
            )
        except Exception as erro:
            print(f"{VERMELHO}Erro ao ler arquivo: {erro}{RESET}")

    return ""


def dividir_texto(texto):
    texto = " ".join(texto.split())

    if not texto:
        return []

    pedacos = []
    inicio = 0

    while inicio < len(texto):
        fim = min(inicio + TAMANHO_CHUNK, len(texto))
        pedaco = texto[inicio:fim]

        if pedaco.strip():
            pedacos.append(pedaco.strip())

        if fim >= len(texto):
            break

        inicio = fim - SOBREPOSICAO

    return pedacos


def gerar_embedding(texto):
    resposta = ollama.embed(
        model=MODELO_EMBEDDING,
        input=texto
    )

    if isinstance(resposta, dict):
        embeddings = resposta.get("embeddings") or []
    else:
        embeddings = getattr(resposta, "embeddings", [])

    if not embeddings:
        raise ValueError("A resposta de embedding não retornou embeddings.")

    return embeddings[0]


def gerar_hash_arquivo(caminho):
    sha256 = hashlib.sha256()

    with open(caminho, "rb") as arquivo:
        while True:
            bloco = arquivo.read(1024 * 1024)

            if not bloco:
                break

            sha256.update(bloco)

    return sha256.hexdigest()


def gerar_id(caminho, numero):
    identificador = f"{caminho.resolve()}::{numero}"

    return hashlib.sha256(
        identificador.encode("utf-8")
    ).hexdigest()


def obter_colecao():
    CHROMA_DIR.mkdir(parents=True, exist_ok=True)

    client = chromadb.PersistentClient(path=str(CHROMA_DIR))

    return client.get_or_create_collection(
        name=COLECAO,
        configuration={
            "hnsw": {
                "space": "cosine"
            }
        }
    )


def listar_arquivos():
    arquivos = []

    if not BANCO_DIR.exists():
        return arquivos

    for arquivo in BANCO_DIR.rglob("*"):
        if not arquivo.is_file():
            continue

        if arquivo.suffix.lower() in [".pdf", ".txt", ".md"]:
            arquivos.append(arquivo)

    return arquivos


def remover_documento(collection, caminho):
    caminho_resolvido = str(caminho.resolve())

    resultado = collection.get(
        where={
            "caminho": caminho_resolvido
        },
        include=["metadatas"]
    )

    ids = resultado.get("ids", [])

    if ids:
        collection.delete(ids=ids)

    return len(ids)


def indexar_arquivo(collection, arquivo, fail_on_error=False):
    print()
    print(f"{CIANO}📖 Indexando: {arquivo.name}{RESET}")

    texto = ler_arquivo(arquivo)

    if not texto.strip():
        print(f"{AMARELO}⚠ Nenhum texto foi extraído.{RESET}")
        return 0

    pedacos = dividir_texto(texto)
    hash_arquivo = gerar_hash_arquivo(arquivo)
    total = 0

    for numero, pedaco in enumerate(pedacos):
        try:
            print(f"  🧠 Embedding {numero + 1}/{len(pedacos)}...")

            embedding = gerar_embedding(pedaco)
            documento_id = gerar_id(arquivo, numero)

            collection.add(
                ids=[documento_id],
                embeddings=[embedding],
                documents=[pedaco],
                metadatas=[{
                    "arquivo": arquivo.name,
                    "caminho": str(arquivo.resolve()),
                    "numero_pedaco": numero,
                    "hash_arquivo": hash_arquivo
                }]
            )

            total += 1
        except Exception as erro:
            if fail_on_error:
                raise
            print(
                f"{VERMELHO}Erro ao indexar trecho "
                f"{numero + 1}: {erro}{RESET}"
            )

    return total


def atualizar_banco():
    print()
    print(f"{ROXO}=== SINCRONIZAÇÃO DO BANCO ==={RESET}")

    BANCO_DIR.mkdir(parents=True, exist_ok=True)
    collection = obter_colecao()
    arquivos = listar_arquivos()

    if not arquivos:
        print(f"{AMARELO}Nenhum PDF, TXT ou MD encontrado em:{RESET}")
        print(BANCO_DIR)
        return

    arquivos_indexados = 0
    trechos_indexados = 0

    for arquivo in arquivos:
        caminho_resolvido = str(arquivo.resolve())
        hash_atual = gerar_hash_arquivo(arquivo)

        resultado = collection.get(
            where={"caminho": caminho_resolvido},
            include=["metadatas"]
        )

        metadatas = resultado.get("metadatas") or []
        hashes_antigos = set()

        for metadata in metadatas:
            if not metadata:
                continue

            hash_arquivo = metadata.get("hash_arquivo")

            if isinstance(hash_arquivo, (str, bytes, int, float, bool)):
                hashes_antigos.add(hash_arquivo)

        if hashes_antigos == {hash_atual}:
            print(f"{VERDE}✓ Já atualizado: {arquivo.name}{RESET}")
            continue

        if resultado.get("ids"):
            removidos = remover_documento(collection, arquivo)
            print(
                f"{AMARELO}↻ Atualizando {arquivo.name} "
                f"({removidos} trechos antigos removidos){RESET}"
            )

        total = indexar_arquivo(collection, arquivo)

        if total:
            arquivos_indexados += 1
            trechos_indexados += total

    print()
    print(
        f"{VERDE}Sincronização concluída. "
        f"{arquivos_indexados} arquivo(s), "
        f"{trechos_indexados} trecho(s) indexado(s).{RESET}"
    )


def buscar_conhecimento(collection, pergunta):
    try:
        embedding = gerar_embedding(pergunta)

        resultado = collection.query(
            query_embeddings=[embedding],
            n_results=RESULTADOS_BUSCA,
            include=["documents", "metadatas", "distances"]
        )
    except Exception as erro:
        print(f"{VERMELHO}Erro ao buscar no banco: {erro}{RESET}")
        return []

    documentos = resultado.get("documents", [[]])[0]
    metadatas = resultado.get("metadatas", [[]])[0]
    distancias = resultado.get("distances", [[]])[0]

    encontrados = []

    for documento, metadata, distancia in zip(
        documentos,
        metadatas,
        distancias
    ):
        relevancia = 1 - float(distancia)

        if relevancia < LIMIAR_RELEVANCIA:
            continue

        encontrados.append({
            "texto": documento,
            "arquivo": (metadata or {}).get("arquivo", "Arquivo desconhecido"),
            "relevancia": relevancia
        })

    return encontrados


def construir_contexto(resultados):
    if not resultados:
        return "Nenhum trecho relevante foi encontrado no banco local."

    partes = []

    for indice, resultado in enumerate(resultados, start=1):
        partes.append(
            f"[Fonte local {indice}: {resultado['arquivo']} | "
            f"relevância {resultado['relevancia']:.2f}]\n"
            f"{resultado['texto']}"
        )

    return "\n\n".join(partes)


def precisa_internet(pergunta):
    termos = [
        "pesquise",
        "pesquisa",
        "pesquisar",
        "internet",
        "web",
        "google",
        "notícia",
        "noticias",
        "notícias",
        "atualmente",
        "atualizado",
        "atualizada",
        "hoje",
        "agora",
        "wiki",
        "wikipedia",
        "confira na internet",
        "confere na internet"
    ]

    pergunta_normalizada = pergunta.lower()

    return any(termo in pergunta_normalizada for termo in termos)


def preparar_busca_web(pergunta):
    pergunta = re.sub(
        r"\b(pesquise|pesquisa|pesquisar|na internet|na web|no google)\b",
        "",
        pergunta,
        flags=re.IGNORECASE
    )

    pergunta = " ".join(pergunta.split())

    return pergunta or "informações atualizadas"


def extrair_texto_pagina(url):
    try:
        resposta = requests.get(
            url,
            headers={"User-Agent": USER_AGENT},
            timeout=TEMPO_MAXIMO_PAGINA
        )
        resposta.raise_for_status()

        soup = BeautifulSoup(resposta.text, "html.parser")

        for elemento in soup(
            ["script", "style", "noscript", "header", "footer", "nav", "aside"]
        ):
            elemento.decompose()

        texto = soup.get_text(" ", strip=True)
        texto = " ".join(texto.split())

        return texto[:MAX_CHARS_PAGINA]
    except Exception:
        return ""


def pesquisar_web(consulta):
    if DDGS is None:
        print(
            f"{AMARELO}DDGS não está instalado. "
            f"Pesquisa web indisponível.{RESET}"
        )
        return []

    try:
        with DDGS() as ddgs:
            resultados_brutos = list(
                ddgs.text(
                    consulta,
                    region="br-pt",
                    safesearch="moderate",
                    max_results=RESULTADOS_WEB
                )
            )
    except Exception as erro:
        print(f"{VERMELHO}Erro na pesquisa web: {erro}{RESET}")
        return []

    resultados = []

    for resultado in resultados_brutos:
        url = resultado.get("href") or resultado.get("url") or ""

        if not url.startswith(("http://", "https://")):
            continue

        titulo = resultado.get("title", "Sem título").strip()
        descricao = (
            resultado.get("body")
            or resultado.get("snippet")
            or ""
        ).strip()

        texto_pagina = extrair_texto_pagina(url)

        resultados.append({
            "titulo": titulo,
            "url": url,
            "dominio": urlparse(url).netloc,
            "descricao": descricao,
            "texto": texto_pagina
        })

    return resultados


def construir_contexto_web(resultados):
    if not resultados:
        return (
            "A pesquisa web foi solicitada, mas nenhuma fonte confiável "
            "pôde ser recuperada."
        )

    partes = []

    for indice, resultado in enumerate(resultados, start=1):
        conteudo = resultado["texto"] or resultado["descricao"]

        if not conteudo:
            continue

        partes.append(
            f"[Fonte web {indice}]\n"
            f"Título: {resultado['titulo']}\n"
            f"Domínio: {resultado['dominio']}\n"
            f"URL: {resultado['url']}\n"
            f"Conteúdo: {conteudo}"
        )

    if not partes:
        return "A pesquisa web não retornou conteúdo utilizável."

    return "\n\n".join(partes)


def chamou_fearth(pergunta):
    pergunta_normalizada = pergunta.lower()

    termos = [
        "fearth",
        "fearth-ia",
        "segunda opinião",
        "segunda opiniao",
        "opinião da fearth",
        "opiniao da fearth",
        "pergunta para a fearth",
        "pergunte para a fearth",
        "consulta a fearth",
        "consulte a fearth"
    ]

    return any(termo in pergunta_normalizada for termo in termos)


def consultar_fearth(pergunta, montagem_contexto, temperatura=None):
    prompt = f"""
Você é Fearth-IA, um agente independente que está sendo consultado por Guy.

Responda diretamente à solicitação abaixo em português brasileiro.
Não finja ser Guy e não escreva falas de Guy.
Não diga que você foi consultada se não puder analisar o conteúdo.
Não invente fontes, fatos ou resultados de pesquisa.
Responda à mensagem atual delimitada; o contexto auxiliar pode não se aplicar.
""".strip()

    try:
        resposta = ollama.chat(
            model=MODELO_FEARTH,
            messages=[
                {
                    "role": "system",
                    "content": prompt
                },
                {"role": "user", "content": montagem_contexto["prompt"]},
            ],
            options=opcoes_modelo("fearth", temperatura)
        )

        conteudo = resposta["message"]["content"].strip()

        if not conteudo:
            return ""

        return conteudo
    except Exception as erro:
        print(f"{VERMELHO}❌ Erro ao consultar Fearth: {erro}{RESET}")
        return ""


def limpar_fato_memoria(texto):
    texto = " ".join(texto.strip().split())
    texto = texto.strip(" .,!?:;")

    return texto[:350]


def extrair_memorias_relevantes(mensagem):
    """
    Extrai fatos simples e persistentes do usuário sem depender de uma
    resposta do modelo. O retorno é uma lista de dicionários compatível
    com adicionar_memoria(username, texto, categoria=..., importancia=...).
    """
    texto = " ".join(mensagem.strip().split())
    texto_normalizado = texto.lower()

    if not texto:
        return []

    fatos = []
    vistos = set()

    def adicionar_fato(conteudo, categoria="perfil", importancia=3):
        conteudo = limpar_fato_memoria(conteudo)

        if not conteudo:
            return

        chave = conteudo.lower()

        if chave in vistos:
            return

        vistos.add(chave)

        fatos.append({
            "conteudo": conteudo,
            "categoria": categoria,
            "importancia": importancia
        })

    padroes_nome = [
        r"\bmeu nome é\s+([A-Za-zÀ-ÿ][A-Za-zÀ-ÿ0-9 ._-]{0,60})",
        r"\bpode me chamar de\s+([A-Za-zÀ-ÿ][A-Za-zÀ-ÿ0-9 ._-]{0,60})",
        r"\beu me chamo\s+([A-Za-zÀ-ÿ][A-Za-zÀ-ÿ0-9 ._-]{0,60})"
    ]

    for padrao in padroes_nome:
        encontrado = re.search(padrao, texto, flags=re.IGNORECASE)

        if encontrado:
            nome = limpar_fato_memoria(encontrado.group(1))
            nome = re.split(
                r"\b(e eu|e gosto|e adoro|e curto|, eu|\. eu)\b",
                nome,
                maxsplit=1,
                flags=re.IGNORECASE
            )[0].strip()

            if nome:
                adicionar_fato(
                    f"O nome que o usuário informou é {nome}.",
                    "identidade",
                    5
                )

            break

    padroes_interesse = [
        r"\beu gosto (?:muito )?de\s+([^.!?]+)",
        r"\beu adoro\s+([^.!?]+)",
        r"\beu curto\s+([^.!?]+)",
        r"\bme interesso por\s+([^.!?]+)",
        r"\bminha paixão é\s+([^.!?]+)"
    ]

    for padrao in padroes_interesse:
        encontrado = re.search(padrao, texto, flags=re.IGNORECASE)

        if encontrado:
            interesse = limpar_fato_memoria(encontrado.group(1))
            interesse = re.split(
                r"\b(e |mas |porque |quando )\b",
                interesse,
                maxsplit=1,
                flags=re.IGNORECASE
            )[0].strip()

            if interesse:
                adicionar_fato(
                    f"O usuário gosta ou se interessa por {interesse}.",
                    "interesse",
                    4
                )

    padroes_preferencia = [
        r"\bminha comida favorita é\s+([^.!?]+)",
        r"\bmeu jogo favorito é\s+([^.!?]+)",
        r"\bminha série favorita é\s+([^.!?]+)",
        r"\bmeu filme favorito é\s+([^.!?]+)",
        r"\bminha cor favorita é\s+([^.!?]+)",
        r"\beu prefiro\s+([^.!?]+)"
    ]

    for padrao in padroes_preferencia:
        encontrado = re.search(padrao, texto, flags=re.IGNORECASE)

        if encontrado:
            preferencia = limpar_fato_memoria(encontrado.group(1))

            if preferencia:
                adicionar_fato(
                    f"Preferência do usuário: {preferencia}.",
                    "preferencia",
                    3
                )

    padroes_profissao = [
        r"\beu trabalho como\s+([^.!?]+)",
        r"\bsou (?:um|uma)\s+([^.!?]+)",
        r"\beu estudo\s+([^.!?]+)",
        r"\bestou estudando\s+([^.!?]+)"
    ]

    for padrao in padroes_profissao:
        encontrado = re.search(padrao, texto, flags=re.IGNORECASE)

        if encontrado:
            informacao = limpar_fato_memoria(encontrado.group(1))

            if informacao and len(informacao) <= 120:
                adicionar_fato(
                    f"Informação pessoal/profissional do usuário: "
                    f"{informacao}.",
                    "perfil",
                    3
                )

    if (
        "guarda isso na memória" in texto_normalizado
        or "guarde isso na memória" in texto_normalizado
        or "lembra disso" in texto_normalizado
        or "memoriza isso" in texto_normalizado
    ) and not fatos:
        adicionar_fato(
            f"O usuário pediu para lembrar: {texto}.",
            "lembranca_solicitada",
            3
        )

    return fatos


def salvar_memorias_relevantes(username, mensagem):
    fatos = extrair_memorias_relevantes(mensagem)

    for fato in fatos:
        try:
            adicionar_memoria(
                username,
                fato["conteudo"],
                categoria=fato["categoria"],
                importancia=fato["importancia"]
            )
        except Exception as erro:
            print(f"{AMARELO}Aviso ao salvar memória: {erro}{RESET}")

    return fatos


_STOPWORDS = {
    "a", "ao", "aos", "as", "com", "como", "da", "das", "de", "dela",
    "dele", "deles", "do", "dos", "e", "ela", "ele", "em", "essa",
    "essas", "esse", "esses", "esta", "estas", "este", "estes", "eu",
    "foi", "isso", "isto", "ja", "lhe", "mais", "mas", "me", "meu",
    "minha", "muito", "na", "nas", "no", "nos", "o", "os", "ou",
    "para", "pela", "pelas", "pelo", "pelos", "por", "qual", "quando",
    "que", "quem", "se", "sem", "ser", "sua", "suas", "tambem", "te",
    "tem", "um", "uma", "voce",
}
_SUFIXOS_SIMPLES = (
    "amentos", "imentos", "acoes", "adoras", "adores", "mente", "idades",
    "amento", "imento", "acao", "adora", "ador", "antes", "ancia",
    "encia", "idade", "ando", "endo", "indo", "ados", "adas", "idos",
    "idas", "es", "os", "as", "s",
)
_FOLLOW_UP_PATTERNS = (
    r"\bexplique\s+melhor\b",
    r"\bcontinue\b",
    r"\be\s+a\s+terceira\b",
    r"\be\s+a\s+proxima\b",
    r"\bconverta\b",
    r"\bmelhore\b",
    r"\bdetalhe\b",
    r"\bexplica\s+melhor\b",
    r"\bmais\s+claro\b",
    r"\b(isso|disso|nisso|aquilo|daquilo)\b",
)
_FOLLOW_UP_SHORT_TOKENS = {
    "sim", "nao", "mais", "qual", "porque", "por", "exemplo", "outra",
    "outro", "segunda", "terceira", "quarta", "continue",
}


def _normalizar_token(token):
    token = "".join(
        caractere for caractere in unicodedata.normalize("NFD", token)
        if unicodedata.category(caractere) != "Mn"
    )
    if token in _STOPWORDS or len(token) < 2:
        return ""

    for sufixo in _SUFIXOS_SIMPLES:
        if token.endswith(sufixo) and len(token) - len(sufixo) >= 3:
            return token[:-len(sufixo)]
    return token


def _tokenizar_texto(texto):
    texto = str(texto or "").lower()
    texto = re.sub(r"https?://\S+", " ", texto)
    tokens = re.findall(r"[a-z0-9À-ÿ]+", texto)
    return [normalizado for token in tokens if (normalizado := _normalizar_token(token))]


def _texto_mensagem(item):
    if isinstance(item, dict):
        return str(item.get("content", ""))
    return str(item)


def _mensagem_role(item):
    return item.get("role", "user") if isinstance(item, dict) else "user"


def _chave_turno(item):
    return " ".join(_tokenizar_texto(_texto_mensagem(item)))


def _turno_repetido(tokens, anteriores, limiar=0.8):
    atuais = set(tokens)
    if not atuais:
        return False
    for anterior in anteriores:
        if abs(len(atuais) - len(anterior)) > 1:
            continue
        uniao = atuais | anterior
        similaridade = len(atuais & anterior) / len(uniao) if uniao else 0.0
        if similaridade >= limiar:
            return True
    return False


def _mensagem_follow_up(texto, tokens):
    sem_acentos = "".join(
        caractere for caractere in unicodedata.normalize("NFD", str(texto).lower())
        if unicodedata.category(caractere) != "Mn"
    )
    sem_acentos = " ".join(re.findall(r"[a-z0-9]+", sem_acentos))
    normalizado = " ".join(_tokenizar_texto(texto))
    tem_referencia = any(
        re.search(padrao, normalizado)
        for padrao in _FOLLOW_UP_PATTERNS
    ) or any(
        re.search(padrao, sem_acentos)
        for padrao in (
            r"\be\s+a\s+terceira\b",
            r"\bconverta\b",
            r"\bexplique\s+melhor\b",
            r"\bcontinue\b",
            r"\b(isso|disso|nisso|aquilo|daquilo)\b",
        )
    )
    return tem_referencia or (
        len(tokens) <= 3
        and bool(set(tokens) & _FOLLOW_UP_SHORT_TOKENS)
    )


def selecionar_historico_relevante(
    pergunta,
    historico,
    limite=4,
    limiar=0.25,
    limiar_duplicacao=0.8,
):
    """Seleciona candidatos por sobreposição lexical; repetições não somam peso."""
    if not historico:
        return []

    tokens_pergunta = set(_tokenizar_texto(pergunta))
    follow_up = _mensagem_follow_up(str(pergunta or ""), tokens_pergunta)
    if not tokens_pergunta:
        return list(historico[-2:]) if follow_up else []

    pontuados = []
    turnos_vistos = []
    ignorar_resposta_duplicada = False
    for indice, item in enumerate(historico):
        role = _mensagem_role(item)

        if role == "user":
            tokens_turno = _tokenizar_texto(_texto_mensagem(item))
            ignorar_resposta_duplicada = _turno_repetido(
                tokens_turno,
                turnos_vistos,
                limiar=limiar_duplicacao,
            )
            if tokens_turno:
                turnos_vistos.append(set(tokens_turno))
        elif ignorar_resposta_duplicada:
            continue

        tokens_item = set(_tokenizar_texto(_texto_mensagem(item)))
        intersecao = tokens_pergunta & tokens_item
        score = len(intersecao) / len(tokens_pergunta) if tokens_item else 0.0
        pontuados.append((indice, item, score, ignorar_resposta_duplicada))

    selecionados = []
    if follow_up:
        selecionados = list(historico[-min(2, len(historico)):])
    else:
        distintos = set()
        candidatos = []
        for indice, item, score, duplicado in pontuados:
            if duplicado:
                continue
            chave = _chave_turno(item)
            if chave and chave in distintos:
                continue
            if chave:
                distintos.add(chave)
            if score >= limiar:
                candidatos.append((score, indice, item))
        candidatos.sort(key=lambda registro: (-registro[0], -registro[1]))
        selecionados = [
            item for _, _, item in sorted(candidatos[:max(0, limite)], key=lambda r: r[1])
        ]

    return selecionados


def montar_prompt_contexto(
    mensagem,
    historico,
    memoria,
    modo=True,
    configuracao=None,
    contexto_adicional=None,
    contexto_da_tarefa=None,
):
    """Monta o prompt contextual de forma determinística e sem I/O."""
    configuracao = {
        **CONFIGURACAO_CONTEXTO,
        **(configuracao or {}),
    }
    modo = bool(modo)
    limiar = float(configuracao["limiar_relevancia"])
    limite = int(configuracao["historico_limite"])
    historico = list(historico or [])
    pergunta = str(mensagem or "").strip()
    pergunta_tokens = set(_tokenizar_texto(pergunta))
    follow_up = _mensagem_follow_up(pergunta, pergunta_tokens)
    historico_relevante = (
        selecionar_historico_relevante(
            pergunta,
            historico,
            limite=limite,
            limiar=limiar,
            limiar_duplicacao=float(configuracao["limiar_duplicacao"]),
        )
        if modo else []
    )
    selecionados_ids = {id(item) for item in historico_relevante}
    decisoes = []
    vistos = []
    duplicados = set()
    for indice, item in enumerate(historico):
        role = _mensagem_role(item)
        chave = _chave_turno(item)
        texto = _texto_mensagem(item)
        score = (
            len(pergunta_tokens & set(_tokenizar_texto(texto))) / len(pergunta_tokens)
            if pergunta_tokens else 0.0
        )
        duplicado = False
        if role == "user" and chave:
            tokens_turno = _tokenizar_texto(texto)
            duplicado = _turno_repetido(
                tokens_turno,
                vistos,
                limiar=float(configuracao["limiar_duplicacao"]),
            )
            if tokens_turno:
                vistos.append(set(tokens_turno))
            if duplicado:
                duplicados.add(indice)
                if (
                    indice + 1 < len(historico)
                    and _mensagem_role(historico[indice + 1]) == "assistant"
                ):
                    duplicados.add(indice + 1)
        incluido = id(item) in selecionados_ids and indice not in duplicados
        if not modo:
            motivo = "contexto desativado"
        elif indice in duplicados:
            motivo = "turno repetido; não aumenta a relevância"
        elif incluido and follow_up:
            motivo = "follow-up; mínimo do turno anterior"
        elif incluido:
            motivo = "score acima do limiar"
        elif score < limiar:
            motivo = "score abaixo do limiar"
        else:
            motivo = "reservatório não selecionado pelo limite"
        decisoes.append({
            "indice": indice,
            "incluido": bool(incluido),
            "motivo": motivo,
            "score": round(score, 4),
        })

    memoria_texto = str(memoria or "").strip()
    secoes = [
        "CONTEXTO AUXILIAR — pode não se aplicar; o assunto é a mensagem atual.",
        "Use o contexto auxiliar apenas quando ele for aplicável à mensagem atual.",
    ]
    if modo and historico_relevante:
        secoes.append(
            "CONTEXTO RELEVANTE DA CONVERSA\n"
            + montar_historico_texto(historico_relevante)
        )
    if modo:
        for rotulo, conteudo in (contexto_adicional or {}).items():
            conteudo = str(conteudo or "").strip()
            if conteudo:
                secoes.append(f"{rotulo}\n{conteudo}")
    for rotulo, conteudo in (contexto_da_tarefa or {}).items():
        conteudo = str(conteudo or "").strip()
        if conteudo:
            secoes.append(f"{rotulo}\n{conteudo}")
    if memoria_texto:
        secoes.append(
            "MEMÓRIA PERSISTENTE DO USUÁRIO\n"
            "São fatos duráveis, não o assunto presumido da conversa.\n"
            + memoria_texto
        )
    secoes.extend([
        "MENSAGEM ATUAL DO USUÁRIO (define o assunto; responda a esta mensagem)\n"
        f"<<<INÍCIO>>>\n{pergunta}\n<<<FIM>>>",
    ])
    return {
        "mensagem_atual": pergunta,
        "historico": historico_relevante,
        "historico_texto": montar_historico_texto(historico_relevante),
        "memoria": memoria_texto,
        "decisoes": decisoes,
        "modo": modo,
        "prompt": "\n\n".join(secoes),
    }


def registrar_decisao_contexto(logger, montagem, agente):
    if logger.getEffectiveLevel() > logging.INFO:
        logger.setLevel(logging.INFO)
    logger.info(
        "Decisão de contexto: %s",
        json.dumps({
            "agente": agente,
            "modo": montagem["modo"],
            "considerados": len(montagem["decisoes"]),
            "incluidos": sum(decisao["incluido"] for decisao in montagem["decisoes"]),
            "excluidos": sum(not decisao["incluido"] for decisao in montagem["decisoes"]),
            "decisoes": montagem["decisoes"],
        }, ensure_ascii=False),
    )


def montar_historico_texto(historico):
    partes = []

    for mensagem in historico:
        if isinstance(mensagem, dict):
            nome = "Usuário" if mensagem.get("role") == "user" else "Guy"
            partes.append(f"{nome}: {mensagem.get('content', '')}")
        else:
            partes.append(f"Mensagem: {mensagem}")

    return "\n".join(partes)


def processar_mensagem(
    usuario,
    pergunta,
    agente="guy",
    temperatura=None,
    contexto_habilitado=True,
):
    username = usuario["username"]
    agente = str(agente).strip().lower()

    if agente not in ["guy", "fearth"]:
        agente = "guy"

    if username not in historicos:
        historicos[username] = []

    historico = historicos[username]
    perfil = obter_perfil(username)

    contexto = ""
    contexto_web = ""
    if contexto_habilitado:
        try:
            collection = obter_colecao()
            resultados = buscar_conhecimento(collection, pergunta)
            contexto = construir_contexto(resultados)
        except Exception as erro:
            print(f"{AMARELO}Aviso no RAG: {erro}{RESET}")
            contexto = "O banco local não está disponível nesta mensagem."

        contexto_web = "A internet não foi consultada nesta mensagem."
        if precisa_internet(pergunta):
            consulta_web = preparar_busca_web(pergunta)
            resultados_web = pesquisar_web(consulta_web)
            contexto_web = construir_contexto_web(resultados_web)
    try:
        contexto_perfil = (
            construir_contexto_perfil(username) if contexto_habilitado else ""
        )
    except Exception as erro:
        print(f"{AMARELO}Aviso no perfil técnico: {erro}{RESET}")
        contexto_perfil = "O perfil técnico não está disponível nesta mensagem."

    try:
        memorias = construir_contexto_memoria(username)
    except Exception as erro:
        _LOGGER.exception("Falha ao carregar a memória persistente: %s", erro)
        memorias = "A memória persistente não está disponível nesta mensagem."

    contexto_adicional = {
        "INFORMAÇÕES PERMANENTES DO USUÁRIO": (
            f"Username (identificador): {usuario['username']}\nTipo: {usuario['tipo']}"
        ),
        "BANCO LOCAL": contexto,
        "INTERNET": contexto_web,
        "PERFIL TÉCNICO E FONTES PÚBLICAS DO USUÁRIO": contexto_perfil,
    }
    contexto_prompt = montar_prompt_contexto(
        pergunta,
        historico,
        memorias,
        modo=contexto_habilitado,
        contexto_adicional=contexto_adicional,
    )

    if agente == "fearth":
        registrar_decisao_contexto(_LOGGER, contexto_prompt, agente)
        resposta = consultar_fearth(
            pergunta,
            contexto_prompt,
            temperatura=temperatura
        )

        if not resposta:
            return "⚠️ A Fearth-IA não conseguiu responder nesta mensagem."

        historico.append({
            "role": "user",
            "content": pergunta
        })
        historico.append({
            "role": "assistant",
            "content": resposta
        })

        salvar_memorias_relevantes(username, pergunta)

        return resposta

    registrar_decisao_contexto(_LOGGER, contexto_prompt, agente)
    resposta_fearth = ""
    fearth_solicitada = chamou_fearth(pergunta)

    if fearth_solicitada:
        resposta_fearth = consultar_fearth(
            pergunta,
            contexto_prompt,
            temperatura=temperatura
        )

        # Não deixa Guy improvisar, simular ou inventar uma fala da Fearth.
        if not resposta_fearth:
            return (
                "⚠️ A Fearth-IA não conseguiu responder agora. "
                "Não vou inventar uma opinião por ela."
            )

    contexto_fearth = (
        "A Fearth-IA não foi consultada nesta mensagem."
    )

    if resposta_fearth:
        contexto_fearth = f"""
A resposta abaixo foi realmente produzida pela Fearth-IA.

--- INÍCIO DA RESPOSTA REAL DA FEARTH-IA ---
{resposta_fearth}
--- FIM DA RESPOSTA REAL DA FEARTH-IA ---

Regras obrigatórias:
- Não escreva perguntas dirigidas à Fearth-IA.
- Não simule uma conversa entre Guy e Fearth-IA.
- Não crie, complete, resuma como citação ou atribua à Fearth-IA algo que
  não esteja no texto acima.
- Se mencionar a Fearth-IA, deixe claro que essa é a resposta que ela enviou.
- Você pode comparar a sua análise com a resposta real acima.
""".strip()

    if resposta_fearth:
        contexto_prompt = montar_prompt_contexto(
            pergunta,
            historico,
            memorias,
            modo=contexto_habilitado,
            contexto_adicional=contexto_adicional,
            contexto_da_tarefa={"RESPOSTA REAL DA FEARTH-IA": contexto_fearth},
        )
    mensagens = [
        {
            "role": "system",
            "content": (
                "Responda à última mensagem do usuário delimitada no prompt. "
                "O histórico e outros contextos são auxiliares e podem não se "
                "aplicar ao assunto atual. Não invente fontes nem fatos."
                "\n\n"
                + instrucao_preferencias(perfil["preferencias"])
            ),
        },
        {"role": "user", "content": contexto_prompt["prompt"]},
    ]

    try:
        resposta_modelo = ollama.chat(
            model=MODELO_GUY,
            messages=mensagens,
            options=opcoes_modelo("guy", temperatura)
        )

        resposta = resposta_modelo["message"]["content"].strip()

        if not resposta:
            resposta = "Não consegui gerar uma resposta agora."
    except Exception as erro:
        print(f"{VERMELHO}Erro ao consultar Guy: {erro}{RESET}")
        return "⚠️ O Guy não conseguiu responder nesta mensagem."

    historico.append({
        "role": "user",
        "content": pergunta
    })
    historico.append({
        "role": "assistant",
        "content": resposta
    })

    salvar_memorias_relevantes(username, pergunta)

    return resposta
