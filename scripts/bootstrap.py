from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen


ROOT = Path(__file__).resolve().parent.parent
VENV = ROOT / ".venv"
VENV_PYTHON = VENV / "Scripts" / "python.exe"
REQUIREMENTS = ROOT / "requirements.txt"
DEPENDENCY_MARKER = VENV / ".guy-requirements.sha256"
OLLAMA_LOG = ROOT / "data" / "logs" / "ollama-serve.log"
REFERENCIA_VOZ = ROOT / "data" / "voz" / "referencia.wav"
MODELOS_OLLAMA = (
    "joaoguilhermeomiranda/guy",
    "joaoguilhermeomiranda/fearth",
    "nomic-embed-text",
)
OLLAMA_API = "http://127.0.0.1:11434"


class PreparacaoFalhou(RuntimeError):
    pass


def status(mensagem: str) -> None:
    print(f"\nG.U.Y. · {mensagem}", flush=True)


def executar(comando: list[str], *, cwd: Path = ROOT) -> None:
    subprocess.run(comando, cwd=cwd, check=True)


def hash_requisitos() -> str:
    try:
        conteudo = REQUIREMENTS.read_bytes()
    except OSError as erro:
        raise PreparacaoFalhou(
            f"Nao foi possivel ler a lista de dependencias: {REQUIREMENTS}"
        ) from erro
    return hashlib.sha256(conteudo).hexdigest()


def garantir_ambiente_python() -> None:
    if sys.version_info < (3, 14):
        raise PreparacaoFalhou(
            "O inicializador precisa do Python 3.14 ou mais recente."
        )

    ambiente_valido = False
    if VENV_PYTHON.is_file():
        try:
            subprocess.run(
                [
                    str(VENV_PYTHON),
                    "-c",
                    "import sys; raise SystemExit(sys.version_info < (3, 14))",
                ],
                cwd=ROOT,
                check=True,
                capture_output=True,
                text=True,
            )
            ambiente_valido = True
        except (OSError, subprocess.CalledProcessError):
            status("Recriando o ambiente Python local...")
            try:
                shutil.rmtree(VENV)
            except OSError as erro:
                raise PreparacaoFalhou(
                    "O ambiente Python local esta inconsistente e nao pode ser "
                    "recriado. Feche qualquer processo Python que esteja usando "
                    "a pasta .venv e tente novamente."
                ) from erro

    if not ambiente_valido:
        status("Criando o ambiente Python isolado...")
        try:
            executar([sys.executable, "-m", "venv", str(VENV)])
        except subprocess.CalledProcessError as erro:
            raise PreparacaoFalhou(
                "Nao foi possivel criar o ambiente Python local."
            ) from erro

    try:
        marcador_atual = DEPENDENCY_MARKER.read_text(encoding="ascii")
    except (OSError, UnicodeError):
        marcador_atual = ""
    hash_atual = hash_requisitos()
    if marcador_atual == hash_atual:
        status("Dependencias Python ja estao atualizadas.")
        return

    status("Instalando ou atualizando as dependencias Python...")
    try:
        executar(
            [
                str(VENV_PYTHON),
                "-m",
                "pip",
                "install",
                "--disable-pip-version-check",
                "-r",
                str(REQUIREMENTS),
            ]
        )
        DEPENDENCY_MARKER.write_text(hash_atual, encoding="ascii")
    except subprocess.CalledProcessError as erro:
        raise PreparacaoFalhou(
            "A instalacao das dependencias Python falhou. Confira a mensagem "
            "acima e tente iniciar o G.U.Y. novamente."
        ) from erro
    except OSError as erro:
        raise PreparacaoFalhou(
            "Nao foi possivel concluir a instalacao das dependencias Python."
        ) from erro


def garantir_dependencia_voz() -> None:
    if not REFERENCIA_VOZ.is_file():
        return

    status("Verificando o mecanismo da voz salva...")
    verificacao = verificar_importacao_voz()
    if verificacao.returncode:
        saidas = (verificacao.stdout, verificacao.stderr)
        detalhe = "\n".join(saida.strip() for saida in saidas if saida.strip())
        detalhe = detalhe[-1_500:]
        raise PreparacaoFalhou(
            "A dependencia da voz continua sem carregar no ambiente do G.U.Y. "
            f"Python: {VENV_PYTHON}. Erro de importacao: "
            f"{detalhe or 'causa nao informada'}"
        )


def verificar_importacao_voz() -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            [
                str(VENV_PYTHON),
                "-c",
                (
                    "from app.voz import preparar_dependencia_voz; "
                    "preparar_dependencia_voz()"
                ),
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
            timeout=1_920,
        )
    except subprocess.TimeoutExpired as erro:
        raise PreparacaoFalhou(
            "A preparacao/verificacao da dependencia de voz excedeu 32 minutos."
        ) from erro
    except OSError as erro:
        raise PreparacaoFalhou(
            f"Nao foi possivel verificar a dependencia de voz: {erro}"
        ) from erro


