<script lang="ts">
	import type { Exercise } from '$lib/api';
	import { equipmentLabel, muscleGroupLabel } from '$lib/labels';
	import { m } from '$lib/paraglide/messages';

	let { exercise, onClose }: { exercise: Exercise; onClose: () => void } = $props();

	const images = $derived(exercise.media_urls);
	let index = $state(0);
	let animating = $state(false);
	let timer: ReturnType<typeof setInterval> | null = null;

	function stop(): void {
		if (timer) {
			clearInterval(timer);
			timer = null;
		}
		animating = false;
	}

	function toggleAnimate(): void {
		if (animating) {
			stop();
			return;
		}
		if (images.length < 2) return;
		animating = true;
		// alterna entre início e fim do movimento ~1,2x/s para simular a execução
		timer = setInterval(() => {
			index = (index + 1) % images.length;
		}, 800);
	}

	function show(i: number): void {
		stop();
		index = i;
	}

	$effect(() => {
		// limpa o timer ao desmontar
		return () => {
			if (timer) clearInterval(timer);
		};
	});
</script>

<div
	class="fixed inset-0 z-50 flex items-end justify-center bg-black/60 sm:items-center sm:p-4"
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
			{#if images.length > 0}
				{#each images as url, i (url)}
					<img
						src={url}
						alt="{exercise.name} — {i === 0 ? m.movement_start() : m.movement_end()}"
						class="absolute inset-0 h-full w-full object-cover transition-opacity duration-200"
						style="opacity: {i === index ? 1 : 0}"
						loading="lazy"
					/>
				{/each}
				{#if images.length > 1}
					<div class="absolute top-2 left-2 rounded-full bg-black/50 px-2.5 py-1 text-xs font-semibold text-white">
						{index === 0 ? m.movement_start() : m.movement_end()}
					</div>
				{/if}
			{:else}
				<div class="grid h-full place-items-center text-center text-sm text-slate-400">
					{m.no_photo()}
				</div>
			{/if}
		</div>

		{#if images.length > 1}
			<div class="mt-3 flex items-center gap-2">
				<button
					type="button"
					onclick={toggleAnimate}
					class="flex h-12 flex-1 items-center justify-center gap-2 rounded-2xl font-bold text-white
						{animating ? 'bg-slate-700' : 'bg-emerald-600 active:bg-emerald-700'}"
				>
					{#if animating}
						<svg viewBox="0 0 24 24" class="h-5 w-5" fill="currentColor"><rect x="6" y="5" width="4" height="14" rx="1" /><rect x="14" y="5" width="4" height="14" rx="1" /></svg>
						{m.pause_movement()}
					{:else}
						<svg viewBox="0 0 24 24" class="h-5 w-5" fill="currentColor"><path d="M8 5v14l11-7z" /></svg>
						{m.play_movement()}
					{/if}
				</button>
				<div class="flex gap-1.5">
					{#each images as _, i (i)}
						<button
							type="button"
							aria-label={`${i + 1}`}
							onclick={() => show(i)}
							class="h-3 w-3 rounded-full {i === index ? 'bg-emerald-600' : 'bg-slate-300'}"
						></button>
					{/each}
				</div>
			</div>
			<p class="mt-2 text-center text-xs text-slate-400">{m.movement_hint()}</p>
		{/if}

		{#if images.length > 0}
			<a
				href={images[index]}
				target="_blank"
				rel="noopener noreferrer"
				class="mt-3 block text-center text-sm font-semibold text-emerald-700"
			>
				{m.open_in_browser()}
			</a>
		{/if}
	</div>
</div>
