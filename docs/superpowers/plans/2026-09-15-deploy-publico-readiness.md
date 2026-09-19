# Deploy Publico Readiness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deixar o Cesta Solidaria pronto para deploy publico, corrigindo todo gap critico, importante e minor listado na auditoria de 2026-09-15.

**Architecture:** Mudancas cirurgicas por arquivo, sem reestruturação. Cada fix com teste primeiro quando houver logica testavel. Git via branch feature propria com PR para main. Parte operacional via checklist manual com evidencia.

**Tech Stack:** Python maior igual 3.11, Streamlit 1.46 mais, Supabase PostgREST mais Auth mais RLS, pytest, ruff, GitHub Actions, Streamlit Community Cloud.

**Spec:** README.md na raiz do repo, mais auditoria de deploy registrada no historico da sessao de 2026-09-15, mais db/schema.sql como fonte de verdade do banco.

## Global Constraints

- Texto visivel e mensagens de commit em pt-BR.
- Zero emojis em codigo, docs, commits, nomes de arquivo.
- TDD sempre: teste que falha primeiro, minimo para passar, refatorar com testes verdes.
- Antes de fechar cada task, rodar a ferramenta real do projeto: pytest menos q e ruff check ponto.
- Confirmar branch base antes de criar qualquer branch nova.
- Nunca commitar direto em branch compartilhada como main.
- Antes de qualquer push, verificar git branch menos menos show-current.
- Stage seletivo: apos git add menos p, commitar com git commit sem path.
- Nunca salvar token ou credencial em memoria ou arquivos do repo.
- Secrets so via st.secrets ou env, nunca hardcoded, com fallback documentado apenas para token publico do frontend Tenda.
- RLS admin-only para escrita, com leitura autenticada onde o schema define.
- Nomes de dominio em portugues no codigo.
- Uma linha de commit por mudanca, sem prefixo convencional, sem corpo salvo quando necessario.

---

## File Structure

Mapa do que cada task toca e por que.

- `pages/1_Estoque.py`, `pages/2_Simulador.py`, `pages/5_Config.py`: tree sujo atual. Task 1 congela esse diff em branch feature e leva a main via PR. Nenhuma logica nova aqui.
- `src/boot.py` novo mais `app.py`: Task 2 remove vazamento de stack trace no boot. boot.py tem uma responsabilidade: gerar mensagem generica de falha de boot e registrar detalhe em log. app.py so chama o helper.
- `src/ui.py` mais `tests/test_ui.py` novo: Task 3 fecha XSS pequeno no parametro variant de badge via allowlist com fallback neutro.
- `requirements.txt`: Task 4 trava versoes exatas validadas para o Cloud nao resolver versao nova a cada rebuild.
- `README.md`: Task 5 corrige duas divergencias contra o codigo real: graficos e seed com token_tenda.
- `SECURITY.md` novo, `.github/dependabot.yml` novo, `.github/ISSUE_TEMPLATE/bug_report.md` novo, `.github/pull_request_template.md` novo: Task 6 da ao repo publico canal de reporte e manutencao minima.
- `db/schema.sql` leitura apenas mais checklist operacional: Task 7 decide privacidade de compras e valida o deploy de ponta a ponta com evidencia. Schema so muda se o dono optar por restringir leitura de compras; o SQL da opcao restritiva vai completo na task.

Ordem de execucao: Task 1 primeiro para limpar o tree. Tasks 2 a 6 em sequencia. Task 7 por ultimo, com app ja final.

---

### Task 1: Congelar tree sujo em branch feature e levar a main via PR

**Files:**
- Modify: `pages/1_Estoque.py`
- Modify: `pages/2_Simulador.py`
- Modify: `pages/5_Config.py`

**Interfaces:**
- Consumes: nada de codigo, apenas estado atual do git.
- Produces: main com o diff atual aplicado via merge de PR, tree limpo para as tasks seguintes.

Contexto para o executor: o diff atual tem 7 insercoes e 7 remocoes. Em 1_Estoque.py, coercao numerica com pd.to_numeric antes de fillna e astype. Em 2_Simulador.py e 5_Config.py, troca de except Exception as e por except limpo onde a variavel nao era usada. Nada mais entra nesse commit.

