<script lang="ts">
	import type { RecipeView } from '$lib/api';
	import { m } from '$lib/paraglide/messages';
	import { getLocale } from '$lib/paraglide/runtime';

	// Visualizacao READ-ONLY de uma receita (biblioteca ou favorita): mostra a ficha
	// inteira antes de incluir. Nao edita nada. Acao primaria opcional (incluir/adotar).
	let {
		recipe,
		loading = false,
		onClose,
		actionLabel = null,
		onAction = null,
		actionBusy = false
	}: {
		recipe: RecipeView | null;
		loading?: boolean;
		onClose: () => void;
		actionLabel?: string | null;
		onAction?: (() => void) | null;
		actionBusy?: boolean;
	} = $props();

	const nf = new Intl.NumberFormat(getLocale());

	function tagLabel(tag: string): string {
		return (
			{
				protein: m.tag_protein(),
				quick: m.tag_quick(),
				veggie: m.tag_veggie(),
				sweet: m.tag_sweet(),
				budget: m.tag_budget()
			}[tag] ?? tag
		);
	}
</script>

<div
	class="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
	role="button"
	tabindex="-1"
	onclick={onClose}
	onkeydown={(e) => e.key === 'Escape' && onClose()}
>
	<div
		class="max-h-[90dvh] w-full max-w-md overflow-y-auto rounded-3xl bg-white"
		role="dialog"
		aria-modal="true"
		tabindex="-1"
		onclick={(e) => e.stopPropagation()}
		onkeydown={() => {}}
	>
		{#if loading || !recipe}
			<div class="flex justify-center py-20">
				<div class="h-8 w-8 animate-spin rounded-full border-4 border-amber-500 border-t-transparent"></div>
			</div>
		{:else}
			<!-- Cabecalho com acento ambar (receitas), prato + nome + favorito -->
			<header class="relative rounded-t-3xl bg-gradient-to-b from-amber-50 to-white px-5 pt-5 pb-4">
				<button
					type="button"
					aria-label={m.close()}
					onclick={onClose}
					class="absolute top-4 right-4 grid h-9 w-9 place-items-center rounded-full bg-white/80 text-slate-500 shadow-sm active:bg-slate-100"
				>
					<svg viewBox="0 0 24 24" class="h-5 w-5" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M6 6l12 12M18 6L6 18" /></svg>
				</button>
				<div class="flex items-start gap-3 pr-10">
					<span class="grid h-11 w-11 shrink-0 place-items-center rounded-2xl bg-amber-100 text-amber-600">
						<svg viewBox="0 0 24 24" class="h-6 w-6" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3v6M9 3h6M7 9h10l-1.2 9.2A2 2 0 0 1 13.8 20h-3.6a2 2 0 0 1-2-1.8z" /></svg>
					</span>
					<div class="min-w-0 flex-1">
						<h2 class="flex items-center gap-1.5 text-lg leading-tight font-bold text-slate-900">
							<span class="min-w-0">{recipe.name}</span>
							{#if recipe.is_favorite}
								<svg viewBox="0 0 24 24" class="h-4 w-4 shrink-0 text-amber-400" fill="currentColor"><path d="M12 3l2.9 5.9 6.5.9-4.7 4.6 1.1 6.5L12 17.8 6.2 20.9l1.1-6.5L2.6 9.8l6.5-.9z" /></svg>
							{/if}
						</h2>
						<p class="mt-0.5 text-xs text-slate-500">
							{m.recipe_yield()}
							{recipe.servings}
							{recipe.servings === 1 ? m.serving_singular() : m.serving_plural()}
						</p>
						{#if recipe.tags.length > 0}
							<div class="mt-2 flex flex-wrap gap-1.5">
								{#each recipe.tags as tag (tag)}
									<span class="rounded-full bg-amber-100 px-2.5 py-0.5 text-xs font-semibold text-amber-700">{tagLabel(tag)}</span>
								{/each}
							</div>
						{/if}
					</div>
				</div>
			</header>

			<div class="px-5 pb-5">
				<!-- Macros por porcao (o que sera lancado) -->
				<p class="mb-1.5 text-xs font-bold text-slate-400 uppercase">{m.per_serving_label()}</p>
				<div class="grid grid-cols-4 gap-2 rounded-2xl bg-amber-50 py-3 text-center">
					<div>
						<p class="text-lg font-bold text-slate-900">{nf.format(Math.round(recipe.per_serving.kcal))}</p>
						<p class="text-xs text-slate-400">kcal</p>
					</div>
					<div>
						<p class="text-lg font-bold text-slate-900">{nf.format(Math.round(recipe.per_serving.protein_g))}</p>
						<p class="text-xs text-slate-400">P</p>
					</div>
					<div>
						<p class="text-lg font-bold text-slate-900">{nf.format(Math.round(recipe.per_serving.carbs_g))}</p>
						<p class="text-xs text-slate-400">C</p>
					</div>
					<div>
						<p class="text-lg font-bold text-slate-900">{nf.format(Math.round(recipe.per_serving.fat_g))}</p>
						<p class="text-xs text-slate-400">G</p>
					</div>
				</div>

				<!-- Ingredientes -->
				<p class="mt-5 mb-1 text-xs font-bold text-slate-400 uppercase">{m.ingredients_title()}</p>
				<ul class="divide-y divide-slate-100">
					{#each recipe.ingredients as ing (ing.name)}
						<li class="flex items-center justify-between gap-3 py-2.5">
							<span class="min-w-0 flex-1 truncate text-sm text-slate-700">{ing.name}</span>
							<span class="shrink-0 text-sm font-semibold text-slate-500 tabular-nums">{nf.format(ing.grams)} g</span>
						</li>
					{/each}
				</ul>

				<p class="mt-3 text-center text-xs text-slate-400">
					{m.whole_recipe()}: {nf.format(Math.round(recipe.total.kcal))} kcal · {recipe.servings}
					{recipe.servings === 1 ? m.serving_singular() : m.serving_plural()}
				</p>

				{#if actionLabel && onAction}
					<button
						type="button"
						disabled={actionBusy}
						onclick={onAction}
						class="mt-4 h-14 w-full rounded-2xl bg-amber-500 text-lg font-bold text-white active:bg-amber-600 disabled:opacity-50"
					>
						{actionLabel}
					</button>
				{/if}
			</div>
		{/if}
	</div>
</div>
