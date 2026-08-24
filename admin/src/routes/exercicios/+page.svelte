<script lang="ts">
	import {
		api,
		ApiError,
		type AdminExercisePage,
		type AdminExerciseQuery,
		type AdminExerciseRow,
		type MuscleGroup,
		type MuscleRegion
	} from '$lib/api';
	import { showToast } from '$lib/toast.svelte';
	import { errorMessage, num } from '$lib/format';

	// Curadoria da subdivisao muscular (ver docs/subdivisao-muscular): o script de
	// preenchimento automatico classifica por palavra-chave no slug e deixa NULL na
	// duvida - esta tela fecha o que sobrou, priorizando o que ja tem nome em pt-BR
	// (endpoint ja devolve nessa ordem).
	const GRUPOS: { valor: MuscleGroup; rotulo: string }[] = [
		{ valor: 'chest', rotulo: 'Peito' },
		{ valor: 'back', rotulo: 'Costas' },
		{ valor: 'shoulders', rotulo: 'Ombros' },
		{ valor: 'biceps', rotulo: 'Biceps' },
		{ valor: 'triceps', rotulo: 'Triceps' },
		{ valor: 'legs', rotulo: 'Pernas' },
		{ valor: 'glutes', rotulo: 'Gluteos' },
		{ valor: 'abs', rotulo: 'Abdomen' },
		{ valor: 'calves', rotulo: 'Panturrilha' },
		{ valor: 'cardio', rotulo: 'Cardio' }
	];

	const REGIOES_POR_GRUPO: Record<MuscleGroup, { valor: MuscleRegion; rotulo: string }[]> = {
		chest: [
			{ valor: 'chest_upper', rotulo: 'Peito superior' },
			{ valor: 'chest_mid', rotulo: 'Peito medio' },
			{ valor: 'chest_lower', rotulo: 'Peito inferior' }
		],
		back: [
			{ valor: 'lats', rotulo: 'Dorsal' },
			{ valor: 'upper_back', rotulo: 'Meio das costas' },
			{ valor: 'traps', rotulo: 'Trapezio' },
			{ valor: 'lower_back', rotulo: 'Lombar' }
		],
		shoulders: [
			{ valor: 'delt_front', rotulo: 'Ombro anterior' },
			{ valor: 'delt_side', rotulo: 'Ombro lateral' },
			{ valor: 'delt_rear', rotulo: 'Ombro posterior' }
		],
		biceps: [
			{ valor: 'biceps', rotulo: 'Biceps' },
			{ valor: 'forearms', rotulo: 'Antebraco' }
		],
		triceps: [
			{ valor: 'triceps_long', rotulo: 'Triceps - cabeca longa' },
			{ valor: 'triceps_lateral', rotulo: 'Triceps - lateral' }
		],
		legs: [
			{ valor: 'quads', rotulo: 'Anterior de coxa' },
			{ valor: 'hamstrings', rotulo: 'Posterior de coxa' },
			{ valor: 'adductors', rotulo: 'Adutores' },
			{ valor: 'abductors', rotulo: 'Abdutores' }
		],
		glutes: [
			{ valor: 'glute_max', rotulo: 'Gluteo maximo' },
			{ valor: 'glute_med', rotulo: 'Gluteo medio' }
		],
		abs: [
			{ valor: 'abs_upper', rotulo: 'Abdomen superior' },
			{ valor: 'abs_lower', rotulo: 'Abdomen inferior' },
			{ valor: 'obliques', rotulo: 'Obliquos' },
			{ valor: 'core', rotulo: 'Core' }
		],
		calves: [
			{ valor: 'gastrocnemius', rotulo: 'Panturrilha em pe' },
			{ valor: 'soleus', rotulo: 'Panturrilha sentado' }
		],
		cardio: []
	};

	function rotuloGrupo(grupo: MuscleGroup): string {
		return GRUPOS.find((g) => g.valor === grupo)?.rotulo ?? grupo;
	}

	let query = $state<AdminExerciseQuery>({
		page: 1,
		page_size: 50,
		muscle_group: undefined,
		only_missing: true,
		q: ''
	});

	let resultado = $state<AdminExercisePage | null>(null);
	let carregando = $state(false);
	let buscaTexto = $state('');
	let salvandoId = $state<number | null>(null);
	let buscaTimer: ReturnType<typeof setTimeout> | null = null;

	$effect(() => {
		const atual = { ...query };
		carregando = true;
		api
			.listExercisesForCuration(atual)
			.then((page) => {
				resultado = page;
			})
			.catch((error) => {
				showToast(errorMessage(error instanceof ApiError ? error.code : 'GENERIC_ERROR'));
			})
			.finally(() => {
				carregando = false;
			});
	});

	function aoDigitar(event: Event): void {
		buscaTexto = (event.target as HTMLInputElement).value;
		if (buscaTimer) clearTimeout(buscaTimer);
		buscaTimer = setTimeout(() => {
			query = { ...query, q: buscaTexto, page: 1 };
		}, 300);
	}

	async function salvarRegiao(exercise: AdminExerciseRow, valor: string): Promise<void> {
		const regiao = (valor || null) as MuscleRegion | null;
		salvandoId = exercise.id;
		try {
			const atualizado = await api.setExerciseRegion(exercise.id, regiao);
			if (!resultado) return;
			// so_sem_subdivisao filtra pelo servidor: se a pessoa acabou de escolher uma
			// regiao com o filtro padrao ligado, a linha some da lista (ja foi resolvida)
			// em vez de ficar exibindo uma classificacao que a proxima carga nao repetiria.
			const items = query.only_missing && atualizado.muscle_region
				? resultado.items.filter((it) => it.id !== exercise.id)
				: resultado.items.map((it) => (it.id === exercise.id ? atualizado : it));
			resultado = { ...resultado, items, total: query.only_missing && atualizado.muscle_region ? resultado.total - 1 : resultado.total };
			showToast('Subdivisao salva!');
		} catch (error) {
			showToast(errorMessage(error instanceof ApiError ? error.code : 'GENERIC_ERROR'));
		} finally {
			salvandoId = null;
		}
	}

	const totalPaginas = $derived(
		resultado ? Math.max(1, Math.ceil(resultado.total / resultado.page_size)) : 1
	);
	const primeiroDaPagina = $derived(
		resultado && resultado.total > 0 ? (resultado.page - 1) * resultado.page_size + 1 : 0
	);
	const ultimoDaPagina = $derived(
		resultado ? Math.min(resultado.page * resultado.page_size, resultado.total) : 0
	);
