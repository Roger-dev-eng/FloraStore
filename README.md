# FloraStore

Catálogo público de plantas com busca, filtros, carrinho e finalização pelo WhatsApp. No painel administrativo, busque uma planta pelo nome comum ou científico, selecione o resultado e clique em **Usar espécie** para preencher os nomes da planta e aproveitar uma foto licenciada, quando disponível. O administrador define o preço de cada novo cadastro. A descrição é opcional. Também é possível cadastrar a planta manualmente.

Na tela inicial, **Entrar como cliente** abre o catálogo como visitante. Digite um nome popular ou científico em **Buscar plantas** e use **Categoria** para refinar os resultados. **Entrar como administrador** abre o formulário de login do Supabase. Quando o catálogo do cliente está vazio ou indisponível, ele exibe exemplos do iNaturalist. Use **Trocar acesso** ou **Sair** para retornar à tela inicial.

## Arquitetura dos dados

| Tecnologia | Responsabilidade |
| --- | --- |
| **Supabase Auth / PostgreSQL** | Login por e-mail e senha, identidade e autorização do administrador. A permissão fica em `app_metadata.role` e é consultada diretamente no Supabase antes de publicar um produto. |
| **MongoDB** | Fonte do catálogo. Cada documento contém nome, categoria, descrição, preço em centavos e, quando disponíveis, origem botânica e créditos da foto. Cadastros manuais também guardam o identificador Supabase de quem os criou. |
| **Redis** | Lista os oito últimos produtos adicionados por sessão anônima durante 24 horas após a última seleção. Também guarda a validação da sessão administrativa por até 30 segundos, usando um hash do token como chave e sem salvar senhas ou tokens no cache. Se o Redis estiver indisponível, o painel consulta o Supabase diretamente. |
| **Streamlit** | Interface pública e painel. O carrinho vive na sessão do navegador. O catálogo aberto consulta o MongoDB a cada cinco segundos para refletir novos produtos. |
| **iNaturalist** | Fonte externa de espécies e fotos. O catálogo lê os produtos do MongoDB após a importação. Os preços e nomes comerciais iniciais são exemplos da FloraStore. |
| **Supabase pgvector** | Armazena embeddings e trechos dos produtos e da base de conhecimento. A função `match_flora_knowledge` faz busca por similaridade do cosseno. |
| **n8n local** | Recebe perguntas, aciona a recuperação vetorial, aciona a geração com Groq e devolve a resposta ao chat da loja. |

O botão de compra abre o WhatsApp com quantidades, subtotais e total. O cliente revisa e envia a mensagem no WhatsApp.

## Configuração dos serviços

### Supabase

1. Crie um projeto e copie a URL e a chave **Publishable** em **Project Settings → API Keys**. Use-as em `SUPABASE_URL` e `SUPABASE_KEY`.
2. Em **Authentication → Users**, crie uma conta de teste com e-mail e senha e confirme seu e-mail.
3. Copie o UUID do usuário, substitua o UUID de exemplo em [scripts/grant_admin.sql](scripts/grant_admin.sql) e execute a consulta no **SQL Editor**. Faça login no painel com essa conta.

