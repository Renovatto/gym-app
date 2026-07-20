<script lang="ts">
	import { api, type Food, type MealType, type Recipe } from '$lib/api';
	import Stepper from '$lib/components/Stepper.svelte';
	import { showToast } from '$lib/toast.svelte';
	import { mealTypeLabel, portionLabel } from '$lib/labels';
	import { normalizeSearch, searchMatches } from '$lib/text';
	import { m } from '$lib/paraglide/messages';
	import { getLocale } from '$lib/paraglide/runtime';

	// Modal de adicionar alimento/receita a uma refeicao. Fica ABERTA apos cada
	// inclusao (da pra lancar varios itens seguidos); "Concluido" fecha. O pai
	// recarrega o diario via onAdded sem perder a posicao de rolagem.
	let {
		meal,
		day,
		onClose,
		onAdded,
		label = null
	}: {
		meal: MealType;
		day: string;
		onClose: () => void;
		onAdded: () => void;
		// rotulo customizado da refeicao (ex.: nome digitado no "Outros")
		label?: string | null;
	} = $props();

	const nf = new Intl.NumberFormat(getLocale());

	let tab = $state<'foods' | 'recipes'>('foods');
	let query = $state('');
	let foods = $state<Food[]>([]);
	let recentFoods = $state<Food[]>([]);
	let recipes = $state<Recipe[]>([]);
	let loading = $state(false);
	let addedCount = $state(0);

	const searching = $derived(query.trim().length > 0);

	// Filtro de escopo da lista de alimentos. 'default' preserva o comportamento de
	// sempre (favoritos + recentes + catalogo); os outros mostram so aquela categoria.
	const FOOD_SCOPES = ['default', 'mine', 'favorites', 'recent'] as const;
	type FoodScope = (typeof FOOD_SCOPES)[number];
	let foodScope = $state<FoodScope>('default');

	function foodScopeLabel(scope: FoodScope): string {
		return {
			default: m.food_scope_default(),
			mine: m.food_scope_mine(),
			favorites: m.food_scope_favorites(),
			recent: m.food_scope_recent()
		}[scope];
	}

	// 'default'/'mine' vem paginado do backend; 'favorites'/'recent' ja tem tudo
	// carregado (listas curtas) e so filtramos pelo texto no cliente.
	const PAGE_SIZE = 60;
	let foodsHasMore = $state(true);
	let loadingMore = $state(false);

	// item selecionado para lançar
	let selFood = $state<Food | null>(null);
	let selRecipe = $state<Recipe | null>(null);
	let grams = $state(100);
	let servings = $state(1);
	let saving = $state(false);

	// quantidade por porção (ex.: 2 unidades) ou por gramas
	let qtyMode = $state<'portion' | 'grams'>('grams');
	let selPortion = $state<{ label_key: string; grams: number } | null>(null);
	let count = $state(1);

	const effectiveGrams = $derived(
		qtyMode === 'portion' && selPortion ? count * selPortion.grams : grams
	);

	// Guarda contra respostas fora de ordem: cada busca ganha um token; quando a resposta
	// volta, so aplica se ainda for a MAIS RECENTE. Sem isso, ao digitar rapido as
	// respostas chegam embaralhadas e uma antiga (vazia/errada) sobrescreve a nova (o "loop").
	let searchToken = 0;

	// Carrega a 1a pagina (reset) da lista paginada ('default' ou 'mine'). As outras
	// duas escopos (favoritos/recentes) nao passam por aqui - sao filtradas no cliente.
	async function loadFoods(q: string, scope: FoodScope): Promise<void> {
		const token = ++searchToken;
		loading = true;
		try {
			const result = await api.getFoods(q, undefined, {
				scope: scope === 'mine' ? 'mine' : undefined,
				limit: PAGE_SIZE,
				offset: 0
			});
			if (token !== searchToken) return; // resposta velha: descarta
			foods = result;
			foodsHasMore = result.length === PAGE_SIZE;
		} finally {
			if (token === searchToken) loading = false;
		}
	}

	// Rolagem infinita: busca a proxima pagina e acrescenta. Guardado pelo mesmo
	// token do loadFoods - se uma nova busca/reset comecar enquanto isso carrega,
	// a resposta desta pagina antiga e descartada (evita duplicar/misturar listas).
	async function loadMoreFoods(q: string, scope: FoodScope): Promise<void> {
		if (!foodsHasMore || loadingMore || loading) return;
		const token = searchToken;
		loadingMore = true;
		try {
			const result = await api.getFoods(q, undefined, {
				scope: scope === 'mine' ? 'mine' : undefined,
				limit: PAGE_SIZE,
				offset: foods.length
			});
			if (token !== searchToken) return;
			foods = [...foods, ...result];
			foodsHasMore = result.length === PAGE_SIZE;
		} finally {
			if (token === searchToken) loadingMore = false;
		}
	}

	// Dispara a proxima pagina quando a rolagem chega perto do fim da modal.
	function handleScroll(e: Event): void {
		if (tab !== 'foods' || foodScope === 'favorites' || foodScope === 'recent') return;
		const el = e.currentTarget as HTMLElement;
		if (el.scrollHeight - el.scrollTop - el.clientHeight < 400) {
			loadMoreFoods(query, foodScope);
		}
	}

	async function loadRecipes(): Promise<void> {
		loading = true;
		recipes = await api.getRecipes();
		loading = false;
	}

	// recentes e favoritos carregam uma vez (mostrados quando não há busca)
	api.getRecentFoods().then((r) => (recentFoods = r));
	let favoriteFoods = $state<Food[]>([]);
	api.getFavoriteFoods().then((f) => (favoriteFoods = f));

	// fonte unica da verdade da estrelinha dos alimentos (vale em todas as listas)
	const favFoodIds = $derived(new Set(favoriteFoods.map((f) => f.id)));
	const scopedTerm = $derived(normalizeSearch(query));
	const filteredFavoriteFoods = $derived(
		favoriteFoods.filter((f) => searchMatches(f.name, scopedTerm))
	);
	const filteredRecentFoods = $derived(recentFoods.filter((f) => searchMatches(f.name, scopedTerm)));

	$effect(() => {
		if (tab !== 'foods') {
			loadRecipes();
			return;
		}
		if (foodScope === 'favorites' || foodScope === 'recent') return; // filtrado no cliente, sem fetch
		// debounce: so busca ~250ms depois que voce para de digitar; a limpeza cancela a
		// busca anterior a cada tecla, evitando uma rajada de requisicoes concorrentes.
		const q = query;
		const scope = foodScope;
		const handle = setTimeout(() => loadFoods(q, scope), 250);
		return () => clearTimeout(handle);
	});

	async function toggleFoodFav(food: Food): Promise<void> {
		const { favorite } = await api.toggleFavorite('food', food.id);
		if (favorite) {
			if (!favoriteFoods.some((f) => f.id === food.id)) {
				favoriteFoods = [...favoriteFoods, { ...food, is_favorite: true }];
			}
			showToast(m.toast_favorited());
		} else {
			favoriteFoods = favoriteFoods.filter((f) => f.id !== food.id);
			showToast(m.toast_unfavorited());
		}
	}

	async function toggleRecipeFav(recipe: Recipe): Promise<void> {
		const { favorite } = await api.toggleFavorite('recipe', recipe.id);
		showToast(favorite ? m.toast_favorited() : m.toast_unfavorited());
		await loadRecipes(); // backend ja devolve favoritas primeiro
	}

	function pickFood(food: Food): void {
		selFood = food;
		count = 1;
		// se o alimento tem porções (ex.: unidade de 50g), começa no modo porção
		if (food.portions.length > 0) {
			selPortion = food.portions[0];
			qtyMode = 'portion';
			grams = food.default_portion_g;
		} else {
			selPortion = null;
			qtyMode = 'grams';
			grams = food.default_portion_g;
		}
	}

	function pickRecipe(recipe: Recipe): void {
		selRecipe = recipe;
		servings = 1;
	}

	const foodPreview = $derived(
		selFood
			? {
					kcal: (selFood.kcal * effectiveGrams) / 100,
					protein: (selFood.protein_g * effectiveGrams) / 100,
					carbs: (selFood.carbs_g * effectiveGrams) / 100,
					fat: (selFood.fat_g * effectiveGrams) / 100
				}
			: null
	);
	const recipePreview = $derived(
		selRecipe
			? {
					kcal: selRecipe.per_serving.kcal * servings,
					protein: selRecipe.per_serving.protein_g * servings,
					carbs: selRecipe.per_serving.carbs_g * servings,
					fat: selRecipe.per_serving.fat_g * servings
				}
			: null
	);

	async function confirmFood(): Promise<void> {
		if (!selFood) return;
		saving = true;
		try {
			await api.addDiaryEntry({
				entry_date: day,
				meal_type: meal,
				source: 'food',
				food_id: selFood.id,
				quantity: effectiveGrams
			});
			showToast(m.toast_added());
			// permanece aberta: fecha so o painel de quantidade e segue lancando
			selFood = null;
			addedCount += 1;
			onAdded();
		} finally {
			saving = false;
		}
	}

	async function confirmRecipe(): Promise<void> {
		if (!selRecipe) return;
		saving = true;
		try {
			await api.addDiaryEntry({
				entry_date: day,
				meal_type: meal,
				source: 'recipe',
				recipe_id: selRecipe.id,
				quantity: servings
			});
			showToast(m.toast_added());
			selRecipe = null;
			addedCount += 1;
			onAdded();
		} finally {
			saving = false;
		}
	}
