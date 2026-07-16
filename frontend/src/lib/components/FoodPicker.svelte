<script lang="ts">
	import { api, type Food } from '$lib/api';
	import { m } from '$lib/paraglide/messages';
	import { getLocale } from '$lib/paraglide/runtime';

	// addedCount: quantos itens ja entraram nesta sessao do picker (mostrado no botao
	// Pronto, ja que a tela fica aberta para adicionar varios seguidos).
	let {
		onPick,
		onClose,
		addedCount = 0
	}: { onPick: (food: Food) => void; onClose: () => void; addedCount?: number } = $props();

	const nf = new Intl.NumberFormat(getLocale());
	let query = $state('');
	let foods = $state<Food[]>([]);
	let loading = $state(true);

	async function load(): Promise<void> {
		loading = true;
		foods = await api.getFoods(query);
		loading = false;
	}

	$effect(() => {
		load();
	});
</script>

<div class="fixed inset-0 z-40 overflow-y-auto bg-slate-50">
	<div class="mx-auto max-w-md px-4 pt-6 pb-24">
		<div class="mb-3 flex items-center justify-between">
			<h1 class="text-xl font-bold">{m.add_ingredient()}</h1>
			<button
				type="button"
				onclick={onClose}
				class="rounded-full bg-emerald-600 px-5 py-2 text-sm font-bold text-white active:bg-emerald-700"
			>
				{m.done()}{addedCount > 0 ? ` (${addedCount})` : ''}
			</button>
		</div>
		<input
			bind:value={query}
			placeholder={m.search_food()}
			class="mb-3 h-12 w-full rounded-2xl border-2 border-slate-200 bg-white px-4 outline-none focus:border-emerald-600"
		/>
		{#if loading}
			<div class="flex justify-center py-10">
				<div class="h-7 w-7 animate-spin rounded-full border-4 border-emerald-600 border-t-transparent"></div>
			</div>
		{:else}
			<div class="space-y-2">
				{#each foods as food (food.id)}
					<button
						type="button"
						onclick={() => onPick(food)}
						class="flex w-full items-center justify-between rounded-2xl bg-white p-3.5 text-left shadow-sm active:bg-slate-50"
					>
						<span class="min-w-0 flex-1">
							<span class="block truncate font-semibold text-slate-900">{food.name}</span>
							<span class="text-xs text-slate-500">{nf.format(food.kcal)} kcal / 100 g</span>
						</span>
						<span class="ml-2 text-xl font-bold text-emerald-600">+</span>
					</button>
				{/each}
			</div>
		{/if}
	</div>
</div>
