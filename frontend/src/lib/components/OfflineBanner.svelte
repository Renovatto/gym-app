<script lang="ts">
	import { fly } from 'svelte/transition';
	import { cubicOut } from 'svelte/easing';
	import { m } from '$lib/paraglide/messages';

	// navigator.onLine responde "tem rede?", nao "a API respondeu?" - um Wi-Fi sem
	// internet segue como online aqui. Serve para o caso que importa no celular
	// (modo aviao, metro, academia sem sinal), e e o unico sinal que chega sem
	// custo de requisicao.
	let offline = $state(false);

	$effect(() => {
		offline = !navigator.onLine;
		function update(): void {
			offline = !navigator.onLine;
		}
		window.addEventListener('online', update);
		window.addEventListener('offline', update);
		return () => {
			window.removeEventListener('online', update);
			window.removeEventListener('offline', update);
		};
	});
</script>

{#if offline}
	<div
		class="fixed inset-x-0 top-0 z-[55] px-3 pt-[calc(env(safe-area-inset-top)+0.5rem)]"
		role="status"
		aria-live="polite"
	>
		<div
			class="mx-auto flex max-w-md items-center gap-2.5 rounded-2xl border border-amber-200 bg-amber-50 px-4 py-2.5 text-[13px] font-semibold text-amber-800 shadow-lg"
			in:fly={{ y: -16, duration: 260, easing: cubicOut }}
			out:fly={{ y: -16, duration: 200, easing: cubicOut }}
		>
			<svg
				viewBox="0 0 24 24"
				class="h-4 w-4 shrink-0 text-amber-600"
				fill="none"
				stroke="currentColor"
				stroke-width="2.2"
				stroke-linecap="round"
			>
				<path d="M2 2l20 20" />
				<path d="M8.5 16.5a5 5 0 017 0" />
				<path d="M5 13a10 10 0 013.5-2.3M19 13a10 10 0 00-6.7-2.9" />
				<path d="M2 8.8A15 15 0 016 6.4M22 8.8a15 15 0 00-9.7-3.7" />
			</svg>
			{m.offline_banner()}
		</div>
	</div>
{/if}
