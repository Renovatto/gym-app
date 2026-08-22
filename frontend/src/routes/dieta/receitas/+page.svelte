<script lang="ts">
	import {
		ApiError,
		api,
		type Connection,
		type Food,
		type LibraryRecipe,
		type ReceivedItem,
		type Recipe,
		type RecipeView,
		type ShareOffer
	} from '$lib/api';
	import PillChoices from '$lib/components/PillChoices.svelte';
	import RecipeViewModal from '$lib/components/RecipeViewModal.svelte';
	import { errorMessage } from '$lib/errors';
	import { refreshSharingPending } from '$lib/sharing.svelte';
	import { FOOD_CATEGORIES, foodCategoryLabel } from '$lib/foodCategories';
	import { normalizeSearch, searchMatches } from '$lib/text';
	import { showToast } from '$lib/toast.svelte';
	import { m } from '$lib/paraglide/messages';
	import { getLocale } from '$lib/paraglide/runtime';

	// Visualizacao read-only: biblioteca ja tem a forma certa; minhas receitas mapeiam.
	let viewRecipe = $state<RecipeView | null>(null);
	function openMyRecipeView(recipe: Recipe): void {
		viewRecipe = {
			name: recipe.name,
			tags: [],
			servings: recipe.servings,
			total: recipe.total,
			per_serving: recipe.per_serving,
			ingredients: recipe.ingredients.map((i) => ({ name: i.food.name, grams: i.grams, macros: i.macros })),
			is_favorite: recipe.is_favorite
		};
	}

	// A tela e das DUAS coisas que a pessoa cadastrou. Antes o alimento so era
	// alcancavel fingindo que se ia lancar uma refeicao (Adicionar > lapis), e nao
	// tinha onde ser criado nem compartilhado. As abas repetem o par que a modal de
	// adicionar ja ensina, entao ninguem precisa aprender nada novo.
	let tab = $state<'foods' | 'recipes'>('recipes');

	let recipes = $state<Recipe[]>([]);
	let myFoods = $state<Food[]>([]);
	let library = $state<LibraryRecipe[]>([]);
	let loading = $state(true);
	const nf = new Intl.NumberFormat(getLocale());

	// --- Compartilhar entre contas -------------------------------------------
	let connections = $state<Connection[]>([]);
	let offers = $state<ShareOffer[]>([]);
	let received = $state<ReceivedItem[]>([]);

	const partners = $derived(connections.filter((c) => c.status === 'accepted'));
	// item copiado de alguem -> nome de quem mandou (o selo "de Ana" na linha)
	const receivedFrom = $derived(
		new Map(received.filter((r) => r.item_kind === 'recipe').map((r) => [r.item_id, r.from_name]))
	);
	const receivedFoodFrom = $derived(
		new Map(received.filter((r) => r.item_kind === 'food').map((r) => [r.item_id, r.from_name]))
	);

	async function loadSharing(): Promise<void> {
		[connections, offers, received] = await Promise.all([
			api.getConnections(),
			api.getShareOffers(),
			api.getReceivedItems()
		]);
		// o badge da barra de abas precisa cair no mesmo instante em que a pilula cai
		await refreshSharingPending();
	}

	async function load(): Promise<void> {
		[recipes, myFoods, library] = await Promise.all([
			api.getRecipes(),
			// so o que a pessoa criou: o catalogo global nao e dela para editar ou mandar
			api.getFoods('', undefined, { scope: 'mine', limit: 200 }),
			api.getRecipeLibrary()
		]);
		await loadSharing();
		loading = false;
	}

	// A pilula tem dois estados de proposito: com contador ela avisa que tem coisa
	// esperando aceite (e abre a caixa de entrada); sem contador ela e so um filtro.
	let showInbox = $state(false);
	let onlyReceived = $state(false);
	let answering = $state<number | null>(null);

	function tapReceivedPill(): void {
		if (offers.length > 0) {
			showInbox = true;
			return;
		}
		onlyReceived = !onlyReceived;
	}

	async function acceptOffer(offer: ShareOffer): Promise<void> {
		answering = offer.id;
		try {
			await api.acceptShareOffer(offer.id);
			await load();
			showToast(m.sharing_added_toast());
			if (offers.length === 0) showInbox = false;
		} catch (e) {
			showToast(errorMessage(e instanceof ApiError ? e.code : 'GENERIC_ERROR'));
			await loadSharing();
		} finally {
			answering = null;
		}
	}

	async function declineOffer(offer: ShareOffer): Promise<void> {
		answering = offer.id;
		try {
			await api.declineShareOffer(offer.id);
			await loadSharing();
			showToast(m.sharing_dismissed_toast());
			if (offers.length === 0) showInbox = false;
		} finally {
			answering = null;
		}
	}

	// Selecao multipla: mandar tudo de uma vez e o caso do primeiro dia. A escolha
	// guarda o TIPO junto do id porque atravessa as abas - da para marcar a receita e
	// o tempero que ela leva e mandar os dois numa oferta so.
	let selecting = $state(false);
	let selected = $state<{ kind: 'food' | 'recipe'; id: number }[]>([]);
	let pickingPartner = $state(false);
	let sending = $state(false);

	function isSelected(kind: 'food' | 'recipe', id: number): boolean {
		return selected.some((x) => x.kind === kind && x.id === id);
	}

	function toggleSelected(kind: 'food' | 'recipe', id: number): void {
		selected = isSelected(kind, id)
			? selected.filter((x) => !(x.kind === kind && x.id === id))
			: [...selected, { kind, id }];
	}

	function startSelecting(): void {
		selecting = true;
		selected = [];
	}

	function cancelSelecting(): void {
		selecting = false;
		selected = [];
		pickingPartner = false;
	}

	function confirmShare(): void {
		// com um parceiro so nao ha o que escolher: vai direto
		if (partners.length === 1) {
			shareWith(partners[0]);
			return;
		}
		pickingPartner = true;
	}

	async function shareWith(partner: Connection): Promise<void> {
		sending = true;
		try {
			await api.createShareOffers(
				partner.id,
				selected.map((x) => ({ item_kind: x.kind, item_id: x.id }))
			);
			cancelSelecting();
			showToast(m.sharing_sent_toast({ name: partner.person_name }));
		} catch (e) {
			showToast(errorMessage(e instanceof ApiError ? e.code : 'GENERIC_ERROR'));
		} finally {
			sending = false;
		}
	}

	$effect(() => {
		load();
	});

	// Busca de verdade: sem acento/caixa (normalizeSearch) e olhando tambem os
	// INGREDIENTES da biblioteca ("frango" acha toda receita que leva frango).
	let query = $state('');
	const term = $derived(normalizeSearch(query));
	const filteredMyRecipes = $derived(
		recipes.filter(
			(r) => searchMatches(r.name, term) && (!onlyReceived || receivedFrom.has(r.id))
		)
	);

	const filteredMyFoods = $derived(
		myFoods.filter(
			(f) => searchMatches(f.name, term) && (!onlyReceived || receivedFoodFrom.has(f.id))
		)
	);

	async function toggleFoodFav(food: Food): Promise<void> {
		const { favorite } = await api.toggleFavorite('food', food.id);
		showToast(favorite ? m.toast_favorited() : m.toast_unfavorited());
		await load();
	}

	async function toggleRecipeFav(recipe: Recipe): Promise<void> {
		const { favorite } = await api.toggleFavorite('recipe', recipe.id);
		showToast(favorite ? m.toast_favorited() : m.toast_unfavorited());
		await load(); // backend devolve favoritas primeiro (recarrega minhas + biblioteca)
	}

	// --- Catalogo de alimentos -----------------------------------------------
	// O paralelo da biblioteca de receitas, com uma diferenca que muda o botao:
	// receita da biblioteca precisa ser COPIADA para virar sua, alimento do catalogo
	// ja da para lancar direto. Entao aqui nao existe "adotar" - copiar so criaria
	// um alimento igual disputando espaco na busca. O que faz diferenca e a
	// estrelinha: favorito sobe para o topo do picker na hora de lancar.
	let catalog = $state<Food[]>([]);
	let catalogLoading = $state(false);
	let catalogLoaded = $state(false);
	let activeCategory = $state<string | null>(null);

	// O endpoint corta em 200 por chamada e o catalogo ja passa disso, entao pagina
	// ate vir uma pagina curta - sem isso a tela mentiria dizendo que o alimento nao
	// existe so porque ele ficou depois do corte.
	async function loadCatalog(): Promise<void> {
		if (catalogLoaded || catalogLoading) return;
		catalogLoading = true;
		try {
			const pagina = 200;
			const todos: Food[] = [];
			for (let offset = 0; offset < 5000; offset += pagina) {
				const lote = await api.getFoods('', undefined, { scope: 'catalog', limit: pagina, offset });
				todos.push(...lote);
				if (lote.length < pagina) break;
			}
			catalog = todos;
			catalogLoaded = true;
		} finally {
			catalogLoading = false;
		}
	}

	// so busca o catalogo quando a aba de alimentos e aberta de fato
	$effect(() => {
		if (tab === 'foods') void loadCatalog();
	});

	const filteredCatalog = $derived(
		catalog.filter(
			(f) => (!activeCategory || f.category === activeCategory) && searchMatches(f.name, term)
		)
	);

	async function toggleCatalogFav(food: Food): Promise<void> {
		const { favorite } = await api.toggleFavorite('food', food.id);
		showToast(favorite ? m.toast_favorited() : m.toast_unfavorited());
		// so a linha muda de estado: recarregar o catalogo inteiro por uma estrela
		// custaria duas chamadas e faria a lista piscar
		catalog = catalog.map((f) => (f.id === food.id ? { ...f, is_favorite: favorite } : f));
	}

	// Biblioteca: filtro por tag e "adotar" (copia para as minhas receitas)
	const TAGS = ['protein', 'quick', 'veggie', 'sweet', 'budget'] as const;
	let activeTag = $state<string | null>(null);
	let adopting = $state<string | null>(null);

	function tagLabel(tag: string): string {
		return {
			protein: m.tag_protein(),
			quick: m.tag_quick(),
			veggie: m.tag_veggie(),
			sweet: m.tag_sweet(),
			budget: m.tag_budget()
		}[tag] ?? tag;
	}

	const filteredLibrary = $derived(
		library.filter(
			(r) =>
				(!activeTag || r.tags.includes(activeTag)) &&
				(searchMatches(r.name, term) ||
					r.ingredients.some((ing) => searchMatches(ing.name, term)))
		)
	);
	// nomes que o usuario ja tem (pra marcar como adicionada)
	const myNames = $derived(new Set(recipes.map((r) => r.name)));

	async function adopt(recipe: LibraryRecipe): Promise<void> {
		adopting = recipe.slug;
		try {
			await api.adoptLibraryRecipe(recipe.slug);
			await load();
			showToast(m.recipe_adopted());
		} finally {
			adopting = null;
		}
	}
