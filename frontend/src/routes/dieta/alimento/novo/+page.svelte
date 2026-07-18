<script lang="ts">
	import { goto } from '$app/navigation';
	import { api, type ExternalFood, type FoodCategory } from '$lib/api';
	import ChoiceChips from '$lib/components/ChoiceChips.svelte';
	import Stepper from '$lib/components/Stepper.svelte';
	import Spinner from '$lib/components/Spinner.svelte';
	import { showToast } from '$lib/toast.svelte';
	import { m } from '$lib/paraglide/messages';

	let name = $state('');
	let category = $state<FoodCategory>('protein');
	let kcal = $state(0);
	let protein = $state(0);
	let carbs = $state(0);
	let fat = $state(0);
	let portion = $state(100);
	let busy = $state(false);

	// Busca externa (Open Food Facts): preenche os campos com dados reais do produto.
	let extQuery = $state('');
	let extResults = $state<ExternalFood[]>([]);
	let extSearching = $state(false);
	let extSearched = $state(false);

	// Guarda contra respostas fora de ordem: se o usuario buscar de novo antes da
	// resposta anterior voltar, a resposta antiga (mais lenta) nao pode sobrescrever
	// a mais nova ao chegar depois - so aplicamos o resultado da busca MAIS RECENTE.
	let extRequestId = 0;

	async function searchExternal(): Promise<void> {
		if (extQuery.trim().length < 2) return;
		const requestId = ++extRequestId;
		extSearching = true;
		try {
			const results = await api.searchExternalFoods(extQuery.trim());
			if (requestId !== extRequestId) return; // uma busca mais nova ja foi disparada
			extResults = results;
			extSearched = true;
		} finally {
			if (requestId === extRequestId) extSearching = false;
		}
	}

	function pickExternal(food: ExternalFood): void {
		name = food.brand ? `${food.name} (${food.brand})` : food.name;
		kcal = Math.round(food.kcal);
		protein = Math.round(food.protein_g * 10) / 10;
		carbs = Math.round(food.carbs_g * 10) / 10;
		fat = Math.round(food.fat_g * 10) / 10;
		extResults = [];
		extSearched = false;
		extQuery = '';
		showToast(m.ext_search_filled());
	}

	const canSave = $derived(name.trim().length > 0);

	async function save(): Promise<void> {
		if (!canSave) return;
		busy = true;
		try {
			await api.createFood({
				name: name.trim(),
				category,
				kcal,
				protein_g: protein,
				carbs_g: carbs,
				fat_g: fat,
				default_portion_g: portion
			});
			showToast(m.toast_created());
			history.back();
		} finally {
			busy = false;
		}
	}
</script>

<div class="mb-4 flex items-center gap-2">
	<button
		type="button"
		aria-label={m.back()}
		onclick={() => history.back()}
		class="grid h-10 w-10 place-items-center rounded-full bg-white text-slate-500 shadow-sm"
	>
		<svg viewBox="0 0 24 24" class="h-5 w-5" fill="none" stroke="currentColor" stroke-width="2">
			<path d="M15 6l-6 6 6 6" stroke-linecap="round" stroke-linejoin="round" />
		</svg>
	</button>
	<h1 class="text-2xl font-bold">{m.create_food()}</h1>
</div>

<input
	bind:value={name}
	placeholder={m.food_name_placeholder()}
	class="h-14 w-full rounded-2xl border-2 border-slate-200 bg-white px-4 text-base font-semibold outline-none focus:border-emerald-600"
/>

