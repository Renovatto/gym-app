<script lang="ts">
	import { fly } from 'svelte/transition';
	import { cubicOut } from 'svelte/easing';
	import ActionToast from '$lib/components/ActionToast.svelte';
	import { actionToasts, toastState } from '$lib/toast.svelte';
</script>

<div class="pointer-events-none fixed inset-x-0 top-4 z-[60] flex max-h-[calc(100dvh-2rem)] flex-col items-center gap-2 overflow-y-auto px-4 pb-2">
{#if toastState.visible}
	<div role="status" aria-live="polite">
		<!-- Vidro esmeralda: fundo translucido + blur (liquid glass), texto maior e icone
			 de acento. Legivel no claro e no escuro (tokens .dark remapeiam o verde). -->
		<div
			class="flex items-center gap-3 rounded-2xl border border-emerald-400/50 bg-emerald-500/20 px-5 py-3.5 text-[15px] font-semibold text-emerald-900 shadow-xl"
			style="-webkit-backdrop-filter: blur(16px) saturate(1.6); backdrop-filter: blur(16px) saturate(1.6);"
			in:fly={{ y: -16, duration: 320, easing: cubicOut }}
			out:fly={{ y: -16, duration: 260, easing: cubicOut }}
		>
			<span class="grid h-6 w-6 shrink-0 place-items-center rounded-full bg-emerald-500 text-white">
				<svg viewBox="0 0 24 24" class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="3">
					<path d="M20 6L9 17l-5-5" stroke-linecap="round" stroke-linejoin="round" />
				</svg>
			</span>
			{toastState.message}
		</div>
	</div>
{/if}

	{#each actionToasts as toast (toast.id)}
		<ActionToast {toast} />
	{/each}
</div>
