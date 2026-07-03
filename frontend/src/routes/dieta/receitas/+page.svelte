<script lang="ts">
	import { api, type Recipe } from '$lib/api';
	import { m } from '$lib/paraglide/messages';
	import { getLocale } from '$lib/paraglide/runtime';

	let recipes = $state<Recipe[]>([]);
	let loading = $state(true);
	const nf = new Intl.NumberFormat(getLocale());

	async function load(): Promise<void> {
		recipes = await api.getRecipes();
		loading = false;
	}

	$effect(() => {
		load();
	});
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
	{#if recipes.length === 0}
		<div class="rounded-3xl border-2 border-dashed border-slate-200 p-8 text-center">
			<p class="font-semibold text-slate-600">{m.no_recipes_title()}</p>
			<p class="mt-1 text-sm text-slate-400">{m.no_recipes_text()}</p>
		</div>
	{:else}
		<div class="space-y-2">
			{#each recipes as recipe (recipe.id)}
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
					<span class="text-sm font-semibold text-slate-400">{m.edit()}</span>
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
{/if}