<div class="mt-3 rounded-2xl bg-white p-4 shadow-sm">
	<p class="mb-2 text-sm font-semibold text-slate-600">{m.ext_search_title()}</p>
	<div class="flex gap-2">
		<div class="relative min-w-0 flex-1">
			<input
				bind:value={extQuery}
				onkeydown={(e) => e.key === 'Enter' && searchExternal()}
				placeholder={m.food_name_placeholder()}
				class="h-11 w-full rounded-2xl border-2 border-slate-200 bg-white pr-10 pl-3 text-sm outline-none focus:border-emerald-600"
			/>
			{#if extQuery}
				<button
					type="button"
					aria-label={m.clear()}
					title={m.clear()}
					onclick={() => (extQuery = '')}
					class="absolute top-1/2 right-1.5 grid h-7 w-7 -translate-y-1/2 place-items-center rounded-full text-slate-400 active:bg-slate-100"
				>
					<svg viewBox="0 0 24 24" class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M6 6l12 12M18 6L6 18" /></svg>
				</button>
			{/if}
		</div>
		<button
			type="button"
			disabled={extSearching || extQuery.trim().length < 2}
			onclick={searchExternal}
			class="flex h-11 shrink-0 items-center gap-2 rounded-2xl bg-emerald-600 px-4 text-sm font-bold text-white active:bg-emerald-700 disabled:opacity-50"
		>
			{#if extSearching}<Spinner class="h-4 w-4" />{/if}
			{m.ext_search_action()}
		</button>
	</div>
	{#if extResults.length > 0}
		<div class="mt-2 space-y-1.5">
			{#each extResults as f, i (f.name + (f.brand ?? '') + i)}
				<button
					type="button"
					onclick={() => pickExternal(f)}
					class="flex w-full items-center gap-2 rounded-xl bg-slate-50 px-3 py-2 text-left active:bg-slate-100"
				>
					<div class="min-w-0 flex-1">
						<p class="truncate text-sm font-semibold text-slate-800">{f.name}{f.brand ? ` · ${f.brand}` : ''}</p>
						<p class="text-xs text-slate-500">
							{Math.round(f.kcal)} kcal · {f.protein_g}p {f.carbs_g}c {f.fat_g}f · 100 g
						</p>
					</div>
					<svg viewBox="0 0 24 24" class="h-4 w-4 shrink-0 text-emerald-500" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 5v14M5 12h14" stroke-linecap="round" /></svg>
				</button>
			{/each}
		</div>
	{:else if extSearched && !extSearching}
		<p class="mt-2 text-xs text-slate-400">{m.ext_search_empty()}</p>
	{/if}
	<p class="mt-2 text-[11px] text-slate-400">{m.ext_search_hint()}</p>
</div>

<div class="mt-3 rounded-2xl bg-white p-4 shadow-sm">
	<p class="mb-2 text-sm font-semibold text-slate-600">{m.category_label()}</p>
	<ChoiceChips
		columns={3}
		bind:value={category}
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
</div>

<div class="mt-3 rounded-2xl bg-white p-4 shadow-sm">
	<p class="mb-3 text-sm font-semibold text-slate-600">{m.per_100g()}</p>
	<div class="space-y-4">
		<div>
			<p class="mb-1 text-xs font-semibold text-slate-500">{m.calories_label()} (kcal)</p>
			<Stepper bind:value={kcal} min={0} max={1000} step={5} />
		</div>
		<div class="grid grid-cols-3 gap-2">
			<div>
				<p class="mb-1 text-xs font-semibold text-slate-500">{m.protein()} (g)</p>
				<Stepper size="sm" bind:value={protein} min={0} max={100} step={0.5} decimals={1} />
			</div>
			<div>
				<p class="mb-1 text-xs font-semibold text-slate-500">{m.carbs()} (g)</p>
				<Stepper size="sm" bind:value={carbs} min={0} max={100} step={0.5} decimals={1} />
			</div>
			<div>
				<p class="mb-1 text-xs font-semibold text-slate-500">{m.fat()} (g)</p>
				<Stepper size="sm" bind:value={fat} min={0} max={100} step={0.5} decimals={1} />
			</div>
		</div>
		<div>
			<p class="mb-1 text-xs font-semibold text-slate-500">{m.default_portion()} (g)</p>
			<Stepper bind:value={portion} min={1} max={2000} step={5} unit="g" />
		</div>
	</div>
</div>

<button
	type="button"
	disabled={!canSave || busy}
	onclick={save}
	class="mt-3 h-14 w-full rounded-2xl bg-emerald-600 text-lg font-bold text-white active:bg-emerald-700 disabled:opacity-40"
>
	{m.save()}
</button>
