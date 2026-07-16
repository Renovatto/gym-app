<script lang="ts">
	import { goto } from '$app/navigation';
	import { page } from '$app/state';
	import { api, type Food } from '$lib/api';
	import FoodPicker from '$lib/components/FoodPicker.svelte';
	import Stepper from '$lib/components/Stepper.svelte';
	import { showToast } from '$lib/toast.svelte';
	import { m } from '$lib/paraglide/messages';
	import { getLocale } from '$lib/paraglide/runtime';

	interface Ingredient {
		food: Food;
		grams: number;
	}

	const recipeId = $derived(page.params.id);
	const isNew = $derived(recipeId === 'nova');
	const nf = new Intl.NumberFormat(getLocale());

	let name = $state('');
	let servings = $state(1);
	let ingredients = $state<Ingredient[]>([]);
	let loading = $state(true);
	let picking = $state(false);
	let busy = $state(false);

	async function load(): Promise<void> {
		if (isNew) {
			name = '';
			servings = 1;
			ingredients = [];
		} else {
			const recipe = await api.getRecipes().then((rs) => rs.find((r) => r.id === Number(recipeId)));
			if (recipe) {
				name = recipe.name;
				servings = recipe.servings;
				ingredients = recipe.ingredients.map((i) => ({ food: i.food, grams: i.grams }));
			}
		}
		loading = false;
	}

	// contador de itens adicionados nesta abertura do picker (mostrado no Pronto)
	let pickerAdded = $state(0);

	function addFood(food: Food): void {
		if (ingredients.some((i) => i.food.id === food.id)) return;
		ingredients = [...ingredients, { food, grams: food.default_portion_g }];
		pickerAdded += 1;
		showToast(m.toast_added());
	}

	function removeIngredient(index: number): void {
		ingredients = ingredients.filter((_, i) => i !== index);
	}

	// total ao vivo somando os ingredientes
	const total = $derived(
		ingredients.reduce(
			(acc, ing) => {
				const f = ing.grams / 100;
				acc.kcal += ing.food.kcal * f;
				acc.protein += ing.food.protein_g * f;
				acc.carbs += ing.food.carbs_g * f;
				acc.fat += ing.food.fat_g * f;
				return acc;
			},
			{ kcal: 0, protein: 0, carbs: 0, fat: 0 }
		)
	);
	const perServing = $derived({
		kcal: total.kcal / Math.max(servings, 1),
		protein: total.protein / Math.max(servings, 1),
		carbs: total.carbs / Math.max(servings, 1),
		fat: total.fat / Math.max(servings, 1)
	});

	const canSave = $derived(name.trim().length > 0 && ingredients.length > 0);

	async function save(): Promise<void> {
		if (!canSave) return;
		busy = true;
		const payload = {
			name: name.trim(),
			servings,
			ingredients: ingredients.map((i) => ({ food_id: i.food.id, grams: i.grams }))
		};
		try {
			if (isNew) await api.createRecipe(payload);
			else await api.updateRecipe(Number(recipeId), payload);
			showToast(isNew ? m.toast_created() : m.toast_saved());
			await goto('/dieta/receitas');
		} finally {
			busy = false;
		}
	}

	// exclusao sempre com confirmacao
	let confirmingDelete = $state(false);

	async function remove(): Promise<void> {
		busy = true;
		try {
			await api.deleteRecipe(Number(recipeId));
			showToast(m.toast_deleted());
			await goto('/dieta/receitas');
		} finally {
			busy = false;
		}
	}

	$effect(() => {
		load();
	});
</script>

