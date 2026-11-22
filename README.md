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
| **Assistente Python / Groq** | Executa no próprio Streamlit, recupera contexto no Supabase e gera respostas com a Groq. O modelo de embeddings fica em cache no servidor. |

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

## Assistente Python com Supabase e Groq

O botão de conversa fica no canto inferior direito após entrar na loja. Ele abre um painel pequeno com histórico da sessão, campo de perguntas, opção de nova conversa e fontes consultadas. A integração com Groq e o fluxo de contexto foram adaptados do projeto [Roger-dev-eng/ChatBot](https://github.com/Roger-dev-eng/ChatBot).

O chat chama funções Python dentro do próprio processo do Streamlit. A loja publicada funciona com o computador do desenvolvedor desligado, sem iniciar outros servidores.

### Preparar o banco e as chaves

1. No Supabase da FloraStore, execute [scripts/setup_vectors.sql](scripts/setup_vectors.sql) no **SQL Editor**, caso ainda não tenha feito isso. O script cria pgvector, a tabela `flora_knowledge`, o índice e a função `match_flora_knowledge`. A tabela tem RLS e acesso restrito à chave de serviço.
2. Nas configurações de API do Supabase, copie a chave **Secret** para `SUPABASE_SERVICE_KEY`. Preserve `SUPABASE_KEY`, que continua sendo a chave pública usada na autenticação administrativa.
3. Configure a chave da Groq como `GROQ_API_KEY`. Localmente, ela também pode continuar no `.env`. Na nuvem, cadastre-a em **Settings → Secrets**, pois o `.env` local não é enviado ao Cloud.

Acrescente estas configurações aos segredos existentes:

```toml
SUPABASE_SERVICE_KEY = "sua chave Secret do Supabase"
GROQ_API_KEY = "sua chave da Groq"
# Opcional: modelo habilitado na sua conta Groq
GROQ_MODEL = "qwen/qwen3.8-27b"
```

`SUPABASE_URL`, `MONGODB_URI` e `MONGODB_DATABASE` continuam sendo as configurações da loja. Nunca publique os arquivos de segredos no GitHub.

### Executar localmente ou no Cloud

As dependências do chat estão no `requirements.txt` principal. Para testar localmente:

```powershell
uv pip install --python .venv/Scripts/python.exe -r requirements.txt
.venv/Scripts/python.exe -m streamlit run streamlit_app.py
```

No Streamlit Cloud, publique o código atualizado e acrescente as chaves acima em **Manage app → Settings → Secrets**, preservando as conexões já existentes. O Cloud reinstala as dependências quando o `requirements.txt` muda. Use Python 3.12. Entre como cliente, abra o chat e pergunte **Quanto custa a zamioculca?** ou **Como funciona a compra?**.

### Busca vetorial e desempenho

O FastEmbed gera vetores de 384 dimensões com `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`. O primeiro envio de pergunta baixa e carrega o modelo; pode demorar mais. O serviço fica em `st.cache_resource`, compartilhando o modelo entre sessões e preservando as conversas somente na sessão de cada cliente. Ao reiniciar o aplicativo ou mudar as credenciais, o serviço é criado novamente. O catálogo e a tela de login não carregam o modelo antecipadamente.

Os vetores são persistidos no Supabase e continuam disponíveis após reinícios do Streamlit. A base inclui o catálogo do MongoDB e [assistant/knowledge.json](assistant/knowledge.json). A cada pergunta, o assistente compara os hashes dos documentos e sincroniza somente os trechos alterados. A busca combina similaridade vetorial com correspondência de nomes. Os preços atuais são lidos do MongoDB ao montar o contexto. O histórico de cada conversa é enviado à Groq com os trechos recuperados.

A utilização depende dos limites de recursos do Streamlit Cloud e das cotas da Groq. Se o modelo não puder ser carregado ou algum serviço externo falhar, o chat informa indisponibilidade sem impedir o uso do catálogo. Se faltar uma chave obrigatória, o campo de perguntas fica desabilitado. No vídeo, mostre as fontes no chat e os vetores em **Supabase → Table Editor → flora_knowledge**.

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
