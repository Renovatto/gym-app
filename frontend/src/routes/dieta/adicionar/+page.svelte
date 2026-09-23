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

<!-- trapBack={false}: aqui a "modal" e a tela toda, entao o Voltar do aparelho ja
	 devolve para de onde a pessoa veio. replaceState no Concluido pelo mesmo motivo -
	 sem ele, voltar da Dieta traria esta tela de novo, que e de onde acabou de sair. -->
<AddEntryModal
	{meal}
	day={entryDay}
	trapBack={false}
	onClose={() => goto('/dieta', { replaceState: true })}
	onAdded={() => {}}
/>
