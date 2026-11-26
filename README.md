# FloraStore — Catálogo de Plantas com Banco de Dados Vetorial integrado com IA

### Integrantes
- Roger Oliveira Feitosa
- Geovanny Mahtus Aguiar Silva

[Vídeo explicativo](https://drive.google.com/file/d/1ZxrPQADNfxri73jif-gs63HPZ-DR2U64/view?usp=sharing)

## Conteúdo

- [Descrição](#descrição)
- [Objetivo](#objetivo)
- [Funcionalidades](#funcionalidades)
- [Estrutura do projeto](#estrutura-do-projeto)
- [Explicação dos principais componentes](#explicação-dos-principais-componentes)
- [Arquitetura dos dados](#arquitetura-dos-dados)
- [Como executar localmente](#como-executar-localmente)
- [Como usar](#como-usar)
- [Como o assistente funciona](#como-o-assistente-funciona)
- [Deploy no Streamlit Cloud](#deploy-no-streamlit-cloud)
- [Demonstração do projeto](#demonstração-do-projeto)
- [Tecnologias utilizadas](#tecnologias-utilizadas)
- [Créditos](#créditos)

## Descrição

A **FloraStore** é uma aplicação web de catálogo e pedidos de plantas. O cliente pode pesquisar espécies, filtrar produtos por categoria, montar um carrinho e finalizar o pedido pelo WhatsApp. O administrador possui uma área restrita para cadastrar produtos e aproveitar informações botânicas e fotos do iNaturalist.

O projeto utiliza **Python** e **Streamlit**, com uma arquitetura de **banco de dados poliglota**: Supabase para autenticação e armazenamento vetorial, MongoDB para os produtos e Redis para cache. Um assistente com IA consulta o catálogo e uma base de conhecimento para responder perguntas sobre as plantas e o funcionamento da loja.

Acesse a aplicação: [FloraStore no Streamlit Cloud](https://florastore.streamlit.app/).

## Objetivo

Aplicar diferentes tecnologias de persistência em uma mesma aplicação, atribuindo a cada banco uma responsabilidade adequada ao seu modelo de dados. O sistema reúne autenticação administrativa, documentos de produtos, cache de consultas recentes e busca vetorial para apoiar o atendimento ao cliente.

## Funcionalidades

- Escolher entre acesso como cliente e login como administrador.
- Autenticar o administrador pelo Supabase e verificar sua permissão de acesso.
- Cadastrar plantas com nome, categoria, preço, imagem e descrição opcional.
- Pesquisar espécies pelo nome comum ou científico no cadastro administrativo.
- Preencher os nomes da planta e aproveitar uma foto licenciada ao selecionar uma espécie.
- Importar um catálogo inicial de até 30 espécies para o MongoDB.
- Buscar produtos por nome comum ou científico e filtrar por categoria.
- Exibir uma mensagem quando a planta não possui foto disponível.
- Adicionar e remover itens do carrinho, alterar quantidades e calcular o total.
- Consultar os produtos selecionados recentemente, com cache no Redis.
- Abrir o WhatsApp com o pedido formatado para revisão e envio pelo cliente.
- Conversar com um assistente em um painel flutuante, com histórico e fontes consultadas.

## Estrutura do projeto

```text
FloraStore/
├── .streamlit/
│   ├── config.toml             # Tema e configurações da interface
│   └── secrets.toml            # Credenciais locais; criado pelo usuário e ignorado pelo Git
├── flora/
│   ├── __init__.py
│   ├── auth.py                 # Autenticação e autorização administrativa
│   ├── assistant_widget.py     # Botão e painel do assistente
│   ├── inaturalist.py          # Busca de espécies e fotos
│   ├── products.py             # Modelo, validações, busca e cálculo dos pedidos
│   ├── settings.py             # Carregamento das configurações
│   └── storage.py              # Persistência dos produtos e cache de recentes
├── assistant/
│   ├── __init__.py
│   ├── groq_client.py          # Integração com a API da Groq
│   ├── knowledge.json          # Conteúdos e fontes da base de conhecimento
│   ├── rag.py                  # Embeddings, sincronização e busca no Supabase
│   └── service.py              # Coordenação da conversa com o contexto recuperado
├── scripts/
│   ├── grant_admin.sql         # Concessão da permissão administrativa
│   ├── seed_catalog.py         # Importação do catálogo inicial
│   └── setup_vectors.sql       # Tabela, índice e função de busca vetorial
├── streamlit_app.py            # Entrada da aplicação e composição das telas
├── style.css                   # Estilos e responsividade
├── requirements.txt            # Dependências Python
├── .gitignore
└── README.md
```

## Explicação dos principais componentes

### `streamlit_app.py`

Organiza a tela de entrada, o catálogo público, o carrinho e o painel administrativo. Integra os serviços de dados e atualiza a listagem do catálogo a cada cinco segundos para refletir novos cadastros.

### `flora/`

Reúne as regras da loja, a integração com o iNaturalist, a autenticação no Supabase, o acesso ao MongoDB e o cache no Redis. O módulo `products.py` trata os preços em centavos e monta a mensagem e o link do WhatsApp.

### `assistant/`

Concentra o processamento das perguntas, a recuperação do contexto no Supabase e a geração das respostas pela Groq. O painel de conversa fica em `flora/assistant_widget.py`, que chama esse serviço diretamente no processo do Streamlit.

### `scripts/`

Contém a importação das espécies iniciais e os scripts SQL de autorização administrativa e preparação do banco vetorial. Os arquivos SQL devem ser executados no projeto Supabase utilizado pela loja.

## Arquitetura dos dados

| Tecnologia | Responsabilidade |
| --- | --- |
| **Supabase Auth / PostgreSQL** | Autenticação por e-mail e senha e autorização pelo atributo `app_metadata.role`. A permissão é consultada novamente no Supabase antes de publicar um produto. |
| **MongoDB** | Armazenamento dos documentos na coleção `products`, com nomes, categoria, descrição, preço, imagem e dados de origem. |
| **Redis** | Cache dos oito últimos produtos adicionados ao carrinho por sessão, com validade de 24 horas após a última seleção. Também armazena a validação administrativa por até 30 segundos, sem guardar senhas ou tokens no cache. |
| **Supabase pgvector** | Armazenamento dos trechos e vetores na tabela `flora_knowledge` e busca por similaridade com a função `match_flora_knowledge`. |

O carrinho e o histórico de conversa ficam na sessão do Streamlit. A finalização abre uma mensagem no WhatsApp; a aplicação não processa pagamentos nem grava pedidos em uma coleção própria.

## Como executar localmente

### 1. Pré-requisitos

- Python **3.12**.
- [uv](https://docs.astral.sh/uv/) para criar o ambiente e instalar as dependências.
- Um projeto no Supabase, um cluster MongoDB Atlas e uma conexão Redis.
- Chave da Groq para habilitar o assistente.
- Número de WhatsApp da loja para habilitar a finalização do pedido.

### 2. Clonar o repositório e instalar as dependências

```powershell
git clone https://github.com/Roger-dev-eng/FloraStore.git
cd FloraStore
uv venv --python 3.12 .venv
uv pip install --python .venv/Scripts/python.exe -r requirements.txt
```

Se o ambiente `.venv` já existir, execute apenas a instalação das dependências.

### 3. Configurar as credenciais

Crie manualmente o arquivo `.streamlit/secrets.toml` com as configurações abaixo. Se o arquivo já existir, edite somente os valores necessários, preservando suas credenciais.

```toml
SUPABASE_URL = "https://SEU-PROJETO.supabase.co"
SUPABASE_KEY = "SUA_CHAVE_PUBLICA_DO_SUPABASE"
MONGODB_URI = "mongodb+srv://USUARIO:SENHA@SEU-CLUSTER.mongodb.net/?retryWrites=true&w=majority"
MONGODB_DATABASE = "florastore"
REDIS_URL = "rediss://USUARIO:SENHA@HOST:PORTA/0"
WHATSAPP_NUMBER = "55DDNUMERO"

# Configurações do assistente
SUPABASE_SERVICE_KEY = "SUA_CHAVE_SECRET_DO_SUPABASE"
GROQ_API_KEY = "SUA_CHAVE_DA_GROQ"

# Opcional: modelo habilitado na sua conta Groq
GROQ_MODEL = "qwen/qwen3.8-27b"
```

Use o número do WhatsApp com código do país, DDD e número, somente com dígitos. Para um Redis local sem TLS, utilize `redis://`; em uma conexão com TLS, use `rediss://`.

As configurações também podem ser fornecidas por variáveis de ambiente ou por um `.env` local. O `.env` e o `.streamlit/secrets.toml` são ignorados pelo Git. As variáveis de ambiente têm prioridade sobre os valores do TOML.

### 4. Preparar o Supabase

1. Copie a URL do projeto e a chave **Publishable**, ou a chave legada **anon**, para `SUPABASE_URL` e `SUPABASE_KEY`.
2. Em **Authentication → Users**, crie o usuário administrador com e-mail confirmado e senha.
3. Copie o UUID desse usuário. No SQL Editor, adapte a consulta de [scripts/grant_admin.sql](scripts/grant_admin.sql), substituindo o UUID presente no arquivo pelo UUID da sua conta, e execute.
4. Para habilitar o assistente, execute [scripts/setup_vectors.sql](scripts/setup_vectors.sql). Esse script prepara a tabela, o índice e a função de busca com pgvector.
5. Copie a chave **Secret**, ou a chave legada **service_role**, para `SUPABASE_SERVICE_KEY`. Essa chave é utilizada no servidor para acessar a base vetorial e deve permanecer privada.

O login administrativo utiliza a conta criada no Supabase. Não há usuário ou senha padrão no código.

### 5. Preparar o MongoDB e o Redis

No MongoDB Atlas, crie um usuário com acesso de leitura e escrita ao banco configurado e preencha `MONGODB_URI` com a conexão do driver Python. Caracteres reservados na senha precisam ser codificados na URI. Autorize o IP do computador em **Network Access** para executar e importar o catálogo localmente.

O script de importação cria o índice de ordenação da coleção `products`. Para o Redis, preencha `REDIS_URL` com a URL de conexão do seu serviço. Se o Redis estiver indisponível, a validação administrativa consulta diretamente o Supabase; o login continua sob responsabilidade do Supabase.

### 6. Importar as plantas e iniciar a aplicação

```powershell
.venv/Scripts/python.exe -m scripts.seed_catalog
.venv/Scripts/python.exe -m streamlit run streamlit_app.py
```

Acesse [http://localhost:8501](http://localhost:8501) no navegador. Para encerrar, pressione **Ctrl+C** no terminal.

A importação consulta o iNaturalist para cadastrar até 30 espécies. Ela pode ser repetida: os identificadores são estáveis e produtos já existentes não são sobrescritos. Os preços iniciais são exemplos definidos no script da FloraStore, não valores fornecidos pelo iNaturalist.

## Como usar

### Cliente

1. Na tela inicial, escolha **Entrar como cliente**.
2. Pesquise pelo nome comum ou científico e utilize o filtro de categoria.
3. Adicione plantas ao carrinho e consulte os produtos selecionados recentemente.
4. Abra **Carrinho**, ajuste as quantidades e confira o total.
5. Clique em **Comprar pelo WhatsApp**, revise a mensagem e envie o pedido para a loja.

### Administrador

1. Escolha **Entrar como administrador** e informe o e-mail e a senha cadastrados no Supabase.
2. Pesquise a planta pelo nome comum ou científico.
3. Selecione a espécie e clique em **Usar espécie** para preencher os nomes e aproveitar uma foto, quando disponível.
4. Confira os dados, informe o preço e publique o produto. A descrição é opcional; o cadastro manual também está disponível.
5. Volte ao catálogo do cliente para conferir o novo produto.

### Assistente

Após entrar na loja, clique no botão flutuante de conversa. Pergunte, por exemplo, **Quanto custa a zamioculca?** ou **Como funciona a compra?**. O painel permite consultar as fontes utilizadas e apagar o histórico com **Nova conversa**.

## Como o assistente funciona

1. O cliente envia uma pergunta pelo painel do Streamlit.
2. O serviço consulta os produtos no MongoDB e sincroniza os trechos novos ou alterados com a base vetorial do Supabase.
3. O FastEmbed gera o vetor da pergunta com o modelo multilíngue `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`, de 384 dimensões.
4. A busca combina similaridade vetorial e correspondência de nomes das espécies. Os preços atuais são acrescentados ao contexto a partir do MongoDB.
5. A Groq recebe a pergunta, o histórico recente e o contexto recuperado para gerar a resposta, apresentada no chat com suas fontes.

A base inclui os produtos e os conteúdos de [assistant/knowledge.json](assistant/knowledge.json). Os vetores ficam persistidos no Supabase. O modelo de embeddings é carregado na primeira pergunta e reutilizado com `st.cache_resource`, enquanto as conversas permanecem separadas por sessão.

O assistente executa no próprio Streamlit, inclusive no Cloud. A primeira pergunta pode demorar pelo download e carregamento do modelo. Seu funcionamento depende das configurações, das cotas da Groq e dos recursos disponíveis no servidor. Sem as chaves obrigatórias, o campo de perguntas fica desabilitado.

## Deploy no Streamlit Cloud

1. Envie o código atualizado para o GitHub.
2. Em [Streamlit Community Cloud](https://share.streamlit.io/), crie um aplicativo usando o repositório `Roger-dev-eng/FloraStore`, a branch `main` e o arquivo `streamlit_app.py`.
3. Selecione Python **3.12** nas configurações de implantação.
4. Preencha **Secrets** com as configurações da loja e do assistente. O `.env` e o arquivo local de segredos não são enviados automaticamente ao Cloud.
5. No MongoDB Atlas, autorize as conexões do Streamlit Cloud conforme a [documentação de endereços IP](https://docs.streamlit.io/deploy/streamlit-community-cloud/status).
6. Publique o aplicativo e confira o catálogo, o login administrativo, o carrinho e uma pergunta ao assistente.

Em um aplicativo já publicado, atualize as credenciais em **Manage app → Settings → Secrets**. Preserve as conexões existentes e mantenha as entradas do exemplo TOML no nível principal, antes de eventuais seções. Consulte os logs em **Manage app** se algum serviço falhar.

A aplicação publicada acessa os bancos e a Groq pela nuvem e pode funcionar com o computador do desenvolvedor desligado.

## Demonstração do projeto

Para a entrega acadêmica, grave um vídeo de **5 a 10 minutos** mostrando:

1. A entrada do cliente e a organização do catálogo.
2. O login do administrador pelo Supabase.
3. O cadastro de uma planta e sua atualização no catálogo público.
4. A montagem do carrinho e o cálculo do total.
5. O redirecionamento para o WhatsApp com o pedido formatado.
6. Como complemento, uma pergunta ao assistente e as fontes apresentadas na resposta.

Envie o link do repositório e o vídeo na Plataforma A. Verifique se o link da gravação está acessível antes de entregar e mantenha credenciais fora da gravação.

## Tecnologias utilizadas

| Tecnologia | Função |
| --- | --- |
| **Python** | Linguagem principal da aplicação |
| **Streamlit** | Interface, estado de sessão e execução do assistente |
| **Supabase Auth / PostgreSQL** | Identidade e autorização do administrador |
| **MongoDB Atlas / PyMongo** | Armazenamento e consulta dos produtos |
| **Redis** | Cache de produtos recentes e validação administrativa |
| **pgvector** | Armazenamento e busca por similaridade dos vetores no Supabase |
| **FastEmbed** | Geração local dos embeddings no servidor da aplicação |
| **Groq API** | Geração das respostas do assistente |
| **iNaturalist API** | Consulta de espécies e fotos com créditos |
| **HTTPX** | Requisições às APIs externas |
| **python-dotenv** | Leitura das configurações do `.env` local |
| **CSS** | Estilos e adaptação da interface a diferentes telas |
| **uv** | Criação do ambiente e instalação das dependências |
| **Streamlit Community Cloud** | Hospedagem da aplicação |

## Créditos

As informações botânicas e fotos são consultadas no [iNaturalist](https://www.inaturalist.org/). A integração utiliza fotos identificadas como **CC0** ou **CC BY**, com os respectivos créditos exibidos no catálogo.
