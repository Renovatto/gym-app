<script lang="ts">
	import {
		api,
		type BuildMeal,
		type Food,
		type FoodSuggestion,
		type MealType,
		type PantryRecipeMatch,
		type RecipeView
	} from '$lib/api';
	import MacroBreakdown from '$lib/components/MacroBreakdown.svelte';
	import RecipeViewModal from '$lib/components/RecipeViewModal.svelte';
	import Spinner from '$lib/components/Spinner.svelte';
	import { mealTypeLabel } from '$lib/labels';
	import { showToast } from '$lib/toast.svelte';
	import { m } from '$lib/paraglide/messages';
	import { getLocale } from '$lib/paraglide/runtime';

	// "Montar refeicao com o que tenho em casa": tela unica, sem etapa de "ver
	// sugestoes" no meio - toca no que tem e o resultado (receitas + alimentos
	// avulsos) atualiza na hora, embaixo. Fica aberta apos cada inclusao, igual ao
	// AddEntryModal; "Concluido" fecha.
	let {
		day,
		meal,
		onClose,
		onAdded
	}: {
		day: string;
		meal: MealType;
		onClose: () => void;
		onAdded: () => void;
	} = $props();

	const nf = new Intl.NumberFormat(getLocale());

	// Selecao = chips removiveis (ordem de escolha, por isso array e nao Set).
	let haveIds = $state<number[]>([]);
	let haveFoods = $state<Food[]>([]);
	const haveIdSet = $derived(new Set(haveIds));

	// Chips rapidos pra tocar sem digitar: favoritos + recentes, sem duplicar - cobre
	// o caso comum (a comida de sempre) sem precisar buscar nada.
	let quickFoods = $state<Food[]>([]);
	Promise.all([api.getFavoriteFoods(), api.getRecentFoods()]).then(([favs, recent]) => {
		const seen = new Set<number>();
		quickFoods = [...favs, ...recent].filter((f) =>
			seen.has(f.id) ? false : (seen.add(f.id), true)
		);
	});
	const quickFoodsToShow = $derived(quickFoods.filter((f) => !haveIdSet.has(f.id)));

	// Busca por texto (fora dos chips rapidos): mesmo debounce + token anti-corrida
	// ja usado no AddEntryModal (resposta lenta de uma busca antiga nao pode
	// sobrescrever uma busca mais nova).
	let query = $state('');
	let searchResults = $state<Food[]>([]);
	let searchToken = 0;
	async function runSearch(q: string): Promise<void> {
		const token = ++searchToken;
		if (!q.trim()) {
			if (token === searchToken) searchResults = [];
			return;
		}
		const found = await api.getFoods(q, undefined, { limit: 8 });
		if (token !== searchToken) return;
		searchResults = found.filter((f) => !haveIdSet.has(f.id));
	}
	$effect(() => {
		const q = query;
		const handle = setTimeout(() => runSearch(q), 250);
		return () => clearTimeout(handle);
	});

	// Resultado ao vivo: token proprio, SEM debounce - um toque em chip ja e um gesto
	// deliberado (nao e digitacao), o token sozinho basta pra descartar resposta velha
	// se uma selecao mais nova ja foi disparada antes dela voltar. Nunca zera "result"
	// entre requisicoes: troca so quando a resposta mais nova chega, pra nao piscar a
	// tela em toques rapidos seguidos.
	let result = $state<BuildMeal | null>(null);
	let buildToken = 0;
	let buildBusy = $state(false);
	async function refresh(): Promise<void> {
		const token = ++buildToken;
		buildBusy = true;
		try {
			const r = await api.getBuildMeal(day, haveIds, meal);
			if (token !== buildToken) return;
			result = r;
		} finally {
			if (token === buildToken) buildBusy = false;
		}
	}
	refresh(); // 1a carga com selecao vazia - nunca comeca em branco

	function toggleHave(food: Food): void {
		if (haveIdSet.has(food.id)) {
			haveIds = haveIds.filter((id) => id !== food.id);
			haveFoods = haveFoods.filter((f) => f.id !== food.id);
		} else {
			haveIds = [...haveIds, food.id];
			haveFoods = [...haveFoods, food];
		}
		refresh();
	}
	function addFromSearch(food: Food): void {
		toggleHave(food);
		query = '';
		searchResults = [];
	}

	// Preview de receita: mesma modal "olho" ja usada no resto do app (biblioteca).
	let viewRecipe = $state<RecipeView | null>(null);
	let viewLoading = $state(false);
	async function openPreview(slug: string): Promise<void> {
		viewLoading = true;
		try {
			viewRecipe = await api.getLibraryRecipe(slug);
		} finally {
			viewLoading = false;
		}
	}

	let addBusy = $state(false);
	async function addRecipeMatch(match: PantryRecipeMatch): Promise<void> {
		if (addBusy) return;
		addBusy = true;
		try {
			// quantity precisa ir explicito: e calculada (pode ser fracionaria), diferente
			// da sugestao simples do card do dia, que sempre usa 1 porcao implicita.
			await api.addDiaryFromLibrary({
				slug: match.slug,
				entry_date: day,
				meal_type: meal,
				quantity: match.quantity
			});
			showToast(m.reco_added());
			onAdded();
		} finally {
			addBusy = false;
		}
	}
	async function addFoodMatch(fm: FoodSuggestion): Promise<void> {
		if (addBusy) return;
		addBusy = true;
		try {
			await api.addDiaryEntry({
				entry_date: day,
				meal_type: meal,
				source: 'food',
				food_id: fm.food.id,
				quantity: fm.grams
			});
			showToast(m.reco_added());
			onAdded();
		} finally {
			addBusy = false;
		}
	}

	function matchPercent(ratio: number): string {
		return `${Math.round(ratio * 100)}%`;
	}