def encontrar_ollama() -> str | None:
    encontrado = shutil.which("ollama")
    if encontrado:
        return encontrado

    candidatos = (
        Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Ollama" / "ollama.exe",
        Path(os.environ.get("ProgramFiles", "")) / "Ollama" / "ollama.exe",
    )
    return next((str(caminho) for caminho in candidatos if caminho.is_file()), None)


def instalar_ollama() -> str:
    winget = shutil.which("winget")
    if not winget:
        raise PreparacaoFalhou(
            "O Ollama nao foi encontrado e o winget nao esta disponivel para "
            "instala-lo automaticamente. Instale o Instalador de Aplicativos "
            "do Windows e abra o G.U.Y. novamente."
        )

    status("Instalando o Ollama automaticamente...")
    try:
        executar([
            winget,
            "install",
            "--id",
            "Ollama.Ollama",
            "--exact",
            "--silent",
            "--accept-source-agreements",
            "--accept-package-agreements",
        ])
    except subprocess.CalledProcessError as erro:
        raise PreparacaoFalhou(
            "A instalacao automatica do Ollama falhou. Confira a mensagem acima "
            "e tente iniciar o G.U.Y. novamente."
        ) from erro

    ollama = encontrar_ollama()
    if not ollama:
        raise PreparacaoFalhou(
            "O instalador do Ollama terminou, mas o comando nao foi encontrado. "
            "Feche e abra o G.U.Y. novamente para atualizar o PATH."
        )
    return ollama


def listar_modelos() -> set[str] | None:
    try:
        with urlopen(f"{OLLAMA_API}/api/tags", timeout=2) as resposta:
            dados = json.load(resposta)
    except (OSError, URLError, json.JSONDecodeError):
        return None
    if not isinstance(dados, dict) or not isinstance(dados.get("models"), list):
        return None
    return {
        str(modelo.get("name") or modelo.get("model", "")).split(":")[0]
        for modelo in dados.get("models", [])
        if isinstance(modelo, dict)
    }


def garantir_servidor_ollama(ollama: str) -> None:
    if listar_modelos() is not None:
        return

    status("Iniciando o servico local do Ollama...")
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        OLLAMA_LOG.parent.mkdir(parents=True, exist_ok=True)
        log = OLLAMA_LOG.open("a", encoding="utf-8")
        subprocess.Popen(
            [ollama, "serve"],
            cwd=ROOT,
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=subprocess.STDOUT,
            creationflags=flags,
        )
    except OSError as erro:
        if "log" in locals():
            log.close()
        raise PreparacaoFalhou(
            "Nao foi possivel iniciar o Ollama. Confira a instalacao e tente "
            "abrir o G.U.Y. novamente."
        ) from erro
    else:
        log.close()

    limite = time.monotonic() + 90
    while time.monotonic() < limite:
        if listar_modelos() is not None:
            return
        time.sleep(1)
    raise PreparacaoFalhou(
        "O Ollama nao iniciou a tempo. Aguarde e tente abrir o G.U.Y. novamente."
    )


def garantir_modelos_ollama(ollama: str) -> None:
    modelos_instalados = listar_modelos()
    if modelos_instalados is None:
        raise PreparacaoFalhou("O servico local do Ollama nao esta respondendo.")

    faltantes = [
        modelo for modelo in MODELOS_OLLAMA if modelo.split(":")[0] not in modelos_instalados
    ]
    for modelo in faltantes:
        status(f"Baixando modelo {modelo}. Isso pode levar um tempo na primeira vez...")
        try:
            executar([ollama, "pull", modelo])
        except subprocess.CalledProcessError as erro:
            raise PreparacaoFalhou(
                f"Nao foi possivel baixar o modelo {modelo}. Confira a conexao "
                "com a internet e tente iniciar o G.U.Y. novamente."
            ) from erro


def iniciar_aplicativo() -> int:
    status("Iniciando o G.U.Y....")
    return subprocess.run(
        [str(VENV_PYTHON), str(ROOT / "main.py")],
        cwd=ROOT,
        check=False,
    ).returncode


def main() -> int:
    try:
        garantir_ambiente_python()
        garantir_dependencia_voz()
        ollama = encontrar_ollama() or instalar_ollama()
        garantir_servidor_ollama(ollama)
        garantir_modelos_ollama(ollama)
        return iniciar_aplicativo()
    except PreparacaoFalhou as erro:
        print(f"\nNao foi possivel preparar o G.U.Y.: {erro}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nPreparacao interrompida.")
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
