<script lang="ts">
	import { toastState } from '$lib/toast.svelte';
</script>

<div class="toasts" aria-live="polite">
	{#if toastState.visible}
		<div class="toast">
			<svg
				width="16"
				height="16"
				viewBox="0 0 24 24"
				fill="none"
				stroke="currentColor"
				stroke-width="2.4"
				stroke-linecap="round"
				stroke-linejoin="round"
			>
				<path d="m5 12.5 4.5 4.5L19 7" />
			</svg>
			<span>{toastState.message}</span>
		</div>
	{/if}
</div>
