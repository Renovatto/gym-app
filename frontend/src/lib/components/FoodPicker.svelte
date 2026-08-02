<script lang="ts">
	import { api, type Food, type FoodCategory } from '$lib/api';
	import ChoiceChips from '$lib/components/ChoiceChips.svelte';
	import Stepper from '$lib/components/Stepper.svelte';
	import { showToast } from '$lib/toast.svelte';
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

	// --- Cadastrar alimento sem sair daqui -----------------------------------
	// O ingrediente que falta costuma ser descoberto no meio da receita ("nao tenho
	// o tempero da casa cadastrado"). Mandar a pessoa para a tela de alimento jogaria
	// fora a receita em edicao, que ainda nao foi salva - entao o cadastro acontece
	// aqui mesmo, e o alimento novo ja entra como ingrediente.
	let creating = $state(false);
	let saving = $state(false);
	let newName = $state('');
	let newCategory = $state<FoodCategory>('protein');
	let newKcal = $state(0);
	let newProtein = $state(0);
	let newCarbs = $state(0);
	let newFat = $state(0);
	let newPortion = $state(100);

	const canCreate = $derived(newName.trim().length > 0 && !saving);

	function openCreate(): void {
		// o que ja foi digitado na busca vira o nome: quem procurou e nao achou
		// acabou de escrever o nome do alimento que quer criar
		newName = query.trim();
		newCategory = 'protein';
		newKcal = 0;
		newProtein = 0;
		newCarbs = 0;
		newFat = 0;
		newPortion = 100;
		creating = true;
	}

	async function createAndAdd(): Promise<void> {
		if (!canCreate) return;
		saving = true;
		try {
			const food = await api.createFood({
				name: newName.trim(),
				category: newCategory,
				kcal: newKcal,
				protein_g: newProtein,
				carbs_g: newCarbs,
				fat_g: newFat,
				default_portion_g: newPortion
			});
			creating = false;
			// entra direto na receita: criar e voltar para procurar de novo seria
			// obrigar a pessoa a achar o que ela mesma acabou de cadastrar
			onPick(food);
			query = '';
		} finally {
			saving = false;
		}
	}
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

		{#if creating}
			<!-- Formulario curto de proposito: so o essencial para o alimento virar
				 ingrediente agora. O cadastro completo (busca online, traducoes) segue
				 na tela de alimento, para quando houver tempo de caprichar. -->
			<div class="rounded-2xl bg-white p-4 shadow-sm">
				<div class="mb-3 flex items-center justify-between gap-2">
					<p class="font-bold text-slate-900">{m.create_food()}</p>
					<button
						type="button"
						aria-label={m.cancel()}
						onclick={() => (creating = false)}
						class="grid h-9 w-9 shrink-0 place-items-center rounded-full bg-slate-100 text-slate-500 active:bg-slate-200"
					>
						<svg viewBox="0 0 24 24" class="h-5 w-5" fill="none" stroke="currentColor" stroke-width="2"><path d="M6 6l12 12M18 6L6 18" stroke-linecap="round" /></svg>
					</button>
				</div>

				<input
					bind:value={newName}
					placeholder={m.food_name_placeholder()}
					class="h-12 w-full rounded-2xl border-2 border-slate-200 px-4 font-semibold outline-none focus:border-emerald-600"
				/>

				<p class="mt-3 mb-2 text-sm font-semibold text-slate-600">{m.category_label()}</p>
				<ChoiceChips
					columns={3}
					bind:value={newCategory}
					options={[
						{ value: 'protein', label: m.cat_protein() },
						{ value: 'carb', label: m.cat_carb() },
						{ value: 'fat', label: m.cat_fat() },
						{ value: 'fruit', label: m.cat_fruit() },
						{ value: 'vegetable', label: m.cat_vegetable() },
						{ value: 'dairy', label: m.cat_dairy() },
						{ value: 'legume', label: m.cat_legume() },
						{ value: 'sweet', label: m.cat_sweet() },
						{ value: 'prepared', label: m.cat_prepared() },
						{ value: 'supplement', label: m.cat_supplement() },
						{ value: 'other', label: m.cat_other() }
					]}
				/>

				<p class="mt-4 mb-3 text-sm font-semibold text-slate-600">{m.per_100g()}</p>
				<div class="space-y-4">
					<div>
						<p class="mb-1 text-xs font-semibold text-slate-500">{m.calories_label()} (kcal)</p>
						<Stepper bind:value={newKcal} min={0} max={1000} step={5} />
					</div>
					<div class="grid grid-cols-3 gap-2">
						<div>
							<p class="mb-1 text-xs font-semibold text-slate-500">{m.protein()} (g)</p>
							<Stepper size="sm" bind:value={newProtein} min={0} max={100} step={0.5} decimals={1} />
						</div>
						<div>
							<p class="mb-1 text-xs font-semibold text-slate-500">{m.carbs()} (g)</p>
							<Stepper size="sm" bind:value={newCarbs} min={0} max={100} step={0.5} decimals={1} />
						</div>
						<div>
							<p class="mb-1 text-xs font-semibold text-slate-500">{m.fat()} (g)</p>
							<Stepper size="sm" bind:value={newFat} min={0} max={100} step={0.5} decimals={1} />
						</div>
					</div>
					<div>
						<p class="mb-1 text-xs font-semibold text-slate-500">{m.default_portion()} (g)</p>
						<Stepper bind:value={newPortion} min={1} max={2000} step={5} unit="g" />
					</div>
				</div>

				<button
					type="button"
					disabled={!canCreate}
					onclick={createAndAdd}
					class="mt-4 h-12 w-full rounded-2xl bg-emerald-600 font-bold text-white active:bg-emerald-700 disabled:opacity-40"
				>
					{m.food_create_and_add()}
				</button>
			</div>
		{:else}
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
				{#if foods.length === 0}
					<p class="rounded-2xl bg-white px-4 py-3 text-center text-sm text-slate-400 shadow-sm">
						{m.search_no_results()}
					</p>
				{/if}
			{/if}

			<!-- Depois da lista: so quem procurou e nao achou precisa cadastrar. -->
			<button
				type="button"
				onclick={openCreate}
				class="mt-3 h-12 w-full rounded-2xl border-2 border-dashed border-emerald-300 font-bold text-emerald-700 active:bg-emerald-50"
			>
				+ {m.create_food()}
			</button>
		{/if}
	</div>
</div>
