<script lang="ts">
	import ExerciseBrowser from '$lib/components/ExerciseBrowser.svelte';
	import { m } from '$lib/paraglide/messages';
</script>

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
	<h1 class="text-2xl font-bold">{m.exercise_catalog()}</h1>
</div>

<ExerciseBrowser />