</script>

<div class="fixed inset-0 z-40 overflow-y-auto bg-slate-50">
	<div class="mx-auto max-w-md px-4 pt-4 pb-24">
		<div class="mb-4 flex items-center justify-between gap-2">
			<div class="min-w-0">
				<h1 class="text-xl font-bold">{m.pantry_title()}</h1>
				<p class="text-sm text-slate-500">{mealTypeLabel(meal)}</p>
			</div>
			<button
				type="button"
				onclick={onClose}
				class="shrink-0 rounded-full bg-emerald-600 px-5 py-2.5 text-sm font-bold text-white active:bg-emerald-700"
			>
				{m.done()}
			</button>
		</div>

		{#if haveFoods.length > 0}
			<p class="mb-1.5 text-xs font-bold tracking-wide text-slate-400 uppercase">{m.pantry_selected_label()}</p>
			<div class="mb-3 flex flex-wrap gap-1.5">
				{#each haveFoods as food (food.id)}
					<button
						type="button"
						onclick={() => toggleHave(food)}
						class="flex items-center gap-1.5 rounded-full bg-emerald-600 px-3 py-1.5 text-xs font-bold text-white active:bg-emerald-700"
					>
						{food.name}
						<svg viewBox="0 0 24 24" class="h-3 w-3" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round"><path d="M6 6l12 12M18 6L6 18" /></svg>
					</button>
				{/each}
			</div>
		{/if}

		<p class="mb-1.5 text-xs font-bold tracking-wide text-slate-400 uppercase">{m.pantry_hint()}</p>
		{#if quickFoodsToShow.length > 0}
			<div class="mb-3 flex flex-wrap gap-1.5">
				{#each quickFoodsToShow as food (food.id)}
					<button
						type="button"
						onclick={() => toggleHave(food)}
						class="rounded-full border-2 border-slate-200 bg-white px-3 py-1.5 text-xs font-bold text-slate-700 active:bg-slate-100"
					>
						{food.name}
					</button>
				{/each}
			</div>
		{/if}

		<div class="relative mb-3">
			<input
				bind:value={query}
				placeholder={m.pantry_search_placeholder()}
				class="h-12 w-full rounded-2xl border-2 border-slate-200 bg-white pr-11 pl-4 outline-none focus:border-emerald-600"
			/>
			{#if query}
				<button
					type="button"
					aria-label={m.clear()}
					title={m.clear()}
					onclick={() => (query = '')}
					class="absolute top-1/2 right-2 grid h-8 w-8 -translate-y-1/2 place-items-center rounded-full text-slate-400 active:bg-slate-100"
				>
					<svg viewBox="0 0 24 24" class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M6 6l12 12M18 6L6 18" /></svg>
				</button>
			{/if}
			{#if searchResults.length > 0}
				<div class="absolute z-10 mt-1 w-full space-y-1 rounded-2xl bg-white p-1.5 shadow-lg">
					{#each searchResults as food (food.id)}
						<button
							type="button"
							onclick={() => addFromSearch(food)}
							class="flex w-full items-center justify-between rounded-xl px-3 py-2 text-left text-sm font-semibold text-slate-700 active:bg-slate-50"
						>
							{food.name}
							<svg viewBox="0 0 24 24" class="h-4 w-4 shrink-0 text-emerald-500" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M12 5v14M5 12h14" /></svg>
						</button>
					{/each}
				</div>
			{/if}
		</div>

		<div class="flex items-center gap-2 rounded-2xl bg-slate-100 px-3 py-2.5">
			<svg viewBox="0 0 24 24" class="h-4 w-4 shrink-0 text-slate-400" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2v20M2 12h20" /></svg>
			<p class="text-xs text-slate-500">{m.pantry_staples_note()}</p>
		</div>

		<div class="mt-5 mb-2 flex items-center gap-2">
			<p class="text-xs font-bold tracking-wide text-slate-400 uppercase">{m.pantry_recipe_matches_label()}</p>
			{#if buildBusy}<span class="h-1.5 w-1.5 animate-pulse rounded-full bg-emerald-500"></span>{/if}
		</div>

		{#if !result || result.recipe_matches.length === 0}
			<div class="rounded-2xl bg-white px-4 py-6 text-center">
				<p class="text-sm text-slate-400">{m.pantry_no_recipe_matches()}</p>
			</div>
		{:else}
			<div class="space-y-2">
				{#each result.recipe_matches as match (match.slug)}
					{@const full = match.missing.length === 0}
					<div class="rounded-2xl border {full ? 'border-emerald-200 bg-emerald-50/40' : 'border-amber-200 bg-amber-50/50'} p-3">
						<div class="flex items-start gap-2.5">
							<span class="grid h-9 w-9 shrink-0 place-items-center rounded-xl {full ? 'bg-emerald-100 text-emerald-600' : 'bg-amber-100 text-amber-600'}">
								<svg viewBox="0 0 24 24" class="h-4.5 w-4.5" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 15a7 7 0 0 1 14 0" /><path d="M2 15h20" /><path d="M12 8V5" /><circle cx="12" cy="4" r="1" /></svg>
							</span>
							<div class="min-w-0 flex-1">
								<p class="flex items-center gap-1 truncate text-sm font-semibold text-slate-800">
									{#if match.is_favorite}
										<svg viewBox="0 0 24 24" class="h-3.5 w-3.5 shrink-0 text-amber-400" fill="currentColor"><path d="M12 3l2.9 5.9 6.5.9-4.7 4.6 1.1 6.5L12 17.8 6.2 20.9l1.1-6.5L2.6 9.8l6.5-.9z" /></svg>
									{/if}
									<span class="truncate">{match.name}</span>
								</p>
								<p class="text-xs text-slate-500">
									{m.pantry_quantity({ qty: nf.format(match.quantity) })} ·
									{nf.format(Math.round(match.macros.kcal))} kcal
								</p>
								<MacroBreakdown
									protein_g={match.macros.protein_g}
									carbs_g={match.macros.carbs_g}
									fat_g={match.macros.fat_g}
									class="text-[11px] text-slate-400"
								/>
							</div>
							<span
								class="shrink-0 rounded-full px-2.5 py-1 text-[10px] font-bold whitespace-nowrap {full
									? 'bg-emerald-100 text-emerald-700'
									: 'bg-amber-100 text-amber-700'}"
							>
								{full ? m.pantry_match_full({ pct: matchPercent(match.match_ratio) }) : m.pantry_match_missing({ count: match.missing.length, pct: matchPercent(match.match_ratio) })}
							</span>
						</div>
						{#if !full}
							<p class="mt-2 border-t border-dashed border-amber-200 pt-2 text-xs text-amber-700">
								<b class="font-bold">{m.pantry_missing_label()}:</b> {match.missing.join(', ')}
							</p>
						{/if}
						<div class="mt-2.5 flex gap-2">
							<button
								type="button"
								aria-label={m.recipe_view()}
								title={m.recipe_view()}
								onclick={() => openPreview(match.slug)}
								class="grid h-10 w-10 shrink-0 place-items-center rounded-xl border-2 {full ? 'border-emerald-200 text-emerald-600' : 'border-amber-200 text-amber-600'} active:bg-white"
							>
								<svg viewBox="0 0 24 24" class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7-10-7-10-7z" /><circle cx="12" cy="12" r="3" /></svg>
							</button>
							<button
								type="button"
								disabled={addBusy}
								onclick={() => addRecipeMatch(match)}
								class="h-10 flex-1 rounded-xl {full ? 'bg-emerald-600 active:bg-emerald-700' : 'bg-amber-500 active:bg-amber-600'} text-sm font-bold text-white disabled:opacity-50"
							>
								+ {m.reco_add()}
							</button>
						</div>
					</div>
				{/each}
			</div>
		{/if}

		<p class="mt-5 mb-2 text-xs font-bold tracking-wide text-slate-400 uppercase">{m.pantry_food_matches_label()}</p>
		{#if !result || result.food_matches.length === 0}
			<div class="rounded-2xl bg-white px-4 py-5 text-center">
				<p class="text-sm text-slate-400">{m.pantry_no_food_matches()}</p>
			</div>
		{:else}
			<div class="space-y-2">
				{#each result.food_matches as fm (fm.food.id)}
					<div class="flex items-center gap-2 rounded-2xl bg-white px-3 py-2 shadow-sm">
						<div class="min-w-0 flex-1">
							<p class="truncate text-sm font-semibold text-slate-800">{fm.food.name}</p>
							<p class="text-xs text-slate-500">{nf.format(fm.grams)} g · {nf.format(Math.round(fm.macros.kcal))} kcal</p>
							<MacroBreakdown
								protein_g={fm.macros.protein_g}
								carbs_g={fm.macros.carbs_g}
								fat_g={fm.macros.fat_g}
								class="text-[11px] text-slate-400"
							/>
						</div>
						<button
							type="button"
							disabled={addBusy}
							onclick={() => addFoodMatch(fm)}
							class="shrink-0 rounded-xl bg-emerald-600 px-3 py-2 text-sm font-bold text-white active:bg-emerald-700 disabled:opacity-50"
						>
							+ {m.reco_add()}
						</button>
					</div>
				{/each}
			</div>
		{/if}
	</div>
</div>

{#if viewRecipe || viewLoading}
	<RecipeViewModal recipe={viewRecipe} loading={viewLoading} onClose={() => (viewRecipe = null)} />
{/if}
