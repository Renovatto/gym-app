<script lang="ts">
	import { api, type Exercise, type MuscleGroup } from '$lib/api';
	import ExercisePhotoModal from './ExercisePhotoModal.svelte';
	import { MUSCLE_GROUPS, equipmentLabel, muscleGroupLabel } from '$lib/labels';
	import { m } from '$lib/paraglide/messages';

	let {
		onPick,
		selectedIds = new Set()
	}: { onPick?: (exercise: Exercise) => void; selectedIds?: Set<number> } = $props();

	let group = $state<MuscleGroup>('chest');
	let exercises = $state<Exercise[]>([]);
	let loading = $state(true);
	let photoOf = $state<Exercise | null>(null);

	async function load(g: MuscleGroup): Promise<void> {
		loading = true;
		exercises = await api.getExercises(g);
		loading = false;
	}

	$effect(() => {
		load(group);
	});
</script>

<div class="-mx-4 overflow-x-auto px-4">
	<div class="flex w-max gap-2 pb-1">
		{#each MUSCLE_GROUPS as g (g)}
			<button
				type="button"
				onclick={() => (group = g)}
				class="h-10 shrink-0 rounded-full px-4 text-sm font-semibold transition-colors
					{group === g ? 'bg-emerald-600 text-white' : 'bg-white text-slate-600'}"
			>
				{muscleGroupLabel(g)}
			</button>
		{/each}
	</div>
</div>

{#if loading}
	<div class="flex justify-center py-12">
		<div class="h-8 w-8 animate-spin rounded-full border-4 border-emerald-600 border-t-transparent"></div>
	</div>
{:else}
	<div class="mt-3 space-y-2">
		{#each exercises as exercise (exercise.id)}
			{@const picked = selectedIds.has(exercise.id)}
			<div class="flex items-center gap-3 rounded-2xl bg-white p-3 shadow-sm">
				<button
					type="button"
					aria-label={m.view_photo()}
					onclick={() => (photoOf = exercise)}
					class="grid h-14 w-14 shrink-0 place-items-center overflow-hidden rounded-xl bg-slate-100"
				>
					{#if exercise.media_url}
						<img src={exercise.media_url} alt="" class="h-full w-full object-cover" loading="lazy" />
					{:else}
						<svg viewBox="0 0 24 24" class="h-6 w-6 text-slate-400" fill="none" stroke="currentColor" stroke-width="2">
							<rect x="3" y="3" width="18" height="18" rx="2" /><path d="M3 15l5-5 4 4 3-3 6 6" stroke-linecap="round" stroke-linejoin="round" />
						</svg>
					{/if}
				</button>
				<div class="min-w-0 flex-1">
					<p class="truncate font-semibold text-slate-900">{exercise.name}</p>
					<p class="text-sm text-slate-500">{equipmentLabel(exercise.equipment)}</p>
				</div>
				{#if onPick}
					<button
						type="button"
						onclick={() => onPick(exercise)}
						disabled={picked}
						class="grid h-11 w-11 shrink-0 place-items-center rounded-full text-xl font-bold
							{picked ? 'bg-emerald-100 text-emerald-600' : 'bg-emerald-600 text-white active:bg-emerald-700'}"
					>
						{picked ? '✓' : '+'}
					</button>
				{:else}
					<button
						type="button"
						aria-label={m.view_photo()}
						onclick={() => (photoOf = exercise)}
						class="grid h-11 w-11 shrink-0 place-items-center rounded-full bg-slate-100 text-slate-500 active:bg-slate-200"
					>
						<svg viewBox="0 0 24 24" class="h-5 w-5" fill="none" stroke="currentColor" stroke-width="2">
							<circle cx="12" cy="12" r="3" /><path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7-10-7-10-7z" />
						</svg>
					</button>
				{/if}
			</div>
		{/each}
	</div>
{/if}

{#if photoOf}
	<ExercisePhotoModal exercise={photoOf} onClose={() => (photoOf = null)} />
{/if}
