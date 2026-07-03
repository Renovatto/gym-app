<script lang="ts">
	import { api, localDay, type DiaryDay, type MealType } from '$lib/api';
	import MacroSummary from '$lib/components/MacroSummary.svelte';
	import { MEAL_TYPES, mealTypeLabel } from '$lib/labels';
	import { m } from '$lib/paraglide/messages';
	import { getLocale } from '$lib/paraglide/runtime';

	let diary = $state<DiaryDay | null>(null);
	let loading = $state(true);

	const nf = new Intl.NumberFormat(getLocale());
	const today = localDay();

	async function load(): Promise<void> {
		diary = await api.getDiary(today);
		loading = false;
	}

	async function removeEntry(id: number): Promise<void> {
		await api.deleteDiaryEntry(id);
		await load();
	}

	function mealGroup(meal: MealType) {
		return diary?.meals.find((g) => g.meal_type === meal);
	}

	$effect(() => {
		load();
	});
</script>

<h1 class="mb-4 text-2xl font-bold">{m.tab_diet()}</h1>

{#if loading}
	<div class="flex justify-center py-16">
		<div class="h-8 w-8 animate-spin rounded-full border-4 border-emerald-600 border-t-transparent"></div>
	</div>
{:else if diary}
	<MacroSummary totals={diary.totals} goals={diary.goals} />

	<div class="mt-4 space-y-3">
		{#each MEAL_TYPES as meal (meal)}
			{@const group = mealGroup(meal)}
			<section class="rounded-3xl bg-white p-4 shadow-sm">
				<div class="flex items-center justify-between">
					<h2 class="font-bold text-slate-900">{mealTypeLabel(meal)}</h2>
					<span class="text-sm font-semibold text-slate-400">
						{group ? nf.format(Math.round(group.subtotal.kcal)) : 0} kcal
					</span>
				</div>

				{#if group && group.entries.length > 0}
					<div class="mt-2 space-y-1">
						{#each group.entries as entry (entry.id)}
							<div class="flex items-center gap-2 rounded-xl bg-slate-50 px-3 py-2">
								<div class="min-w-0 flex-1">
									<p class="truncate text-sm font-semibold text-slate-800">{entry.name}</p>
									<p class="text-xs text-slate-500">
										{entry.source === 'recipe'
											? `${nf.format(entry.quantity)} ${entry.quantity === 1 ? m.serving_singular() : m.serving_plural()}`
											: `${nf.format(entry.quantity)} g`}
										· {nf.format(Math.round(entry.macros.kcal))} kcal
									</p>
								</div>
								<button
									type="button"
									aria-label={m.remove()}
									onclick={() => removeEntry(entry.id)}
									class="text-slate-300 active:text-red-500"
								>
									<svg viewBox="0 0 24 24" class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="2">
										<path d="M6 6l12 12M18 6L6 18" stroke-linecap="round" />
									</svg>
								</button>
							</div>
						{/each}
					</div>
				{/if}

				<a
					href="/dieta/adicionar?meal={meal}"
					class="mt-2 flex h-11 items-center justify-center rounded-2xl border-2 border-dashed border-emerald-200 text-sm font-bold text-emerald-700 active:bg-emerald-50"
				>
					+ {m.add_food()}
				</a>
			</section>
		{/each}
	</div>

	<a
		href="/dieta/receitas"
		class="mt-4 flex h-12 w-full items-center justify-center rounded-2xl border-2 border-slate-200 bg-white font-semibold text-slate-700 active:bg-slate-100"
	>
		{m.my_recipes()}
	</a>
{/if}
