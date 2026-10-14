# Registro alimentar e ajuste da meta

Branch de simplificacao: `fix/simplifica-detalhes-da-meta`.
Base da simplificacao: `1b25a6b`.
Branch original: `feat/registro-alimentar-e-ajuste-claro`.
Base anterior: `1eee189a972e387aedc4db5b1d9641f94413281c`.
Migracao adicional: `89c5e4e43a4b`; revisao anterior: `018ff10eff0a`.

## Comportamento

O cartao de Progresso destaca a manutencao estimada, a variacao semanal e a meta
atual, lado a lado com a sugestao quando ela esta disponivel para adocao.

Os requisitos, datas analisadas, explicacoes e atualizacao manual ficam dentro de
"Ver mais informacoes", fechado por padrao. A lista mostra somente dias sem
lancamento, abaixo do filtro ou com calorias nao informadas. O dia em andamento e
os dias aceitos nao aparecem nessa lista de pendencias. Os links abrem o diario
tradicional na data selecionada, sem pedir confirmacao do registro.

A Dieta usa o fluxo tradicional de alimentos, receitas e porcoes. Nao ha caixa de
revisao diaria nem formulario para criar refeicoes aproximadas. Quem ja criou
registros no formulario anterior pode consulta-los, edita-los e exclui-los em
"Lancamentos anteriores", que so aparece se houver esses dados e inicia fechado.
Nenhum registro e apagado ou convertido automaticamente.

Nao e necessario confirmar cada dia para adotar uma estimativa. Permanecem os
minimos de dados, os bloqueios de plausibilidade e a validacao no servidor antes de
adotar a manutencao. Anotacoes antigas sem calorias continuam bloqueando a adocao
ate serem corrigidas ou excluidas; nao sao transformadas em consumo zero.

As tabelas e endpoints anteriores de revisao/aproximacao sao mantidos para
compatibilidade com clientes em cache e preservacao do historico. Uma revisao
antiga ainda pode explicar como um dia de consumo baixo entrou no calculo, mas
nao e uma obrigacao nem uma nova etapa do diario. Hoje nao entra nas medias.

## Compatibilidade e reversao

Publicar apenas um branch nao altera a producao. O deploy e disparado pelo push
na `main`, depois do merge autorizado e das verificacoes de CI.

O diario original, seus enums e suas colunas permanecem intactos. Apenas duas
tabelas sao adicionadas: `diary_day_reviews` e `diary_estimates`. Os novos campos de
API sao adicionais. Os handlers de arrastar refeicoes nao foram modificados.

Para desfazer somente a simplificacao, restaure o codigo de `1b25a6b`: nao ha
nova migracao nem mudanca de schema nesta etapa. Para remover o recurso original
por completo e voltar a base anterior, use o procedimento abaixo.

Se esta versao ja tiver sido instalada em um ambiente:

1. Pare a API e preserve um backup do banco, conforme o procedimento desse ambiente.
2. Ainda com o codigo deste branch disponivel e com a URL do banco correto,
   execute em `backend`: `.venv/bin/alembic downgrade 018ff10eff0a` (use o ambiente
   virtual correspondente no servidor).
3. O downgrade **renomeia**, sem apagar, as duas tabelas novas para
   `diary_estimates_saved` e `diary_day_reviews_saved`. O historico legado nao muda.
4. Publique o backend e o frontend anteriores juntos e reinicie o servico.
   O codigo antigo nao mostra as aproximacoes/revisoes, mas elas ficam preservadas
   nas tabelas arquivadas. Os totais antigos voltam a considerar apenas o diario
   que aquela versao conhece; a reversao nao converte aproximacoes em alimentos.
5. Para reaplicar a funcionalidade, publique novamente este codigo e execute
   `alembic upgrade head`: as tabelas preservadas sao restauradas com seus dados.

Nao executar downgrade para uma revisao mais antiga que a indicada nem apagar as
tabelas `_saved`. Em um merge futuro, reverter apenas os arquivos sem coordenar a
revisao Alembic nao e suficiente: o codigo antigo nao conhece a revisao nova.

A interface tambem tolera o contrato anterior da API, para o caso de um navegador
ainda manter arquivos novos em cache durante a reversao. Os detalhes por data e a
revisao so aparecem quando a resposta os suporta; a adocao de uma meta fica
bloqueada nessa transicao. A compatibilidade e a volta ao contrato novo foram
verificadas no navegador com respostas antigas simuladas.

## Verificacao

Depois de aplicar a migracao local:

```sh
cd backend
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/alembic check
```

O CI executa os testes de integracao em PostgreSQL. As transacoes dos testes sao
desfeitas; nao dependem de dados pessoais ou de acesso ao servidor.

Para ensaiar reversao com dados, crie uma base PostgreSQL local **vazia e exclusiva**
com `_check_` no nome. Exporte sua URL em `GYMAPP_DATABASE_URL` e execute:

```sh
cd backend
.venv/bin/python scripts/check_diary_migration.py
```

O script recusa uma base ja preenchida e verifica migracao inicial, dados legados,
preservacao de aproximacoes/revisoes, downgrade, restauracao e alinhamento do schema.

No frontend, compilar Paraglide nos tres idiomas, executar `svelte-check` e build.
Na verificacao manual, cobrir datas locais, falha de atualizacao, confirmacao de
exclusao, edicao normal, compartilhamento/copia do diario legado, arrasto por mouse
e toque e persistencia da ordem apos recarregar.

Verificacoes do recurso original: 12 testes de integracao aprovados; endpoints novos por
curl; navegação por data, revisao, aproximacoes e exclusao no navegador; arrasto por
mouse e toque; ordem preservada depois de recarregar; recuperacao de falha de
atualizacao; migracao de ida e volta com preservacao dos dados. Foram usados apenas
registros ficticios locais nessas verificacoes.

Na simplificacao, foram aprovados no navegador: detalhes fechados por padrao, lista
restrita a pendencias, meta atual proxima aos indicadores, ausencia de validacao
diaria e do formulario sem balanca, preservacao e edicao dos registros anteriores.
Os gestos de arrastar nao foram repetidos nesta etapa, conforme solicitado. Os 13
testes de integracao passaram, incluindo adocao sem confirmacao diaria e bloqueio
preservado para anotacoes antigas sem calorias. Svelte-check e build aprovados.
