# MedPage Back

API FastAPI da Plataforma de Revisao de ECG.

## Requisitos

- Python 3.11+
- Ambiente virtual Python

## Configuracao

Use `.env.example` como referencia quando precisar alterar banco, credenciais iniciais, CORS ou fonte de metadados. A aplicacao le variaveis do ambiente com `os.getenv`; portanto, exporte essas variaveis no shell ou carregue um arquivo `.env` pela sua ferramenta de execucao antes de subir a API.

Variaveis principais:

- `DATABASE_URL`: banco operacional da aplicacao. O default local e `sqlite:///./ecg_review.db`.
- `DATABASE_CONNECT_TIMEOUT_SECONDS`: timeout de conexao para PostgreSQL via psycopg2, limitado entre 1 e 30 segundos. O padrao e 5 segundos.
- `RESET_DATABASE_ON_STARTUP`: recria tabelas ao subir quando `true`. Use `false` como padrao seguro e habilite reset apenas em desenvolvimento local.
- `AUTH_SECRET_KEY`: chave usada para assinar tokens JWT. Troque fora do desenvolvimento local.
- `DEFAULT_USER_*` e `DEFAULT_ADMIN_*`: usuarios criados pela seed inicial quando configurados.
- `BP_ALLOWED_EMAIL_DOMAINS`: lista CSV de dominios aceitos para usuarios nao administradores.
- `METADATA_DATABASE_PATH`: caminho opcional para o SQLite externo de metadados extraidos dos ECGs. Caminhos relativos sao resolvidos a partir da raiz do back.
- `BACKEND_CORS_ORIGINS`: lista CSV de origens permitidas para o front.
- `BACKEND_CORS_ORIGIN_REGEX`: regex opcional para origens permitidas.

## Dados externos

A pasta `data/` dentro do back nao deve ser versionada. PDFs, arquivos compactados, imagens reais de ECG, agrupamentos de referencia e `metadata.db` devem ser tratados como dados externos ao repositorio.

Por padrao, o back procura metadados reais em:

```text
data/database/metadata.db
```

Para usar outro arquivo, configure:

```env
METADATA_DATABASE_PATH=C:/caminho/para/metadata.db
```

Se o arquivo nao existir, a seed usa dados simulados de desenvolvimento. Se o arquivo real existir e o banco operacional local ainda tiver a seed simulada, a seed remove os exames simulados conhecidos e importa os exames reais por `metadata_hash`.

O back usa ORM tambem para ler `metadata.db`, mas esse arquivo continua sendo uma fonte externa somente leitura para a aplicacao. O schema da tabela `metadata` nao e criado, migrado, resetado ou versionado por este repositorio; ele deve ser fornecido pronto pelo processo que gera os metadados.

## Rodar localmente

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

No Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

URLs locais:

- API: `http://localhost:8000`
- Swagger: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`
- OpenAPI JSON: `http://localhost:8000/openapi.json`

## Documentacao e testes pelo Swagger

O Swagger organiza os endpoints por sistema, autenticacao, validacao, suporte,
exames, diagnosticos e dashboard. O health check e as paginas de documentacao
sao publicos; os demais endpoints exigem um access token JWT do Amazon Cognito.

Para testar uma rota protegida:

1. Obtenha o access token pelo fluxo Cognito/Amplify da aplicacao.
2. Abra `http://localhost:8000/docs`.
3. Clique em `Authorize` e cole somente o token JWT no campo exibido.
4. Execute o endpoint desejado. O Swagger enviara o header
   `Authorization: Bearer <token>` automaticamente.

O back continua usando `OAuth2PasswordBearer` para extrair o token das
requisicoes. A obtencao de usuario e senha nao acontece no Swagger.

## Health check

Use `GET /health` para verificar se a API consegue abrir uma conexao com o
banco operacional:

```json
{
  "status": "ok",
  "database": "connected"
}
```

Quando o banco nao estiver acessivel, o endpoint retorna HTTP `503` com uma
mensagem sanitizada, sem expor detalhes da conexao.

## Testes

```bash
python -m unittest discover -s tests
```

## Login de desenvolvimento

No SQLite local padrao, a seed cria usuarios iniciais:

- Medico: `dr.joao` / `medpage123`
- Admin: `admin` / `admin123`

Em bancos que nao sejam o SQLite local padrao, defina explicitamente as senhas em `DEFAULT_USER_PASSWORD` e `DEFAULT_ADMIN_PASSWORD`.

## CORS

Por padrao, a API aceita o front local nas portas `5173`, `5174` e `5175`, alem de IPs locais `192.168.*` nessas portas.

Para configurar outro front:

```env
BACKEND_CORS_ORIGINS=https://front.exemplo.com,http://localhost:5173
BACKEND_CORS_ORIGIN_REGEX=
```
