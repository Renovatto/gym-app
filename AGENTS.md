# Regras do projeto (e de boa programacao)

Estas regras valem para este projeto e servem de referencia para outros. O objetivo
central e: **codigo consistente e facil de um humano ler**. Nao busque o codigo mais
curto; busque o codigo mais claro.

## Colaboracao com o usuario

- Sempre que criar um artefato visual ou documento para o usuario, abra-o ao terminar
  no navegador ou aplicativo adequado e confirme que ficou visivel. Nao basta fornecer
  apenas o caminho do arquivo.

- Avalie sugestoes do usuario com criterio proprio. Nao concorde automaticamente,
  nao elogie para agradar e nao trate uma preferencia como prova de superioridade tecnica.
- Quando houver motivo para discordar, diga isso de forma direta e respeitosa,
  explicando os riscos, as alternativas e a recomendacao.
- Diferencie fatos verificados, hipoteses e preferencias. Nao afirme vantagens de
  modelos, custo ou qualidade sem evidencia; proponha uma avaliacao quando necessario.
- Reavalie recomendacoes anteriores quando a evidencia mudar. Nao discorde apenas
  para aparentar independencia: o objetivo e ajudar o usuario a decidir bem.

## Uso de subagentes

### Quando delegar

- Use subagentes quando houver trabalho delimitado que justifique a coordenacao.
  Tarefas triviais ou etapas fortemente dependentes ficam com o agente principal.
- Comece com no maximo 2 subagentes simultaneos. Nao crie paralelismo artificial:
  o revisor deve avaliar uma alteracao pronta para revisao.
- Cada tarefa deve informar objetivo, arquivos relevantes, restricoes e criterio
  de conclusao. Evite que agentes diferentes editem os mesmos arquivos.

### Modelo e esforco

- Use `gpt-6-luna` com esforco `medium` para busca de codigo, levantamento de
  traducoes, verificacoes delimitadas e implementacao simples com padrao existente.
- Nao use Luna como padrao para qualquer implementacao. Avalie as dependencias
  e as regras do dominio antes de delegar, mesmo quando o diff esperado for pequeno.
- Use `gpt-6.1-sol` com esforco `medium` desde o inicio para calculos, migracoes,
  autenticacao, integridade dos dados e mudancas que cruzem varias areas do app.
- O agente principal pode executar essas tarefas diretamente; nao e necessario
  criar um subagente apenas para cumprir a escolha de modelo.
- `medium` e o padrao. Se uma investigacao dificil justificar `high`, explique
  a necessidade ao usuario antes de mudar o esforco.
- Nao utilize `gpt-6-astra` nesta configuracao.
- Use os modelos explicitamente ao disparar subagentes. Se o modelo solicitado
  nao estiver disponivel, informe a limitacao em vez de substituir silenciosamente.

### Revisao

- Use um revisor dedicado com `gpt-6.1-sol`, esforco `medium` e contexto separado
  para mudancas de comportamento ou dados. Alteracoes triviais podem ser revisadas
  pelo proprio agente principal.
- Forneca ao revisor o objetivo original, o diff e os testes executados, com acesso
  ao codigo relacionado. Nao forneca apenas o resumo ou a conclusao do implementador.
- O revisor procura bugs, regressoes, violacoes deste AGENTS.md e lacunas nos testes.
  Quando envolvidos, confira calculos, datas, plausibilidade, relacionamentos do banco,
  traducoes, toasts e confirmacoes.
- O revisor nao edita arquivos. Relate cada problema com arquivo, linha, impacto
  e correcao sugerida; se nao houver achados, informe isso e as limitacoes da revisao.
- O agente principal avalia os achados, resolve os problemas pertinentes e valida
  o resultado integrado. A revisao nao substitui testes nem garante ausencia de bugs.

### Avaliacao da politica

- Trate a combinacao Luna + Sol como uma hipotese a avaliar em tarefas reais,
  sem presumir economia de custo, ganho de tempo ou qualidade equivalente.
- Observe correcoes exigidas na revisao, regressoes e tempo total, incluindo retrabalho.
  Reavalie a distribuicao das tarefas conforme os resultados.
- Se o Luna nao resolver uma tarefa, o agente principal reavalia o problema antes
  de delegar novamente; nao repita tentativas equivalentes sem nova evidencia.
- Ao concluir trabalho delegado, informe os modelos usados, as validacoes executadas
  e qualquer limitacao relevante.

## Layout e temas (memoria persistente)

- Toda criacao ou alteracao de layout deve respeitar os modos claro e escuro,
  incluindo toasts, confirmacoes, timers, estados de erro, hover e foco.
- Antes de escolher cores, confira os tokens e seu remapeamento em
  `frontend/src/routes/layout.css`. Uma classe de tom escuro pode nao ter
  equivalente remapeado no tema escuro; nao presuma que toda cor se adapta.
