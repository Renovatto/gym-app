<script lang="ts">
	import { goto } from '$app/navigation';
	import { page } from '$app/state';
	import { closeOnBack } from '$lib/modalBack';
	import { ApiError, api, type Connection, type Food } from '$lib/api';
	import { errorMessage } from '$lib/errors';
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
	let partners = $state<Connection[]>([]);
	let pickingPartner = $state(false);
	let sharing = $state(false);
	let archivedAt = $state<string | null>(null);
	let isDuplicate = $state(false);
	let confirmingArchive = $state(false);
	let confirmingUnarchive = $state(false);

	// Rendimento: por PORCOES (direto, como sempre foi) ou por PESO por porcao (g) -
	// nesse modo, o numero de porcoes e derivado do peso total / peso por porcao.
	// O peso total ja e a soma dos ingredientes, sem precisar de nada novo no backend.
	let yieldMode = $state<'servings' | 'grams'>('servings');
	let servingGrams = $state(150);
	const totalGrams = $derived(ingredients.reduce((sum, i) => sum + i.grams, 0));
	const derivedServings = $derived(Math.max(1, Math.round(totalGrams / Math.max(servingGrams, 1))));
	const effectiveServings = $derived(yieldMode === 'grams' ? derivedServings : servings);

	async function load(): Promise<void> {
		if (isNew) {
			name = '';
			servings = 1;
			ingredients = [];
		} else {
			const [allRecipes, duplicates] = await Promise.all([
				api.getRecipes(undefined, true),
				api.getDietDuplicates()
			]);
			const recipe = allRecipes.find((item) => item.id === Number(recipeId));
			if (recipe) {
				archivedAt = recipe.archived_at;
				isDuplicate = duplicates.some(
					(group) => group.item_kind === 'recipe' && group.items.some((item) => item.id === recipe.id)
				);
				name = recipe.name;
				servings = recipe.servings;
				ingredients = recipe.ingredients.map((i) => ({ food: i.food, grams: i.grams }));
				// ponto de partida sensato se o usuario trocar para o modo "peso por porcao"
				const total = ingredients.reduce((sum, i) => sum + i.grams, 0);
				servingGrams = Math.max(1, Math.round(total / Math.max(recipe.servings, 1)));
				if (recipe.archived_at === null) void loadPartners();
			}
		}
		loading = false;
	}

	async function loadPartners(): Promise<void> {
		const connections = await api.getConnections();
		partners = connections.filter((connection) => connection.status === 'accepted');
	}

	function startShare(): void {
		if (partners.length === 1) {
			void shareWith(partners[0]);
			return;
		}
		pickingPartner = true;
	}

	async function shareWith(partner: Connection): Promise<void> {
		sharing = true;
		try {
			await api.createShareOffers(partner.id, [
				{ item_kind: 'recipe', item_id: Number(recipeId) }
			]);
			pickingPartner = false;
			showToast(m.sharing_sent_toast({ name: partner.person_name }));
		} catch (error) {
			showToast(errorMessage(error instanceof ApiError ? error.code : 'GENERIC_ERROR'));
		} finally {
			sharing = false;
		}
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
		kcal: total.kcal / Math.max(effectiveServings, 1),
		protein: total.protein / Math.max(effectiveServings, 1),
		carbs: total.carbs / Math.max(effectiveServings, 1),
		fat: total.fat / Math.max(effectiveServings, 1)
	});

	const canSave = $derived(name.trim().length > 0 && ingredients.length > 0);

	async function save(): Promise<void> {
		if (!canSave) return;
		busy = true;
		const payload = {
			name: name.trim(),
			servings: effectiveServings,
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
		} catch (e) {
			confirmingDelete = false;
			showToast(errorMessage(e instanceof ApiError ? e.code : 'GENERIC_ERROR'));
		} finally {
			busy = false;
		}
	}

	async function archive(): Promise<void> {
		busy = true;
		try {
			await api.archiveRecipe(Number(recipeId));
			showToast(m.diet_duplicate_archived_toast());
			await goto('/dieta/receitas');
		} catch (error) {
			showToast(errorMessage(error instanceof ApiError ? error.code : 'GENERIC_ERROR'));
		} finally {
			busy = false;
		}
	}

	async function unarchive(): Promise<void> {
		busy = true;
		try {
			await api.unarchiveRecipe(Number(recipeId));
			showToast(m.diet_duplicate_restored_toast());
			await goto('/dieta/receitas');
		} catch (error) {
			showToast(errorMessage(error instanceof ApiError ? error.code : 'GENERIC_ERROR'));
		} finally {
			busy = false;
		}
	}

	$effect(() => {
		load();
	});

	$effect(() => {
		if (pickingPartner) return closeOnBack(() => (pickingPartner = false));
	});
</script>

