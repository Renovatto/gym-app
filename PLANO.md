# Plano: 3 melhorias no treino

> Plano de execução para as próximas melhorias. Seguir na ordem. Fazer UMA feature
> por vez, validar, commitar, e só então passar para a próxima.

## Contexto do projeto (ler antes de começar)

- **Stack**: SvelteKit SPA estática (`frontend/`, Svelte 5 **runes** — `$state`/`$derived`/`$effect`, nunca stores) + FastAPI/SQLite (`backend/`).
- **Rodar**: `./start.sh` → app em http://localhost:5175, API em http://localhost:8765 (docs em /docs). Backend tem `--reload` (recarrega sozinho ao editar).
- **Usuário de teste**: `teste@teste.com` / `senha12345`.
- **i18n**: toda string de UI vira chave nos TRÊS arquivos `frontend/messages/{pt-br,en,es}.json`. Depois de editar mensagens, rodar:
  `cd frontend && npx paraglide-js compile --project ./project.inlang --outdir ./src/lib/paraglide`
- **Validação obrigatória antes de cada commit**:
  1. `cd frontend && npx svelte-check --tsconfig ./tsconfig.json` → 0 erros
  2. `npm run build` → sucesso
  3. Testar endpoints novos com curl (exemplos abaixo)
- **Commits**: mensagem em português, SEM trailer de co-autoria, sem mencionar Claude.
- **Pegadinhas conhecidas**:
  - FastAPI: rota estática (`/me/sessions/active`) deve ser declarada ANTES da rota parametrizada (`/me/sessions/{session_id}`) no mesmo router, senão "active" vira session_id.
  - SQLModel: `session.exec(select(Model.coluna))` retorna escalares, não tuplas.
  - Componente `Stepper.svelte` já existe e é fluido — usar ele para qualquer entrada numérica.
  - Sub-rotas de `/treino/...` e `/dieta/...` escondem a tab bar automaticamente (layout raiz).
  - Toast global: `import { showToast } from '$lib/toast.svelte';` → `showToast(m.chave())`.

---

## Feature 1 — Timer de descanso + tempo total do treino

**Objetivo**: na tela de execução (`frontend/src/routes/treino/sessao/[id]/+page.svelte`):
(a) cronômetro do tempo total da sessão no cabeçalho; (b) ao marcar uma série,
iniciar contagem regressiva de descanso com aviso ao terminar; (c) poder ajustar
o descanso por exercício na montagem da rotina.

### 1.1 Tempo total (só frontend)

- A sessão já tem `started_at` (vem de `api.getSession`). Guardar em `$state` no load.
- Criar `let now = $state(Date.now())` e um `setInterval` de 1s dentro de `$effect`
  (retornar cleanup que faz `clearInterval`).
- Derivar `elapsed = Math.max(0, Math.floor((now - startedAtMs) / 1000))`.
  - ATENÇÃO: `started_at` vem do backend em UTC **sem sufixo Z** (ex.
    `2026-07-03T10:00:39.580767`). Parsear com `new Date(started_at + 'Z')`.
- Exibir no cabeçalho ao lado do progresso: formato `mm:ss` (ou `h:mm:ss` se ≥ 1h).
- Ao finalizar o treino, mostrar toast com o tempo total: usar chave
  `workout_finished_in` com parâmetro (ver mensagens abaixo; em paraglide,
  mensagem com parâmetro é `"{time}"` no JSON e `m.workout_finished_in({ time })` no uso).

### 1.2 Timer de descanso (só frontend)

- Estado: `restRemaining` (s), `restTotal` (s), `restActive` (bool).
- Em `toggleSet`, quando a série é MARCADA (não desmarcada) e não é cardio:
  iniciar descanso com `block.item.rest_seconds` (fallback 90).
- Mesmo interval de 1s do tempo total pode decrementar o descanso (um relógio só).
- UI: barra fixa no rodapé (a tab bar está oculta nessa tela, então usar
  `fixed inset-x-0 bottom-0 z-20`), fundo `bg-slate-900 text-white`, contendo:
  - contagem grande `mm:ss` restante + barra de progresso fina;
  - botão `+30s` (soma 30 em restRemaining e restTotal);
  - botão "Pular" (encerra o descanso).