</script>

<article class="card">
	<div class="card-head" style="flex-wrap:wrap;gap:10px">
		<div>
			<h2 class="card-title">Subdivisao muscular</h2>
			<p class="card-note">
				{resultado ? num(resultado.total) : '—'} exercicios do catalogo com os filtros atuais
			</p>
		</div>
	</div>

	<div class="card-body" style="padding-bottom:12px">
		<div class="filtros">
			<label class="field field-search">
				<svg
					width="15"
					height="15"
					viewBox="0 0 24 24"
					fill="none"
					stroke="currentColor"
					stroke-width="2"
					stroke-linecap="round"><circle cx="11" cy="11" r="6.5" /><path d="m16 16 4 4" /></svg
				>
				<input
					type="search"
					placeholder="Buscar por nome ou slug"
					aria-label="Buscar por nome ou slug"
					value={buscaTexto}
					oninput={aoDigitar}
				/>
			</label>

			<label class="field">
				<span class="eyebrow">Grupo</span>
				<select
					aria-label="Filtrar por grupo muscular"
					value={query.muscle_group ?? ''}
					onchange={(event) =>
						(query = {
							...query,
							muscle_group: (event.currentTarget.value || undefined) as MuscleGroup | undefined,
							page: 1
						})}
				>
					<option value="">Todos</option>
					{#each GRUPOS as g (g.valor)}
						<option value={g.valor}>{g.rotulo}</option>
					{/each}
				</select>
			</label>

			<label class="field" style="flex-direction:row;align-items:center;gap:8px">
				<input
					type="checkbox"
					checked={query.only_missing}
					onchange={(event) =>
						(query = { ...query, only_missing: event.currentTarget.checked, page: 1 })}
				/>
				<span>So sem subdivisao</span>
			</label>
		</div>

		{#if !carregando && resultado && resultado.items.length === 0}
			<div class="empty">
				<h3>Nada com esses filtros</h3>
				<p>
					{query.only_missing
						? 'Todo exercicio deste grupo ja tem subdivisao classificada.'
						: 'Tente um termo mais curto na busca ou outro grupo.'}
				</p>
			</div>
		{:else}
			<div class="table-wrap" class:is-loading={carregando}>
				<table>
					<caption class="sr-only">Exercicios do catalogo, com grupo e subdivisao muscular</caption>
					<thead>
						<tr>
							<th scope="col">Exercicio</th>
							<th scope="col">Grupo</th>
							<th scope="col">Subdivisao</th>
						</tr>
					</thead>
					<tbody>
						{#each resultado?.items ?? [] as exercise (exercise.id)}
							<tr>
								<td>
									<span class="name">{exercise.name}</span>
									<span class="mono" style="display:block;font-size:11px;color:var(--ink-3)">
										{exercise.slug}
									</span>
								</td>
								<td>{rotuloGrupo(exercise.muscle_group)}</td>
								<td>
									<select
										aria-label="Subdivisao de {exercise.name}"
										disabled={salvandoId === exercise.id || REGIOES_POR_GRUPO[exercise.muscle_group].length === 0}
										value={exercise.muscle_region ?? ''}
										onchange={(event) => salvarRegiao(exercise, event.currentTarget.value)}
									>
										<option value="">— sem subdivisao —</option>
										{#each REGIOES_POR_GRUPO[exercise.muscle_group] as r (r.valor)}
											<option value={r.valor}>{r.rotulo}</option>
										{/each}
									</select>
								</td>
							</tr>
						{/each}
					</tbody>
				</table>
			</div>

			<div class="pager">
				<div class="pager-range">
					<b>{num(primeiroDaPagina)}–{num(ultimoDaPagina)}</b> de {num(resultado?.total ?? 0)}
				</div>

				<div class="pager-right">
					<button
						class="page-btn"
						type="button"
						disabled={query.page <= 1}
						onclick={() => (query = { ...query, page: query.page - 1 })}
					>
						‹ Anterior
					</button>
					<span class="mono" style="font-size:12.5px;color:var(--ink-2)">
						{query.page} / {totalPaginas}
					</span>
					<button
						class="page-btn"
						type="button"
						disabled={query.page >= totalPaginas}
						onclick={() => (query = { ...query, page: query.page + 1 })}
					>
						Proxima ›
					</button>
				</div>
			</div>
		{/if}
	</div>
</article>