- [ ] **Step 1: Confirmar base e estado atual**

```bash
git branch --show-current
git status --short
git log --oneline -3
```

- [ ] **Step 2: Ver o diff completo antes de mover qualquer coisa**

```bash
git diff pages/1_Estoque.py pages/2_Simulador.py pages/5_Config.py
```

Esperado: apenas os 3 arquivos, 7 insercoes, 7 remocoes, sem arquivo extra.

- [ ] **Step 3: Criar branch feature a partir da base confirmada**

```bash
git checkout -b fix/higiene-excecoes-estoque-simulador-config
git branch --show-current
```

- [ ] **Step 4: Stage seletivo e revisao do staged**

```bash
git add -p pages/1_Estoque.py pages/2_Simulador.py pages/5_Config.py
git diff --cached --stat
```

Esperado: 3 arquivos, 7 insercoes, 7 remocoes.

- [ ] **Step 5: Rodar verificacao real antes do commit**

```bash
ruff check .
python -m pytest -q
```

Esperado: ruff com All checks passed, pytest com 71 passed.

- [ ] **Step 6: Commit sem path**

```bash
git commit -m "higienizar excecoes nao usadas e coercao numerica no estoque"
git log --oneline -2
git status --short
```

- [ ] **Step 7: Push na branch feature e abrir PR para main**

```bash
git push -u origin fix/higiene-excecoes-estoque-simulador-config
```

Depois abrir PR no GitHub com titulo igual a mensagem do commit e descricao curta em pt-BR listando os 3 arquivos. Aguardar CI verde e merge. So prosseguir para a Task 2 com `git status --short` limpo na main atualizada.

---

### Task 2: Boot sem vazar stack trace

**Files:**
- Create: `src/boot.py`
- Modify: `app.py`
- Test: `tests/test_boot.py`

**Interfaces:**
- Consumes: nada de tasks anteriores alem de tree limpo.
- Produces: `src/boot.py` com `MENSAGEM_ERRO_BOOT: str` e `mensagem_erro_boot(exc: BaseException) -> str`, usados por `app.py` e pela Task 7 no smoke.

Por que helper separado: app.py executa Streamlit no import e nao da para testar direto com pytest. A logica testavel mora em src/boot.py, que usa so stdlib e nunca importa streamlit.

- [ ] **Step 1: Escrever o teste que falha**

```python
from src import boot


def test_mensagem_padrao_pt_br_sem_acento():
    assert boot.MENSAGEM_ERRO_BOOT == "Falha ao iniciar o app. Tente recarregar a pagina."


def test_helper_retorna_generico_e_nao_vaza_detalhe():
    try:
        raise RuntimeError("segredo-sensivel-123")
    except RuntimeError as exc:
        msg = boot.mensagem_erro_boot(exc)
    assert msg == boot.MENSAGEM_ERRO_BOOT
    assert "segredo-sensivel-123" not in msg
    assert "Traceback" not in msg
```

Salvar em `tests/test_boot.py`.

- [ ] **Step 2: Rodar o teste e ver falhar**

Run: `python -m pytest tests/test_boot.py -v`
Expected: FAIL com ModuleNotFoundError ou ImportError para src.boot.

- [ ] **Step 3: Criar implementacao minima**

```python
import traceback

MENSAGEM_ERRO_BOOT = "Falha ao iniciar o app. Tente recarregar a pagina."


def mensagem_erro_boot(exc: BaseException) -> str:
    traceback.print_exception(type(exc), exc, exc.__traceback__)
    return MENSAGEM_ERRO_BOOT
```

Salvar em `src/boot.py`. Detalhe vai para o log do servidor via print_exception, nunca para a tela.

- [ ] **Step 4: Rodar o teste e ver passar**

Run: `python -m pytest tests/test_boot.py -v`
Expected: PASS nos 2 testes.

- [ ] **Step 5: Aplicar o helper em app.py**

Trocar o bloco atual:

```python
import traceback

import streamlit as st

try:
    from src.ui import carregar_logo_b64, load_css
except Exception as e:
    st.error(f"Erro ao importar modulos: {e}")
    st.code(traceback.format_exc())
    st.stop()
```

