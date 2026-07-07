<script lang="ts">
	// Icone objetivo para cada tipo de medida de composicao corporal.
	// kind: fat | muscle | skeletal | water | visceral | metabolism | weight
	let { kind, class: klass = 'h-5 w-5' }: { kind: string; class?: string } = $props();
</script>

<svg viewBox="0 0 24 24" class={klass} fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
	{#if kind === 'fat'}
		<!-- dobra de gordura (skinfold): duas curvas se aproximando -->
		<path d="M3 8c4 3 14 3 18 0" />
		<path d="M3 16c4-3 14-3 18 0" />
	{:else if kind === 'muscle'}
		<!-- braco flexionado (biceps) -->
		<path d="M6 21v-5a3 3 0 013-3h1.5a2.5 2.5 0 002.5-2.5V7" />
		<path d="M13 9c0-3 2-5 5-5 0 4-1 6-4 7" />
		<path d="M6 21h5" />
	{:else if kind === 'skeletal'}
		<!-- osso -->
		<path d="M7 8a2 2 0 10-2.8 1.8L9 14l-4.8 4.2A2 2 0 107 20l5-4.5 5 4.5a2 2 0 102.8-1.8L15 14l4.8-4.2A2 2 0 1017 8l-5 4.5L7 8z" />
	{:else if kind === 'water'}
		<!-- gota -->
		<path d="M12 3s6 6 6 10a6 6 0 11-12 0c0-4 6-10 6-10z" />
	{:else if kind === 'visceral'}
		<!-- alvo/nucleo (gordura visceral fica no centro do abdomen) -->
		<circle cx="12" cy="12" r="8" />
		<circle cx="12" cy="12" r="3.2" />
	{:else if kind === 'metabolism'}
		<!-- chama (gasto energetico) -->
		<path d="M12 3c1.5 2.5 4 4 4 8a4 4 0 11-8 0c0-1.6.8-2.8 1.8-3.8C10 9 11 10 11 11.5 11 9.5 11.5 6 12 3z" />
	{:else}
		<!-- peso: balanca -->
		<path d="M4 20h16" />
		<path d="M6 20l2.5-9h7L18 20" />
		<circle cx="12" cy="7" r="3" />
	{/if}
</svg>