{#if picking}
	<FoodPicker onPick={addFood} addedCount={pickerAdded} onClose={() => (picking = false)} />
{/if}

{#if pickingPartner}
	<div
		class="fixed inset-0 z-50 flex items-end justify-center bg-black/50 p-4"
		role="button"
		tabindex="-1"
		onclick={() => (pickingPartner = false)}
		onkeydown={(event) => event.key === 'Escape' && (pickingPartner = false)}
	>
		<div
			class="w-full max-w-md rounded-3xl bg-white p-5"
			role="dialog"
			aria-modal="true"
			aria-label={m.sharing_share_action()}
			tabindex="-1"
			onclick={(event) => event.stopPropagation()}
			onkeydown={() => {}}
		>
			<div class="mb-3 flex items-center justify-between">
				<h2 class="font-bold text-slate-900">{m.sharing_share_action()}</h2>
				<button type="button" aria-label={m.cancel()} onclick={() => (pickingPartner = false)} class="grid h-10 w-10 place-items-center rounded-full bg-slate-100 text-slate-500">×</button>
			</div>
			<div class="space-y-2">
				{#each partners as partner (partner.id)}
					<button
						type="button"
						disabled={sharing}
						onclick={() => shareWith(partner)}
						class="flex w-full items-center gap-3 rounded-2xl bg-slate-50 p-3 text-left active:bg-slate-100 disabled:opacity-50"
					>
						<span class="min-w-0 flex-1 truncate font-semibold text-slate-800">{partner.person_name}</span>
						<svg viewBox="0 0 24 24" class="h-5 w-5 shrink-0 text-slate-400" fill="none" stroke="currentColor" stroke-width="2"><path d="M9 6l6 6-6 6" stroke-linecap="round" stroke-linejoin="round" /></svg>
					</button>
				{/each}
			</div>
		</div>
	</div>
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
		<div class="mb-2 flex items-center justify-between gap-2">
			<p class="text-sm font-semibold text-slate-600">{m.servings_label()}</p>
			<div class="flex gap-1 rounded-full bg-slate-100 p-0.5">
				<button
					type="button"
					onclick={() => (yieldMode = 'servings')}
					class="rounded-full px-3 py-1 text-xs font-bold {yieldMode === 'servings' ? 'bg-white text-emerald-700 shadow-sm' : 'text-slate-500'}"
				>
					{m.yield_by_servings()}
				</button>
				<button
					type="button"
					onclick={() => (yieldMode = 'grams')}
					class="rounded-full px-3 py-1 text-xs font-bold {yieldMode === 'grams' ? 'bg-white text-emerald-700 shadow-sm' : 'text-slate-500'}"
				>
					{m.yield_by_grams()}
				</button>
			</div>
		</div>

		{#if yieldMode === 'servings'}
			<Stepper bind:value={servings} min={1} max={50} />
		{:else}
			<Stepper bind:value={servingGrams} min={5} max={2000} step={5} unit="g" />
			<p class="mt-2 text-xs text-slate-400">
				{m.yield_grams_hint({ servings: nf.format(derivedServings) })}
			</p>
		{/if}

		{#if totalGrams > 0}
			<p class="mt-2 text-xs font-medium text-slate-400">
				{m.recipe_total_weight({ grams: nf.format(totalGrams) })}
			</p>
		{/if}
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
		disabled={!canSave || busy || archivedAt !== null}
		onclick={save}
		class="mt-3 h-14 w-full rounded-2xl bg-emerald-600 text-lg font-bold text-white active:bg-emerald-700 disabled:opacity-40"
	>
		{m.save_recipe()}
	</button>

	{#if !isNew}
		{#if archivedAt}
			{#if confirmingUnarchive}
				<p class="mt-3 rounded-xl bg-amber-50 px-4 py-3 text-sm font-medium text-amber-900">{m.diet_duplicate_restore_confirm()}</p>
				<div class="mt-2 flex gap-2">
					<button type="button" onclick={() => (confirmingUnarchive = false)} class="h-12 flex-1 rounded-2xl border-2 border-slate-200 font-semibold text-slate-700 active:bg-slate-100">{m.cancel()}</button>
					<button type="button" disabled={busy} onclick={unarchive} class="h-12 flex-1 rounded-2xl bg-emerald-600 font-semibold text-white active:bg-emerald-700 disabled:opacity-50">{m.diet_duplicate_restore_action()}</button>
				</div>
			{:else}
				<button type="button" onclick={() => (confirmingUnarchive = true)} class="mt-3 h-12 w-full rounded-2xl bg-emerald-600 font-bold text-white active:bg-emerald-700">{m.diet_duplicate_restore_action()}</button>
			{/if}
		{:else}
			{#if partners.length > 0}
				<button
					type="button"
					disabled={sharing}
					onclick={startShare}
					class="mt-3 flex h-12 w-full items-center justify-center gap-2 rounded-2xl bg-emerald-50 font-bold text-emerald-700 active:bg-emerald-100 disabled:opacity-50"
				>
					<svg viewBox="0 0 24 24" class="h-5 w-5" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="18" cy="5" r="3" /><circle cx="6" cy="12" r="3" /><circle cx="18" cy="19" r="3" /><path d="M8.6 13.5l6.8 4M15.4 6.5l-6.8 4" /></svg>
					{m.sharing_share_action()}
				</button>
			{/if}
			{#if isDuplicate}
				{#if confirmingArchive}
					<p class="mt-3 rounded-xl bg-amber-50 px-4 py-3 text-sm font-medium text-amber-900">{m.diet_duplicate_archive_confirm()}</p>
					<div class="mt-2 flex gap-2">
						<button type="button" onclick={() => (confirmingArchive = false)} class="h-12 flex-1 rounded-2xl border-2 border-slate-200 font-semibold text-slate-700 active:bg-slate-100">{m.cancel()}</button>
						<button type="button" disabled={busy} onclick={archive} class="h-12 flex-1 rounded-2xl bg-amber-100 font-semibold text-amber-900 active:bg-amber-200 disabled:opacity-50">{m.diet_duplicate_archive_action()}</button>
					</div>
				{:else}
					<button type="button" onclick={() => (confirmingArchive = true)} class="mt-3 h-12 w-full rounded-2xl border-2 border-amber-200 bg-amber-50 font-bold text-amber-900 active:bg-amber-100">{m.diet_duplicate_archive_action()}</button>
				{/if}
			{/if}
		{/if}
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
