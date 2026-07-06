<script lang="ts">
	import { api, localDay, type DiaryDay, type DiaryEntry, type MealType } from '$lib/api';
	import MacroSummary from '$lib/components/MacroSummary.svelte';
	import Stepper from '$lib/components/Stepper.svelte';
	import { showToast } from '$lib/toast.svelte';
	import { MEAL_TYPES, mealTypeLabel } from '$lib/labels';
	import { m } from '$lib/paraglide/messages';
	import { getLocale } from '$lib/paraglide/runtime';

	let diary = $state<DiaryDay | null>(null);
	let loading = $state(true);
	let day = $state(localDay());

	// edição de um lançamento existente
	let editing = $state<DiaryEntry | null>(null);
	let editQty = $state(0);
	let editBusy = $state(false);

	function openEdit(entry: DiaryEntry): void {
		editing = entry;
		editQty = entry.quantity;
	}

	async function saveEdit(): Promise<void> {
		if (!editing) return;
		editBusy = true;
		try {
			await api.updateDiaryEntry(editing.id, editQty);
			editing = null;
			await load();
		} finally {
			editBusy = false;
		}
	}

	async function deleteEditing(): Promise<void> {
		if (!editing) return;
		editBusy = true;
		try {
			await api.deleteDiaryEntry(editing.id);
			editing = null;
			await load();
		} finally {
			editBusy = false;
		}
	}

	// prévia dos macros ao mudar a quantidade (proporção linear ao valor atual)
	const editPreview = $derived(
		editing && editing.quantity > 0
			? Math.round((editing.macros.kcal / editing.quantity) * editQty)
			: 0
	);

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

	async function repeatPrevious(): Promise<void> {
		await api.copyPreviousDay(day, shiftDay(day, -1));
		await load();
		showToast(m.day_copied());
	}

	async function repeatMeal(meal: MealType): Promise<void> {
		await api.copyPreviousDay(day, shiftDay(day, -1), meal);
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
							<button
								type="button"
								onclick={() => openEdit(entry)}
								class="flex w-full items-center gap-2 rounded-xl bg-slate-50 px-3 py-2 text-left active:bg-slate-100"
							>
								<div class="min-w-0 flex-1">
									<p class="truncate text-sm font-semibold text-slate-800">{entry.name}</p>
									<p class="text-xs text-slate-500">
										{entry.source === 'recipe'
											? `${nf.format(entry.quantity)} ${entry.quantity === 1 ? m.serving_singular() : m.serving_plural()}`
											: `${nf.format(entry.quantity)} g`}
										· {nf.format(Math.round(entry.macros.kcal))} kcal
									</p>
								</div>
								<svg viewBox="0 0 24 24" class="h-4 w-4 shrink-0 text-slate-300" fill="none" stroke="currentColor" stroke-width="2"><path d="M9 6l6 6-6 6" stroke-linecap="round" stroke-linejoin="round" /></svg>
							</button>
						{/each}
					</div>
				{/if}

				<div class="mt-2 flex gap-2">
					<a
						href="/dieta/adicionar?meal={meal}&day={day}"
						class="flex h-11 flex-1 items-center justify-center rounded-2xl border-2 border-dashed border-emerald-200 text-sm font-bold text-emerald-700 active:bg-emerald-50"
					>
						+ {m.add_food()}
					</a>
					{#if !group || group.entries.length === 0}
						<button
							type="button"
							aria-label={m.repeat_meal()}
							title={m.repeat_meal()}
							onclick={() => repeatMeal(meal)}
							class="grid h-11 w-11 shrink-0 place-items-center rounded-2xl border-2 border-slate-200 text-slate-500 active:bg-slate-100"
						>
							<svg viewBox="0 0 24 24" class="h-5 w-5" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 4v6h6M20 20v-6h-6M20 8a8 8 0 00-14-3M4 16a8 8 0 0014 3" stroke-linecap="round" stroke-linejoin="round" /></svg>
						</button>
					{/if}
				</div>
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

{#if editing}
	<div
		class="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
		role="button"
		tabindex="-1"
		onclick={() => (editing = null)}
		onkeydown={(e) => e.key === 'Escape' && (editing = null)}
	>
		<div
			class="w-full max-w-md rounded-3xl bg-white p-5"
			role="dialog"
			tabindex="-1"
			onclick={(e) => e.stopPropagation()}
			onkeydown={() => {}}
		>
			<h2 class="text-lg font-bold text-slate-900">{editing.name}</h2>
			<p class="mb-4 text-sm text-slate-500">{editPreview} kcal</p>
			{#if editing.source === 'recipe'}
				<Stepper bind:value={editQty} min={1} max={20} step={1} unit={m.serving_plural()} />
			{:else}
				<Stepper bind:value={editQty} min={1} max={2000} step={5} unit="g" />
			{/if}
			<div class="mt-5 flex gap-2">
				<button
					type="button"
					disabled={editBusy}
					onclick={deleteEditing}
					class="h-12 flex-1 rounded-2xl border-2 border-red-200 font-semibold text-red-600 active:bg-red-50 disabled:opacity-50"
				>
					{m.remove()}
				</button>
				<button
					type="button"
					disabled={editBusy}
					onclick={saveEdit}
					class="h-12 flex-[2] rounded-2xl bg-emerald-600 font-bold text-white active:bg-emerald-700 disabled:opacity-50"
				>
					{m.save()}
				</button>
			</div>
		</div>
	</div>
{/if}
