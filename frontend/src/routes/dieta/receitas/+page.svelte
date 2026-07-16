<script lang="ts">
	import { api, type LibraryRecipe, type Recipe } from '$lib/api';
	import { normalizeSearch, searchMatches } from '$lib/text';
	import { showToast } from '$lib/toast.svelte';
	import { m } from '$lib/paraglide/messages';
	import { getLocale } from '$lib/paraglide/runtime';

	let recipes = $state<Recipe[]>([]);
	let library = $state<LibraryRecipe[]>([]);
	let loading = $state(true);
	const nf = new Intl.NumberFormat(getLocale());

	async function load(): Promise<void> {
		[recipes, library] = await Promise.all([api.getRecipes(), api.getRecipeLibrary()]);
		loading = false;
	}

	$effect(() => {
		load();
	});

	// Busca de verdade: sem acento/caixa (normalizeSearch) e olhando tambem os
	// INGREDIENTES da biblioteca ("frango" acha toda receita que leva frango).
	let query = $state('');
	const term = $derived(normalizeSearch(query));
	const filteredMyRecipes = $derived(
		recipes.filter((r) => searchMatches(r.name, term))
	);

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
	<h1 class="text-2xl font-bold">{m.my_recipes()}</h1>
</div>

{#if loading}
	<div class="flex justify-center py-16">
		<div class="h-8 w-8 animate-spin rounded-full border-4 border-emerald-600 border-t-transparent"></div>
	</div>
{:else}
	<!-- busca sem acento/caixa; na biblioteca vale tambem por INGREDIENTE -->
	<div class="relative mb-4">
		<svg viewBox="0 0 24 24" class="pointer-events-none absolute top-1/2 left-4 h-5 w-5 -translate-y-1/2 text-slate-400" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="7" /><path d="M21 21l-4.3-4.3" stroke-linecap="round" /></svg>
		<input
			bind:value={query}
			placeholder={m.search_recipes()}
			class="h-12 w-full rounded-2xl border-2 border-slate-200 bg-white pr-4 pl-11 outline-none focus:border-emerald-600"
		/>
	</div>

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
				<a
					href="/dieta/receita/{recipe.id}"
					class="flex items-center justify-between rounded-2xl bg-white p-4 shadow-sm active:bg-slate-50"
				>
					<div class="min-w-0 flex-1">
						<p class="truncate font-bold text-slate-900">{recipe.name}</p>
						<p class="text-sm text-slate-500">
							{recipe.ingredients.length}
							{recipe.ingredients.length === 1 ? m.ingredient_singular() : m.ingredient_plural()}
							· {nf.format(Math.round(recipe.per_serving.kcal))} kcal/{m.serving_singular()}
						</p>
					</div>
					<span aria-label={m.edit()} title={m.edit()} class="grid h-9 w-9 shrink-0 place-items-center rounded-xl text-slate-400">
						<svg viewBox="0 0 24 24" class="h-5 w-5" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 20h9M16.5 3.5a2.1 2.1 0 013 3L7 19l-4 1 1-4z" /></svg>
					</span>
				</a>
			{/each}
		</div>
	{/if}

	<a
		href="/dieta/receita/nova"
		class="mt-4 flex h-14 w-full items-center justify-center rounded-2xl bg-emerald-600 text-lg font-bold text-white active:bg-emerald-700"
	>
		+ {m.create_recipe()}
	</a>

	<!-- Biblioteca de receitas semente: macros calculados dos ingredientes do catalogo -->
	{#if library.length > 0}
		<section class="mt-8">
			<h2 class="text-lg font-bold text-slate-900">{m.library_title()}</h2>
			<p class="mt-0.5 text-sm text-slate-500">{m.library_hint()}</p>

			<div class="mt-3 flex flex-wrap gap-1.5">
				<button
					type="button"
					onclick={() => (activeTag = null)}
					class="rounded-full border-2 px-3 py-1.5 text-sm font-semibold {activeTag === null
						? 'border-emerald-600 bg-emerald-50 text-emerald-800'
						: 'border-slate-200 text-slate-600'}"
				>
					{m.tag_all()}
				</button>
				{#each TAGS as tag (tag)}
					<button
						type="button"
						onclick={() => (activeTag = activeTag === tag ? null : tag)}
						class="rounded-full border-2 px-3 py-1.5 text-sm font-semibold {activeTag === tag
							? 'border-emerald-600 bg-emerald-50 text-emerald-800'
							: 'border-slate-200 text-slate-600'}"
					>
						{tagLabel(tag)}
					</button>
				{/each}
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