Por:

```python
import streamlit as st

try:
    from src.ui import carregar_logo_b64, load_css
except Exception as erro:
    try:
        from src.boot import mensagem_erro_boot

        st.error(mensagem_erro_boot(erro))
    except Exception:
        st.error("Falha ao iniciar o app. Tente recarregar a pagina.")
    st.stop()
```

- [ ] **Step 6: Rodar suite completa e lint**

Run: `ruff check .`
Expected: All checks passed.

Run: `python -m pytest -q`
Expected: 73 passed, sendo 71 antigos mais 2 novos.

- [ ] **Step 7: Commit**

```bash
git add -p src/boot.py tests/test_boot.py app.py
git diff --cached --stat
git commit -m "ocultar stack trace da tela inicial de boot"
```

Conferir `git status --short` depois. Ficar atento: commit sem path apos add seletivo.

---

### Task 3: Fechar XSS pequeno no variant de badge

**Files:**
- Modify: `src/ui.py`
- Test: `tests/test_ui.py`

**Interfaces:**
- Consumes: nada de tasks anteriores.
- Produces: `badge(text, variant)` com allowlist e fallback neutro, coberto por testes usados como regressao.

Contexto para o executor: avatar escapa o size com html.escape, mas badge interpola variant cru no atributo class. Chamadas atuais usam primary, neutral, warning, error. A allowlist abaixo cobre esses mais success e info, que existem no design system do CSS. Qualquer outro valor cai para neutral.

- [ ] **Step 1: Escrever o teste que falha**

```python
from src import ui


def test_badge_escapa_texto():
    out = ui.badge("<script>alert(1)</script>", "primary")
    assert "<script>" not in out
    assert "&lt;script&gt;" in out


def test_badge_mantem_variant_valido():
    out = ui.badge("Adm", "primary")
    assert "badge-primary" in out


def test_badge_invalido_cai_para_neutro():
    out = ui.badge("X", 'neutral"><script>alert(1)</script>')
    assert "<script>" not in out
    assert "badge-neutral" in out
```

Salvar em `tests/test_ui.py`.

- [ ] **Step 2: Rodar o teste e ver falhar**

Run: `python -m pytest tests/test_ui.py -v`
Expected: FAIL, o terceiro teste falha porque o variant cru passa direto para o HTML.

- [ ] **Step 3: Implementacao minima em src/ui.py**

Trocar:

```python
def badge(text: str, variant: str = "neutral") -> str:
    """Gera HTML para badge."""
    return f'<span class="badge badge-{variant}">{html.escape(str(text))}</span>'
```

Por:

```python
_VARIANTES_BADGE = frozenset({"neutral", "primary", "success", "warning", "error", "info"})


def badge(text: str, variant: str = "neutral") -> str:
    """Gera HTML para badge."""
    seguro = variant if variant in _VARIANTES_BADGE else "neutral"
    return f'<span class="badge badge-{seguro}">{html.escape(str(text))}</span>'
```

- [ ] **Step 4: Rodar os testes e ver passar**

Run: `python -m pytest tests/test_ui.py tests/test_boot.py -v`
Expected: PASS em todos.

- [ ] **Step 5: Rodar suite completa e lint**

Run: `ruff check .`
Expected: All checks passed.

Run: `python -m pytest -q`
Expected: 76 passed, sendo 71 originais mais 2 de boot mais 3 de ui.

- [ ] **Step 6: Commit**

```bash
git add -p src/ui.py tests/test_ui.py
git diff --cached --stat
git commit -m "restringir variant de badge a lista fechada com fallback neutro"
```

---

### Task 4: Travar versoes de producao

**Files:**
- Modify: `requirements.txt`

**Interfaces:**
- Consumes: ambiente local com as dependencias instaladas.
- Produces: `requirements.txt` com pins exatos, validados pela Task 7 no smoke e pelo CI.

Contexto para o executor: hoje o arquivo usa faixas largas e o Cloud resolve a versao mais nova a cada rebuild. O objetivo e pinar streamlit, pandas, requests e fpdf2 nas versoes que passam nos testes agora. scripts/requirements.txt continua com faixas porque o job de Actions instala separado e o pin exato la engessaria o cron sem ganho.