- Ao chegar em 0: `navigator.vibrate?.(400)` + beep curto via WebAudio e esconder a barra.
  Beep (colar como função utilitária no próprio componente):
  ```ts
  function beep(): void {
    try {
      const ctx = new AudioContext();
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.connect(gain);
      gain.connect(ctx.destination);
      osc.frequency.value = 880;
      gain.gain.setValueAtTime(0.3, ctx.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.5);
      osc.start();
      osc.stop(ctx.currentTime + 0.5);
    } catch {
      // áudio bloqueado: vibração já cobre
    }
  }
  ```
- Marcar outra série com descanso ativo REINICIA o timer (comportamento padrão de app de treino).

### 1.3 Ajustar descanso na montagem da rotina

- Em `frontend/src/routes/treino/rotina/[id]/+page.svelte`, no card de cada
  exercício de força (não cardio), adicionar terceiro campo "Descanso (s)" com
  `Stepper` (`min={0} max={600} step={15}`) ligado a `item.rest_seconds`.
  O campo já existe no tipo `BuilderItem` e já é enviado no payload — é só expor na UI.
- Layout: trocar o grid de 2 colunas (séries/reps) por séries+reps na primeira
  linha e descanso na segunda (grid-cols-2 + item full-width), para não apertar.

### 1.4 Mensagens (adicionar nos 3 arquivos)

| chave | pt-br | en | es |
|---|---|---|---|
| `rest_label` | Descanso | Rest | Descanso |
| `skip` | Pular | Skip | Saltar |
| `plus_30s` | +30s | +30s | +30s |
| `total_time` | Tempo total | Total time | Tiempo total |
| `rest_seconds_label` | Descanso (seg) | Rest (sec) | Descanso (seg) |
| `workout_finished_in` | Treino concluído em {time}! 💪 | Workout done in {time}! 💪 | ¡Entrenamiento hecho en {time}! 💪 |

(Substituir o uso atual de `workout_done_toast` na finalização da sessão pela nova
`workout_finished_in`; `workout_done_toast` continua usada no "marcar feito" da lista.)

### 1.5 Critérios de aceite

- [ ] Cronômetro total roda no cabeçalho e não zera ao marcar séries.
- [ ] Marcar série de força abre a barra de descanso com o tempo do exercício.
- [ ] +30s e Pular funcionam; ao zerar toca beep/vibra e some.
- [ ] Cardio NÃO dispara descanso.
- [ ] Stepper de descanso aparece na montagem e persiste (salvar rotina e reabrir).
- [ ] Toast final mostra duração. svelte-check e build limpos.

**Commit sugerido**: `Treino: timer de descanso com aviso, tempo total da sessão e ajuste de descanso por exercício`

---

## Feature 2 — Retomar sessão aberta

**Objetivo**: sessão iniciada e abandonada (app fechado) deve poder ser retomada
ou descartada, a partir da tela Treino e da tela Hoje.

### 2.1 Backend (`backend/app/routers/workout.py`)

- **GET `/me/sessions/active`** → `SessionOut | None`: última `WorkoutSession` do
  usuário com `finished_at IS NULL`, ordenada por `started_at` desc. Retornar
  `None` (JSON `null`) se não houver. DECLARAR ANTES de `/me/sessions/{session_id}`.
  ```python
  @router.get("/me/sessions/active", response_model=SessionOut | None)
  def active_session(user: CurrentUser, session: SessionDep) -> SessionOut | None:
      ws = session.exec(
          select(WorkoutSession)
          .where(WorkoutSession.user_id == user.id)
          .where(WorkoutSession.finished_at.is_(None))
          .order_by(desc(WorkoutSession.started_at))
      ).first()
      return _session_out(ws) if ws else None
  ```
- **DELETE `/me/sessions/{session_id}`** → 204: descarta sessão (dona confere via
  `_get_owned_session`); `session.delete(ws)` remove os set_logs em cascata.
- Ao **iniciar** sessão nova (`start_session`): se já existe ativa para o mesmo
  usuário, descartar a antiga se ela não tiver nenhuma série (`len(ws.sets) == 0`),
  senão retornar a ativa existente em vez de criar outra (evita duplicatas).

Teste curl (após login pegar $ACCESS):
```bash
curl -s http://localhost:8765/me/sessions/active -H "Authorization: Bearer $ACCESS"
# inicia, confere que active retorna a mesma, deleta, confere null
```

