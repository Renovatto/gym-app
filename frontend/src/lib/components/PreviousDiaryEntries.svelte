<script lang="ts">
	import { api, ApiError, type DiaryDay, type DiaryEstimate, type MealType } from '$lib/api';
	import { errorMessage } from '$lib/errors';
	import { mealTypeLabel } from '$lib/labels';
	import { showToast } from '$lib/toast.svelte';
	import { m } from '$lib/paraglide/messages';
	import { getLocale } from '$lib/paraglide/runtime';
	import Stepper from './Stepper.svelte';

	let {
		diary,
		day,
		onupdate
	}: {
		diary: DiaryDay;
		day: string;
		onupdate: () => Promise<void>;
	} = $props();

	let busy = $state(false);
	let formOpen = $state(false);
	let editingId = $state<number | undefined>();
	let confirmingDelete = $state<number | null>(null);
	let name = $state('');
	let reference = $state('');
	let portions = $state(1);
	let kcalPerPortion = $state(0);
	let energyKnown = $state(false);
	let meal = $state<MealType>('lunch');
	const meals: MealType[] = [
		'breakfast',
		'pre_workout',
		'post_workout',
		'lunch',
		'snack',
		'dinner',
		'supper',
		'other'
	];
	const nf = new Intl.NumberFormat(getLocale());
	// Total aproximado = kcal por porcao da referencia vezes porcoes informadas.
	const estimatedKcal = $derived(Math.round(portions * kcalPerPortion));
	const validForm = $derived(
		name.trim().length > 0 && (!energyKnown || reference.trim().length > 0)
	);

	function handleError(error: unknown): void {
		showToast(errorMessage(error instanceof ApiError ? error.code : 'GENERIC_ERROR'));
	}

	function openForm(estimate: DiaryEstimate): void {
		editingId = estimate.id;
		name = estimate.name ?? '';
		reference = estimate.reference ?? '';
		portions = estimate.portions ?? 1;
		kcalPerPortion = estimate.kcal_per_portion ?? 0;
		energyKnown = estimate.kcal_per_portion != null;
		meal = estimate.meal_type ?? 'lunch';
		formOpen = true;
	}

	async function saveEstimate(): Promise<void> {
		if (busy || !validForm || editingId === undefined) return;
		busy = true;
		try {
			await api.updateDiaryEstimate(editingId, {
				entry_date: day,
				meal_type: meal,
				name: name.trim(),
				portions,
				kcal_per_portion: energyKnown ? kcalPerPortion : null,
				reference: energyKnown ? reference.trim() : null
			});
			formOpen = false;
			showToast(m.diary_approx_saved());
			await onupdate();
		} catch (error) {
			handleError(error);
		} finally {
			busy = false;
		}
	}

	async function deleteEstimate(id: number): Promise<void> {
		if (busy || confirmingDelete !== id) return;
		busy = true;
		try {
			await api.deleteDiaryEstimate(id);
			confirmingDelete = null;
			showToast(m.diary_approx_deleted());
			await onupdate();
		} catch (error) {
			handleError(error);
		} finally {
			busy = false;
		}
	}
</script>

