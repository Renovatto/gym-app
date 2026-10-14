# Registro alimentar e ajuste da meta

Branch: `feat/registro-alimentar-e-ajuste-claro`.
Base anterior: `1eee189a972e387aedc4db5b1d9641f94413281c`.
Migracao adicional: `89c5e4e43a4b`; revisao anterior: `018ff10eff0a`.

## Comportamento

O cartao de Progresso conserva os requisitos visiveis depois do primeiro calculo,
informa quais dias foram considerados e permite abrir o diario na data escolhida.
Uma estimativa bloqueada nao aparece como uma recomendacao verde. A origem da meta
atual e mostrada separadamente da estimativa calculada agora.

Em Dieta, "Registro do dia" permite declarar que tudo foi registrado ou que ainda
faltam informacoes. Alterar alimentos, aceitar compartilhamentos, copiar refeicoes
ou alterar aproximacoes invalida a revisao quando muda o conteudo revisado. Uma
assinatura do conteudo evita espalhar essa regra por todos os caminhos de escrita.
Uma revisao enviada sobre conteudo desatualizado e recusada com `DIARY_CHANGED`.

Refeicoes aproximadas permitem informar a referencia das calorias por porcao ou
guardar apenas uma anotacao. Energia desconhecida continua desconhecida; os totais
conhecidos sao identificados como parciais. Nao sao inventados macronutrientes.
As sugestoes para fechar metas e a pontuacao de proteina nao tratam esses valores
ausentes como zero. As aproximacoes ficam separadas das refeicoes do cadastro e
nao sao copiadas nem compartilhadas automaticamente. A interface informa isso.

Nao ha um novo limite arbitrario de refeicoes. Os minimos para **calcular** seguem
centralizados no servico adaptativo. Para **adotar**, todos os dias alimentares
encerrados da janela precisam estar revistos e sem energia desconhecida. Essa
regra conservadora evita selecionar apenas os dias faceis de registrar; nao e uma
validacao clinica da estimativa. Na janela habitual sao 20 datas alimentares e 21
datas de peso. Confirmar os dias nao remove os bloqueios de plausibilidade.

Um dia explicitamente confirmado pode participar da estimativa mesmo abaixo do
filtro calorico. Ausencia de lancamentos nunca significa jejum: um dia sem consumo
so pode ser confirmado apos declaracao explicita. Hoje nao entra nas medias.

## Compatibilidade e reversao

Esta entrega nao faz deploy. A publicacao do branch nao modifica a `main` nem o
banco de producao. O deploy atual so e disparado por push na `main`.

O diario original, seus enums e suas colunas permanecem intactos. Apenas duas
tabelas sao adicionadas: `diary_day_reviews` e `diary_estimates`. Os novos campos de
API sao adicionais. Os handlers de arrastar refeicoes nao foram modificados.

Para voltar **antes de integrar ou publicar**, basta usar a `main`; nao ha nenhuma
mudanca de producao para desfazer. Em desenvolvimento, a API antiga exige a
revisao Alembic anterior, conforme o procedimento abaixo.

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

Verificado nesta entrega: 12 testes de integracao aprovados; endpoints novos por
curl; navegação por data, revisao, aproximacoes e exclusao no navegador; arrasto por
mouse e toque; ordem preservada depois de recarregar; recuperacao de falha de
atualizacao; migracao de ida e volta com preservacao dos dados. Foram usados apenas
registros ficticios locais nessas verificacoes.
