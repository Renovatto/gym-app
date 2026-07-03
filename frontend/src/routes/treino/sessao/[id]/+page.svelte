<script lang="ts">
	import { goto } from '$app/navigation';
	import { page } from '$app/state';
	import { api, type Exercise, type RoutineItem } from '$lib/api';
	import ExercisePhotoModal from '$lib/components/ExercisePhotoModal.svelte';
	import Stepper from '$lib/components/Stepper.svelte';
	import { m } from '$lib/paraglide/messages';

	interface SetRow {
		setNumber: number;
		reps: number;
		weight: number;
		done: boolean;
		logId: number | null;
		saving: boolean;
	}
	interface ExerciseBlock {
		item: RoutineItem;
		sets: SetRow[];
	}

	const sessionId = $derived(Number(page.params.id));

	let blocks = $state<ExerciseBlock[]>([]);
	let routineName = $state('');
	let loading = $state(true);
	let finishing = $state(false);
	let photoOf = $state<Exercise | null>(null);

	async function load(): Promise<void> {
		const session = await api.getSession(sessionId);
		routineName = session.routine_name ?? m.free_workout();
		if (session.routine_id === null) {
			blocks = [];
			loading = false;
			return;
		}
		const routine = await api.getRoutine(session.routine_id);
		blocks = routine.items.map((item) => {
			const prefill = item.last_weight_kg ?? item.target_weight_kg ?? 0;
			const sets: SetRow[] = Array.from({ length: item.target_sets }, (_, i) => {
				const logged = session.sets.find(
					(s) => s.exercise_id === item.exercise.id && s.set_number === i + 1
				);
				return {
					setNumber: i + 1,
					reps: logged?.reps ?? item.target_reps,
					weight: logged?.weight_kg ?? prefill,
					done: logged?.done ?? false,
					logId: logged?.id ?? null,
					saving: false
				};
			});
			return { item, sets };
		});
		loading = false;
	}

	async function toggleSet(block: ExerciseBlock, row: SetRow): Promise<void> {
		if (row.saving) return;
		row.saving = true;
		try {
			if (!row.done) {
				const log = await api.logSet(sessionId, {
					exercise_id: block.item.exercise.id,
					set_number: row.setNumber,
					reps: row.reps,
					weight_kg: row.weight,
					done: true
				});
				row.logId = log.id;
				row.done = true;
			} else if (row.logId !== null) {
				await api.deleteSet(sessionId, row.logId);
				row.logId = null;
				row.done = false;
			}
		} finally {
			row.saving = false;
		}
	}

	async function finish(): Promise<void> {
		finishing = true;
		try {
			await api.finishSession(sessionId);
			await goto('/treino');
		} finally {
			finishing = false;
		}
	}

	$effect(() => {
		load();
	});

	const doneCount = $derived(
		blocks.reduce((acc, b) => acc + b.sets.filter((s) => s.done).length, 0)
	);
	const totalCount = $derived(blocks.reduce((acc, b) => acc + b.sets.length, 0));
</script>

{#if loading}
	<div class="flex justify-center py-16">
		<div class="h-8 w-8 animate-spin rounded-full border-4 border-emerald-600 border-t-transparent"></div>
	</div>
{:else}
	<header class="mb-4">
		<p class="text-sm font-semibold text-emerald-600">{m.workout_in_progress()}</p>
		<h1 class="text-2xl font-bold">{routineName}</h1>
		<div class="mt-3 h-2 overflow-hidden rounded-full bg-slate-200">
			<div
				class="h-full rounded-full bg-emerald-600 transition-all"
				style="width: {totalCount ? (doneCount / totalCount) * 100 : 0}%"
			></div>
		</div>
		<p class="mt-1 text-sm text-slate-500">{doneCount} / {totalCount} {m.sets_label()}</p>
	</header>

	<div class="space-y-4">
		{#each blocks as block (block.item.id)}
			<section class="rounded-3xl bg-white p-4 shadow-sm">
				<div class="mb-3 flex items-center gap-3">
					<button
						type="button"
						aria-label={m.view_photo()}
						onclick={() => (photoOf = block.item.exercise)}
						class="grid h-12 w-12 shrink-0 place-items-center overflow-hidden rounded-xl bg-slate-100"
					>
						{#if block.item.exercise.media_url}
							<img src={block.item.exercise.media_url} alt="" class="h-full w-full object-cover" loading="lazy" />
						{:else}
							<svg viewBox="0 0 24 24" class="h-5 w-5 text-slate-400" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="3" /><path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7-10-7-10-7z" /></svg>
						{/if}
					</button>
					<div class="min-w-0 flex-1">
						<p class="truncate font-bold text-slate-900">{block.item.exercise.name}</p>
						<p class="text-sm text-slate-500">
							{block.item.target_sets} × {block.item.target_reps}
							{#if block.item.last_weight_kg !== null}
								· {m.last_time()}: {block.item.last_weight_kg} kg
							{/if}
						</p>
					</div>
				</div>

				<div class="space-y-2">
					{#each block.sets as row (row.setNumber)}
						<div
							class="flex items-center gap-2 rounded-2xl p-1.5 {row.done ? 'bg-emerald-50' : 'bg-slate-50'}"
						>
							<span class="grid h-8 w-8 shrink-0 place-items-center text-sm font-bold text-slate-400">
								{row.setNumber}
							</span>
							<div class="flex flex-1 items-center gap-1">
								<div class="flex-1">
									<Stepper bind:value={row.weight} min={0} max={1000} step={2.5} decimals={1} unit="kg" />
								</div>
							</div>
							<div class="w-24 shrink-0">
								<Stepper bind:value={row.reps} min={0} max={100} unit={m.reps_short()} />
							</div>
							<button
								type="button"
								aria-label={m.done()}
								disabled={row.saving}
								onclick={() => toggleSet(block, row)}
								class="grid h-12 w-12 shrink-0 place-items-center rounded-2xl text-xl font-bold transition-colors
									{row.done ? 'bg-emerald-600 text-white' : 'border-2 border-slate-200 bg-white text-slate-300'}"
							>
								✓
							</button>
						</div>
					{/each}
				</div>
			</section>
		{/each}
	</div>

	<button
		type="button"
		disabled={finishing}
		onclick={finish}
		class="mt-5 h-14 w-full rounded-2xl bg-slate-900 text-lg font-bold text-white active:bg-slate-800 disabled:opacity-50"
	>
		{m.finish_workout()}
	</button>
{/if}

{#if photoOf}
	<ExercisePhotoModal exercise={photoOf} onClose={() => (photoOf = null)} />
{/if}
