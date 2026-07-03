<script lang="ts">
	import { api, localDay, type DiaryDay, type MealType } from '$lib/api';
	import MacroSummary from '$lib/components/MacroSummary.svelte';
	import { showToast } from '$lib/toast.svelte';
	import { MEAL_TYPES, mealTypeLabel } from '$lib/labels';
	import { m } from '$lib/paraglide/messages';
	import { getLocale } from '$lib/paraglide/runtime';

	let diary = $state<DiaryDay | null>(null);
	let loading = $state(true);
	let day = $state(localDay());

	const nf = new Intl.NumberFormat(getLocale());
	const df = new Intl.DateTimeFormat(getLocale(), { weekday: 'short', day: '2-digit', month: 'short' });
	const today = localDay();
	const isToday = $derived(day === today);

	function shiftDay(base: string, delta: number): string {
		const d = new Date(base + 'T12:00:00');
		d.setDate(d.getDate() + delta);
		return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
	}

	async function load(): Promise<void> {
		loading = true;
		diary = await api.getDiary(day);
		loading = false;
	}

	async function removeEntry(id: number): Promise<void> {
		await api.deleteDiaryEntry(id);
		await load();
	}

	async function repeatPrevious(): Promise<void> {
		await api.copyPreviousDay(day, shiftDay(day, -1));
		await load();
		showToast(m.day_copied());
	}

	function mealGroup(meal: MealType) {
		return diary?.meals.find((g) => g.meal_type === meal);
	}

	const dayLabel = $derived(
		isToday ? m.today_title() : df.format(new Date(day + 'T12:00:00'))
	);
	const isEmpty = $derived(diary ? diary.meals.every((g) => g.entries.length === 0) : true);

	$effect(() => {
		day;
		load();
	});
</script>

<div class="mb-4 flex items-center justify-between gap-2">
	<h1 class="text-2xl font-bold">{m.tab_diet()}</h1>
	<div class="flex items-center gap-1">
		<button
			type="button"
			aria-label={m.previous_day()}
			onclick={() => (day = shiftDay(day, -1))}
			class="grid h-9 w-9 place-items-center rounded-full bg-white text-slate-500 shadow-sm active:bg-slate-100"
		>
			<svg viewBox="0 0 24 24" class="h-5 w-5" fill="none" stroke="currentColor" stroke-width="2"><path d="M15 6l-6 6 6 6" stroke-linecap="round" stroke-linejoin="round" /></svg>
		</button>
		<span class="min-w-24 text-center text-sm font-semibold text-slate-600">{dayLabel}</span>
		<button
			type="button"
			aria-label={m.next_day()}
			disabled={isToday}
			onclick={() => (day = shiftDay(day, 1))}
			class="grid h-9 w-9 place-items-center rounded-full bg-white text-slate-500 shadow-sm active:bg-slate-100 disabled:opacity-30"
		>
			<svg viewBox="0 0 24 24" class="h-5 w-5" fill="none" stroke="currentColor" stroke-width="2"><path d="M9 6l6 6-6 6" stroke-linecap="round" stroke-linejoin="round" /></svg>
		</button>
	</div>
</div>

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
					href="/dieta/adicionar?meal={meal}&day={day}"
					class="mt-2 flex h-11 items-center justify-center rounded-2xl border-2 border-dashed border-emerald-200 text-sm font-bold text-emerald-700 active:bg-emerald-50"
				>
					+ {m.add_food()}
				</a>
			</section>
		{/each}
	</div>

	{#if isEmpty}
		<button
			type="button"
			onclick={repeatPrevious}
			class="mt-4 flex h-12 w-full items-center justify-center rounded-2xl border-2 border-slate-200 bg-white font-semibold text-slate-700 active:bg-slate-100"
		>
			{m.repeat_previous_day()}
		</button>
	{/if}

	<a
		href="/dieta/receitas"
		class="mt-3 flex h-12 w-full items-center justify-center rounded-2xl border-2 border-slate-200 bg-white font-semibold text-slate-700 active:bg-slate-100"
	>
		{m.my_recipes()}
	</a>
{/if}
