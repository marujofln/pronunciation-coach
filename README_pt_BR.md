[English](README.md)

# Pronunciation Coach

Um aplicativo web local para praticar a pronúncia do inglês. Escolha uma frase, grave você mesmo dizendo-a e receba feedback imediato: um modelo Whisper open source transcreve a gravação, e um pipeline de pontuação em nível de fonema compara o resultado com a frase-alvo para destacar exatamente quais palavras (e sons) você acertou ou errou.

## Recursos

- **Frases de prática** — banco de dados com 133 frases em inglês semeadas, distribuídas por níveis de dificuldade (fácil/médio/difícil) e 20 categorias, cada uma oferecendo as três dificuldades:
  - *conversa do dia a dia* — cumprimentos, small talk, comida, viagem, clima, trava-línguas
  - *registros profissionais* — tecnologia da informação, médico, jurídico, financeiro, negócios, educação, ciência, engenharia, atendimento ao cliente, entrevista de emprego, oratória
  - *exercícios de fonética* — pares mínimos (ship/sheep, think/sink), números e datas (thirteen/thirty), expressões idiomáticas
- **Speech-to-text** — [faster-whisper](https://github.com/SYSTRAN/faster-whisper) (`small.en`, CPU, int8) transcreve a gravação localmente, sem chamadas a APIs na nuvem.
- **Pontuação em nível de fonema** — tanto a frase-alvo quanto a sua transcrição são convertidas em fonemas ARPAbet ([g2p_en](https://github.com/Kyubyong/g2p)) e comparadas por distância de edição de fonemas, de modo que a pontuação reflita a precisão real da pronúncia, e não só "o Whisper entendeu as palavras". O feedback por palavra mostra os fonemas esperados vs. os ouvidos.
- **Ouça como deve soar** — um botão de falar reproduz a frase-alvo e, após a pontuação, você pode passar o mouse (ou tocar) em qualquer palavra do feedback para ouvir só aquela palavra — assim uma palavra mal pronunciada vem com uma referência, e não só com uma marca vermelha. Usa a Web Speech API nativa do navegador — sem serviço extra, sem chamada à nuvem, sem nova dependência.
- **Histórico de tentativas** — cada gravação, transcrição e pontuação é salva no PostgreSQL, com média acumulada e estatísticas por frase. Mudanças de schema são enviadas como migrações [Alembic](https://alembic.sqlalchemy.org/).
- **Preferências salvas** — a seleção de filtros de dificuldade e categoria é lembrada no navegador e restaurada na próxima visita, para você não precisar escolher de novo toda vez.
- **Sem contas, sem login** — é um app local de usuário único; não há cadastro e nenhum provedor de identidade para configurar.
- **Sem etapa de build** — o frontend é HTML/CSS/JS puro, servido diretamente pelo FastAPI.

Não é necessário GPU — o modelo padrão é ajustado para inferência em CPU.

## Começando (Docker, preferido)

A forma preferida de rodar o app é via Docker — não exige nada instalado localmente além do próprio Docker.

**Requisitos:** Docker e Docker Compose. A única configuração é uma senha de banco de dados, que não tem valor padrão — a stack se recusa a subir em vez de cair em algo adivinhável.

```bash
echo "POSTGRES_PASSWORD=$(openssl rand -base64 32 | tr -d '\n')" >> .env
echo "HOST_UID=$(id -u)" >> .env
echo "HOST_GID=$(id -g)" >> .env
docker compose up -d --build
```

O `.env` está no `.gitignore` e é específico da máquina. `HOST_UID`/`HOST_GID` fazem o container rodar como o seu usuário do host, e não como root, para que os arquivos gravados no diretório `data/` montado por bind (gravações salvas, caches de modelos) fiquem com a sua propriedade, e não de `root`.

O `docker compose up` sobe três serviços: `pronunciation-coach-db` (PostgreSQL), um `pronunciation-coach-migrate` de execução única que roda `alembic upgrade head` e encerra, e então o `pronunciation-coach` em si, só depois que a migração tiver concluído com sucesso. As migrações propositalmente *não* são aplicadas no startup do app, para que uma migração ruim falhe de forma visível no container de migrate em vez de deixar o app em crash-loop.

O banco fica em um volume nomeado do Docker (`pronunciation-coach-db-data`), não em `data/` — então, diferente do antigo arquivo SQLite, **`docker compose down -v` destrói o seu histórico de prática**. Um `docker compose down` simples não faz isso.

Abra <http://localhost:8000>, permita o acesso ao microfone e comece a gravar.

Na primeira execução, o app baixa o modelo Whisper (~150MB) e os dados `cmudict`/POS-tagger do nltk para `data/` (montado por bind a partir do host) — isso precisa de internet uma vez; depois disso tudo roda offline, inclusive após rebuilds de container.

Comandos úteis: `docker compose logs -f` (acompanhar logs), `docker compose down` (parar e remover o container), `docker compose up -d --build` (rebuild depois de mudar dependências ou código).

## Começando (nativo, para desenvolvimento)

Rodar nativamente com `uv` é mais rápido para iterar ao editar código, já que o `fastapi dev` oferece auto-reload.

**Requisitos:** Python 3.12+, [uv](https://docs.astral.sh/uv/), `ffmpeg` (usado na decodificação de áudio do faster-whisper) e um PostgreSQL acessível. O mais fácil de emprestar é o da stack de desenvolvimento, que publica na porta **55432** do host:

```bash
docker compose -f docker-compose.dev.yml up -d pronunciation-coach-db
export DATABASE_URL=postgresql+psycopg://pronunciation_coach:dev-insecure-app-postgres-password@127.0.0.1:55432/pronunciation_coach
```

```bash
uv sync
uv run alembic upgrade head   # aplique as migrações primeiro — o app não cria mais o próprio schema
uv run fastapi dev
```

O mesmo comportamento de download de modelo/nltk na primeira execução descrito acima, no mesmo diretório `data/` de qualquer forma. Para uma execução nativa no estilo produção (sem auto-reload): `uv run fastapi run`.

## Atualizando uma instalação local existente

Versões anteriores deste app guardavam os dados em um arquivo SQLite e, por um breve período, protegiam tudo atrás de um login OIDC do [Authentik](https://goauthentik.io/) com histórico por conta. Ambos foram removidos, e não há caminho de upgrade a partir de nenhum dos dois — recrie o banco:

```bash
docker compose down -v          # destrói o volume antigo; veja o aviso acima
rm -f data/pronunciation_coach.db
docker compose up -d --build
```

O serviço de migrate cria o schema e o app ressemeia as frases no startup. As gravações salvas em `data/audio/` permanecem intactas, mas as linhas de tentativa que as referenciavam não são migradas. Daqui em diante, mudanças de schema vêm como migrações Alembic (`uv run alembic upgrade head`), e não como "apague o seu banco".

A integração com Authentik não foi apagada, só não é enviada: ela vive no branch `auth-authentik` se você precisar autenticar um deployment compartilhado.

## Stack de desenvolvimento

Para desenvolvimento/teste local, o `docker-compose.dev.yml` sobe a mesma stack com segredos só de desenvolvimento embutidos — sem nenhuma configuração de `.env`.

```bash
git switch dev
docker compose -f docker-compose.dev.yml up -d --build
```

O serviço do app faz build da árvore de trabalho, e não de uma ref fixa, então a stack roda o que estiver no checkout — inclusive edições não commitadas. O trabalho do dia a dia cai no branch `dev`, por isso o trecho muda para ele primeiro; o `master` só recebe pushes solicitados explicitamente.

Ele também publica o Postgres na porta **55432** do host, que é o que a seção de desenvolvimento nativo acima empresta.

**Os segredos deste arquivo são placeholders hardcoded, não aleatórios e só de desenvolvimento de propósito** — seguros para commitar, seguros para compartilhar, e com nomes claros o bastante para não serem confundidos com algo real (`dev-insecure-...`). Nunca reutilize nenhum valor dele em um deployment real ou compartilhado; use o `docker-compose.yml` normal para isso. É uma duplicata completa e independente do `docker-compose.yml` (não uma camada de override), com nomes de volume próprios, para as duas stacks coexistirem na mesma máquina sem colidir — derrube uma (`docker compose [-f docker-compose.dev.yml] down`) antes de subir a outra se estiver alternando entre elas, já que as duas publicam a porta 8000 do host.

## Configuração

Toda a configuração é via variáveis de ambiente (veja `app/config.py`), definíveis nativamente ou no `docker-compose.yml`:

| Variável | Padrão | Finalidade |
| --- | --- | --- |
| `WHISPER_MODEL_SIZE` | `small.en` | tamanho do modelo faster-whisper (ex.: `base.en`, `medium.en`) |
| `WHISPER_COMPUTE_TYPE` | `int8` | tipo de compute do CTranslate2 |
| `PRONUNCIATION_COACH_DATA_DIR` | `./data` | diretório raiz das gravações salvas e dos caches de modelo/nltk (não o banco — esse é o Postgres) |
| `POSTGRES_HOST` / `POSTGRES_PORT` | `localhost` / `5432` | servidor do banco deste app |
| `POSTGRES_DB` / `POSTGRES_USER` | `pronunciation_coach` / `pronunciation_coach` | nome do banco e papel deste app |
| `POSTGRES_PASSWORD` | *(obrigatório, sem padrão)* | senha do banco do app |
| `DATABASE_URL` | *(não definida)* | URL completa do SQLAlchemy (ex.: `postgresql+psycopg://user:pw@host/db`). Quando definida, sobrescreve as cinco variáveis `POSTGRES_*` — a escapatória para um banco gerenciado, um socket unix ou parâmetros de conexão na query string |
| `HOST_UID` / `HOST_GID` | `1000` / `1000` | só Docker — UID/GID com que o container roda, para os arquivos montados por bind baterem com o usuário do host |

## Desenvolvimento

```bash
uv run pytest          # roda a suíte de testes
uv run ruff check .    # lint
uv run ruff format .   # formatação
```

A suíte de testes não precisa de setup de banco: sobe um `postgres:16-alpine` descartável via [testcontainers](https://testcontainers-python.readthedocs.io/) no primeiro uso, reinicia o schema e aplica as migrações. Só os testes que de fato tocam o banco disparam isso — os testes de frontend marcados com `frontend`, guiados pelo navegador, nunca sobem o Docker. Para rodar contra um Postgres já em execução (CI, ou repetições mais rápidas), defina `PRONUNCIATION_COACH_TEST_DATABASE_URL`; a suíte dropa e recria o schema `public` no início da sessão, e se recusa a tocar em um banco cujo nome não contenha `test`.

### Migrações

```bash
uv run alembic upgrade head                        # aplica migrações pendentes
uv run alembic revision --autogenerate -m "..."    # depois de editar app/models.py
uv run alembic check                               # verifica drift entre models e migrações
uv run alembic downgrade -1                        # desfaz uma revisão
```

O autogenerate compara `app/models.py` com o banco *ao vivo*, então aponte-o para um que já esteja em head. Sempre leia a revisão gerada antes de commitá-la — o autogenerate é um primeiro rascunho, não um oráculo. O `alembic check` também roda como teste (`app/tests/test_migrations.py`), então uma mudança de model sem migração falha a suíte em vez de aparecer como coluna ausente em runtime.

Veja `CLAUDE.md` para notas de arquitetura.

## Layout do projeto

```text
app/
├── main.py         # app FastAPI, lifespan de startup, wiring de routers/frontend
├── __init__.py      # naming convention de constraints do SQLModel (deve carregar antes dos models)
├── config.py         # caminhos e URL do banco via env
├── db.py              # engine/session do SQLModel
├── alembic/            # ambiente de migração + versions/
├── models.py            # models das tabelas Phrase, Attempt
├── schemas.py            # models de request/response da API
├── seed_data.py           # frases de prática embutidas
├── ml.py                   # carregamento dos models Whisper + G2p
├── scoring.py               # alinhamento de fonemas e algoritmo de pontuação
├── routers/                  # /api/phrases, /api/attempts
└── tests/                     # suíte pytest
frontend/
├── index.html
├── app.js            # gravação, envio, renderização de resultados, playback TTS
└── style.css
alembic.ini
Dockerfile
docker-compose.yml
docker-compose.dev.yml   # stack de dev independente com segredos só de desenvolvimento
```

## Licença

Este projeto está sob a licença BSD 3-Clause. Veja [LICENSE](LICENSE) para detalhes.
