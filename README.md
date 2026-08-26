# Cesta Solidária

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.46+-FF4B4B.svg)](https://streamlit.io)
[![Supabase](https://img.shields.io/badge/Supabase-PostgreSQL-3ECF8E.svg)](https://supabase.com)
[![Tests](https://img.shields.io/badge/tests-71%20passing-brightgreen.svg)]()
[![Deploy](https://img.shields.io/badge/Deploy-Streamlit%20Cloud-FF4B4B.svg)](https://streamlit.io/cloud)

Sistema de gestão de cestas básicas para projetos sociais e instituições de caridade. Controle de estoque, simulação de cestas, geração de lista de compras em PDF, histórico de compras e automação de preços via scraping do Tenda Atacado.

---

## Demonstração

| Página | Descrição |
|--------|-----------|
| **Login** | Autenticação segura com sessão persistente (30 dias) |
| **Dashboard** | Stats em tempo real, alertas inteligentes, ações rápidas |
| **Estoque** | CRUD completo, filtros, ordenação, import/export CSV |
| **Simulador** | Cálculo por estoque/orçamento, lista de compras, PDF |
| **Histórico** | Compras passadas, evolução de preços com gráficos |
| **Usuários** | Admin: gestão de voluntários e administradores |
| **Configurações** | Regiões Tenda, threshold de preço, ações admin |

---

## Stack Tecnológica

| Camada | Tecnologia |
|--------|------------|
| **Frontend** | Streamlit 1.46+ (multi-page nativo) |
| **Backend** | Python 3.11+ |
| **Banco/Auth** | Supabase (PostgreSQL + Auth + RLS) |
| **Automação** | GitHub Actions (cron diário/semanal) |
| **Deploy** | Streamlit Community Cloud (gratuito) |
| **Testes** | pytest (71 testes) |

---

## Deploy Rápido

### 1. Supabase (gratuito)
```bash
# No SQL Editor do Supabase, execute db/schema.sql
# Cria 6 tabelas + RLS + triggers + seed de 4 regiões
```

### 2. Variáveis de Ambiente

**Streamlit Cloud -> Settings -> Secrets:**
```toml
SUPABASE_URL = "https://SEU-PROJETO.supabase.co"
SUPABASE_ANON_KEY = "sua-anon-key-publica"
```
Criar/excluir usuários usa RPC `security definer` no banco com porteira de
`is_admin` - a SERVICE_ROLE_KEY não é necessária no app (só nos workflows
do GitHub).

**GitHub -> Settings -> Secrets -> Actions:**
| Secret | Valor |
|--------|-------|
| `SUPABASE_URL` | `https://SEU-PROJETO.supabase.co` |
| `SUPABASE_SERVICE_ROLE_KEY` | `sua-service-role-key` (privada, só GitHub Actions) |
| `BACKUP_KEY` | senha forte para cifrar o backup semanal (AES-256) |
| `TENDA_BEARER_TOKEN` | opcional; token público do site Tenda (tem fallback no código) |

### 3. Seed Inicial (produtos + regiões)
```bash
export SUPABASE_URL="https://SEU-PROJETO.supabase.co"
export SUPABASE_SERVICE_ROLE_KEY="sua-service-role-key"
python scripts/seed_from_csv.py
# Insere 26 produtos base + 4 regiões (Indaiatuba, Salto, Itu, Campinas)
```

### 4. Criar Primeiro Admin
1. Supabase Dashboard -> Authentication -> Users -> "Add user" (email/senha)
2. Copie o UUID gerado
3. SQL Editor:
```sql
INSERT INTO public.profiles (id, nome, is_admin)
VALUES ('<UUID_AQUI>', 'Administrador', true)
ON CONFLICT (id) DO UPDATE SET is_admin = true;
```

### 5. Streamlit Cloud
- New app -> Conecte este repo GitHub
- Main file: `app.py` -> Deploy
- Configure os secrets do passo 2

### 6. GitHub Actions
- Secrets já configurados no passo 2
- Workflows rodam automáticos:
  - `update-prices.yml`: todo dia 07:00 UTC (scraper + alerta falha com dedupe de issue)
  - `backup-db.yml`: domingo 04:00 UTC (backup JSON cifrado AES-256 + alerta falha com dedupe de issue)

---

## Estrutura do Projeto

```
cesta-solidaria/
├── app.py                      # Entry point + navegação multipage
├── requirements.txt            # Dependências produção
├── requirements-dev.txt        # Dependências dev (pytest, ruff)
├── pyproject.toml              # Config ruff + pytest
├── .streamlit/config.toml      # Tema Streamlit (cores, font)
├── pages/
│   ├── 0_Login.py              # Login dedicado (glassmorphism, SVG)
│   ├── 0_Dashboard.py          # Stats, alertas, ações rápidas
│   ├── 1_Estoque.py            # CRUD produtos + CSV
│   ├── 2_Simulador.py          # Simulação + PDF download
│   ├── 3_Historico.py          # Histórico + gráficos Plotly
│   ├── 4_Usuarios.py           # Admin: usuários/roles
│   └── 5_Config.py             # Admin: regiões, thresholds, ações
├── src/
│   ├── auth.py                 # Login/logout, sessão 24h/30d, JWT
│   ├── calc.py                 # Cálculos puros (testáveis)
│   ├── config.py               # Constantes, timezone SP, formatação
│   ├── csv_io.py               # CSV export/import + validação
│   ├── db.py                   # Supabase/PostgREST client (15+ funções)
│   ├── pdf.py                  # PDF via fpdf2 (lista de compras)
│   ├── scraper_tenda.py        # Scraper Tenda Atacado (Next.js parsing)
│   ├── secrets_loader.py       # Secrets unificado (st.secrets + env)
│   └── ui.py                   # Componentes reutilizáveis (HTML/CSS)
├── scripts/
│   ├── scraper_tenda.py        # Job diário GitHub Actions
│   ├── seed_from_csv.py        # Seed inicial produtos
│   └── backup_db.py            # Backup semanal JSON
├── db/schema.sql               # Schema completo (6 tabelas, RLS, triggers)
├── .github/workflows/
│   ├── update-prices.yml       # Cron diário + alerta falha
│   └── backup-db.yml           # Cron semanal + alerta falha
├── seed/produtos_initial.csv   # 26 produtos base (sem token_tenda)
├── assets/
│   ├── style.css               # Design system (variáveis, tema)
│   └── cesta.png               # Logo/favicon
└── tests/                      # 71 testes (auth, calc, csv, db, scraper, etc)
```

---

## Scripts Úteis

```bash
# Instalar dependências
pip install -r requirements.txt

# Rodar testes
pytest -q

# Rodar scraper local (precisa SUPABASE_URL + SERVICE_ROLE_KEY)
python scripts/scraper_tenda.py

# Gerar backup local
python scripts/backup_db.py

# Seed inicial local
python scripts/seed_from_csv.py
```

---

## Troubleshooting

| Problema | Solução |
|----------|---------|
| **Login falha "Email ou senha inválidos"** | Verifique se usuário existe no Supabase Auth E tem profile com `is_admin=true` (se admin) |
| **Scraper não atualiza preços** | Confira `token_tenda` nos produtos + `tenda_region_id` nas configurações + região existe no Tenda |
| **Erro "relation does not exist"** | Execute `db/schema.sql` no SQL Editor do Supabase |
| **Deploy falha no Streamlit Cloud** | Repo deve ser **público**; secrets devem estar em Settings -> Secrets (não no código) |
| **CSV import falha** | Colunas obrigatórias: `nome`, `qtd_por_cesta`, `estoque_atual` |
| **Sessão expira rápido** | Default: 24h. Com "Lembrar-me": 30 dias. Config em `src/auth.py` |

---

## Segurança

- **RLS (Row Level Security)** ativo em todas as tabelas; `is_admin` protegido por trigger (autenticado não altera o próprio papel)
- **Service Role Key** só no GitHub Actions e nas operações admin do app (server-side, nunca exposta ao navegador)
- **Anon Key** no Streamlit (pública; escrita limitada pelas políticas RLS)
- **Senhas** hasheadas pelo Supabase Auth
- **Sessão** 24h / 30 dias com renovação automática via refresh_token
- **Backup semanal cifrado** (AES-256, secret `BACKUP_KEY`) antes de virar artifact do repo público
- **Timeout** em todas as chamadas HTTP ao Supabase

### Restaurar backup

```bash
# 1. Decifrar (o checksum sha256 vem em stderr quando o backup roda)
openssl enc -d -aes-256-cbc -pbkdf2 -in backup.json.enc -out backup.json -pass env:BACKUP_KEY

# 2. Conferir integridade contra o checksum registrado na execucao
sha256sum backup.json

# 3. Recarregar tabelas via PostgREST/SQL Editor:
#    produtos, precos_historico, compras, regions, config.
#    profiles fica de fora por conter dados de contas.

# Limitacoes: artifact retido 30 dias; sem BACKUP_KEY os backups sao
# irrecuperaveis. Para segunda copia externa, baixe o artifact e guarde
# o .enc em outro lugar.
```

Nota: `compras` e legivel por qualquer usuario autenticado (politica
`select` aberta) - transparencia total entre voluntarios da equipe. Se
isso nao for desejado, restrinja a politica para `criado_por = auth.uid()`
ou admin-only.

---

## Contribuindo

```bash
# Fork -> Clone -> Branch
git checkout -b feat/nova-funcionalidade

# Código + Testes
pytest -q  # deve passar 71/71

# Commit descritivo (sem prefixos feat:/fix:)
git commit -m "adicionar exportação XLSX no estoque"

# Push -> PR
```

**Padrões:**
- Zero emojis no código/docs/commits
- Nomes em português (produto, não `product`)
- Testes primeiro (TDD)
- Tipagem onde possível

---

## Licença

MIT - Uso livre para projetos sociais, educacionais ou comerciais.

[![MIT License](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

---

## Créditos

Desenvolvido para gestão de cestas básicas em projetos sociais.
Inspirado na necessidade real de controle de estoque e custos para doações.

**Deploy oficial:** https://cesta-solidaria.streamlit.app/