A aplicação usa o banco PostgreSQL gerenciado pelo Supabase por meio do Supabase Auth. Guarde a senha da conta de teste separadamente. [Documentação do Supabase Auth](https://supabase.com/docs/guides/auth/users)

### MongoDB Atlas

1. Crie um cluster e um usuário de banco com permissão `readWrite` no banco `florastore`.
2. Copie a URI de conexão do driver Python para `MONGODB_URI`. Codifique caracteres reservados na senha antes de colocá-la na URI.
3. Na lista de acesso de rede, autorize o IP da sua máquina para testar e importar o catálogo. Para publicar, adicione os IPs do Streamlit Community Cloud conforme a documentação atual. [Lista de IPs do Streamlit](https://docs.streamlit.io/deploy/streamlit-community-cloud/status) · [Acesso de rede do Atlas](https://www.mongodb.com/docs/atlas/security/ip-access-list/)

### Redis e WhatsApp

1. Em um Redis gerenciado, copie a URL do endpoint para `REDIS_URL`. Use `rediss://` para conexões TLS e `redis://` para desenvolvimento local sem TLS.
2. Em `WHATSAPP_NUMBER`, informe o número da loja em formato internacional, com código do país e DDD. O checkout ficará indisponível enquanto o campo estiver vazio.

### Executar localmente

No PowerShell, use o [uv](https://docs.astral.sh/uv/getting-started/installation/) a partir da raiz do repositório. Se `.venv` já existir, use o ambiente existente.

```powershell
if (-not (Test-Path .venv/Scripts/python.exe)) {
    uv venv --python 3.12 .venv
}
uv pip install --python .venv/Scripts/python.exe -r requirements.txt
if (-not (Test-Path .streamlit/secrets.toml)) {
    Copy-Item .streamlit/secrets.example.toml .streamlit/secrets.toml
}
```

Preencha `.streamlit/secrets.toml` com as credenciais. O Git ignora esse arquivo. As mesmas chaves também podem ser fornecidas como variáveis de ambiente.

```powershell
# Importa 30 espécies iniciais e cria o índice de ordenação no MongoDB
.venv\Scripts\python.exe -m scripts.seed_catalog

# Inicia a aplicação
.venv\Scripts\python.exe -m streamlit run streamlit_app.py
```

A importação pode ser repetida. Cada espécie importada tem um identificador estável baseado no iNaturalist. O script só insere produtos ausentes e só aproveita fotos marcadas como CC0 ou CC BY. Os respectivos créditos aparecem no catálogo. [API do iNaturalist](https://api.inaturalist.org/v1/docs/)

## Assistente local com n8n e RAG

O botão de conversa fica no canto inferior direito após entrar na loja. Ele abre um painel pequeno com histórico da sessão, campo de perguntas, opção de nova conversa e fontes consultadas. A integração com Groq e o fluxo de contexto foram adaptados do projeto [Roger-dev-eng/ChatBot](https://github.com/Roger-dev-eng/ChatBot).

O serviço Python usa FastEmbed para gerar vetores de 384 dimensões com o modelo multilíngue `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`. O primeiro uso baixa o modelo. Os vetores são persistidos na tabela `flora_knowledge` do Supabase. A base inclui o catálogo do MongoDB e os conteúdos de [assistant/knowledge.json](assistant/knowledge.json), com suas fontes. A busca combina similaridade vetorial com correspondência de nomes para perguntas sobre espécies específicas. O catálogo é sincronizado antes de cada busca. Preços são lidos do MongoDB ao compor o contexto da resposta.

### Preparar o Supabase e as chaves

1. No projeto Supabase da FloraStore, abra **SQL Editor**, cole [scripts/setup_vectors.sql](scripts/setup_vectors.sql) e execute. O script cria a extensão pgvector, a tabela, o índice e a função de busca. A tabela fica com RLS habilitado e acesso pelo serviço local.
2. Em **Settings → API Keys**, copie a chave **Secret** e acrescente `SUPABASE_SERVICE_KEY = "sb_secret_..."` ao `.streamlit/secrets.toml` local. Mantenha as conexões existentes. O [modelo das chaves do assistente](.streamlit/assistant.example.toml) mostra os nomes esperados.
3. Instale as dependências do serviço local e prepare a configuração.

```powershell
uv pip install --python .venv/Scripts/python.exe -r requirements-assistant.txt
.venv/Scripts/python.exe -m scripts.configure_assistant
```

O script gera uma chave para a comunicação local, preenche o webhook no arquivo de segredos e cria `.assistant_data/n8n/credentials.json`. Se o repositório `ChatBot` estiver ao lado da FloraStore, reaproveita sua chave Groq em um `.env` local. Caso contrário, configure `GROQ_API_KEY` nesse arquivo usando [.env.assistant.example](.env.assistant.example). O Git ignora os arquivos locais com chaves.

### Iniciar e configurar o n8n

Com o Docker Desktop aberto, execute na raiz da FloraStore.

```powershell
docker compose up -d n8n
docker compose exec -T n8n n8n import:credentials --input=/files/private/credentials.json
docker compose exec -T n8n n8n import:workflow --input=/files/workflows/florastore-assistant.json
docker compose exec -T n8n n8n publish:workflow --id=FloraAssistantRag
```

Abra [n8n local](http://localhost:5678). Na primeira abertura, configure sua conta local de proprietário. O fluxo **FloraStore - Assistente com Supabase pgvector e Groq** possui quatro etapas visíveis.

1. **Pergunta do cliente** recebe um POST autenticado no caminho `/webhook/florastore-assistant`.
2. **Buscar vetores no Supabase** chama o serviço Python, que gera o embedding da pergunta e consulta `match_flora_knowledge`.
3. **Gerar resposta com Groq** usa os trechos recuperados como contexto para gerar a resposta.
4. **Responder ao cliente** devolve o texto e as fontes ao Streamlit.

Os nós usam a credencial **FloraStore local** importada pelo comando acima. As etapas HTTP chamam `http://host.docker.internal:8001`, que aponta do contêiner para o serviço Python no Windows. Na aba **Executions**, você pode inspecionar os trechos, os resultados da busca e a resposta para demonstrar o RAG.

### Iniciar o assistente e a loja

Em um terminal, inicie o serviço do RAG.

```powershell
.venv/Scripts/python.exe -m uvicorn assistant.server:app --host 0.0.0.0 --port 8001
```

Confira [a saúde do serviço](http://localhost:8001/health). Quando `ready` for `true`, a base vetorial estará pronta. Se aparecer `HTTPStatusError`, confira a chave Secret, a execução do SQL e os acessos do projeto Supabase. Se o serviço indicar `ValueError` ao iniciar, revise os nomes das chaves listados no terminal. Reinicie o serviço após corrigir uma configuração.

Em outro terminal, abra a loja local.

```powershell
.venv/Scripts/python.exe -m streamlit run streamlit_app.py
```

Entre como cliente, clique no balão de conversa e pergunte, por exemplo, **Quanto custa a zamioculca?** ou **Como funciona a compra?**. No vídeo, mostre as fontes no chat, a execução do n8n e os vetores em **Supabase → Table Editor → flora_knowledge**.

Essa configuração conecta a loja local ao n8n do computador. Para usar o assistente a partir da loja no Streamlit Cloud, será necessário disponibilizar o webhook local por uma URL HTTPS acessível pela nuvem e configurar essa URL em `N8N_WEBHOOK_URL` nos Secrets do Cloud, junto de `ASSISTANT_API_KEY`. O computador e os dois serviços locais precisam permanecer ligados.

Para parar o n8n, execute `docker compose stop n8n`. Para iniciar novamente, use `docker compose up -d n8n`. Os fluxos e a conta permanecem no volume Docker `n8n_data`.

## Publicar no Streamlit Community Cloud

1. Em [Streamlit Community Cloud](https://share.streamlit.io/), entre com a conta que tem acesso ao repositório do projeto no GitHub. Selecione **Create app**.
2. Selecione `Roger-dev-eng/FloraStore`, branch `main` e arquivo `streamlit_app.py`.
3. Abra **Advanced settings**, selecione Python 3.12 e cole o conteúdo do arquivo local de segredos no campo **Secrets**.
4. Clique em **Deploy**. Abra a URL gerada e confirme que o catálogo carrega, que o administrador consegue entrar e que adicionar um produto faz aparecer a seção **Selecionados recentemente**. [Guia de publicação](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/deploy) · [Configuração dos segredos](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/secrets-management)

## Roteiro do vídeo de demonstração

Grave de 5 a 10 minutos. Use sua conta administrativa de teste e mantenha senhas e chaves fora da gravação.

| Tempo sugerido | O que mostrar |
| --- | --- |
| 0:00–0:50 | Mostre as duas opções da tela inicial, entre como cliente e explique o papel de Supabase, MongoDB e Redis. |
| 0:50–1:45 | Em outra janela, escolha **Entrar como administrador**, faça login e mostre o painel de cadastro. |
| 1:45–3:15 | Consulte uma espécie no iNaturalist, clique em **Usar espécie**, informe a categoria e o preço e publique. Volte à janela do cliente e mostre a planta recém-cadastrada. |
| 3:15–4:45 | Adicione dois produtos, mostre a lista de recentes, altere uma quantidade e confira o total. |
| 4:45–5:30 | Clique em **Comprar pelo WhatsApp** para mostrar o redirecionamento e o texto preenchido. Encerre a simulação nessa etapa. |

Na Plataforma A, envie o link do repositório e anexe o vídeo ou o link da gravação. Teste o link do vídeo em uma janela anônima antes de entregar.
