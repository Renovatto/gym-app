<script lang="ts">
	import { toastState } from '$lib/toast.svelte';
</script>

{#if toastState.visible}
	<div
		class="pointer-events-none fixed inset-x-0 top-4 z-[60] flex justify-center px-4"
		role="status"
		aria-live="polite"
	>
		<div
			class="flex items-center gap-2 rounded-2xl bg-ink px-4 py-3 text-sm font-semibold text-white shadow-lg"
		>
			<svg viewBox="0 0 24 24" class="h-5 w-5 text-emerald-400" fill="none" stroke="currentColor" stroke-width="2.5">
				<path d="M20 6L9 17l-5-5" stroke-linecap="round" stroke-linejoin="round" />
			</svg>
			{toastState.message}
		</div>
	</div>
{/if}
