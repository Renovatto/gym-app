# Regras do projeto (e de boa programacao)

Estas regras valem para este projeto e servem de referencia para outros. O objetivo
central e: **codigo consistente e facil de um humano ler**. Nao busque o codigo mais
curto; busque o codigo mais claro.

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

## Padroes ja adotados no projeto (nao reinventar)

- Backend: FastAPI + SQLModel. `session.exec(select(Model.coluna))` retorna escalar, nao tupla.
- Ao atualizar filhos de um pai (rotina->itens, receita->ingredientes), limpe a colecao
  com `colecao.clear()` (delete-orphan). Nunca `session.delete(item)` + re-adicionar o pai.
- Migracao leve de coluna em SQLite: adicionar em `_COLUMN_MIGRATIONS` no `db.py`.
- Busca textual SEMPRE via `normalize_search` (sem acento, sem caixa) dos dois lados.
- Datas locais do usuario: cliente envia dia local + `tz_offset` (Date.getTimezoneOffset()).
- Frontend: Svelte 5 runes (`$state`/`$derived`/`$effect`), nunca stores. Componente
  `Stepper` para qualquer entrada numerica. Toast global via `showToast`.
- i18n: toda string de UI vira chave nos 3 arquivos `messages/{pt-br,en,es}.json` e depois
  `npx paraglide-js compile`. A API retorna codigo de erro, nunca texto pronto.

## Antes de qualquer commit

1. `cd frontend && npx svelte-check --tsconfig ./tsconfig.json` -> 0 erros.
2. `npm run build` -> sucesso.
3. Testar endpoints novos com curl.
4. Mensagem de commit em portugues, sem mencao a IA/Claude.
