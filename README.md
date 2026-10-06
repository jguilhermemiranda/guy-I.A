# G.U.Y.

Assistente local de desktop para Windows, com interface própria, memória persistente e acesso a uma base de conhecimento local. O app usa modelos executados via Ollama e não exige conta, login ou cadastro.

## Funcionalidades

- Chat local em janela desktop própria.
- Dois agentes de conversa: `guy` e `fearth`, além do modo `debate`.
- Base local de conhecimento em arquivos PDF, TXT e MD.
- Busca semântica com embeddings e ChromaDB.
- Memórias persistentes em SQLite.
- Pesquisa web opcional quando a pergunta pede informações atualizadas.
- Sem configuração manual de `Modelfile`.

## Requisitos

| Requisito | Observação |
|---|---|
| Windows | Sistema suportado no projeto |
| Python 3.14+ | Necessário para criar o ambiente virtual |
| [Ollama](https://ollama.com) | Deve estar em execução durante a preparação e o uso |
| RAM / VRAM / espaço em disco | Depende dos modelos baixados e do tamanho da base de conhecimento |

> O projeto define `requires-python = ">=3.14"` em `pyproject.toml` e o script de inicialização também valida Python 3.14 ou superior.

## Modelos usados

Os modelos abaixo são baixados/atualizados pelo script de preparação:

| Modelo | Função |
|---|---|
| `joaoguilhermeomiranda/guy` | Agente principal do assistente |
| `joaoguilhermeomiranda/fearth` | Agente analítica/contraponto |
| `nomic-embed-text` | Embeddings para busca semântica de documentos |

## Início rápido

1. Instale o Python 3.14 e o Ollama.
2. Inicie o Ollama.
3. Rode o script de preparação:

```powershell
scripts\pre-comit.bat
```

Esse script cria a pasta `models/` se necessário e faz o download dos modelos usados pelo aplicativo.

4. Inicie a aplicação:

```powershell
scripts\iniciar.bat
```

Na primeira execução, o script cria o ambiente virtual, instala as dependências e inicia o app. Nas próximas vezes, basta executar o mesmo arquivo novamente.

## Execução manual

Se preferir rodar sem os arquivos `.bat`:

```powershell
py -3.14 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe main.py
```

## Configuração

Opcionalmente, crie um arquivo `.env` na raiz do projeto com variáveis locais.

| Variável | Descrição | Padrão |
|---|---|---|
| `GUY_USERNAME` | Identificador local do usuário no app | `usuario` |

Exemplo:

```env
GUY_USERNAME=seu_nome
```

## Base de conhecimento

Há duas formas de trabalhar com a base local:

- Pela interface: clique em `Base de conhecimento` para adicionar arquivos PDF, TXT ou MD, consultar o que já está salvo e remover documentos da base. Os arquivos adicionados são indexados imediatamente no banco vetorial.
- Pela pasta: os documentos podem ficar em `data/knowledge/` e são armazenados localmente para uso do sistema. O código do projeto também inclui a lógica de sincronização/indexação desses arquivos, mas o fluxo principal do app é adicionar arquivos pela interface.

Arquivos suportados:

- `.pdf`
- `.txt`
- `.md`

O limite de upload indicado no app é de 50 MB por arquivo.

## Dados locais e versionamento

Estes dados são criados e atualizados durante o uso e não devem ser versionados:

| Dado | Local | Git |
|---|---|---|
| Índice vetorial (ChromaDB) | `data/chroma_db/` | Ignorado |
| Memórias e bancos locais | `data/` | Ignorado |
| Modelos gerenciados pelo Ollama | Fora do projeto | Fora do projeto |
| Arquivos de configuração locais | `models/` | Ignorados |

A pasta `data/` também guarda bancos e índices locais usados durante a execução.

## Estrutura do projeto

```text
.
├── app/                # código Python do aplicativo
├── data/               # bancos, índices e arquivos locais de conhecimento
├── models/             # pasta opcional para arquivos locais de configuração/modelo
├── resources/          # templates, CSS, JS e imagens da interface
├── scripts/            # scripts de preparação e inicialização no Windows
├── .env.example        # exemplo de variáveis de ambiente
├── main.py             # ponto de entrada
├── pyproject.toml      # configuração do projeto
├── requirements.txt    # dependências do ambiente Python
├── README.md           # documentação do projeto
└── uv.lock             # lockfile do projeto
```

## Solução de problemas

- **Falha ao baixar os modelos**: confirme que o Ollama está em execução antes de rodar `scripts\pre-comit.bat`.
- **Python não encontrado**: instale o Python 3.14 ou superior e tente novamente.
- **Ambiente virtual inválido**: delete a pasta `.venv` e rode `scripts\iniciar.bat` novamente.
- **Arquivo não indexa**: verifique se o arquivo está em um formato suportado, tem conteúdo legível e não está vazio.