{#if picking}
	<FoodPicker onPick={addFood} addedCount={pickerAdded} onClose={() => (picking = false)} />
{/if}

{#if loading}
	<div class="flex justify-center py-16">
		<div class="h-8 w-8 animate-spin rounded-full border-4 border-emerald-600 border-t-transparent"></div>
	</div>
{:else}
	<div class="mb-4 flex items-center gap-2">
		<a
			href="/dieta/receitas"
			aria-label={m.back()}
			class="grid h-10 w-10 place-items-center rounded-full bg-white text-slate-500 shadow-sm"
		>
			<svg viewBox="0 0 24 24" class="h-5 w-5" fill="none" stroke="currentColor" stroke-width="2">
				<path d="M15 6l-6 6 6 6" stroke-linecap="round" stroke-linejoin="round" />
			</svg>
		</a>
		<h1 class="text-2xl font-bold">{isNew ? m.new_recipe() : m.edit_recipe()}</h1>
	</div>

	<input
		bind:value={name}
		placeholder={m.recipe_name_placeholder()}
		class="h-14 w-full rounded-2xl border-2 border-slate-200 bg-white px-4 text-base font-semibold outline-none focus:border-emerald-600"
	/>

	<div class="mt-3 rounded-2xl bg-white p-4 shadow-sm">
		<p class="mb-2 text-sm font-semibold text-slate-600">{m.servings_label()}</p>
		<Stepper bind:value={servings} min={1} max={50} />
	</div>

	<div class="mt-3 space-y-2">
		{#each ingredients as ing, index (ing.food.id)}
			<div class="rounded-2xl bg-white p-3 shadow-sm">
				<div class="flex items-center justify-between gap-2">
					<p class="min-w-0 flex-1 truncate font-semibold text-slate-900">{ing.food.name}</p>
					<button
						type="button"
						aria-label={m.remove()}
						onclick={() => removeIngredient(index)}
						class="text-slate-300 active:text-red-500"
					>
						<svg viewBox="0 0 24 24" class="h-5 w-5" fill="none" stroke="currentColor" stroke-width="2">
							<path d="M6 6l12 12M18 6L6 18" stroke-linecap="round" />
						</svg>
					</button>
				</div>
				<div class="mt-2">
					<Stepper bind:value={ing.grams} min={1} max={2000} step={5} unit="g" />
				</div>
			</div>
		{/each}
	</div>

	<button
		type="button"
		onclick={() => {
			pickerAdded = 0;
			picking = true;
		}}
		class="mt-3 h-14 w-full rounded-2xl border-2 border-dashed border-emerald-300 font-bold text-emerald-700 active:bg-emerald-50"
	>
		+ {m.add_ingredient()}
	</button>

	{#if ingredients.length > 0}
		<div class="mt-3 rounded-2xl bg-ink p-4 text-white">
			<div class="flex items-center justify-between">
				<span class="text-sm font-semibold text-slate-300">{m.per_serving()}</span>
				<span class="text-lg font-bold">{nf.format(Math.round(perServing.kcal))} kcal</span>
			</div>
			<div class="mt-1 flex gap-4 text-sm text-slate-300">
				<span>P {nf.format(Math.round(perServing.protein))}g</span>
				<span>C {nf.format(Math.round(perServing.carbs))}g</span>
				<span>G {nf.format(Math.round(perServing.fat))}g</span>
			</div>
		</div>
	{/if}

	<button
		type="button"
		disabled={!canSave || busy}
		onclick={save}
		class="mt-3 h-14 w-full rounded-2xl bg-emerald-600 text-lg font-bold text-white active:bg-emerald-700 disabled:opacity-40"
	>
		{m.save_recipe()}
	</button>

	{#if !isNew}
		{#if confirmingDelete}
			<p class="mt-3 rounded-xl bg-red-50 px-4 py-3 text-sm font-medium text-red-700">
				{m.confirm_delete()}
			</p>
			<div class="mt-2 flex gap-2">
				<button
					type="button"
					onclick={() => (confirmingDelete = false)}
					class="h-12 flex-1 rounded-2xl border-2 border-slate-200 font-semibold text-slate-700 active:bg-slate-100"
				>
					{m.cancel()}
				</button>
				<button
					type="button"
					disabled={busy}
					onclick={remove}
					class="h-12 flex-1 rounded-2xl bg-red-600 font-semibold text-white active:bg-red-700 disabled:opacity-50"
				>
					{m.delete_confirm_button()}
				</button>
			</div>
		{:else}
			<button
				type="button"
				onclick={() => (confirmingDelete = true)}
				class="mt-3 h-12 w-full rounded-2xl border-2 border-red-200 font-semibold text-red-600 active:bg-red-50"
			>
				{m.delete_recipe()}
			</button>
		{/if}
	{/if}
{/if}