<details class="mt-3 rounded-3xl bg-white p-5 shadow-sm" data-testid="previous-diary-entries">
	<summary class="cursor-pointer text-sm font-semibold text-slate-600"
		>{m.diary_previous_entries()}</summary
	>
	<p class="mt-3 text-xs text-slate-500">{m.diary_previous_entries_help()}</p>

	{#if formOpen}
		<form
			class="mt-4 space-y-4 rounded-2xl bg-slate-50 p-4"
			onsubmit={(event) => {
				event.preventDefault();
				saveEstimate();
			}}
		>
			<label class="block text-xs font-semibold text-slate-600">
				{m.diary_approx_name()}
				<input
					bind:value={name}
					required
					maxlength="160"
					class="mt-2 w-full rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-sm"
				/>
			</label>
			<select
				bind:value={meal}
				aria-label={m.tab_diet()}
				class="min-h-11 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm"
			>
				{#each meals as mealType (mealType)}<option value={mealType}
						>{mealTypeLabel(mealType)}</option
					>{/each}
			</select>
			<label class="flex items-center gap-2 text-sm font-semibold text-slate-600">
				<input
					type="checkbox"
					bind:checked={energyKnown}
					class="accent-emerald-600"
				/>{m.diary_approx_known()}
			</label>
			{#if energyKnown}
				<label class="block text-xs font-semibold text-slate-600">
					{m.diary_approx_reference()}
					<input
						bind:value={reference}
						required
						maxlength="240"
						class="mt-2 w-full rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-sm"
					/>
				</label>
				<div>
					<p class="mb-2 text-xs font-semibold text-slate-600">{m.diary_approx_kcal()}</p>
					<Stepper bind:value={kcalPerPortion} min={0} max={10000} step={10} unit="kcal" />
				</div>
				<div>
					<p class="mb-2 text-xs font-semibold text-slate-600">{m.diary_approx_portions()}</p>
					<Stepper bind:value={portions} min={0.1} max={50} step={0.5} decimals={1} />
				</div>
				<p class="text-sm font-bold text-slate-700">
					{m.diary_approx_badge()}: {nf.format(estimatedKcal)} kcal
				</p>
			{:else}
				<p class="rounded-xl bg-amber-50 p-3 text-xs text-amber-800">{m.diary_approx_unknown()}</p>
			{/if}
			<div class="flex gap-2">
				<button
					type="submit"
					disabled={busy || !validForm}
					class="min-h-11 flex-1 rounded-xl bg-emerald-600 px-3 py-2 text-sm font-bold text-white disabled:opacity-40"
					>{m.save()}</button
				>
				<button
					type="button"
					onclick={() => (formOpen = false)}
					disabled={busy}
					class="min-h-11 rounded-xl px-3 text-sm font-semibold text-slate-500">{m.cancel()}</button
				>
			</div>
		</form>
	{/if}

	{#if diary.estimates?.length}
		<div class="mt-4 space-y-3">
			{#each diary.estimates as estimate (estimate.id)}
				<div class="rounded-2xl bg-slate-50 p-3">
					<button type="button" onclick={() => openForm(estimate)} class="w-full text-left">
						<span class="text-[11px] font-bold text-amber-700"
							>{m.diary_approx_badge()} · {mealTypeLabel(estimate.meal_type)}</span
						>
						<p class="mt-1 text-sm font-semibold text-slate-800">{estimate.name}</p>
						<p class="mt-1 text-xs text-slate-500">
							{estimate.kcal === null
								? m.diary_energy_unknown()
								: `${nf.format(estimate.kcal)} kcal`}
						</p>
						{#if estimate.reference}<p class="mt-1 break-words text-xs text-slate-400">
								{estimate.reference}
							</p>{/if}
					</button>
					{#if confirmingDelete === estimate.id}
						<div class="mt-3 rounded-xl bg-red-50 p-3">
							<p class="text-xs text-red-700">{m.confirm_delete()}</p>
							<div class="mt-2 flex gap-2">
								<button
									type="button"
									onclick={() => deleteEstimate(estimate.id)}
									disabled={busy}
									class="min-h-11 rounded-xl bg-red-600 px-3 text-xs font-bold text-white"
									>{m.confirm_delete()}</button
								>
								<button
									type="button"
									onclick={() => (confirmingDelete = null)}
									disabled={busy}
									class="min-h-11 px-3 text-xs font-semibold text-slate-500">{m.cancel()}</button
								>
							</div>
						</div>
					{:else}
						<button
							type="button"
							onclick={() => (confirmingDelete = estimate.id)}
							class="mt-2 min-h-11 text-xs font-semibold text-red-600">{m.delete()}</button
						>
					{/if}
				</div>
			{/each}
		</div>
		<p class="mt-3 text-xs text-slate-500">{m.diary_approx_separate()}</p>
		<p class="mt-2 text-xs text-amber-700">{m.diary_recommendations_paused()}</p>
	{/if}
</details>
