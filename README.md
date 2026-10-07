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
| Windows com `winget` | Usado para instalar Python 3.14 e Ollama automaticamente quando necessário |
| Python 3.14+ | Instalado pelo inicializador se estiver ausente |
| [Ollama](https://ollama.com) | Instalado e iniciado pelo inicializador quando necessário |
| RAM / VRAM / espaço em disco | Depende dos modelos baixados e do tamanho da base de conhecimento |

> O projeto define `requires-python = ">=3.14"` em `pyproject.toml`. No Windows, `scripts\iniciar.bat` usa o `winget` (Instalador de Aplicativos do Windows) para preparar o Python 3.14 quando ele não está instalado.

## Modelos usados

Os modelos abaixo são baixados automaticamente na primeira inicialização:

| Modelo | Função |
|---|---|
| `joaoguilhermeomiranda/guy` | Agente principal do assistente |
| `joaoguilhermeomiranda/fearth` | Agente analítica/contraponto |
| `nomic-embed-text` | Embeddings para busca semântica de documentos |

## Início rápido

1. Abra o aplicativo pelo inicializador:

```powershell
scripts\iniciar.bat
```

Na primeira execução, o inicializador prepara o Python 3.14 e o ambiente virtual, instala as dependências, instala/inicia o Ollama e baixa os modelos necessários. A preparação acontece numa única janela; não é preciso fechar o app para abrir outros scripts. Os modelos e dependências já instalados são reutilizados nas próximas inicializações.

## Execução manual

Se preferir rodar sem o inicializador:

```powershell
py -3.14 scripts\bootstrap.py
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

## Voz, perfil e preferências

- No chat, o botão de microfone grava no navegador e transcreve localmente com Whisper. A transcrição aparece no campo antes de ser enviada, para que você possa revisá-la.
- Em **Perfil e preferências**, você pode escolher tom, nível de detalhe, idioma e a voz de saída; a opção de falar respostas é desligada por padrão. A fala do Guy também omite a formatação de Markdown e blocos de código para soar mais natural.
- O perfil também permite informar nome e nome de usuário para personalizar o contexto das respostas. Esses campos não alteram o identificador local usado para separar memórias.
- A fala pode usar vozes instaladas no Windows ou uma amostra de voz gravada em **Perfil e preferências**. A tela mostra um pequeno roteiro em português para a pessoa ler sem improvisar durante a gravação. Para clonagem local, confirme que a voz é sua ou que você tem autorização e grave de 5 a 30 segundos. O inicializador instala `coqui-tts` com o componente de codecs exigido pelo PyTorch 2.9+ e, se necessário, alinha `torch` e `torchaudio` ao par CPU 2.11.0, disponível para Python 3.14 no Windows; o modelo XTTS-v2 é baixado automaticamente no primeiro teste/uso e pode levar alguns minutos (requer internet). Depois, a geração e o áudio de referência ficam no computador. O modelo é destinado a uso não comercial conforme sua licença.
- A amostra fica em `data/voz/` (ignorada pelo Git), pode ser apagada pela tela de preferências e não é enviada a um serviço externo.
- O perfil aceita uma URL pública de perfil ou repositório do GitHub, notas sobre seu estilo de programação e até cinco fontes públicas adicionais. O conteúdo dessas fontes é consultado somente no momento de responder e é usado como contexto para Guy, Fearth e Debate.
- As preferências e notas ficam apenas em `data/perfil.db`. O G.U.Y. não grava token do GitHub e não acessa repositórios privados.

Após iniciar o G.U.Y. pelo fluxo normal, a primeira transcrição baixa automaticamente o modelo multilíngue `faster-whisper-base` (cerca de 150 MB). A preparação da fala clonada também ocorre automaticamente no primeiro teste ou uso da voz personalizada. Ambos exigem internet apenas na primeira preparação.

> Se a captura de áudio não estiver disponível no WebView/Edge, o chat continua funcionando por texto e informa isso na própria tela.

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
├── scripts/            # inicializador automático do Windows
├── .env.example        # exemplo de variáveis de ambiente
├── main.py             # ponto de entrada
├── pyproject.toml      # configuração do projeto
├── requirements.txt    # dependências do ambiente Python
├── README.md           # documentação do projeto
└── uv.lock             # lockfile do projeto
```

## Solução de problemas

- **Falha ao baixar os modelos**: confirme que o Ollama está em execução antes de rodar `scripts\preparar-modelos.bat`.
- **Python não encontrado**: instale o Python 3.14 ou superior e tente novamente.
- **Ambiente virtual inválido**: delete a pasta `.venv` e rode `scripts\iniciar.bat` novamente.
- **Arquivo não indexa**: verifique se o arquivo está em um formato suportado, tem conteúdo legível e não está vazio.
