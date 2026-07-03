<script lang="ts">
	import type { Exercise } from '$lib/api';
	import { equipmentLabel, muscleGroupLabel } from '$lib/labels';
	import { m } from '$lib/paraglide/messages';

	let { exercise, onClose }: { exercise: Exercise; onClose: () => void } = $props();

	let loading = $state(true);
	let failed = $state(false);
</script>

<div
	class="fixed inset-0 z-50 flex items-end justify-center bg-black/60 p-0 sm:items-center sm:p-4"
	role="button"
	tabindex="-1"
	onclick={onClose}
	onkeydown={(e) => e.key === 'Escape' && onClose()}
>
	<div
		class="w-full max-w-md rounded-t-3xl bg-white p-5 sm:rounded-3xl"
		role="dialog"
		tabindex="-1"
		onclick={(e) => e.stopPropagation()}
		onkeydown={() => {}}
	>
		<div class="mb-3 flex items-start justify-between gap-3">
			<div>
				<h2 class="text-lg font-bold text-slate-900">{exercise.name}</h2>
				<p class="text-sm text-slate-500">
					{muscleGroupLabel(exercise.muscle_group)} · {equipmentLabel(exercise.equipment)}
				</p>
			</div>
			<button
				type="button"
				aria-label={m.close()}
				onclick={onClose}
				class="grid h-10 w-10 shrink-0 place-items-center rounded-full bg-slate-100 text-slate-500 active:bg-slate-200"
			>
				<svg viewBox="0 0 24 24" class="h-5 w-5" fill="none" stroke="currentColor" stroke-width="2">
					<path d="M6 6l12 12M18 6L6 18" stroke-linecap="round" />
				</svg>
			</button>
		</div>

		<div class="relative aspect-square overflow-hidden rounded-2xl bg-slate-100">
			{#if exercise.media_url && !failed}
				{#if loading}
					<div class="absolute inset-0 grid place-items-center">
						<div
							class="h-8 w-8 animate-spin rounded-full border-4 border-slate-300 border-t-transparent"
						></div>
					</div>
				{/if}
				<img
					src={exercise.media_url}
					alt={exercise.name}
					class="h-full w-full object-cover"
					onload={() => (loading = false)}
					onerror={() => {
						loading = false;
						failed = true;
					}}
				/>
			{:else}
				<div class="grid h-full place-items-center text-center text-sm text-slate-400">
					{m.no_photo()}
				</div>
			{/if}
		</div>

		{#if exercise.media_url}
			<a
				href={exercise.media_url}
				target="_blank"
				rel="noopener noreferrer"
				class="mt-3 block text-center text-sm font-semibold text-emerald-700"
			>
				{m.open_in_browser()}
			</a>
		{/if}
	</div>
</div>
