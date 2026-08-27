# MedPage Back

API FastAPI da Plataforma de Revisao de ECG.

## Requisitos

- Python 3.11+
- Ambiente virtual Python

## Configuracao

Use `.env.example` como referencia quando precisar alterar banco, credenciais iniciais, CORS ou fonte de metadados. A aplicacao le variaveis do ambiente com `os.getenv`; portanto, exporte essas variaveis no shell ou carregue um arquivo `.env` pela sua ferramenta de execucao antes de subir a API.

Variaveis principais:

- `DATABASE_URL`: banco operacional da aplicacao. O default local e `sqlite:///./ecg_review.db`.
- `RESET_DATABASE_ON_STARTUP`: recria tabelas ao subir quando `true`. Use `false` como padrao seguro e habilite reset apenas em desenvolvimento local.
- `AUTH_SECRET_KEY`: chave usada para assinar tokens JWT. Troque fora do desenvolvimento local.
- `DEFAULT_USER_*` e `DEFAULT_ADMIN_*`: usuarios criados pela seed inicial quando configurados.
- `BP_ALLOWED_EMAIL_DOMAINS`: lista CSV de dominios aceitos para usuarios nao administradores.
- `METADATA_DATABASE_PATH`: caminho opcional para o SQLite externo de metadados extraidos dos ECGs. Caminhos relativos sao resolvidos a partir da raiz do back.
- `AI_MODE_ENABLED`: override operacional opcional do modo IA informativo. Aceita `true`/`false`, `1`/`0`, `yes`/`no` ou `on`/`off`.
- `BACKEND_CORS_ORIGINS`: lista CSV de origens permitidas para o front.
- `BACKEND_CORS_ORIGIN_REGEX`: regex opcional para origens permitidas.

## Modo IA informativo

As recomendacoes simuladas sao versionadas em `app/config/ai_recommendations.json` e ficam desabilitadas por padrao. Cada entrada associa um `exam_code` a diagnosticos padronizados que ja devem existir no exame:

```json
{
  "enabled": false,
  "suggestions": [
    {
      "exam_code": "A03B5F",
      "standard_diagnoses": ["Ritmo sinusal"]
    }
  ]
}
```

Quando habilitado no arquivo ou por `AI_MODE_ENABLED=true`, `GET /validation/context` informa `ai_mode_enabled` e os payloads de diagnostico informam `ai_suggested`. O pareamento usa o codigo do exame e a mesma padronizacao canonica aplicada pela validacao.

A IA e somente informativa: ela nao cria diagnosticos, nao persiste inferencias e nao altera as decisoes medicas de concordancia ou discordancia. Arquivo ausente, formato invalido ou override desconhecido desabilitam o modo com seguranca. O rollout recomendado e publicar este backend antes do frontend, que trata campos ausentes como `false`.

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
- OpenAPI JSON: `http://localhost:8000/openapi.json`

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
