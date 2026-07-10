<script lang="ts">
	// Rota fina: o fluxo de adicionar virou o componente AddEntryModal (usado como
	// modal dentro da tela de Dieta). Esta pagina existe para links diretos
	// (ex.: botao "+" do dashboard) continuarem funcionando.
	import { goto } from '$app/navigation';
	import { page } from '$app/state';
	import { localDay, type MealType } from '$lib/api';
	import AddEntryModal from '$lib/components/AddEntryModal.svelte';

	const meal = $derived((page.url.searchParams.get('meal') ?? 'breakfast') as MealType);
	const entryDay = $derived(page.url.searchParams.get('day') ?? localDay());
</script>

<AddEntryModal {meal} day={entryDay} onClose={() => goto('/dieta')} onAdded={() => {}} />