- [ ] **Step 1: Instalar a partir do estado atual**

```bash
pip install -r requirements.txt
```

- [ ] **Step 2: Capturar versoes resolvidas**

```bash
pip freeze | grep -Ei "^(streamlit|pandas|requests|fpdf2)=="
```

Anotar as 4 linhas de saida. Exemplo de formato esperado, com numeros ilustrativos apenas para formato:

```text
streamlit==1.49.0
pandas==2.3.1
requests==2.32.3
fpdf2==2.8.2
```

Os numeros reais sao os que o comando acima imprimir na maquina do executor, nunca os do exemplo.

- [ ] **Step 3: Reescrever requirements.txt com os pins reais**

Conteudo final com exatamente 4 linhas, usando os numeros capturados no step 2:

```text
streamlit==X.Y.Z
pandas==X.Y.Z
requests==X.Y.Z
fpdf2==X.Y.Z
```

- [ ] **Step 4: Reinstalar do pin e rodar verificacao real**

```bash
pip install -r requirements.txt
ruff check .
python -m pytest -q
```

Expected: All checks passed e mesma contagem de testes da Task 3, sem skips novos.

- [ ] **Step 5: Commit**

```bash
git add -p requirements.txt
git diff --cached
git commit -m "travar versoes de producao testadas para o deploy"
```

Se o diff mostrar qualquer linha alem das 4 do requirements, parar e revisar antes de commitar.

---

### Task 5: Corrigir duas divergencias do README contra o codigo

**Files:**
- Modify: `README.md`

**Interfaces:**
- Consumes: nada de codigo novo.
- Produces: README fiel ao codigo, usado pela Task 7 como guia do smoke.

Divergencia A: estrutura lista Historico com graficos Plotly, mas o codigo usa st.line_chart nativo. Divergencia B: estrutura diz que seed/produtos_initial.csv vem sem token_tenda, mas o CSV atual traz token_tenda preenchido.

- [ ] **Step 1: Confirmar as divergencias com grep**

```bash
grep -n "Plotly" README.md pages/3_Historico.py
grep -n "token_tenda" README.md | head -5
head -2 seed/produtos_initial.csv
```

Esperado: Plotly aparece so no README, nunca em pages. token_tenda aparece no header do CSV.

- [ ] **Step 2: Corrigir linha do Historico na estrutura**

Trocar na secao de estrutura do README:

```text
│   ├── 3_Historico.py          # Histórico + gráficos Plotly
```

Por:

```text
│   ├── 3_Historico.py          # Histórico + gráficos line_chart nativo
```

- [ ] **Step 3: Corrigir linha do seed na estrutura**

Trocar:

```text
├── seed/produtos_initial.csv   # 26 produtos base (sem token_tenda)
```

Por:

```text
├── seed/produtos_initial.csv   # 26 produtos base (com token_tenda e termo_busca)
```

- [ ] **Step 4: Conferir diff e commitar**

```bash
git diff README.md
git add -p README.md
git commit -m "alinhar README com graficos e seed reais"
```

Diff esperado: 2 linhas trocadas, nada mais.

---

### Task 6: Higiene minima de repo publico

**Files:**
- Create: `SECURITY.md`
- Create: `.github/dependabot.yml`
- Create: `.github/ISSUE_TEMPLATE/bug_report.md`
- Create: `.github/pull_request_template.md`

**Interfaces:**
- Consumes: nada de codigo.
- Produces: canal de reporte de seguranca, updates automaticos de dependencias, templates de issue e PR.

Manter conteudo curto e em pt-BR. Nada de workflow novo, nada de bot novo.

- [ ] **Step 1: Criar SECURITY.md**

