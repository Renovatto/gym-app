<script lang="ts">
	import { fly } from 'svelte/transition';
	import { cubicOut } from 'svelte/easing';
	import { toastState } from '$lib/toast.svelte';
</script>

{#if toastState.visible}
	<div
		class="pointer-events-none fixed inset-x-0 top-4 z-[60] flex justify-center px-4"
		role="status"
		aria-live="polite"
	>
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