- Valide os dois temas antes de concluir: texto, fundo, bordas, botoes e indicadores
  devem permanecer legiveis. Para texto comum, contraste minimo de 4.5:1; para
  texto grande e indicadores essenciais, 3:1. Corrigir bug de contraste exige
  regressao automatizada que verifique as cores efetivamente renderizadas.

## Legibilidade acima de tudo

- Escreva para uma pessoa ler, nao para impressionar. Prefira o obvio ao esperto.
- Nomes de classes, funcoes e variaveis devem ter **ligacao clara com o que representam**.
  Nada de nomes genericos (`data`, `tmp`, `x`) quando existe um nome com significado.
  Ex.: `compute_daily_calorie_target`, `visceral_fat_index`, `latest_weigh_in`.
- Nao invente nomes de campos, funcoes ou APIs que nao existem (sem alucinacao). Se nao
  tiver certeza de que algo existe, verifique no codigo antes de usar.
- Funcao faz uma coisa e o nome descreve essa coisa. Se o nome precisa de "e"/"and",
  provavelmente sao duas funcoes.
- Prefira early-return a aninhar muitos `if`.

## Comentarios

- **Todo calculo tem comentario** explicando a formula e a intencao (nao o obvio).
- **Comentarios SEM acentuacao** (facilita diffs, encoding e leitura em qualquer terminal).
  Ex.: escreva "gordura visceral", "porcentagem", "manutencao" sem acento.
- Ao usar uma sigla (BMI, TDEE, BMR, V-fat), deixe uma **legenda curta** na primeira vez
  que ela aparece no arquivo, alem do glossario central (ver abaixo).

## Siglas e glossario

- Siglas usadas no dominio (saude/nutricao/treino) devem ter uma legenda no codigo E
  um verbete no glossario central visivel ao usuario.
- Legendas de referencia (mantras do projeto):
  - **BMI** (Body Mass Index) = IMC, indice de massa corporal = peso / altura^2.
  - **BMR** (Basal Metabolic Rate) = taxa metabolica basal, gasto em repouso absoluto.
  - **TDEE** (Total Daily Energy Expenditure) = gasto energetico total do dia.
  - **V-fat / visceral fat** = gordura visceral, a que fica ao redor dos orgaos (barriga).
  - **BIA** (Bioelectrical Impedance Analysis) = bioimpedancia, metodo da balanca para
    estimar composicao corporal (impreciso no valor absoluto, bom na tendencia).

## Formulas de referencia (fonte unica da verdade)

Todas as formulas ficam centralizadas em `backend/app/services/goals.py` (metas) e
documentadas para o usuario na area de consulta. Nao espalhe formula por varios lugares.

- **BMR (Mifflin-St Jeor):** `10*peso_kg + 6.25*altura_cm - 5*idade + (5 homem | -161 mulher)`.
- **TDEE:** `BMR * fator_de_atividade` (1.2 sedentario ... 1.9 muito ativo).
- **Meta calorica:** `TDEE * multiplicador_do_objetivo`, com **piso no BMR** (nunca abaixo).
- **Macros:** proteina por g/kg do objetivo; gordura como % das calorias; carbo no resto.
- **Agua:** `peso_kg * 35 ml`.

## Feedback ao usuario (regras obrigatorias)

- **Toda mutacao mostra um toast agradavel.** Qualquer acao de salvar, criar, alterar,
  excluir ou ajustar deve confirmar o resultado com um toast (via `showToast`). O usuario
  nunca fica sem retorno visual de que a acao funcionou.
- **Toda exclusao pede confirmacao antes.** Nenhum delete acontece direto no clique: sempre
  ha um passo de confirmacao (inline ou modal) antes de executar. Vale para o app inteiro.
- **Acao de impacto tambem pede confirmacao antes, nao so exclusao.** Qualquer botao que
  troque algo usado no app inteiro dali em diante (ex.: adotar a manutencao medida no lugar
  da formula, renovar/reiniciar um periodo, substituir uma meta) segue o mesmo padrao de
  confirmacao da exclusao (inline: mostra a pergunta + "Confirmar"/"Cancelar" antes de
  chamar a API). Nao vale para toggles leves e reversiveis em 1 toque (favoritar, marcar
  suplemento tomado, marcar serie feita) - esses ja tem feedback pelo proprio estado visual
  ou pelo toast, e confirmar cada um so atrapalharia o uso.

## Padroes ja adotados no projeto (nao reinventar)

- Backend: FastAPI + SQLModel. `session.exec(select(Model.coluna))` retorna escalar, nao tupla.
- **Postgres em todo lugar: dev, CI e producao.** Dev migrou em 19/08/2026 e o suporte a
  SQLite saiu de vez em 22/09/2026 - nao ha mais `IS_SQLITE`, `render_as_batch` nem passo
  de baseline SQLite no CI. Motivo: ninguem usava esse banco, e um banco que so o CI
  exercitava custou um deploy vermelho por uma incompatibilidade (`ALTER COLUMN`) que nao
  afetava usuario nenhum. `docker compose up -d` sobe o banco local (porta 5434).
  `GYMAPP_DATABASE_URL` nao tem default: precisa estar no `backend/.env`.
  Migracao nova nao precisa mais pensar em portabilidade - escreva para o Postgres.