</script>

<div class="mb-4 flex items-center gap-2">
	<a
		href="/dieta"
		aria-label={m.back()}
		class="grid h-10 w-10 place-items-center rounded-full bg-white text-slate-500 shadow-sm"
	>
		<svg viewBox="0 0 24 24" class="h-5 w-5" fill="none" stroke="currentColor" stroke-width="2">
			<path d="M15 6l-6 6 6 6" stroke-linecap="round" stroke-linejoin="round" />
		</svg>
	</a>
	<h1 class="min-w-0 flex-1 truncate text-2xl font-bold">{m.foods_and_recipes()}</h1>
	<!-- Verde, e nao branco: antes era um circulo cinza identico ao botao de voltar
		 logo ao lado, e ninguem achava. Aparece mesmo sem conexao - botao que some nao
		 ensina que a funcao existe; sem parceiro, ele leva para onde se convida alguem. -->
	{#if !loading && (recipes.length > 0 || myFoods.length > 0)}
		{#if partners.length > 0}
			<button
				type="button"
				aria-label={m.sharing_share_action()}
				title={m.sharing_share_action()}
				onclick={() => (selecting ? cancelSelecting() : startSelecting())}
				class="grid h-10 w-10 shrink-0 place-items-center rounded-full shadow-sm {selecting
					? 'bg-emerald-600 text-white'
					: 'bg-emerald-50 text-emerald-600 active:bg-emerald-100'}"
			>
				<svg viewBox="0 0 24 24" class="h-5 w-5" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="18" cy="5" r="3" /><circle cx="6" cy="12" r="3" /><circle cx="18" cy="19" r="3" /><path d="M8.6 13.5l6.8 4M15.4 6.5l-6.8 4" /></svg>
			</button>
		{:else}
			<a
				href="/perfil/conexoes"
				aria-label={m.sharing_share_action()}
				title={m.sharing_share_action()}
				class="grid h-10 w-10 shrink-0 place-items-center rounded-full bg-emerald-50 text-emerald-600 shadow-sm active:bg-emerald-100"
			>
				<svg viewBox="0 0 24 24" class="h-5 w-5" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="18" cy="5" r="3" /><circle cx="6" cy="12" r="3" /><circle cx="18" cy="19" r="3" /><path d="M8.6 13.5l6.8 4M15.4 6.5l-6.8 4" /></svg>
			</a>
		{/if}
	{/if}
</div>

{#if loading}
	<div class="flex justify-center py-16">
		<div class="h-8 w-8 animate-spin rounded-full border-4 border-emerald-600 border-t-transparent"></div>
	</div>
{:else}
	<!-- Mesmo par de abas da modal de adicionar: o padrao ja e conhecido. A selecao
		 de compartilhar NAO se perde ao trocar de aba - e de proposito. -->
	<div class="mb-3 grid grid-cols-2 gap-2">
		<button
			type="button"
			onclick={() => (tab = 'foods')}
			class="h-11 rounded-2xl font-semibold {tab === 'foods'
				? 'bg-emerald-600 text-white'
				: 'bg-white text-slate-600 shadow-sm'}"
		>
			{m.foods_tab()}
		</button>
		<button
			type="button"
			onclick={() => (tab = 'recipes')}
			class="h-11 rounded-2xl font-semibold {tab === 'recipes'
				? 'bg-emerald-600 text-white'
				: 'bg-white text-slate-600 shadow-sm'}"
		>
			{m.recipes_tab()}
		</button>
	</div>

	<!-- busca sem acento/caixa; na biblioteca vale tambem por INGREDIENTE -->
	<div class="relative mb-4">
		<svg viewBox="0 0 24 24" class="pointer-events-none absolute top-1/2 left-4 h-5 w-5 -translate-y-1/2 text-slate-400" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="7" /><path d="M21 21l-4.3-4.3" stroke-linecap="round" /></svg>
		<input
			bind:value={query}
			placeholder={tab === 'foods' ? m.search_food() : m.search_recipes()}
			class="h-12 w-full rounded-2xl border-2 border-slate-200 bg-white pr-11 pl-11 outline-none focus:border-emerald-600"
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

	<!-- Pilula "Recebidas": com contador ela avisa que tem coisa esperando aceite e
		 abre a caixa de entrada; sem contador, e so um filtro da lista. -->
	{#if offers.length > 0 || received.length > 0}
		<div class="mb-3 flex gap-2">
			<button
				type="button"
				onclick={() => (onlyReceived = false)}
				class="rounded-full px-4 py-2 text-sm font-bold {onlyReceived
					? 'bg-white text-slate-500 shadow-sm'
					: 'bg-slate-900 text-white'}"
			>
				{m.filter_all()}
			</button>
			<button
				type="button"
				onclick={tapReceivedPill}
				class="flex items-center gap-2 rounded-full px-4 py-2 text-sm font-bold {offers.length > 0
					? 'bg-rose-50 text-rose-700 ring-2 ring-rose-200'
					: onlyReceived
						? 'bg-slate-900 text-white'
						: 'bg-white text-slate-500 shadow-sm'}"
			>
				{m.sharing_received_pill()}
				{#if offers.length > 0}
					<span class="grid h-5 min-w-5 place-items-center rounded-full bg-rose-600 px-1.5 text-[11px] text-white">
						{offers.length}
					</span>
				{/if}
			</button>
		</div>
	{/if}

	{#if tab === 'foods'}
		{#if myFoods.length === 0}
			<div class="rounded-3xl border-2 border-dashed border-slate-200 p-8 text-center">
				<p class="font-semibold text-slate-600">{m.no_foods_title()}</p>
				<p class="mt-1 text-sm text-slate-400">{m.no_foods_text()}</p>
			</div>
		{:else if filteredMyFoods.length === 0}
			<p class="rounded-2xl bg-white px-4 py-3 text-center text-sm text-slate-400 shadow-sm">
				{m.search_no_results()}
			</p>
		{:else}
			<div class="space-y-2">
				{#each filteredMyFoods as food (food.id)}
					{@const sharedBy = receivedFoodFrom.get(food.id)}
					{@const picked = isSelected('food', food.id)}
					<div
						class="flex items-center gap-1 rounded-2xl bg-white p-1.5 shadow-sm {selecting && picked
							? 'ring-2 ring-emerald-500'
							: ''}"
					>
						{#if selecting}
							<button
								type="button"
								aria-label={food.name}
								onclick={() => toggleSelected('food', food.id)}
								class="flex min-w-0 flex-1 items-center gap-2.5 rounded-xl p-2 text-left active:bg-slate-50"
							>
								<span
									class="grid h-6 w-6 shrink-0 place-items-center rounded-lg border-2 {picked
										? 'border-emerald-600 bg-emerald-600 text-white'
										: 'border-slate-300'}"
								>
									{#if picked}
										<svg viewBox="0 0 24 24" class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="3"><path d="M5 12l5 5L19 7" stroke-linecap="round" stroke-linejoin="round" /></svg>
									{/if}
								</span>
								<div class="min-w-0 flex-1">
									<p class="truncate font-bold text-slate-900">{food.name}</p>
									<p class="truncate text-sm text-slate-500">
										{nf.format(Math.round(food.kcal))} kcal / 100 g
									</p>
								</div>
							</button>
						{:else}
							<a
								href="/dieta/alimento/{food.id}"
								class="flex min-w-0 flex-1 items-center rounded-xl p-2 active:bg-slate-50"
							>
								<div class="min-w-0 flex-1">
									<p class="truncate font-bold text-slate-900">{food.name}</p>
									<p class="text-sm text-slate-500">
										{nf.format(Math.round(food.kcal))} kcal / 100 g
										· {m.default_portion()} {nf.format(food.default_portion_g)} g
									</p>
									{#if sharedBy}
										<span class="mt-1 inline-block rounded-full bg-rose-50 px-2 py-0.5 text-[10px] font-bold text-rose-700">
											{m.sharing_from({ name: sharedBy })}
										</span>
									{/if}
								</div>
							</a>
							<div class="flex shrink-0 items-center">
								<button
									type="button"
									aria-label={m.favorite_toggle()}
									title={m.favorite_toggle()}
									onclick={() => toggleFoodFav(food)}
									class="grid h-11 w-11 place-items-center rounded-xl active:bg-slate-100"
								>
									<svg
										viewBox="0 0 24 24"
										class="h-[22px] w-[22px] {food.is_favorite ? 'text-amber-400' : 'text-slate-300'}"
										fill={food.is_favorite ? 'currentColor' : 'none'}
										stroke="currentColor"
										stroke-width="2"
										stroke-linejoin="round"
									>
										<path d="M12 3l2.9 5.9 6.5.9-4.7 4.6 1.1 6.5L12 17.8 6.2 20.9l1.1-6.5L2.6 9.8l6.5-.9z" stroke-linecap="round" />
									</svg>
								</button>
								<a
									href="/dieta/alimento/{food.id}"
									aria-label={m.edit()}
									title={m.edit()}
									class="grid h-11 w-11 place-items-center rounded-xl text-slate-400 active:bg-slate-100"
								>
									<svg viewBox="0 0 24 24" class="h-[22px] w-[22px]" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 20h9M16.5 3.5a2.1 2.1 0 013 3L7 19l-4 1 1-4z" /></svg>
								</a>
							</div>
						{/if}
					</div>
				{/each}
			</div>
		{/if}

		{#if !selecting}
			<a
				href="/dieta/alimento/novo"
				class="mt-4 flex h-14 w-full items-center justify-center rounded-2xl bg-emerald-600 text-lg font-bold text-white active:bg-emerald-700"
			>
				+ {m.create_food()}
			</a>
		{/if}

		<!-- Catalogo que vem com o app. Sem botao de adotar: o alimento daqui ja pode
			 ser lancado como esta - o que muda a vida e a estrela, que o faz aparecer
			 primeiro na hora de montar a refeicao. -->
		<section class="mt-8">
			<h2 class="text-lg font-bold text-slate-900">{m.food_library_title()}</h2>
			<p class="mt-0.5 text-sm text-slate-500">{m.food_library_hint()}</p>

			{#if catalogLoading}
				<div class="flex justify-center py-10">
					<div class="h-7 w-7 animate-spin rounded-full border-4 border-emerald-600 border-t-transparent"></div>
				</div>
			{:else}
				<div class="mt-3">
					<PillChoices
						bind:value={activeCategory}
						clearLabel={m.tag_all()}
						options={FOOD_CATEGORIES.map((category) => ({
							value: category,
							label: foodCategoryLabel(category)
						}))}
					/>
				</div>

				{#if filteredCatalog.length === 0}
					<p class="mt-3 rounded-2xl bg-white px-4 py-3 text-center text-sm text-slate-400 shadow-sm">
						{m.search_no_results()}
					</p>
				{:else}
					<p class="mt-3 text-xs font-semibold text-slate-400">
						{m.food_library_count({ count: filteredCatalog.length })}
					</p>
					<div class="mt-1.5 space-y-2">
						{#each filteredCatalog as food (food.id)}
							<div class="flex items-center gap-2 rounded-2xl bg-white p-3.5 shadow-sm">
								<div class="min-w-0 flex-1">
									<p class="truncate font-semibold text-slate-900">{food.name}</p>
									<p class="text-xs text-slate-500">
										{nf.format(Math.round(food.kcal))} kcal · P {nf.format(Math.round(food.protein_g))}g
										C {nf.format(Math.round(food.carbs_g))}g G {nf.format(Math.round(food.fat_g))}g · 100 g
									</p>
								</div>
								<button
									type="button"
									aria-label={m.favorite_toggle()}
									title={m.favorite_toggle()}
									onclick={() => toggleCatalogFav(food)}
									class="grid h-10 w-10 shrink-0 place-items-center rounded-xl active:bg-slate-100"
								>
									<svg
										viewBox="0 0 24 24"
										class="h-[22px] w-[22px] {food.is_favorite ? 'text-amber-400' : 'text-slate-300'}"
										fill={food.is_favorite ? 'currentColor' : 'none'}
										stroke="currentColor"
										stroke-width="2"
										stroke-linejoin="round"
									>
										<path d="M12 3l2.9 5.9 6.5.9-4.7 4.6 1.1 6.5L12 17.8 6.2 20.9l1.1-6.5L2.6 9.8l6.5-.9z" stroke-linecap="round" />
									</svg>
								</button>
							</div>
						{/each}
					</div>
				{/if}
			{/if}
		</section>
	{:else}
	{#if recipes.length === 0}
		<div class="rounded-3xl border-2 border-dashed border-slate-200 p-8 text-center">
			<p class="font-semibold text-slate-600">{m.no_recipes_title()}</p>
			<p class="mt-1 text-sm text-slate-400">{m.no_recipes_text()}</p>
		</div>
	{:else if filteredMyRecipes.length === 0}
		<p class="rounded-2xl bg-white px-4 py-3 text-center text-sm text-slate-400 shadow-sm">{m.search_no_results()}</p>
	{:else}
		<div class="space-y-2">
			{#each filteredMyRecipes as recipe (recipe.id)}
				{@const sharedBy = receivedFrom.get(recipe.id)}
				{@const picked = isSelected('recipe', recipe.id)}
				<div
					class="flex items-center gap-1 rounded-2xl bg-white p-1.5 shadow-sm {selecting && picked
						? 'ring-2 ring-emerald-500'
						: ''}"
				>
					{#if selecting}
						<button
							type="button"
							aria-label={recipe.name}
							onclick={() => toggleSelected('recipe', recipe.id)}
							class="flex min-w-0 flex-1 items-center gap-2.5 rounded-xl p-2 text-left active:bg-slate-50"
						>
							<span
								class="grid h-6 w-6 shrink-0 place-items-center rounded-lg border-2 {picked
									? 'border-emerald-600 bg-emerald-600 text-white'
									: 'border-slate-300'}"
							>
								{#if picked}
									<svg viewBox="0 0 24 24" class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="3"><path d="M5 12l5 5L19 7" stroke-linecap="round" stroke-linejoin="round" /></svg>
								{/if}
							</span>
							<div class="min-w-0 flex-1">
								<p class="truncate font-bold text-slate-900">{recipe.name}</p>
								<p class="truncate text-sm text-slate-500">
									{nf.format(Math.round(recipe.per_serving.kcal))} kcal/{m.serving_singular()}
								</p>
							</div>
						</button>
					{:else}
					<a
						href="/dieta/receita/{recipe.id}"
						class="flex min-w-0 flex-1 items-center rounded-xl p-2 active:bg-slate-50"
					>
						<div class="min-w-0 flex-1">
							<p class="truncate font-bold text-slate-900">{recipe.name}</p>
							<p class="text-sm text-slate-500">
								{recipe.ingredients.length}
								{recipe.ingredients.length === 1 ? m.ingredient_singular() : m.ingredient_plural()}
								· {nf.format(Math.round(recipe.per_serving.kcal))} kcal/{m.serving_singular()}
							</p>
							<!-- a origem e um fato, nao um estado: o selo fica mesmo depois de editar -->
							{#if sharedBy}
								<span class="mt-1 inline-block rounded-full bg-rose-50 px-2 py-0.5 text-[10px] font-bold text-rose-700">
									{m.sharing_from({ name: sharedBy })}
								</span>
							{/if}
						</div>
					</a>
					<!-- grupo de acoes: alvos de toque maiores (h-11) e bem juntos (gap-0).
						 No modo de selecao ele sai: a linha inteira e um alvo de escolha. -->
					<div class="flex shrink-0 items-center">
						<button
							type="button"
							aria-label={m.recipe_view()}
							title={m.recipe_view()}
							onclick={() => openMyRecipeView(recipe)}
							class="grid h-11 w-11 place-items-center rounded-xl text-amber-600 active:bg-amber-50"
						>
							<svg viewBox="0 0 24 24" class="h-[22px] w-[22px]" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7-10-7-10-7z" /><circle cx="12" cy="12" r="3" /></svg>
						</button>
						<button
							type="button"
							aria-label={m.favorite_toggle()}
							title={m.favorite_toggle()}
							onclick={() => toggleRecipeFav(recipe)}
							class="grid h-11 w-11 place-items-center rounded-xl active:bg-slate-100"
						>
							<svg
								viewBox="0 0 24 24"
								class="h-[22px] w-[22px] {recipe.is_favorite ? 'text-amber-400' : 'text-slate-300'}"
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
							class="grid h-11 w-11 place-items-center rounded-xl text-slate-400 active:bg-slate-100"
						>
							<svg viewBox="0 0 24 24" class="h-[22px] w-[22px]" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 20h9M16.5 3.5a2.1 2.1 0 013 3L7 19l-4 1 1-4z" /></svg>
						</a>
					</div>
					{/if}
				</div>
			{/each}
		</div>
	{/if}

	{#if !selecting}
		<a
			href="/dieta/receita/nova"
			class="mt-4 flex h-14 w-full items-center justify-center rounded-2xl bg-emerald-600 text-lg font-bold text-white active:bg-emerald-700"
		>
			+ {m.create_recipe()}
		</a>
	{/if}

	<!-- Biblioteca de receitas semente: macros calculados dos ingredientes do catalogo -->
	{#if library.length > 0}
		<section class="mt-8">
			<h2 class="text-lg font-bold text-slate-900">{m.library_title()}</h2>
			<p class="mt-0.5 text-sm text-slate-500">{m.library_hint()}</p>

			<div class="mt-3">
				<PillChoices
					bind:value={activeTag}
					clearLabel={m.tag_all()}
					options={TAGS.map((tag) => ({ value: tag, label: tagLabel(tag) }))}
				/>
			</div>

			{#if filteredLibrary.length === 0}
				<p class="mt-3 rounded-2xl bg-white px-4 py-3 text-center text-sm text-slate-400 shadow-sm">{m.search_no_results()}</p>
			{/if}
			<div class="mt-3 space-y-2">
				{#each filteredLibrary as recipe (recipe.slug)}
					{@const owned = myNames.has(recipe.name)}
					<div class="flex items-center gap-2 rounded-2xl bg-white p-3.5 shadow-sm">
						<div class="min-w-0 flex-1">
							<p class="truncate font-semibold text-slate-900">{recipe.name}</p>
							<p class="text-xs text-slate-500">
								{nf.format(Math.round(recipe.per_serving.kcal))} kcal · P {nf.format(Math.round(recipe.per_serving.protein_g))}g /{m.serving_singular()}
								· {recipe.ingredients.length} {recipe.ingredients.length === 1 ? m.ingredient_singular() : m.ingredient_plural()}
							</p>
						</div>
						<button
							type="button"
							aria-label={m.recipe_view()}
							title={m.recipe_view()}
							onclick={() => (viewRecipe = recipe)}
							class="grid h-9 w-9 shrink-0 place-items-center rounded-xl border-2 border-amber-200 text-amber-600 active:bg-amber-100"
						>
							<svg viewBox="0 0 24 24" class="h-4.5 w-4.5" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7-10-7-10-7z" /><circle cx="12" cy="12" r="3" /></svg>
						</button>
						{#if owned}
							<span class="grid h-9 w-9 shrink-0 place-items-center rounded-xl bg-emerald-100 text-emerald-700">
								<svg viewBox="0 0 24 24" class="h-5 w-5" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M5 13l4 4L19 7" /></svg>
							</span>
						{:else}
							<button
								type="button"
								aria-label={m.recipe_adopt()}
								title={m.recipe_adopt()}
								disabled={adopting === recipe.slug}
								onclick={() => adopt(recipe)}
								class="grid h-9 w-9 shrink-0 place-items-center rounded-xl bg-emerald-600 text-white active:bg-emerald-700 disabled:opacity-50"
							>
								<svg viewBox="0 0 24 24" class="h-5 w-5" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"><path d="M12 5v14M5 12h14" /></svg>
							</button>
						{/if}
					</div>
				{/each}
			</div>
		</section>
		{/if}
	{/if}
{/if}

<!-- Visualizacao read-only da receita (biblioteca ou minha) -->
{#if viewRecipe}
	<RecipeViewModal recipe={viewRecipe} onClose={() => (viewRecipe = null)} />
{/if}

<!-- Barra fixa do modo de selecao: fica no rodape para o polegar alcancar -->
{#if selecting}
	<div class="fixed inset-x-0 bottom-0 z-40 border-t border-slate-200 bg-white/95 p-4 backdrop-blur">
		<div class="mx-auto flex max-w-md items-center gap-2">
			<span class="min-w-0 flex-1 truncate text-sm font-bold text-slate-600">
				{m.sharing_selected_count({ count: selected.length })}
			</span>
			<button
				type="button"
				onclick={cancelSelecting}
				class="h-11 shrink-0 rounded-xl px-3 text-sm font-semibold text-slate-500 active:bg-slate-100"
			>
				{m.cancel()}
			</button>
			<button
				type="button"
				disabled={selected.length === 0 || sending}
				onclick={confirmShare}
				class="h-11 shrink-0 rounded-xl bg-emerald-600 px-5 text-sm font-bold text-white active:bg-emerald-700 disabled:opacity-40"
			>
				{m.sharing_share_action()}
			</button>
		</div>
	</div>
{/if}

<!-- Com mais de uma conexao, escolher para quem vai -->
{#if pickingPartner}
	<div
		class="fixed inset-0 z-50 flex items-end justify-center bg-black/50 p-4"
		role="button"
		tabindex="-1"
		onclick={() => (pickingPartner = false)}
		onkeydown={(e) => e.key === 'Escape' && (pickingPartner = false)}
	>
		<div
			class="w-full max-w-md rounded-3xl bg-white p-5"
			role="dialog"
			tabindex="-1"
			onclick={(e) => e.stopPropagation()}
			onkeydown={() => {}}
		>
			<p class="mb-3 font-bold text-slate-900">{m.sharing_share_action()}</p>
			<div class="space-y-2">
				{#each partners as partner (partner.id)}
					<button
						type="button"
						disabled={sending}
						onclick={() => shareWith(partner)}
						class="flex w-full items-center gap-3 rounded-2xl bg-slate-50 p-3 text-left active:bg-slate-100 disabled:opacity-50"
					>
						<span class="min-w-0 flex-1 truncate font-semibold text-slate-800">
							{partner.person_name}
						</span>
						<svg viewBox="0 0 24 24" class="h-5 w-5 shrink-0 text-slate-300" fill="none" stroke="currentColor" stroke-width="2"><path d="M9 6l6 6-6 6" stroke-linecap="round" stroke-linejoin="round" /></svg>
					</button>
				{/each}
			</div>
		</div>
	</div>
{/if}

<!-- Caixa de entrada: nada entra na conta sem a pessoa aceitar -->
{#if showInbox}
	<div
		class="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
		role="button"
		tabindex="-1"
		onclick={() => (showInbox = false)}
		onkeydown={(e) => e.key === 'Escape' && (showInbox = false)}
	>
		<div
			class="max-h-[90dvh] w-full max-w-md overflow-y-auto rounded-3xl bg-white p-5"
			role="dialog"
			tabindex="-1"
			onclick={(e) => e.stopPropagation()}
			onkeydown={() => {}}
		>
			<div class="mb-3 flex items-start justify-between gap-2">
				<h2 class="text-lg font-bold text-slate-900">{m.sharing_inbox_title()}</h2>
				<button
					type="button"
					aria-label={m.close()}
					onclick={() => (showInbox = false)}
					class="grid h-10 w-10 shrink-0 place-items-center rounded-full bg-slate-100 text-slate-500 active:bg-slate-200"
				>
					<svg viewBox="0 0 24 24" class="h-5 w-5" fill="none" stroke="currentColor" stroke-width="2"><path d="M6 6l12 12M18 6L6 18" stroke-linecap="round" /></svg>
				</button>
			</div>

			<div class="space-y-2">
				{#each offers as offer (offer.id)}
					<div class="rounded-2xl bg-slate-50 p-3">
						<p class="text-[10px] font-bold tracking-wide text-slate-400 uppercase">
							{offer.item_kind === 'recipe' ? m.sharing_kind_recipe() : m.sharing_kind_food()}
						</p>
						<p class="truncate font-bold text-slate-900">{offer.item_name}</p>
						<p class="text-xs font-semibold text-rose-700">
							{m.sharing_from({ name: offer.from_name })}
						</p>
						<div class="mt-2.5 flex gap-2">
							<button
								type="button"
								disabled={answering === offer.id}
								onclick={() => acceptOffer(offer)}
								class="h-10 flex-1 rounded-xl bg-emerald-600 text-sm font-bold text-white active:bg-emerald-700 disabled:opacity-50"
							>
								{m.sharing_add_action()}
							</button>
							<button
								type="button"
								disabled={answering === offer.id}
								onclick={() => declineOffer(offer)}
								class="h-10 shrink-0 rounded-xl px-3 text-sm font-semibold text-slate-500 active:bg-slate-100 disabled:opacity-50"
							>
								{m.sharing_dismiss_action()}
							</button>
						</div>
					</div>
				{/each}
			</div>
		</div>
	</div>
{/if}