```markdown
# Segurança

## Reportar vulnerabilidade

Envie email para o mantenedor com titulo iniciando por RELATO SEGURANCA, descricao do impacto, passos de reproducao e versao ou commit afetado. Nao abra issue publica com exploit funcional antes da correcao.

## Escopo

App Streamlit mais Supabase com PostgREST, Auth e RLS, mais workflows de scraper diario e backup semanal deste repo.

## O que esperar

Confirmacao de recebimento em ate 7 dias. Correcao priorizada para vazamento de segredo, bypass de auth, elevacao para admin e exposicao de dados de contas. Credito ao relator nas notas da correcao, salvo pedido contrario.

## Regras de teste

Teste apenas contra sua propria conta e seu proprio projeto Supabase. Sem acesso a dados de terceiros, sem brute force contra o deploy oficial, sem scraping agressivo do Tenda fora do fluxo do app.
```

- [ ] **Step 2: Criar .github/dependabot.yml**

```yaml
version: 2
updates:
  - package-ecosystem: pip
    directory: /
    schedule:
      interval: weekly
      day: monday
      time: "09:00"
      timezone: America/Sao_Paulo
    open-pull-requests-limit: 3
    labels:
      - dependencies
  - package-ecosystem: github-actions
    directory: /
    schedule:
      interval: weekly
      day: monday
      time: "09:00"
      timezone: America/Sao_Paulo
    open-pull-requests-limit: 3
    labels:
      - dependencies
```

- [ ] **Step 3: Criar .github/ISSUE_TEMPLATE/bug_report.md**

```markdown
---
name: Bug
about: Relatar comportamento errado no app
title: "[BUG] "
labels: bug
---

## O que aconteceu

## Passos para reproduzir

1.
2.
3.

## Esperado

## Ambiente

- Pagina afetada:
- Navegador:
- Commit ou data do deploy:
```

- [ ] **Step 4: Criar .github/pull_request_template.md**

```markdown
## O que muda

## Como testado

- [ ] `ruff check .` passou
- [ ] `python -m pytest -q` passou
- [ ] Smoke manual na pagina afetada

## Risco e rollback

## Checklist

- [ ] Sem segredo no diff
- [ ] Sem emoji em codigo ou docs
- [ ] Branch feature propria, nunca main direto
```

- [ ] **Step 5: Validar YAML e commitar**

```bash
python -c "import yaml,glob; [yaml.safe_load(open(f)) for f in glob.glob('.github/dependabot.yml')]; print('yaml ok')"
git status --short
git add -p SECURITY.md .github/dependabot.yml .github/ISSUE_TEMPLATE/bug_report.md .github/pull_request_template.md
git diff --cached --stat
git commit -m "adicionar canal de seguranca e templates de repo publico"
```

Se PyYAML nao estiver instalado, instalar nao e necessario: pular a primeira linha e validar o arquivo por leitura atenta de indentacao com 2 espacos. O commit exige os 4 arquivos e nada mais.

---

### Task 7: Decisao de privacidade e smoke de deploy com evidencia

**Files:**
- Leitura: `db/schema.sql`
- Opcional, so se o dono optar por restringir: migration SQL nova em `db/migrations/0001_compras_leitura_restrita.sql`
- Nenhum codigo de app muda nesta task salvo a migration opcional.

**Interfaces:**
- Consumes: Tasks 1 a 6 concluidas e mergeadas na main.
- Produces: decisao registrada e deploy validado de ponta a ponta, ou lista de bloqueios com dono.

Contexto para o executor: hoje a politica compras leitura autenticado permite select para todo usuario logado. O README declara isso como transparencia intencional entre voluntarios. Para deploy publico com voluntarios externos, o dono precisa confirmar por escrito se mantem aberto ou restringe. Default e manter aberto. So criar a migration se o dono pedir restricao.

- [ ] **Step 1: Registrar a decisao de privacidade**

Perguntar ao dono, com pedido de permissao no formato obrigatorio do projeto, qual opcao vale:

- Opcao A, manter aberto: nenhum SQL novo. Registrar aceite em comentario da issue ou PR de deploy.
- Opcao B, restringir: criar `db/migrations/0001_compras_leitura_restrita.sql` com o conteudo exato abaixo e aplicar no SQL Editor do Supabase apos review.

```sql
drop policy if exists "compras leitura autenticado" on public.compras;

create policy "compras leitura propria ou admin"
  on public.compras for select to authenticated
  using (
    criado_por = (select auth.uid())
    or (select is_admin from public.profiles where id = auth.uid())
  );
```

