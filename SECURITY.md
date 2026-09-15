# Segurança

## Reportar vulnerabilidade

Envie email para o mantenedor com titulo iniciando por RELATO SEGURANCA, descricao do impacto, passos de reproducao e versao ou commit afetado. Nao abra issue publica com exploit funcional antes da correcao.

## Escopo

App Streamlit mais Supabase com PostgREST, Auth e RLS, mais workflows de scraper diario e backup semanal deste repo.

## O que esperar

Confirmacao de recebimento em ate 7 dias. Correcao priorizada para vazamento de segredo, bypass de auth, elevacao para admin e exposicao de dados de contas. Credito ao relator nas notas da correcao, salvo pedido contrario.

## Regras de teste

Teste apenas contra sua propria conta e seu proprio projeto Supabase. Sem acesso a dados de terceiros, sem brute force contra o deploy oficial, sem scraping agressivo do Tenda fora do fluxo do app.
