<script lang="ts">
	import { goto } from '$app/navigation';
	import { page } from '$app/state';
	import { api, type Exercise, type RoutineItemInput } from '$lib/api';
	import ExerciseBrowser from '$lib/components/ExerciseBrowser.svelte';
	import Stepper from '$lib/components/Stepper.svelte';
	import { m } from '$lib/paraglide/messages';

	interface BuilderItem {
		exercise: Exercise;
		target_sets: number;
		target_reps: number;
		target_weight_kg: number | null;
		rest_seconds: number;
	}

	const routineId = $derived(page.params.id);
	const isNew = $derived(routineId === 'nova');

	let name = $state('');
	let items = $state<BuilderItem[]>([]);
	let loading = $state(true);
	let picking = $state(false);
	let busy = $state(false);

	async function load(): Promise<void> {
		if (isNew) {
			name = '';
			items = [];
		} else {
			const routine = await api.getRoutine(Number(routineId));
			name = routine.name;
			items = routine.items.map((i) => ({
				exercise: i.exercise,
				target_sets: i.target_sets,
				target_reps: i.target_reps,
				target_weight_kg: i.target_weight_kg,
				rest_seconds: i.rest_seconds
			}));
		}
		loading = false;
	}

	function addExercise(exercise: Exercise): void {
		if (items.some((i) => i.exercise.id === exercise.id)) return;
		items = [
			...items,
			{ exercise, target_sets: 3, target_reps: 10, target_weight_kg: null, rest_seconds: 90 }
		];
	}

	function removeItem(index: number): void {
		items = items.filter((_, i) => i !== index);
	}

	const selectedIds = $derived(new Set(items.map((i) => i.exercise.id)));
	const canSave = $derived(name.trim().length > 0 && items.length > 0);

	async function save(): Promise<void> {
		if (!canSave) return;
		busy = true;
		const payload: RoutineItemInput[] = items.map((i) => ({
			exercise_id: i.exercise.id,
			target_sets: i.target_sets,
			target_reps: i.target_reps,
			target_weight_kg: i.target_weight_kg,
			rest_seconds: i.rest_seconds
		}));
		try {
			if (isNew) await api.createRoutine(name.trim(), payload);
			else await api.updateRoutine(Number(routineId), name.trim(), payload);
			await goto('/treino');
		} finally {
			busy = false;
		}
	}

	async function remove(): Promise<void> {
		busy = true;
		try {
			await api.deleteRoutine(Number(routineId));
			await goto('/treino');
		} finally {
			busy = false;
		}
	}

	$effect(() => {
		load();
	});
</script>

{#if picking}
	<div class="fixed inset-0 z-40 overflow-y-auto bg-slate-50">
		<div class="mx-auto max-w-md px-4 pt-6 pb-24">
			<div class="mb-4 flex items-center justify-between">
				<h1 class="text-xl font-bold">{m.add_exercises()}</h1>
				<button
					type="button"
					onclick={() => (picking = false)}
					class="rounded-full bg-emerald-600 px-5 py-2 text-sm font-bold text-white"
				>
					{m.done()}
				</button>
			</div>
			<ExerciseBrowser onPick={addExercise} {selectedIds} />
		</div>
	</div>
{/if}

{#if loading}
	<div class="flex justify-center py-16">
		<div class="h-8 w-8 animate-spin rounded-full border-4 border-emerald-600 border-t-transparent"></div>
	</div>
{:else}
	<div class="mb-4 flex items-center gap-2">
		<a
			href="/treino"
			aria-label={m.back()}
			class="grid h-10 w-10 place-items-center rounded-full bg-white text-slate-500 shadow-sm"
		>
			<svg viewBox="0 0 24 24" class="h-5 w-5" fill="none" stroke="currentColor" stroke-width="2">
				<path d="M15 6l-6 6 6 6" stroke-linecap="round" stroke-linejoin="round" />
			</svg>
		</a>
		<h1 class="text-2xl font-bold">{isNew ? m.new_routine() : m.edit_routine()}</h1>
	</div>

	<input
		bind:value={name}
		placeholder={m.routine_name_placeholder()}
		class="h-14 w-full rounded-2xl border-2 border-slate-200 bg-white px-4 text-base font-semibold outline-none focus:border-emerald-600"
	/>

	<div class="mt-3 space-y-3">
		{#each items as item, index (item.exercise.id)}
			<section class="rounded-3xl bg-white p-4 shadow-sm">
				<div class="mb-3 flex items-center justify-between gap-2">
					<p class="min-w-0 flex-1 truncate font-bold text-slate-900">{item.exercise.name}</p>
					<button
						type="button"
						aria-label={m.remove()}
						onclick={() => removeItem(index)}
						class="text-slate-300 active:text-red-500"
					>
						<svg viewBox="0 0 24 24" class="h-5 w-5" fill="none" stroke="currentColor" stroke-width="2">
							<path d="M4 7h16M9 7V5h6v2M6 7l1 13h10l1-13" stroke-linecap="round" stroke-linejoin="round" />
						</svg>
					</button>
				</div>
				<div class="grid grid-cols-2 gap-3">
					<div>
						<p class="mb-1 text-xs font-semibold text-slate-500">{m.sets_label()}</p>
						<Stepper bind:value={item.target_sets} min={1} max={20} />
					</div>
					<div>
						<p class="mb-1 text-xs font-semibold text-slate-500">{m.reps_label()}</p>
						<Stepper bind:value={item.target_reps} min={1} max={100} />
					</div>
				</div>
			</section>
		{/each}
	</div>

	<button
		type="button"
		onclick={() => (picking = true)}
		class="mt-3 h-14 w-full rounded-2xl border-2 border-dashed border-emerald-300 font-bold text-emerald-700 active:bg-emerald-50"
	>
		+ {m.add_exercises()}
	</button>

	<button
		type="button"
		disabled={!canSave || busy}
		onclick={save}
		class="mt-3 h-14 w-full rounded-2xl bg-emerald-600 text-lg font-bold text-white active:bg-emerald-700 disabled:opacity-40"
	>
		{m.save_routine()}
	</button>

	{#if !isNew}
		<button
			type="button"
			disabled={busy}
			onclick={remove}
			class="mt-3 h-12 w-full rounded-2xl border-2 border-red-200 font-semibold text-red-600 active:bg-red-50"
		>
			{m.delete_routine()}
		</button>
	{/if}
{/if}
