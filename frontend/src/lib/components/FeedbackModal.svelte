<script lang="ts">
	import { untrack } from 'svelte';
	import { api, type FeedbackModule } from '$lib/api';
	import { showToast } from '$lib/toast.svelte';
	import { m } from '$lib/paraglide/messages';

	// Formulario de feedback / reportar problema. O modulo ja vem pre-selecionado pela
	// tela onde o usuario estava (initialModule).
	let {
		initialModule = 'other',
		onClose
	}: { initialModule?: FeedbackModule; onClose: () => void } = $props();

	const MODULES: FeedbackModule[] = ['workout', 'diet', 'progress', 'profile', 'other'];
	// valor inicial vem do prop (modulo da tela atual); untrack deixa claro que e so o inicial
	let selectedModule = $state<FeedbackModule>(untrack(() => initialModule));
	let description = $state('');
	let submitting = $state(false);

	function moduleLabel(mod: FeedbackModule): string {
		return {
			workout: m.tab_workout(),
			diet: m.tab_diet(),
			progress: m.tab_progress(),
			profile: m.tab_profile(),
			other: m.feedback_other()
		}[mod];
	}

	const canSend = $derived(description.trim().length > 0);

	async function send(): Promise<void> {
		if (!canSend || submitting) return;
		submitting = true;
		try {
			await api.submitFeedback(selectedModule, description.trim());
			showToast(m.feedback_sent());
			onClose();
		} finally {
			submitting = false;
		}
	}
</script>

<div
	class="fixed inset-0 z-50 flex items-end justify-center bg-black/50 p-0 sm:items-center sm:p-4"
	role="button"
	tabindex="-1"
	onclick={onClose}
	onkeydown={(e) => e.key === 'Escape' && onClose()}
>
	<div
		class="max-h-[90dvh] w-full max-w-md overflow-y-auto rounded-t-3xl bg-white p-5 pb-[calc(1.25rem+env(safe-area-inset-bottom))] sm:rounded-3xl sm:pb-5"
		role="dialog"
		aria-modal="true"
		tabindex="-1"
		onclick={(e) => e.stopPropagation()}
		onkeydown={() => {}}
	>
		<div class="mb-4 flex items-center gap-3">
			<span class="grid h-11 w-11 shrink-0 place-items-center rounded-2xl bg-emerald-50 text-emerald-600">
				<svg viewBox="0 0 24 24" class="h-6 w-6" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" /></svg>
			</span>
			<div class="min-w-0 flex-1">
				<h2 class="text-lg font-bold text-slate-900">{m.feedback_title()}</h2>
				<p class="text-xs text-slate-500">{m.feedback_subtitle()}</p>
			</div>
			<button
				type="button"
				aria-label={m.close()}
				onclick={onClose}
				class="grid h-9 w-9 shrink-0 place-items-center rounded-full text-slate-400 active:bg-slate-100"
			>
				<svg viewBox="0 0 24 24" class="h-5 w-5" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M6 6l12 12M18 6L6 18" /></svg>
			</button>
		</div>

		<p class="mb-2 text-xs font-bold text-slate-400 uppercase">{m.feedback_module_label()}</p>
		<div class="mb-4 flex flex-wrap gap-2">
			{#each MODULES as mod (mod)}
				<button
					type="button"
					onclick={() => (selectedModule = mod)}
					class="rounded-full border-2 px-3.5 py-1.5 text-sm font-semibold {selectedModule === mod
						? 'border-emerald-600 bg-emerald-50 text-emerald-700'
						: 'border-slate-200 text-slate-500'}"
				>
					{moduleLabel(mod)}
				</button>
			{/each}
		</div>

		<p class="mb-2 text-xs font-bold text-slate-400 uppercase">{m.feedback_desc_label()}</p>
		<textarea
			bind:value={description}
			rows="4"
			placeholder={m.feedback_desc_placeholder()}
			class="w-full resize-none rounded-2xl border-2 border-slate-200 bg-white px-4 py-3 text-sm outline-none focus:border-emerald-600"
		></textarea>

		<button
			type="button"
			disabled={!canSend || submitting}
			onclick={send}
			class="mt-4 h-14 w-full rounded-2xl bg-emerald-600 text-lg font-bold text-white active:bg-emerald-700 disabled:opacity-40"
		>
			{m.feedback_send()}
		</button>
	</div>
</div>