- Ao atualizar filhos de um pai (rotina->itens, receita->ingredientes), limpe a colecao
  com `colecao.clear()` (delete-orphan). Nunca `session.delete(item)` + re-adicionar o pai.
- **Schema: Alembic** (desde 03/08/2026). Coluna nova = editar `models.py` +
  `alembic revision --autogenerate -m "..."` + revisar o arquivo + `alembic upgrade head`
  local + commitar migracao e modelo JUNTOS. Enum novo = migração manual com
  `op.get_context().autocommit_block()` + `ALTER TYPE ... ADD VALUE IF NOT EXISTS`.
  Tabela nova = autogenerate resolve.
- Busca textual SEMPRE via `normalize_search` (sem acento, sem caixa) dos dois lados.
- Deduplicacao de receitas e alimentos compartilhados usa identidade de conteudo, nao
  apenas o ID de origem: itens podem ser editados mantendo o mesmo ID. Para receitas,
  comparar rendimento, ingredientes e quantidades sem depender do nome da receita ou
  dos IDs locais dos alimentos. Para alimentos pessoais, comparar dados nutricionais,
  categoria e porcoes sem depender do nome.
- Duplicatas existentes sao identificadas e resolvidas por inativacao reversivel, nao
  por exclusao: manter referencias e historico, e excluir itens inativos das buscas e
  listas padrao. Ao adicionar compartilhar numa tela de edicao, manter o mesmo fluxo,
  selecao de conexao e feedback das telas equivalentes.
- Lancamentos historicos usam macros e quantidades gravadas no proprio lancamento;
  leitura de dias antigos nao pode recalcular valores a partir de receitas mutaveis.
  Se um campo historico legado nao foi armazenado (ex.: gramas), manter desconhecido em
  vez de inferi-lo usando o conteudo atual da receita.
- Datas locais do usuario: cliente envia dia local + `tz_offset` (Date.getTimezoneOffset()).
- **Media sobre dias do usuario nunca inclui HOJE.** O dia corrente esta sempre pela
  metade e entraria como um dia inteiro de pouco - o vies e sistematico (sempre para
  baixo, toda vez que a tela abre), nao ruido que se cancela. Janela de media termina
  em ontem. Ja quebrou o TDEE adaptativo em producao (ver `services/adaptive.py`).
- **Numero calculado a partir de dado do usuario passa por checagem de plausibilidade
  antes de virar acao.** Mostrar um valor estranho e aceitavel (o usuario tem direito de
  ver o que os dados dele deram); oferecer um botao que o adota, nao. Ex.: manutencao
  medida abaixo do BMR e impossivel - o app exibe e explica, mas bloqueia adotar.
- Frontend: Svelte 5 runes (`$state`/`$derived`/`$effect`), nunca stores. Componente
  `Stepper` para qualquer entrada numerica. Toast global via `showToast`.
- Em novas mutacoes feitas dentro de uma tela (excluir, salvar, editar ou substituir um item),
  preserve a posicao de rolagem sempre que possivel: atualize o estado local ou use
  `reloadSilent()` em vez de `load()`, que substitui a tela por um skeleton e pode levar
  a pessoa de volta ao topo. Use `load()` quando a transicao realmente precisar da tela
  de carregamento, como no carregamento inicial ou na troca de dia.
- i18n: toda string de UI vira chave nos 3 arquivos `messages/{pt-br,en,es}.json` e depois
  `npx paraglide-js compile`. A API retorna codigo de erro, nunca texto pronto.
  **Excecao unica: conteudo escrito em tempo de execucao** (novidades do app, escritas no
  painel admin). Nao existe chave para o paraglide compilar, entao o texto mora no banco
  nos 3 idiomas e o servidor resolve a traducao pelo `user.locale` - mesmo caminho do nome
  de alimento. Vale so para conteudo; interface continua em `messages/*.json`.

## Testes de regressao

- **Todo bug encontrado e corrigido exige um teste de regressao automatizado.** O teste
  deve reproduzir o cenario que causou o bug, falhar sem a correcao e passar com ela,
  protegendo o comportamento esperado contra futuras alteracoes.
- Execute o teste e inclua-o junto com a correcao no mesmo commit.

## Antes de qualquer commit

1. `cd frontend && npx svelte-check --tsconfig ./tsconfig.json` -> 0 erros.
2. `npm run build` -> sucesso.
3. Testar endpoints novos com curl.
4. Mensagem de commit em portugues, sem mencao a IA/Codex.