</script>

<!-- linha de alimento reutilizada em Favoritos, Recentes e Todos: toca no corpo
	 para escolher a quantidade; toca na estrela so favorita (botoes irmaos) -->
{#snippet foodRow(food: Food)}
	<div class="flex items-center gap-1 rounded-2xl bg-white p-2 shadow-sm">
		<button
			type="button"
			onclick={() => pickFood(food)}
			class="flex min-w-0 flex-1 items-center justify-between rounded-xl p-1.5 text-left active:bg-slate-50"
		>
			<span class="min-w-0 flex-1">
				<span class="block truncate font-semibold text-slate-900">{food.name}</span>
				<span class="text-xs text-slate-500">{nf.format(food.kcal)} kcal / 100 g</span>
			</span>
			{#if food.is_custom}
				<span class="ml-2 rounded bg-emerald-50 px-1.5 py-0.5 text-xs font-semibold text-emerald-600">{m.custom_tag()}</span>
			{/if}
		</button>
		<button
			type="button"
			aria-label={m.favorite_toggle()}
			title={m.favorite_toggle()}
			onclick={() => toggleFoodFav(food)}
			class="grid h-10 w-10 shrink-0 place-items-center rounded-xl active:bg-slate-100"
		>
			<svg
				viewBox="0 0 24 24"
				class="h-5 w-5 {favFoodIds.has(food.id) ? 'text-amber-400' : 'text-slate-300'}"
				fill={favFoodIds.has(food.id) ? 'currentColor' : 'none'}
				stroke="currentColor"
				stroke-width="2"
				stroke-linejoin="round"
			>
				<path d="M12 3l2.9 5.9 6.5.9-4.7 4.6 1.1 6.5L12 17.8 6.2 20.9l1.1-6.5L2.6 9.8l6.5-.9z" stroke-linecap="round" />
			</svg>
		</button>
	</div>
{/snippet}

<!-- rodape da lista paginada: spinner ao carregar mais, ou aviso de fim -->
{#snippet loadMoreStatus()}
	{#if loadingMore}
		<div class="flex justify-center py-4">
			<div class="h-5 w-5 animate-spin rounded-full border-4 border-emerald-600 border-t-transparent"></div>
		</div>
	{:else if !foodsHasMore && foods.length > 0}
		<p class="py-3 text-center text-xs text-slate-400">{m.food_list_end()}</p>
	{/if}
{/snippet}

<div class="fixed inset-0 z-40 overflow-y-auto bg-slate-50" onscroll={handleScroll}>
	<div class="mx-auto max-w-md px-4 pt-4 pb-24">
		<div class="mb-4 flex items-center justify-between gap-2">
			<div class="min-w-0">
				<h1 class="text-xl font-bold">{m.add_food()}</h1>
				<p class="text-sm text-slate-500">{label ?? mealTypeLabel(meal)}</p>
			</div>
			<button
				type="button"
				onclick={onClose}
				class="shrink-0 rounded-full bg-emerald-600 px-5 py-2.5 text-sm font-bold text-white active:bg-emerald-700"
			>
				{m.done()}{addedCount > 0 ? ` (${addedCount})` : ''}
			</button>
		</div>

		<div class="mb-3 grid grid-cols-2 gap-2">
			<button
				type="button"
				onclick={() => (tab = 'foods')}
				class="h-11 rounded-2xl font-semibold {tab === 'foods' ? 'bg-emerald-600 text-white' : 'bg-white text-slate-600'}"
			>
				{m.foods_tab()}
			</button>
			<button
				type="button"
				onclick={() => (tab = 'recipes')}
				class="h-11 rounded-2xl font-semibold {tab === 'recipes' ? 'bg-emerald-600 text-white' : 'bg-white text-slate-600'}"
			>
				{m.recipes_tab()}
			</button>
		</div>

		{#if tab === 'foods'}
			<div class="relative mb-3">
				<input
					bind:value={query}
					placeholder={m.search_food()}
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
						<svg viewBox="0 0 24 24" class="h-5 w-5" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M6 6l12 12M18 6L6 18" /></svg>
					</button>
				{/if}
			</div>

			<!-- filtro de escopo: Padrao preserva exatamente o comportamento de sempre -->
			<div class="mb-3 flex gap-1.5 overflow-x-auto">
				{#each FOOD_SCOPES as scope (scope)}
					<button
						type="button"
						onclick={() => (foodScope = scope)}
						class="shrink-0 rounded-full border-2 px-3 py-1.5 text-xs font-bold {foodScope === scope
							? 'border-emerald-600 bg-emerald-50 text-emerald-800'
							: 'border-slate-200 text-slate-500'}"
					>
						{foodScopeLabel(scope)}
					</button>
				{/each}
			</div>

			{#if loading}
				<div class="flex justify-center py-10">
					<div class="h-7 w-7 animate-spin rounded-full border-4 border-emerald-600 border-t-transparent"></div>
				</div>
			{:else if foodScope === 'default'}
				{#if !searching && favoriteFoods.length > 0}
					<p class="mb-2 flex items-center gap-1 text-xs font-bold text-amber-500 uppercase">
						<svg viewBox="0 0 24 24" class="h-3.5 w-3.5" fill="currentColor"><path d="M12 3l2.9 5.9 6.5.9-4.7 4.6 1.1 6.5L12 17.8 6.2 20.9l1.1-6.5L2.6 9.8l6.5-.9z" /></svg>
						{m.favorites_label()}
					</p>
					<div class="mb-4 space-y-2">
						{#each favoriteFoods as food (food.id)}
							{@render foodRow(food)}
						{/each}
					</div>
				{/if}
				{#if !searching && recentFoods.length > 0}
					<p class="mb-2 text-xs font-bold text-slate-400 uppercase">{m.recent_label()}</p>
					<div class="mb-4 space-y-2">
						{#each recentFoods as food (food.id)}
							{@render foodRow(food)}
						{/each}
					</div>
					<p class="mb-2 text-xs font-bold text-slate-400 uppercase">{m.all_foods_label()}</p>
				{/if}
				<div class="space-y-2">
					{#each foods as food (food.id)}
						{@render foodRow(food)}
					{/each}
				</div>
				{@render loadMoreStatus()}
				<a href="/dieta/alimento/novo" class="mt-3 block text-center text-sm font-semibold text-emerald-700">
					{m.create_food()}
				</a>
			{:else if foodScope === 'mine'}
				{#if foods.length === 0}
					<p class="rounded-2xl bg-white px-4 py-3 text-center text-sm text-slate-400 shadow-sm">{m.food_scope_empty()}</p>
				{/if}
				<div class="space-y-2">
					{#each foods as food (food.id)}
						{@render foodRow(food)}
					{/each}
				</div>
				{@render loadMoreStatus()}
				<a href="/dieta/alimento/novo" class="mt-3 block text-center text-sm font-semibold text-emerald-700">
					{m.create_food()}
				</a>
			{:else if foodScope === 'favorites'}
				{#if filteredFavoriteFoods.length === 0}
					<p class="rounded-2xl bg-white px-4 py-3 text-center text-sm text-slate-400 shadow-sm">{m.food_scope_empty()}</p>
				{/if}
				<div class="space-y-2">
					{#each filteredFavoriteFoods as food (food.id)}
						{@render foodRow(food)}
					{/each}
				</div>
			{:else}
				{#if filteredRecentFoods.length === 0}
					<p class="rounded-2xl bg-white px-4 py-3 text-center text-sm text-slate-400 shadow-sm">{m.food_scope_empty()}</p>
				{/if}
				<div class="space-y-2">
					{#each filteredRecentFoods as food (food.id)}
						{@render foodRow(food)}
					{/each}
				</div>
			{/if}
		{:else if loading}
			<div class="flex justify-center py-10">
				<div class="h-7 w-7 animate-spin rounded-full border-4 border-emerald-600 border-t-transparent"></div>
			</div>
		{:else}
			<div class="space-y-2">
				{#each recipes as recipe (recipe.id)}
					<div class="flex items-center gap-1 rounded-2xl bg-white p-2 shadow-sm">
						<button
							type="button"
							onclick={() => pickRecipe(recipe)}
							class="flex min-w-0 flex-1 items-center justify-between rounded-xl p-1.5 text-left active:bg-slate-50"
						>
							<span class="min-w-0 flex-1">
								<span class="block truncate font-semibold text-slate-900">{recipe.name}</span>
								<span class="text-xs text-slate-500">
									{nf.format(Math.round(recipe.per_serving.kcal))} kcal / {m.serving_singular()}
								</span>
							</span>
						</button>
						<button
							type="button"
							aria-label={m.favorite_toggle()}
							title={m.favorite_toggle()}
							onclick={() => toggleRecipeFav(recipe)}
							class="grid h-10 w-10 shrink-0 place-items-center rounded-xl active:bg-slate-100"
						>
							<svg
								viewBox="0 0 24 24"
								class="h-5 w-5 {recipe.is_favorite ? 'text-amber-400' : 'text-slate-300'}"
								fill={recipe.is_favorite ? 'currentColor' : 'none'}
								stroke="currentColor"
								stroke-width="2"
								stroke-linejoin="round"
							>
								<path d="M12 3l2.9 5.9 6.5.9-4.7 4.6 1.1 6.5L12 17.8 6.2 20.9l1.1-6.5L2.6 9.8l6.5-.9z" stroke-linecap="round" />
							</svg>
						</button>
						<a
							href="/dieta/receita/{recipe.id}"
							aria-label={m.edit()}
							title={m.edit()}
							class="grid h-10 w-10 shrink-0 place-items-center rounded-xl text-slate-400 active:bg-slate-100"
						>
							<svg viewBox="0 0 24 24" class="h-5 w-5" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 20h9M16.5 3.5a2.1 2.1 0 013 3L7 19l-4 1 1-4z" /></svg>
						</a>
					</div>
				{/each}
			</div>
			<a href="/dieta/receita/nova" class="mt-3 block text-center text-sm font-semibold text-emerald-700">
				{m.create_recipe()}
			</a>
		{/if}
	</div>
</div>

<!-- Painel de quantidade (alimento) -->
{#if selFood}
	<div
		class="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
		role="button"
		tabindex="-1"
		onclick={() => (selFood = null)}
		onkeydown={(e) => e.key === 'Escape' && (selFood = null)}
	>
		<div
			class="max-h-[90dvh] w-full max-w-md overflow-y-auto rounded-3xl bg-white p-5"
			role="dialog"
			tabindex="-1"
			onclick={(e) => e.stopPropagation()}
			onkeydown={() => {}}
		>
			<h2 class="text-lg font-bold text-slate-900">{selFood.name}</h2>

			{#if selFood.portions.length > 0}
				<p class="mt-3 mb-2 text-xs font-semibold text-slate-500">{m.measure_by()}</p>
				<div class="flex flex-wrap gap-2">
					{#each selFood.portions as portion (portion.label_key)}
						<button
							type="button"
							onclick={() => {
								qtyMode = 'portion';
								selPortion = portion;
							}}
							class="rounded-full border-2 px-3 py-1.5 text-sm font-semibold {qtyMode === 'portion' && selPortion?.label_key === portion.label_key ? 'border-emerald-600 bg-emerald-50 text-emerald-800' : 'border-slate-200 text-slate-600'}"
						>
							{portionLabel(portion.label_key, portion.grams)}
						</button>
					{/each}
					<button
						type="button"
						onclick={() => (qtyMode = 'grams')}
						class="rounded-full border-2 px-3 py-1.5 text-sm font-semibold {qtyMode === 'grams' ? 'border-emerald-600 bg-emerald-50 text-emerald-800' : 'border-slate-200 text-slate-600'}"
					>
						{m.by_grams()}
					</button>
				</div>
			{/if}

			<div class="mt-4">
				{#if qtyMode === 'portion' && selPortion}
					<p class="mb-1 text-center text-xs text-slate-400">
						{count} × {portionLabel(selPortion.label_key, selPortion.grams)} = {effectiveGrams} g
					</p>
					<Stepper bind:value={count} min={1} max={50} step={1} unit="×" />
				{:else}
					<Stepper bind:value={grams} min={1} max={2000} step={5} unit="g" />
				{/if}
			</div>

			{#if foodPreview}
				<div class="mt-4 flex justify-around rounded-2xl bg-slate-50 py-3 text-center">
					<div><p class="text-lg font-bold">{nf.format(Math.round(foodPreview.kcal))}</p><p class="text-xs text-slate-400">kcal</p></div>
					<div><p class="text-lg font-bold">{nf.format(Math.round(foodPreview.protein))}</p><p class="text-xs text-slate-400">P</p></div>
					<div><p class="text-lg font-bold">{nf.format(Math.round(foodPreview.carbs))}</p><p class="text-xs text-slate-400">C</p></div>
					<div><p class="text-lg font-bold">{nf.format(Math.round(foodPreview.fat))}</p><p class="text-xs text-slate-400">G</p></div>
				</div>
			{/if}
			<button
				type="button"
				disabled={saving}
				onclick={confirmFood}
				class="mt-4 h-14 w-full rounded-2xl bg-emerald-600 text-lg font-bold text-white active:bg-emerald-700 disabled:opacity-50"
			>
				{m.add_to_meal()}
			</button>
		</div>
	</div>
{/if}

<!-- Painel de quantidade (receita) -->
{#if selRecipe}
	<div
		class="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
		role="button"
		tabindex="-1"
		onclick={() => (selRecipe = null)}
		onkeydown={(e) => e.key === 'Escape' && (selRecipe = null)}
	>
		<div
			class="max-h-[90dvh] w-full max-w-md overflow-y-auto rounded-3xl bg-white p-5"
			role="dialog"
			tabindex="-1"
			onclick={(e) => e.stopPropagation()}
			onkeydown={() => {}}
		>
			<h2 class="text-lg font-bold text-slate-900">{selRecipe.name}</h2>
			<p class="mb-4 text-sm text-slate-500">{m.how_many_servings()}</p>
			<Stepper bind:value={servings} min={1} max={20} step={1} unit={m.serving_plural()} />
			{#if recipePreview}
				<div class="mt-4 flex justify-around rounded-2xl bg-slate-50 py-3 text-center">
					<div><p class="text-lg font-bold">{nf.format(Math.round(recipePreview.kcal))}</p><p class="text-xs text-slate-400">kcal</p></div>
					<div><p class="text-lg font-bold">{nf.format(Math.round(recipePreview.protein))}</p><p class="text-xs text-slate-400">P</p></div>
					<div><p class="text-lg font-bold">{nf.format(Math.round(recipePreview.carbs))}</p><p class="text-xs text-slate-400">C</p></div>
					<div><p class="text-lg font-bold">{nf.format(Math.round(recipePreview.fat))}</p><p class="text-xs text-slate-400">G</p></div>
				</div>
			{/if}
			<button
				type="button"
				disabled={saving}
				onclick={confirmRecipe}
				class="mt-4 h-14 w-full rounded-2xl bg-emerald-600 text-lg font-bold text-white active:bg-emerald-700 disabled:opacity-50"
			>
				{m.add_to_meal()}
			</button>
		</div>
	</div>
{/if}