### 2.2 Frontend

- `api.ts`: `getActiveSession: () => request<WorkoutSession | null>('/me/sessions/active')`
  e `deleteSession: (id) => request<void>(`/me/sessions/${id}`, { method: 'DELETE' })`.
- **Tela Treino** (`/treino/+page.svelte`): carregar sessão ativa junto com o resto
  (`Promise.all`). Se houver, mostrar banner no topo (card `bg-emerald-600 text-white`):
  nome da rotina + "Treino em andamento", botões **Continuar** (goto
  `/treino/sessao/{id}`) e **Descartar** (deleteSession + recarregar).
- **Tela Hoje** (`/+page.svelte`): se houver sessão ativa, o atalho de treino vira
  "Continuar treino — {nome}" apontando para a sessão.

### 2.3 Mensagens

| chave | pt-br | en | es |
|---|---|---|---|
| `resume_workout` | Continuar treino | Resume workout | Continuar entrenamiento |
| `discard` | Descartar | Discard | Descartar |
| `session_in_progress` | Treino em andamento | Workout in progress (já existe `workout_in_progress` — REUSAR, não criar) | — |

(Só criar `resume_workout` e `discard`; reusar `workout_in_progress`.)

### 2.4 Critérios de aceite

- [ ] Iniciar treino, voltar sem finalizar → banner aparece em /treino e atalho na Hoje.
- [ ] Continuar reabre a MESMA sessão com séries já marcadas.
- [ ] Descartar remove e o banner some.
- [ ] Iniciar de novo com sessão ativa vazia não cria duplicata.
- [ ] curl de /me/sessions/active confere. svelte-check e build limpos.

**Commit sugerido**: `Treino: retomar ou descartar sessão em andamento (banner em Treino e Hoje)`

---

## Feature 3 — Busca no catálogo de exercícios

**Objetivo**: campo de busca por nome no catálogo (728 exercícios).

### 3.1 Backend (`backend/app/routers/workout.py`, endpoint `list_exercises`)

- Adicionar param `q: str = Query(default="", max_length=60)`.
- Se `q` não vazio: filtrar em Python (mesmo padrão do `/foods`): manter exercício
  se o termo estiver no nome localizado OU em qualquer tradução.
  Quando há busca, IGNORAR o filtro `full` (buscar na base inteira), mas manter
  `muscle_group`/`level` se enviados.
- **PADRÃO DO SISTEMA**: comparar SEMPRE com `normalize_search` (de
  `app/services/text.py`) dos dois lados — busca ignora acentos e caixa
  ("supino" acha "Supino", "flexao" acha "Flexão"). Toda busca futura usa isso.

Teste curl: `/exercises?q=supino` deve retornar os supinos; `/exercises?q=curl&full=false` deve achar mesmo sem tradução pt.

### 3.2 Frontend (`frontend/src/lib/components/ExerciseBrowser.svelte`)

- `api.ts`: adicionar `q` ao `getExercises` (novo campo em `opts`).
- Input de busca acima dos chips de grupo (mesmo estilo do input de `/dieta/adicionar`).
- **Debounce 300ms**: `let query = $state('')`, e no `$effect` que carrega,
  `const t = setTimeout(load, 300); return () => clearTimeout(t);`.
- Quando `query` não vazio: chamar sem `muscle_group` (busca global) e mostrar os
  chips de grupo desabilitados/apagados (`opacity-40 pointer-events-none`).
- Limpar busca volta ao comportamento por grupo.

### 3.3 Mensagens

| chave | pt-br | en | es |
|---|---|---|---|
| `search_exercise` | Buscar exercício… | Search exercise… | Buscar ejercicio… |

### 3.4 Critérios de aceite

- [ ] Digitar "supino" lista supinos sem trocar de aba; só 1 request após parar de digitar.
- [ ] Busca acha exercício sem tradução (nome em inglês) mesmo com "mostrar todos" desligado.
- [ ] Limpar volta ao filtro por grupo. svelte-check e build limpos.

**Commit sugerido**: `Treino: busca por nome no catálogo de exercícios (com debounce)`

---

## Ao terminar as 3

1. Rodar o fluxo completo manualmente descrito nos critérios de aceite.
2. Atualizar `README.md` se necessário (nada estrutural muda).
3. NÃO iniciar outras melhorias fora deste plano.