Atenção: essa migration muda comportamento do Historico para voluntarios, que passam a ver so as proprias compras. Validar no smoke com duas contas.

- [ ] **Step 2: Confirmar base e segredos antes do smoke**

```bash
git branch --show-current
git status --short
git log --oneline -5
```

Checklist de segredos, todos fora do repo: SUPABASE_URL e SUPABASE_ANON_KEY na Cloud em Settings mais Secrets. SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, BACKUP_KEY e TENDA_BEARER_TOKEN opcional nos secrets de Actions do GitHub. BACKUP_KEY com senha longa gerada em gerenciador, com copia guardada fora do GitHub. schema.sql aplicado no SQL Editor. Seed rodado com `python scripts/seed_from_csv.py`. Primeiro admin criado via Authentication mais update de profiles com is_admin true.

- [ ] **Step 3: Smoke no app com duas contas**

Executar na URL da Cloud, nessa ordem, anotando evidencia de cada item:

1. Login voluntario e login admin funcionam, senha errada nega sem detalhar motivo.
2. Logout encerra e redireciona para login. Rota direta de pagina interna sem sessao volta para login.
3. Dashboard carrega stats e sugestoes sem erro.
4. Estoque: criar, editar, filtrar, ordenar, exportar CSV, importar CSV valido e invalido.
5. Simulador: simular por estoque e por orcamento, gerar PDF e baixar, salvar calculo.
6. Historico: compra salva aparece, filtros e ordenacao funcionam, graficos rendem com 2 compras ou mais.
7. Usuarios como admin: criar voluntario, criar admin, excluir outro usuario, tentativa de excluir a propria conta nega. Como voluntario, acesso a pagina nega.
8. Config como admin: trocar regiao ativa, salvar limite de dias, gerar backup e baixar, seed com ignore_duplicates sem destruir estoque, descoberta de tokens em um produto de teste.
9. Boot sem segredo: forcar falha temporaria de import em staging nunca em prod, ou revisar que nenhuma tela exibe stack trace.

- [ ] **Step 4: Smoke nos workflows**

Disparar `Atualizar preços Tenda` via workflow_dispatch e conferir scraper com ao menos um produto atualizado ou issue de falha aberta sem dupe. Disparar `Backup semanal do banco` via workflow_dispatch e conferir release com asset backup.json.enc mais artifact de 30 dias. Testar restore local com openssl usando BACKUP_KEY e conferir sha256 contra o checksum do log.

- [ ] **Step 5: Registrar resultado e travar deploy**

Se tudo passou: anotar URL oficial, commit da main validado e data do smoke na descricao da release ou PR de deploy. Se algo falhou: abrir issue com titulo, log relevante sem segredo, e dono de cada item. Nenhum commit de codigo nesta task, salvo a migration opcional da Opcao B, que segue o mesmo ritual de verificacao: aplicar em staging, repetir smoke do Historico com duas contas, commitar em branch feature propria com PR.

---

## Self-Review

Cobertura da auditoria: tree sujo na Task 1. Stack trace no boot na Task 2. Badge variant na Task 3. Pins de requirements na Task 4. Divergencias README na Task 5. SECURITY, dependabot e templates na Task 6. Segredos, seed, admin, smoke de app e workflows, decisao de compras e restore de backup na Task 7. Bearer hardcoded do Tenda coberto como risco documentado com renovacao manual e alerta via issue, sem codigo novo por ser token publico do frontend com fallback declarado. Observabilidade sem Sentry aceita para o porte do projeto, com logs info e alertas de workflow.

Scan de placeholders: nenhum TBD ou similar. Todo step de codigo traz conteudo exato. Unica variavel proposital sao os numeros de versao da Task 4, que o executor captura com comando deterministico em vez de valor inventado.

Consistencia de tipos: mensagem_erro_boot recebe BaseException e retorna str. badge mantem assinatura text mais variant com retorno str. Migration usa nomes de policy e colunas iguais aos do schema. Nomes de branch e mensagens de commit em pt-BR sem prefixo convencional.
