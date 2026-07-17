<script lang="ts">
	import {
		api,
		localDay,
		type DiaryDay,
		type DiaryEntry,
		type DiaryGap,
		type FoodSuggestion,
		type MealPlan,
		type MealPlanMeal,
		type MealType,
		type RecipeSuggestion,
		type RecipeView,
		type SubstituteItem,
		type Substitutes,
		type Supplement,
		type SupplementsDay,
		type DietPeriod,
		type AdaptiveTdee
	} from '$lib/api';
	import MacroSummary from '$lib/components/MacroSummary.svelte';
	import Stepper from '$lib/components/Stepper.svelte';
	import Spinner from '$lib/components/Spinner.svelte';
	import CalendarModal from '$lib/components/CalendarModal.svelte';
	import AddEntryModal from '$lib/components/AddEntryModal.svelte';
	import RecipeViewModal from '$lib/components/RecipeViewModal.svelte';
	import { slide } from 'svelte/transition';
	import { showToast } from '$lib/toast.svelte';
	import { mealTypeLabel } from '$lib/labels';
	import { m } from '$lib/paraglide/messages';
	import { getLocale } from '$lib/paraglide/runtime';

	let diary = $state<DiaryDay | null>(null);
	let loading = $state(true);
	let day = $state(localDay());

	// "O que falta hoje": lacuna + sugestoes vindas do motor de recomendacao.
	let gap = $state<DiaryGap | null>(null);
	let addBusy = $state(false);

	// Cardapio consultivo (nutri): plano por refeicao, aberto por refeicao ou geral.
	let mealPlan = $state<MealPlan | null>(null);
	let expandedMeals = $state<Set<MealType>>(new Set());

	// Trocar uma SUGESTAO por um equivalente: abre a lista de opcoes da mesma categoria.
	let suggSubs = $state<Substitutes | null>(null);
	let suggSubsMeal = $state<MealType | null>(null);
	let loadingSuggSubs = $state(false);

	// calendario: dias com lancamentos ficam marcados
	let showCalendar = $state(false);
	let loggedDays = $state<Set<string>>(new Set());

	// Suplementos (adesao diaria; zero-macro nao entra nos macros)
	let supplements = $state<SupplementsDay | null>(null);
	let supplementBusy = $state(false);
	let showSupplementManager = $state(false);
	let suppName = $state('');
	let suppDose = $state('');
	let suppEditingId = $state<number | null>(null);
	let suppFormBusy = $state(false);
	let confirmingDeleteSupp = $state<number | null>(null);

	// Periodo da dieta (vigencia da meta): datas, objetivo, validade e renovacao
	let dietPeriod = $state<DietPeriod | null>(null);
	let showPeriodModal = $state(false);
	let periodAdaptive = $state<AdaptiveTdee | null>(null);
	let periodBusy = $state(false);
	const pdf = new Intl.DateTimeFormat(getLocale(), { day: '2-digit', month: 'short' });
	function fmtPeriodDate(iso: string): string {
		return pdf.format(new Date(iso + 'T12:00:00'));
	}
	function objectiveLabel(obj: string): string {
		if (obj === 'gain_muscle') return m.objective_gain_muscle();
		if (obj === 'lose_fat') return m.objective_lose_fat();
		if (obj === 'recomp') return m.objective_recomp();
		return m.objective_maintain();
	}
	async function openPeriodModal(): Promise<void> {
		showPeriodModal = true;
		periodAdaptive = null;
		try {
			// a sugestao de adotar a manutencao medida vem do TDEE adaptativo
			periodAdaptive = await api.getAdaptiveTdee(day, new Date().getTimezoneOffset());
		} catch {
			// extra: sem ela ainda da pra renovar reiniciando o periodo
		}
	}
	async function renewPeriod(adopt: boolean): Promise<void> {
		if (periodBusy) return;
		periodBusy = true;
		try {
			const kcal = adopt ? (periodAdaptive?.estimated_maintenance_kcal ?? undefined) : undefined;
			dietPeriod = await api.renewDietPeriod(day, kcal);
			showPeriodModal = false;
			await load(); // a meta muda -> recarrega diario/lacuna/cardapio
			showToast(m.diet_period_renewed());
		} finally {
			periodBusy = false;
		}
	}

	function pad2(n: number): string {
		return String(n).padStart(2, '0');
	}

	async function loadMonthMarks(year: number, month: number): Promise<void> {
		const start = `${year}-${pad2(month)}-01`;
		const end = `${year}-${pad2(month)}-${new Date(year, month, 0).getDate()}`;
		const days = await api.getDiaryLoggedDays(start, end);
		loggedDays = new Set(days);
	}

	// edição de um lançamento existente
	let editing = $state<DiaryEntry | null>(null);
	let editQty = $state(0);
	let editBusy = $state(false);

	function openEdit(entry: DiaryEntry): void {
		editing = entry;
		editQty = entry.quantity;
		confirmingDeleteEntry = false;
		subs = null;
	}

	let confirmingDeleteEntry = $state(false);

	// Substituicao: equivalentes do item aberto na modal.
	let subs = $state<Substitutes | null>(null);
	let loadingSubs = $state(false);
	let swapBusy = $state(false);

	async function saveEdit(): Promise<void> {
		if (!editing) return;
		editBusy = true;
		try {
			await api.updateDiaryEntry(editing.id, editQty);
			editing = null;
			await load();
			showToast(m.toast_saved());
		} finally {
			editBusy = false;
		}
	}

	async function deleteEditing(): Promise<void> {
		if (!editing) return;
		editBusy = true;
		try {
			await api.deleteDiaryEntry(editing.id);
			editing = null;
			confirmingDeleteEntry = false;
			await load();
			showToast(m.toast_deleted());
		} finally {
			editBusy = false;
		}
	}

	// prévia dos macros ao mudar a quantidade (proporção linear ao valor atual)
	const editPreview = $derived(
		editing && editing.quantity > 0
			? Math.round((editing.macros.kcal / editing.quantity) * editQty)
			: 0
	);

	const nf = new Intl.NumberFormat(getLocale());
	const df = new Intl.DateTimeFormat(getLocale(), { weekday: 'short', day: '2-digit', month: 'short' });
	const today = localDay();
	const isToday = $derived(day === today);

	function shiftDay(base: string, delta: number): string {
		const d = new Date(base + 'T12:00:00');
		d.setDate(d.getDate() + delta);
		return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
	}

	// Recarrega os dados SEM o spinner de tela cheia: usado quando a modal de
	// adicionar lanca um item, para a lista atualizar mantendo a posicao de rolagem.
	async function reloadSilent(): Promise<void> {
		[diary, gap, mealPlan, supplements, dietPeriod] = await Promise.all([
			api.getDiary(day),
			api.getDiaryGap(day),
			api.getMealPlan(day),
			api.getSupplements(day),
			api.getDietPeriod(day)
		]);
	}

	async function load(): Promise<void> {
		loading = true;
		await reloadSilent();
		loading = false;
	}

	// Modal de adicionar alimento/receita (fica aberta para lancar varios itens).
	let addingToMeal = $state<MealType | null>(null);

	// Marca/desmarca o suplemento no dia (feedback imediato pelo check, sem toast).
	async function toggleSupplement(s: Supplement): Promise<void> {
		if (supplementBusy) return;
		supplementBusy = true;
		try {
			const updated = s.taken
				? await api.unmarkSupplement(s.id, day)
				: await api.markSupplement(s.id, day);
			if (supplements) {
				supplements.items = supplements.items.map((it) => (it.id === updated.id ? updated : it));
				supplements.taken_count = supplements.items.filter((it) => it.taken).length;
			}
		} finally {
			supplementBusy = false;
		}
	}

	function openSupplementManager(): void {
		showSupplementManager = true;
		suppEditingId = null;
		suppName = '';
		suppDose = '';
		confirmingDeleteSupp = null;
	}

	function editSupplement(s: Supplement): void {
		suppEditingId = s.id;
		suppName = s.name;
		suppDose = s.dose;
		confirmingDeleteSupp = null;
	}

	async function saveSupplement(): Promise<void> {
		const name = suppName.trim();
		if (!name || suppFormBusy) return;
		suppFormBusy = true;
		try {
			if (suppEditingId !== null) {
				await api.updateSupplement(suppEditingId, day, { name, dose: suppDose.trim() });
				showToast(m.toast_saved());
			} else {
				await api.createSupplement(day, { name, dose: suppDose.trim() });
				showToast(m.supp_added());
			}
			suppEditingId = null;
			suppName = '';
			suppDose = '';
			supplements = await api.getSupplements(day);
		} finally {
			suppFormBusy = false;
		}
	}

	async function removeSupplement(id: number): Promise<void> {
		await api.deleteSupplement(id);
		confirmingDeleteSupp = null;
		if (suppEditingId === id) {
			suppEditingId = null;
			suppName = '';
			suppDose = '';
		}
		supplements = await api.getSupplements(day);
		showToast(m.toast_deleted());
	}

	async function repeatPrevious(): Promise<void> {
		await api.copyPreviousDay(day, shiftDay(day, -1));
		await load();
		showToast(m.day_copied());
	}

	async function repeatMeal(meal: MealType): Promise<void> {
		await api.copyPreviousDay(day, shiftDay(day, -1), meal);
		await load();
		showToast(m.day_copied());
	}

	function mealGroup(meal: MealType) {
		return diary?.meals.find((g) => g.meal_type === meal);
	}

	// --- Refeicoes compactas ---
	// Inicio do dia: so mini-cards "+ Nome". Tocar materializa o card completo.
	// Materializada = tem lancamento no dia OU foi adicionada manualmente hoje.
	// O estado do layout reseta por dia; nomes personalizados ficam num historico
	// no aparelho para reutilizar sem digitar de novo.
	const PRINCIPAL_MEALS: MealType[] = ['breakfast', 'lunch', 'dinner'];
	const EXTRA_MEALS: MealType[] = ['snack', 'pre_workout', 'supper', 'other'];
	const MEAL_ORDER: MealType[] = [
		'breakfast', 'pre_workout', 'lunch', 'snack', 'dinner', 'supper', 'other'
	];
	const DAY_STATE_KEY = 'gymapp.diet.dayMeals';
	const CUSTOM_HISTORY_KEY = 'gymapp.diet.customMealNames';

	interface DayMealState {
		day: string;
		added: MealType[];
		customLabel: string | null; // nome digitado para a refeicao "outros" do dia
	}

	function loadDayState(forDay: string): DayMealState {
		try {
			const raw = JSON.parse(localStorage.getItem(DAY_STATE_KEY) ?? 'null') as DayMealState | null;
			if (raw && raw.day === forDay) return raw;
		} catch {
			// estado corrompido: recomeca do zero
		}
		return { day: forDay, added: [], customLabel: null };
	}
	let dayMeals = $state<DayMealState>(loadDayState(localDay()));
	// trocar o dia (setas/calendario) reseta o layout para o daquele dia
	$effect(() => {
		dayMeals = loadDayState(day);
		openMeal = null;
		showMealChooser = false;
		confirmingRemoveMeal = null;
	});
	function saveDayState(): void {
		localStorage.setItem(DAY_STATE_KEY, JSON.stringify($state.snapshot(dayMeals)));
	}

	function loadCustomHistory(): string[] {
		try {
			return JSON.parse(localStorage.getItem(CUSTOM_HISTORY_KEY) ?? '[]');
		} catch {
			return [];
		}
	}
	let customHistory = $state<string[]>(loadCustomHistory());

	let showMealChooser = $state(false);
	let customMealName = $state('');
	// acordeao: uma refeicao expandida por vez
	let openMeal = $state<MealType | null>(null);

	function mealHasEntries(meal: MealType): boolean {
		const group = mealGroup(meal);
		return !!group && group.entries.length > 0;
	}
	const materializedMeals = $derived(
		MEAL_ORDER.filter((meal) => dayMeals.added.includes(meal) || mealHasEntries(meal))
	);
	const miniPrincipals = $derived(
		PRINCIPAL_MEALS.filter((meal) => !materializedMeals.includes(meal))
	);
	const chooserExtras = $derived(
		EXTRA_MEALS.filter((meal) => !materializedMeals.includes(meal))
	);

	function addMealCard(meal: MealType, customLabel: string | null = null): void {
		if (!dayMeals.added.includes(meal)) dayMeals.added = [...dayMeals.added, meal];
		if (customLabel) {
			dayMeals.customLabel = customLabel;
			// historico: mais recente primeiro, sem repetidos, no maximo 8
			customHistory = [customLabel, ...customHistory.filter((n) => n !== customLabel)].slice(0, 8);
			localStorage.setItem(CUSTOM_HISTORY_KEY, JSON.stringify($state.snapshot(customHistory)));
		}
		saveDayState();
		openMeal = meal;
		showMealChooser = false;
		customMealName = '';
	}

	function mealDisplayLabel(meal: MealType): string {
		if (meal === 'other' && dayMeals.customLabel) return dayMeals.customLabel;
		return mealTypeLabel(meal);
	}

	// Remover um card adicionado por engano (so quando vazio; sempre com confirmacao).
	// Refeicao com lancamentos nao remove: apague os itens primeiro.
	let confirmingRemoveMeal = $state<MealType | null>(null);

	function removeMealCard(meal: MealType): void {
		dayMeals.added = dayMeals.added.filter((mt) => mt !== meal);
		if (meal === 'other') dayMeals.customLabel = null;
		saveDayState();
		if (openMeal === meal) openMeal = null;
		confirmingRemoveMeal = null;
		showToast(m.toast_deleted());
	}

	function toggleMealOpen(meal: MealType): void {
		openMeal = openMeal === meal ? null : meal;
	}

	const dayLabel = $derived(
		isToday ? m.today_title() : df.format(new Date(day + 'T12:00:00'))
	);
	const isEmpty = $derived(diary ? diary.meals.every((g) => g.entries.length === 0) : true);

	// Refeicao "do horario" para onde a sugestao entra por padrao (da pra mover depois).
	function mealByTime(): MealType {
		const h = new Date().getHours();
		if (h < 11) return 'breakfast';
		if (h < 15) return 'lunch';
		if (h < 18) return 'snack';
		return 'dinner';
	}

	async function addSuggestion(s: FoodSuggestion, meal: MealType = mealByTime()): Promise<void> {
		addBusy = true;
		try {
			await api.addDiaryEntry({
				entry_date: day,
				meal_type: meal,
				source: 'food',
				food_id: s.food.id,
				quantity: s.grams
			});
			await load();
			showToast(m.reco_added());
		} finally {
			addBusy = false;
		}
	}

	// Sugestao de receita: 1 toque adota a receita da biblioteca e ja lanca a porcao.
	async function addRecipeBySlug(slug: string, meal: MealType): Promise<void> {
		addBusy = true;
		try {
			await api.addDiaryFromLibrary({ slug, entry_date: day, meal_type: meal });
			await load();
			showToast(m.reco_added());
		} finally {
			addBusy = false;
		}
	}

	async function addRecipeSuggestion(
		rs: RecipeSuggestion,
		meal: MealType = mealByTime()
	): Promise<void> {
		await addRecipeBySlug(rs.slug, meal);
	}

	// Visualizacao read-only da receita antes de incluir (icone de olho no card).
	let viewRecipe = $state<RecipeView | null>(null);
	let viewLoading = $state(false);
	let viewOpen = $state(false);
	let viewSlug = $state<string | null>(null);
	let viewMeal = $state<MealType | null>(null);

	async function openRecipeView(rs: RecipeSuggestion, meal: MealType): Promise<void> {
		viewOpen = true;
		viewLoading = true;
		viewSlug = rs.slug;
		viewMeal = meal;
		try {
			viewRecipe = await api.getLibraryRecipe(rs.slug);
		} finally {
			viewLoading = false;
		}
	}

	function closeRecipeView(): void {
		viewOpen = false;
		viewRecipe = null;
		viewSlug = null;
		viewMeal = null;
	}

	async function addFromView(): Promise<void> {
		if (!viewSlug || viewMeal === null) return;
		await addRecipeBySlug(viewSlug, viewMeal);
		closeRecipeView();
	}

	function recipeTagLabel(tag: string): string {
		return (
			{
				protein: m.tag_protein(),
				quick: m.tag_quick(),
				veggie: m.tag_veggie(),
				sweet: m.tag_sweet(),
				budget: m.tag_budget()
			}[tag] ?? tag
		);
	}

	// Abre os equivalentes de uma sugestao (guarda a refeicao alvo para adicionar depois).
	async function openSuggestionSubs(s: FoodSuggestion, meal: MealType): Promise<void> {
		loadingSuggSubs = true;
		suggSubsMeal = meal;
		try {
			suggSubs = await api.getSubstitutes(s.food.id, s.grams);
		} finally {
			loadingSuggSubs = false;
		}
	}

	async function addSubstitute(item: SubstituteItem): Promise<void> {
		if (suggSubsMeal === null) return;
		addBusy = true;
		try {
			await api.addDiaryEntry({
				entry_date: day,
				meal_type: suggSubsMeal,
				source: 'food',
				food_id: item.food.id,
				quantity: item.grams
			});
			suggSubs = null;
			await load();
			showToast(m.reco_added());
		} finally {
			addBusy = false;
		}
	}

	// Cardapio: recomendacao daquela refeicao e controle de expandir (por refeicao ou geral).
	function mealPlanFor(meal: MealType): MealPlanMeal | undefined {
		return mealPlan?.meals.find((mp) => mp.meal_type === meal);
	}
	function isMealExpanded(meal: MealType): boolean {
		return expandedMeals.has(meal);
	}
	// refeicoes que tem sugestao da nutri (alimento ou receita) - p/ abrir/fechar todas
	const mealsWithPlan = $derived(
		(mealPlan?.meals ?? [])
			.filter((mp) => mp.suggestions.length > 0 || mp.recipe_suggestions.length > 0)
			.map((mp) => mp.meal_type)
	);
	const allPlansOpen = $derived(
		mealsWithPlan.length > 0 && mealsWithPlan.every((mt) => expandedMeals.has(mt))
	);
	// o botao geral apenas ENCHE/LIMPA o conjunto: assim o toggle individual sempre
	// consegue fechar (antes um flag "mostrar tudo" prendia os paineis abertos)
	function toggleAllPlans(): void {
		expandedMeals = allPlansOpen ? new Set() : new Set(mealsWithPlan);
	}
	function toggleMealPlan(meal: MealType): void {
		const next = new Set(expandedMeals);
		if (next.has(meal)) next.delete(meal);
		else next.add(meal);
		expandedMeals = next;
	}
	const hasPlan = $derived(
		!!mealPlan &&
			mealPlan.meals.some((mp) => mp.suggestions.length > 0 || mp.recipe_suggestions.length > 0)
	);

	async function openSubstitutes(): Promise<void> {
		if (!editing || editing.food_id === null) return;
		loadingSubs = true;
		try {
			subs = await api.getSubstitutes(editing.food_id, editing.quantity);
		} finally {
			loadingSubs = false;
		}
	}

	// Troca = remove o item atual e adiciona o equivalente na mesma refeicao.
	async function applySwap(item: SubstituteItem): Promise<void> {
		if (!editing) return;
		swapBusy = true;
		try {
			const meal = editing.meal_type;
			await api.deleteDiaryEntry(editing.id);
			await api.addDiaryEntry({
				entry_date: day,
				meal_type: meal,
				source: 'food',
				food_id: item.food.id,
				quantity: item.grams
			});
			editing = null;
			subs = null;
			await load();
			showToast(m.sub_swapped());
		} finally {
			swapBusy = false;
		}
	}

	const showGap = $derived(
		!!gap && gap.suggestions.length > 0 && gap.primary !== 'no_goal' && gap.primary !== 'complete'
	);

	const gapHeadline = $derived.by(() => {
		if (!gap || !gap.remaining) return '';
		const r = gap.remaining;
		if (gap.primary === 'protein') return m.reco_gap_protein({ g: nf.format(Math.round(r.protein_g)) });
		if (gap.primary === 'carbs') return m.reco_gap_carbs({ g: nf.format(Math.round(r.carbs_g)) });
		if (gap.primary === 'fat') return m.reco_gap_fat({ g: nf.format(Math.round(r.fat_g)) });
		if (gap.primary === 'calories') return m.reco_gap_calories({ kcal: nf.format(Math.round(r.kcal)) });
		return '';
	});

	// Detalhe de uma sugestao: gramas, quanto do macro-alvo entrega e as kcal.
	function suggestionHint(s: FoodSuggestion): string {
		const kcal = nf.format(Math.round(s.macros.kcal));
		const grams = `${nf.format(s.grams)} g`;
		if (!gap || gap.primary === 'calories') return `${grams} · ${kcal} kcal`;
		const byPrimary: Record<string, number> = {
			protein: s.macros.protein_g,
			carbs: s.macros.carbs_g,
			fat: s.macros.fat_g
		};
		const amount = Math.round((byPrimary[gap.primary] ?? 0) * 10) / 10;
		return `${grams} · +${nf.format(amount)} g · ${kcal} kcal`;
	}

	function deltaLabel(kcalDelta: number): string {
		const v = Math.round(kcalDelta);
		return `${v > 0 ? '+' : ''}${nf.format(v)} kcal`;
	}

	$effect(() => {
		day;
		load();
	});
</script>

<!-- Sugestao de RECEITA (da biblioteca): borda ambar + icone de prato; "+ Adicionar"
	 adota e lanca em 1 toque. Usada no "o que falta" e no cardapio por refeicao. -->
{#snippet recipeSuggestionCard(rs: RecipeSuggestion, meal: MealType)}
	<div class="flex items-center gap-2 rounded-2xl border border-amber-200 bg-amber-50/50 px-3 py-2">
		<span class="grid h-8 w-8 shrink-0 place-items-center rounded-lg bg-amber-100 text-amber-600">
			<svg viewBox="0 0 24 24" class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 15a7 7 0 0 1 14 0" /><path d="M2 15h20" /><path d="M12 8V5" /><circle cx="12" cy="4" r="1" /></svg>
		</span>
		<div class="min-w-0 flex-1">
			<p class="flex items-center gap-1 truncate text-sm font-semibold text-slate-800">
				{#if rs.is_favorite}
					<svg viewBox="0 0 24 24" class="h-3.5 w-3.5 shrink-0 text-amber-400" fill="currentColor"><path d="M12 3l2.9 5.9 6.5.9-4.7 4.6 1.1 6.5L12 17.8 6.2 20.9l1.1-6.5L2.6 9.8l6.5-.9z" /></svg>
				{/if}
				<span class="truncate">{rs.name}</span>
			</p>
			<p class="text-xs text-slate-500">
				{nf.format(Math.round(rs.macros.kcal))} kcal · P {nf.format(Math.round(rs.macros.protein_g))}g
				{#if rs.tags.length > 0}· {recipeTagLabel(rs.tags[0])}{/if}
			</p>
		</div>
		<button
			type="button"
			aria-label={m.recipe_view()}
			title={m.recipe_view()}
			onclick={() => openRecipeView(rs, meal)}
			class="grid h-9 w-9 shrink-0 place-items-center rounded-xl border-2 border-amber-200 text-amber-600 active:bg-amber-100"
		>
			<svg viewBox="0 0 24 24" class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7-10-7-10-7z" /><circle cx="12" cy="12" r="3" /></svg>
		</button>
		<button
			type="button"
			disabled={addBusy}
			onclick={() => addRecipeSuggestion(rs, meal)}
			class="shrink-0 rounded-xl bg-amber-500 px-3 py-2 text-sm font-bold text-white active:bg-amber-600 disabled:opacity-50"
		>
			+ {m.reco_add()}
		</button>
	</div>
{/snippet}

<div class="mb-4 flex items-center justify-between gap-2">
	<h1 class="text-2xl font-bold">{m.tab_diet()}</h1>
	<div class="flex items-center gap-1">
		<button
			type="button"
			aria-label={m.previous_day()}
			onclick={() => (day = shiftDay(day, -1))}
			class="grid h-9 w-9 place-items-center rounded-full bg-white text-slate-500 shadow-sm active:bg-slate-100"
		>
			<svg viewBox="0 0 24 24" class="h-5 w-5" fill="none" stroke="currentColor" stroke-width="2"><path d="M15 6l-6 6 6 6" stroke-linecap="round" stroke-linejoin="round" /></svg>
		</button>
		<button
			type="button"
			onclick={() => (showCalendar = true)}
			class="flex min-w-24 items-center justify-center gap-1.5 rounded-full bg-white px-3 py-1.5 text-sm font-semibold text-slate-600 shadow-sm active:bg-slate-100"
		>
			<svg viewBox="0 0 24 24" class="h-4 w-4 text-slate-400" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="4" width="18" height="17" rx="2" /><path d="M3 9h18M8 2v4M16 2v4" stroke-linecap="round" /></svg>
			{dayLabel}
		</button>
		<button
			type="button"
			aria-label={m.next_day()}
			disabled={isToday}
			onclick={() => (day = shiftDay(day, 1))}
			class="grid h-9 w-9 place-items-center rounded-full bg-white text-slate-500 shadow-sm active:bg-slate-100 disabled:opacity-30"
		>
			<svg viewBox="0 0 24 24" class="h-5 w-5" fill="none" stroke="currentColor" stroke-width="2"><path d="M9 6l6 6-6 6" stroke-linecap="round" stroke-linejoin="round" /></svg>
		</button>
	</div>
</div>

{#if loading}
	<div class="flex justify-center py-16">
		<div class="h-8 w-8 animate-spin rounded-full border-4 border-emerald-600 border-t-transparent"></div>
	</div>
{:else if diary}
	<MacroSummary totals={diary.totals} goals={diary.goals} />

	{#if dietPeriod}
		<button
			type="button"
			onclick={openPeriodModal}
			class="mt-3 flex w-full items-center gap-2.5 rounded-2xl border px-3 py-2.5 text-left {dietPeriod.due
				? 'border-amber-200 bg-amber-50'
				: 'border-slate-200 bg-white'}"
		>
			<svg viewBox="0 0 24 24" class="h-5 w-5 shrink-0 {dietPeriod.due ? 'text-amber-600' : 'text-slate-400'}" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="4" width="18" height="17" rx="2" /><path d="M3 9h18M8 2v4M16 2v4" stroke-linecap="round" /></svg>
			<span class="min-w-0 flex-1">
				<span class="block text-sm font-semibold {dietPeriod.due ? 'text-amber-800' : 'text-slate-700'}">
					{m.diet_period_label()}
				</span>
				<span class="block truncate text-xs {dietPeriod.due ? 'text-amber-600' : 'text-slate-500'}">
					{#if dietPeriod.due}
						{m.diet_period_due()}
					{:else}
						{m.diet_period_review({ date: fmtPeriodDate(dietPeriod.review_on) })}
					{/if}
					· {objectiveLabel(dietPeriod.objective)}
				</span>
			</span>
			<svg viewBox="0 0 24 24" class="h-5 w-5 shrink-0 text-slate-300" fill="none" stroke="currentColor" stroke-width="2"><path d="M9 6l6 6-6 6" stroke-linecap="round" stroke-linejoin="round" /></svg>
		</button>
	{/if}

	{#if showGap && gap}
		<section class="mt-3 rounded-3xl bg-emerald-50 p-4 ring-1 ring-emerald-100">
			<div class="flex items-center gap-2.5">
				<span class="grid h-8 w-8 shrink-0 place-items-center rounded-xl bg-emerald-600 text-white">
					<svg viewBox="0 0 24 24" class="h-5 w-5" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="8" y="2" width="8" height="4" rx="1" /><path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2" /><path d="M12 11h4" /><path d="M12 16h4" /><path d="M8 11h.01" /><path d="M8 16h.01" /></svg>
				</span>
				<div class="min-w-0">
					<p class="text-[11px] font-bold tracking-wide text-emerald-700 uppercase">{m.reco_title()}</p>
					<p class="text-sm font-semibold text-emerald-900">{gapHeadline}</p>
				</div>
			</div>
			{#if gap.remaining}
				<!-- faltas completas do dia (kcal + 3 macros), nao so o macro prioritario -->
				<div class="mt-2.5 grid grid-cols-4 gap-1.5 text-center">
					<div class="rounded-xl bg-white/70 px-1 py-1.5">
						<p class="text-sm font-bold text-emerald-900">{nf.format(Math.round(gap.remaining.kcal))}</p>
						<p class="text-[10px] font-semibold text-emerald-700">kcal</p>
					</div>
					<div class="rounded-xl bg-white/70 px-1 py-1.5 {gap.primary === 'protein' ? 'ring-2 ring-emerald-400' : ''}">
						<p class="text-sm font-bold text-emerald-900">{nf.format(Math.round(gap.remaining.protein_g))}g</p>
						<p class="text-[10px] font-semibold text-emerald-700">{m.protein()}</p>
					</div>
					<div class="rounded-xl bg-white/70 px-1 py-1.5 {gap.primary === 'carbs' ? 'ring-2 ring-emerald-400' : ''}">
						<p class="text-sm font-bold text-emerald-900">{nf.format(Math.round(gap.remaining.carbs_g))}g</p>
						<p class="text-[10px] font-semibold text-emerald-700">{m.carbs()}</p>
					</div>
					<div class="rounded-xl bg-white/70 px-1 py-1.5 {gap.primary === 'fat' ? 'ring-2 ring-emerald-400' : ''}">
						<p class="text-sm font-bold text-emerald-900">{nf.format(Math.round(gap.remaining.fat_g))}g</p>
						<p class="text-[10px] font-semibold text-emerald-700">{m.fat()}</p>
					</div>
				</div>
			{/if}
			<div class="mt-3 space-y-2">
				{#each gap.suggestions as s (s.food.id)}
					<div class="flex items-center gap-2 rounded-2xl bg-white px-3 py-2">
						<div class="min-w-0 flex-1">
							<p class="truncate text-sm font-semibold text-slate-800">{s.food.name}</p>
							<p class="text-xs text-slate-500">{suggestionHint(s)}</p>
						</div>
						<button
							type="button"
							aria-label={m.sub_action()}
							disabled={loadingSuggSubs}
							onclick={() => openSuggestionSubs(s, mealByTime())}
							class="grid h-9 w-9 shrink-0 place-items-center rounded-xl border-2 border-slate-200 text-slate-500 active:bg-slate-100 disabled:opacity-50"
						>
							<svg viewBox="0 0 24 24" class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 4v6h6M20 20v-6h-6M20 8a8 8 0 00-14-3M4 16a8 8 0 0014 3" stroke-linecap="round" stroke-linejoin="round" /></svg>
						</button>
						<button
							type="button"
							disabled={addBusy}
							onclick={() => addSuggestion(s)}
							class="shrink-0 rounded-xl bg-emerald-600 px-3 py-2 text-sm font-bold text-white active:bg-emerald-700 disabled:opacity-50"
						>
							+ {m.reco_add()}
						</button>
					</div>
				{/each}
				{#each gap.recipe_suggestions as rs (rs.slug)}
					{@render recipeSuggestionCard(rs, mealByTime())}
				{/each}
			</div>
		</section>
	{/if}

	{#if hasPlan}
		<button
			type="button"
			onclick={toggleAllPlans}
			class="mt-3 flex w-full items-center justify-center gap-2 rounded-2xl border-2 border-emerald-200 py-2.5 text-sm font-bold text-emerald-700 active:bg-emerald-50"
		>
			<svg viewBox="0 0 24 24" class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="8" y="2" width="8" height="4" rx="1" /><path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2" /><path d="M12 11h4" /><path d="M12 16h4" /><path d="M8 11h.01" /><path d="M8 16h.01" /></svg>
			{m.nutri_plan()}
			<svg viewBox="0 0 24 24" class="h-4 w-4 transition-transform {allPlansOpen ? 'rotate-180' : ''}" fill="none" stroke="currentColor" stroke-width="2"><path d="M6 9l6 6 6-6" stroke-linecap="round" stroke-linejoin="round" /></svg>
		</button>
	{/if}

	<!-- inicio do dia: mini-cards das refeicoes principais + "Outros" fixo -->
	{#if miniPrincipals.length > 0 || chooserExtras.length > 0}
		<div class="mt-4 flex gap-2">
			{#each miniPrincipals as meal (meal)}
				{@const plan = mealPlanFor(meal)}
				<button
					type="button"
					onclick={() => addMealCard(meal)}
					class="min-w-0 flex-1 rounded-2xl border-2 border-dashed border-slate-200 bg-white px-1 py-2.5 text-center text-slate-500 active:border-emerald-400 active:text-emerald-700"
				>
					<span class="block text-lg leading-none font-extrabold">+</span>
					<span class="mt-1 block truncate px-1 text-[11px] font-bold">{mealTypeLabel(meal)}</span>
					{#if plan}
						<span class="block text-[9px] text-slate-400">~{nf.format(Math.round(plan.target.kcal))} kcal</span>
					{/if}
				</button>
			{/each}
			{#if chooserExtras.length > 0}
				<button
					type="button"
					onclick={() => (showMealChooser = !showMealChooser)}
					class="min-w-0 flex-1 rounded-2xl border-2 border-emerald-100 bg-emerald-50 px-1 py-2.5 text-center text-emerald-700 active:bg-emerald-100"
				>
					<span class="block text-lg leading-none font-extrabold">+</span>
					<span class="mt-1 block truncate px-1 text-[11px] font-bold">{mealTypeLabel('other')}</span>
					<span class="block truncate text-[9px] text-emerald-600/70">{m.meal_other_hint()}</span>
				</button>
			{/if}
		</div>
	{/if}

	<!-- escolha da refeicao extra: categorias + nome personalizado (com historico) -->
	{#if showMealChooser}
		<div class="mt-2 rounded-2xl bg-white p-3 shadow-sm" transition:slide={{ duration: 180 }}>
			<p class="mb-2 text-[11px] font-bold tracking-wide text-slate-400 uppercase">{m.meal_chooser_title()}</p>
			<div class="flex flex-wrap gap-1.5">
				{#each chooserExtras as meal (meal)}
					<button
						type="button"
						onclick={() => addMealCard(meal)}
						class="rounded-full border-2 border-slate-200 px-3 py-1.5 text-sm font-semibold text-slate-600 active:border-emerald-400 active:text-emerald-700"
					>
						{mealTypeLabel(meal)}
					</button>
				{/each}
			</div>
			{#if chooserExtras.includes('other')}
				{#if customHistory.length > 0}
					<div class="mt-2 flex flex-wrap gap-1.5">
						{#each customHistory as name (name)}
							<button
								type="button"
								onclick={() => addMealCard('other', name)}
								class="rounded-full bg-emerald-50 px-3 py-1.5 text-sm font-semibold text-emerald-700 active:bg-emerald-100"
							>
								{name}
							</button>
						{/each}
					</div>
				{/if}
				<div class="mt-2 flex gap-2">
					<input
						bind:value={customMealName}
						maxlength="24"
						placeholder={m.meal_custom_placeholder()}
						class="h-11 min-w-0 flex-1 rounded-2xl border-2 border-slate-200 bg-white px-3 text-sm outline-none focus:border-emerald-600"
					/>
					<button
						type="button"
						disabled={!customMealName.trim()}
						onclick={() => addMealCard('other', customMealName.trim())}
						class="h-11 shrink-0 rounded-2xl bg-emerald-600 px-4 text-sm font-bold text-white active:bg-emerald-700 disabled:opacity-50"
					>
						{m.supp_add()}
					</button>
				</div>
			{/if}
		</div>
	{/if}

	<div class="mt-3 space-y-3">
		{#each materializedMeals as meal (meal)}
			{@const group = mealGroup(meal)}
			{@const plan = mealPlanFor(meal)}
			{@const isOpen = openMeal === meal}
			<section class="overflow-hidden rounded-3xl bg-white shadow-sm">
				<!-- cabecalho: toca para minimizar/expandir (acordeao: um aberto por vez) -->
				<button
					type="button"
					onclick={() => toggleMealOpen(meal)}
					class="flex w-full items-center gap-2 p-4 text-left"
				>
					<h2 class="min-w-0 flex-1 truncate font-bold text-slate-900">{mealDisplayLabel(meal)}</h2>
					<span class="shrink-0 text-sm font-semibold text-slate-400">
						{group ? nf.format(Math.round(group.subtotal.kcal)) : 0} kcal
					</span>
					<svg viewBox="0 0 24 24" class="h-5 w-5 shrink-0 text-slate-300 transition-transform {isOpen ? 'rotate-180' : ''}" fill="none" stroke="currentColor" stroke-width="2"><path d="M6 9l6 6 6-6" stroke-linecap="round" stroke-linejoin="round" /></svg>
				</button>
				{#if isOpen}
				<div class="px-4 pb-4" transition:slide={{ duration: 200 }}>

				{#if plan && (plan.suggestions.length > 0 || plan.recipe_suggestions.length > 0)}
					<button
						type="button"
						onclick={() => toggleMealPlan(meal)}
						class="mt-1.5 flex w-full items-center gap-1.5 text-left text-xs font-semibold text-emerald-700"
					>
						<svg viewBox="0 0 24 24" class="h-3.5 w-3.5 shrink-0" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="8" y="2" width="8" height="4" rx="1" /><path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2" /><path d="M12 11h4" /><path d="M12 16h4" /><path d="M8 11h.01" /><path d="M8 16h.01" /></svg>
						<span class="truncate">{m.nutri_suggestion()} · {m.meal_target({ kcal: nf.format(Math.round(plan.target.kcal)) })}</span>
						<svg viewBox="0 0 24 24" class="ml-auto h-4 w-4 shrink-0 transition-transform {isMealExpanded(meal) ? 'rotate-180' : ''}" fill="none" stroke="currentColor" stroke-width="2"><path d="M6 9l6 6 6-6" stroke-linecap="round" stroke-linejoin="round" /></svg>
					</button>
				{/if}

				{#if group && group.entries.length > 0}
					<div class="mt-2 space-y-1">
						{#each group.entries as entry (entry.id)}
							<button
								type="button"
								onclick={() => openEdit(entry)}
								class="flex w-full items-center gap-2 rounded-xl bg-slate-50 px-3 py-2 text-left active:bg-slate-100"
							>
								<div class="min-w-0 flex-1">
									<p class="truncate text-sm font-semibold text-slate-800">{entry.name}</p>
									<p class="text-xs text-slate-500">
										{entry.source === 'recipe'
											? `${nf.format(entry.quantity)} ${entry.quantity === 1 ? m.serving_singular() : m.serving_plural()}`
											: `${nf.format(entry.quantity)} g`}
										· {nf.format(Math.round(entry.macros.kcal))} kcal
									</p>
								</div>
								<svg viewBox="0 0 24 24" class="h-4 w-4 shrink-0 text-slate-300" fill="none" stroke="currentColor" stroke-width="2"><path d="M9 6l6 6-6 6" stroke-linecap="round" stroke-linejoin="round" /></svg>
							</button>
						{/each}
					</div>
				{/if}

				{#if plan && isMealExpanded(meal) && (plan.suggestions.length > 0 || plan.recipe_suggestions.length > 0)}
					<div class="mt-2 space-y-1.5 rounded-2xl bg-emerald-50 p-2">
						{#each plan.suggestions as s (s.food.id)}
							<div class="flex items-center gap-2 rounded-xl bg-white px-3 py-2">
								<div class="min-w-0 flex-1">
									<p class="truncate text-sm font-semibold text-slate-800">{s.food.name}</p>
									<p class="text-xs text-slate-500">
										{nf.format(s.grams)} g · {nf.format(Math.round(s.macros.protein_g))}g prot · {nf.format(Math.round(s.macros.kcal))} kcal
									</p>
								</div>
								<button
									type="button"
									aria-label={m.sub_action()}
									disabled={loadingSuggSubs}
									onclick={() => openSuggestionSubs(s, meal)}
									class="grid h-9 w-9 shrink-0 place-items-center rounded-xl border-2 border-slate-200 text-slate-500 active:bg-slate-100 disabled:opacity-50"
								>
									<svg viewBox="0 0 24 24" class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 4v6h6M20 20v-6h-6M20 8a8 8 0 00-14-3M4 16a8 8 0 0014 3" stroke-linecap="round" stroke-linejoin="round" /></svg>
								</button>
								<button
									type="button"
									disabled={addBusy}
									onclick={() => addSuggestion(s, meal)}
									class="shrink-0 rounded-xl bg-emerald-600 px-3 py-1.5 text-sm font-bold text-white active:bg-emerald-700 disabled:opacity-50"
								>
									+ {m.reco_add()}
								</button>
							</div>
						{/each}
						{#each plan.recipe_suggestions as rs (rs.slug)}
							{@render recipeSuggestionCard(rs, meal)}
						{/each}
					</div>
				{/if}

				{#if confirmingRemoveMeal === meal}
					<!-- remover o card adicionado por engano: sempre com confirmacao -->
					<div class="mt-2 flex items-center gap-2 rounded-2xl bg-red-50 p-2">
						<span class="min-w-0 flex-1 pl-2 text-sm font-semibold text-red-700">{m.meal_remove_confirm()}</span>
						<button
							type="button"
							onclick={() => removeMealCard(meal)}
							class="h-10 shrink-0 rounded-xl bg-red-600 px-4 text-sm font-bold text-white active:bg-red-700"
						>
							{m.confirm_delete()}
						</button>
						<button
							type="button"
							onclick={() => (confirmingRemoveMeal = null)}
							class="h-10 shrink-0 rounded-xl px-3 text-sm font-semibold text-slate-500 active:bg-slate-100"
						>
							{m.cancel()}
						</button>
					</div>
				{:else}
					<div class="mt-2 flex gap-2">
						<button
							type="button"
							onclick={() => (addingToMeal = meal)}
							class="flex h-11 flex-1 items-center justify-center rounded-2xl border-2 border-dashed border-emerald-200 text-sm font-bold text-emerald-700 active:bg-emerald-50"
						>
							+ {m.add_food()}
						</button>
						{#if !group || group.entries.length === 0}
							<button
								type="button"
								aria-label={m.repeat_meal()}
								title={m.repeat_meal()}
								onclick={() => repeatMeal(meal)}
								class="grid h-11 w-11 shrink-0 place-items-center rounded-2xl border-2 border-slate-200 text-slate-500 active:bg-slate-100"
							>
								<svg viewBox="0 0 24 24" class="h-5 w-5" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 4v6h6M20 20v-6h-6M20 8a8 8 0 00-14-3M4 16a8 8 0 0014 3" stroke-linecap="round" stroke-linejoin="round" /></svg>
							</button>
							{#if dayMeals.added.includes(meal)}
								<button
									type="button"
									aria-label={m.meal_remove()}
									title={m.meal_remove()}
									onclick={() => (confirmingRemoveMeal = meal)}
									class="grid h-11 w-11 shrink-0 place-items-center rounded-2xl border-2 border-slate-200 text-slate-400 active:bg-red-50 active:text-red-500"
								>
									<svg viewBox="0 0 24 24" class="h-5 w-5" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 7h16M9 7V5h6v2M6 7l1 13h10l1-13" stroke-linecap="round" stroke-linejoin="round" /></svg>
								</button>
							{/if}
						{/if}
					</div>
				{/if}
				</div>
				{/if}
			</section>
		{/each}
	</div>

	{#if supplements && supplements.total > 0}
		<section class="mt-4 rounded-3xl bg-white p-4 shadow-sm">
			<div class="mb-3 flex items-center justify-between gap-2">
				<div>
					<h2 class="font-bold text-slate-900">{m.supplements_title()}</h2>
					<p class="text-xs text-slate-500">
						{supplements.taken_count}/{supplements.total} {m.supp_taken_label()}
					</p>
				</div>
				<button
					type="button"
					onclick={openSupplementManager}
					aria-label={m.supp_manage()}
					class="grid h-9 w-9 shrink-0 place-items-center rounded-xl border-2 border-slate-200 text-slate-500 active:bg-slate-100"
				>
					<svg viewBox="0 0 24 24" class="h-5 w-5" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 20h9M16.5 3.5a2.1 2.1 0 013 3L7 19l-4 1 1-4z" stroke-linecap="round" stroke-linejoin="round" /></svg>
				</button>
			</div>
			<div class="space-y-2">
				{#each supplements.items as s (s.id)}
					<button
						type="button"
						onclick={() => toggleSupplement(s)}
						disabled={supplementBusy}
						class="flex w-full items-center gap-3 rounded-2xl px-3 py-2 text-left transition-colors {s.taken
							? 'bg-emerald-50'
							: 'bg-slate-50'}"
					>
						<span
							class="grid h-8 w-8 shrink-0 place-items-center rounded-lg border-2 {s.taken
								? 'border-emerald-600 bg-emerald-600 text-white'
								: 'border-slate-300 text-transparent'}"
						>
							<svg viewBox="0 0 24 24" class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><path d="M5 13l4 4L19 7" /></svg>
						</span>
						<span class="min-w-0 flex-1 truncate font-semibold {s.taken ? 'text-emerald-900' : 'text-slate-800'}">
							{s.name}{#if s.dose}<span class="font-normal text-slate-500"> · {s.dose}</span>{/if}
						</span>
						<span class="shrink-0 text-xs font-semibold text-slate-400">{s.taken_last_7}/7</span>
					</button>
				{/each}
			</div>
		</section>
	{:else if !loading}
		<section class="mt-4 rounded-3xl bg-white p-4 shadow-sm">
			<h2 class="font-bold text-slate-900">{m.supplements_title()}</h2>
			<p class="mt-1 text-xs text-slate-500">{m.supp_empty_hint()}</p>
			<button
				type="button"
				onclick={openSupplementManager}
				class="mt-3 flex h-12 w-full items-center justify-center gap-2 rounded-2xl border-2 border-dashed border-slate-200 font-semibold text-slate-500 active:bg-slate-50"
			>
				<svg viewBox="0 0 24 24" class="h-5 w-5" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 5v14M5 12h14" stroke-linecap="round" /></svg>
				{m.supp_add_first()}
			</button>
		</section>
	{/if}

	{#if isEmpty}
		<button
			type="button"
			onclick={repeatPrevious}
			class="mt-4 flex h-12 w-full items-center justify-center rounded-2xl border-2 border-slate-200 bg-white font-semibold text-slate-700 active:bg-slate-100"
		>
			{m.repeat_previous_day()}
		</button>
	{/if}

	<a
		href="/dieta/receitas"
		class="mt-3 flex h-12 w-full items-center justify-center rounded-2xl border-2 border-slate-200 bg-white font-semibold text-slate-700 active:bg-slate-100"
	>
		{m.my_recipes()}
	</a>
{/if}

{#if editing}
	<div
		class="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
		role="button"
		tabindex="-1"
		onclick={() => (editing = null)}
		onkeydown={(e) => e.key === 'Escape' && (editing = null)}
	>
		<div
			class="w-full max-w-md rounded-3xl bg-white p-5"
			role="dialog"
			tabindex="-1"
			onclick={(e) => e.stopPropagation()}
			onkeydown={() => {}}
		>
			<h2 class="text-lg font-bold text-slate-900">{editing.name}</h2>

			{#if subs}
				<!-- Substituir: equivalentes da mesma categoria, macro-ancora igualado -->
				<p class="mt-1 mb-3 text-sm text-slate-500">{m.sub_title()}</p>
				{#if subs.items.length === 0}
					<p class="rounded-xl bg-slate-50 px-4 py-3 text-sm text-slate-500">{m.sub_none()}</p>
				{:else}
					<div class="space-y-2">
						{#each subs.items as item (item.food.id)}
							<div class="flex items-center gap-2 rounded-2xl bg-slate-50 px-3 py-2">
								<div class="min-w-0 flex-1">
									<p class="truncate text-sm font-semibold text-slate-800">{item.food.name}</p>
									<p class="text-xs text-slate-500">
										{nf.format(item.grams)} g · {nf.format(Math.round(item.macros.kcal))} kcal ·
										<span class={item.kcal_delta > 0 ? 'text-amber-600' : 'text-emerald-600'}>
											{deltaLabel(item.kcal_delta)}
										</span>
									</p>
								</div>
								<button
									type="button"
									disabled={swapBusy}
									onclick={() => applySwap(item)}
									class="shrink-0 rounded-xl bg-emerald-600 px-3 py-2 text-sm font-bold text-white active:bg-emerald-700 disabled:opacity-50"
								>
									{m.sub_swap()}
								</button>
							</div>
						{/each}
					</div>
				{/if}
				<button
					type="button"
					onclick={() => (subs = null)}
					class="mt-4 h-12 w-full rounded-2xl border-2 border-slate-200 font-semibold text-slate-700 active:bg-slate-100"
				>
					{m.back()}
				</button>
			{:else}
				<p class="mb-4 text-sm text-slate-500">{editPreview} kcal</p>
				{#if editing.source === 'recipe'}
					<Stepper bind:value={editQty} min={1} max={20} step={1} unit={m.serving_plural()} />
				{:else}
					<Stepper bind:value={editQty} min={1} max={2000} step={5} unit="g" />
				{/if}

				{#if confirmingDeleteEntry}
					<p class="mt-5 rounded-xl bg-red-50 px-4 py-3 text-sm font-medium text-red-700">
						{m.confirm_delete()}
					</p>
					<div class="mt-2 flex gap-2">
						<button
							type="button"
							onclick={() => (confirmingDeleteEntry = false)}
							class="h-12 flex-1 rounded-2xl border-2 border-slate-200 font-semibold text-slate-700 active:bg-slate-100"
						>
							{m.cancel()}
						</button>
						<button
							type="button"
							disabled={editBusy}
							onclick={deleteEditing}
							class="h-12 flex-1 rounded-2xl bg-red-600 font-semibold text-white active:bg-red-700 disabled:opacity-50"
						>
							{m.delete_confirm_button()}
						</button>
					</div>
				{:else}
					{#if editing.source === 'food'}
						<button
							type="button"
							disabled={loadingSubs}
							onclick={openSubstitutes}
							class="mt-5 flex h-12 w-full items-center justify-center gap-2 rounded-2xl border-2 border-emerald-200 font-semibold text-emerald-700 active:bg-emerald-50 disabled:opacity-50"
						>
							{#if loadingSubs}<Spinner class="h-4 w-4" />{/if}
							{m.sub_action()}
						</button>
					{/if}
					<div class="mt-2 flex gap-2">
						<button
							type="button"
							disabled={editBusy}
							onclick={() => (confirmingDeleteEntry = true)}
							class="h-12 flex-1 rounded-2xl border-2 border-red-200 font-semibold text-red-600 active:bg-red-50 disabled:opacity-50"
						>
							{m.remove()}
						</button>
						<button
							type="button"
							disabled={editBusy}
							onclick={saveEdit}
							class="h-12 flex-[2] rounded-2xl bg-emerald-600 font-bold text-white active:bg-emerald-700 disabled:opacity-50"
						>
							{m.save()}
						</button>
					</div>
				{/if}
			{/if}
		</div>
	</div>
{/if}

<!-- Equivalentes de uma sugestao da nutri -->
{#if suggSubs}
	<div
		class="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
		role="button"
		tabindex="-1"
		onclick={() => (suggSubs = null)}
		onkeydown={(e) => e.key === 'Escape' && (suggSubs = null)}
	>
		<div
			class="w-full max-w-md rounded-3xl bg-white p-5"
			role="dialog"
			tabindex="-1"
			onclick={(e) => e.stopPropagation()}
			onkeydown={() => {}}
		>
			<h2 class="text-lg font-bold text-slate-900">{m.sub_title()}</h2>
			<p class="mt-1 mb-3 text-sm text-slate-500">{suggSubs.source.food.name}</p>
			{#if suggSubs.items.length === 0}
				<p class="rounded-xl bg-slate-50 px-4 py-3 text-sm text-slate-500">{m.sub_none()}</p>
			{:else}
				<div class="space-y-2">
					{#each suggSubs.items as item (item.food.id)}
						<div class="flex items-center gap-2 rounded-2xl bg-slate-50 px-3 py-2">
							<div class="min-w-0 flex-1">
								<p class="truncate text-sm font-semibold text-slate-800">{item.food.name}</p>
								<p class="text-xs text-slate-500">
									{nf.format(item.grams)} g · {nf.format(Math.round(item.macros.kcal))} kcal ·
									<span class={item.kcal_delta > 0 ? 'text-amber-600' : 'text-emerald-600'}>
										{deltaLabel(item.kcal_delta)}
									</span>
								</p>
							</div>
							<button
								type="button"
								disabled={addBusy}
								onclick={() => addSubstitute(item)}
								class="shrink-0 rounded-xl bg-emerald-600 px-3 py-2 text-sm font-bold text-white active:bg-emerald-700 disabled:opacity-50"
							>
								+ {m.reco_add()}
							</button>
						</div>
					{/each}
				</div>
			{/if}
			<button
				type="button"
				onclick={() => (suggSubs = null)}
				class="mt-4 h-12 w-full rounded-2xl border-2 border-slate-200 font-semibold text-slate-700 active:bg-slate-100"
			>
				{m.back()}
			</button>
		</div>
	</div>
{/if}

<!-- Gerenciar suplementos: adicionar, editar e remover (a marcacao diaria e no card) -->
<!-- Detalhes do periodo da dieta: datas, objetivo e renovacao (adotar manutencao medida) -->
{#if showPeriodModal && dietPeriod}
	<div
		class="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
		role="button"
		tabindex="-1"
		onclick={() => (showPeriodModal = false)}
		onkeydown={(e) => e.key === 'Escape' && (showPeriodModal = false)}
	>
		<div
			class="w-full max-w-md rounded-3xl bg-white p-5"
			role="dialog"
			tabindex="-1"
			onclick={(e) => e.stopPropagation()}
			onkeydown={() => {}}
		>
			<div class="mb-4 flex items-start justify-between gap-2">
				<div class="min-w-0">
					<p class="text-xs font-bold uppercase tracking-wide text-slate-400">{m.diet_period_title()}</p>
					<h2 class="truncate text-lg font-bold text-slate-900">{objectiveLabel(dietPeriod.objective)}</h2>
				</div>
				<button
					type="button"
					aria-label={m.close()}
					onclick={() => (showPeriodModal = false)}
					class="grid h-9 w-9 shrink-0 place-items-center rounded-full bg-slate-100 text-slate-500 active:bg-slate-200"
				>
					<svg viewBox="0 0 24 24" class="h-5 w-5" fill="none" stroke="currentColor" stroke-width="2"><path d="M6 6l12 12M18 6L6 18" stroke-linecap="round" /></svg>
				</button>
			</div>

			<div class="grid grid-cols-2 gap-3">
				<div class="rounded-2xl bg-slate-50 p-3">
					<p class="text-xs font-semibold text-slate-500">{m.diet_period_started()}</p>
					<p class="mt-0.5 font-bold text-slate-900">{fmtPeriodDate(dietPeriod.started_on)}</p>
				</div>
				<div class="rounded-2xl p-3 {dietPeriod.due ? 'bg-amber-50' : 'bg-slate-50'}">
					<p class="text-xs font-semibold {dietPeriod.due ? 'text-amber-600' : 'text-slate-500'}">
						{m.diet_period_valid()}
					</p>
					<p class="mt-0.5 font-bold {dietPeriod.due ? 'text-amber-700' : 'text-slate-900'}">
						{fmtPeriodDate(dietPeriod.review_on)}
					</p>
				</div>
			</div>

			<div class="mt-3 flex items-center justify-between rounded-2xl bg-slate-50 px-3 py-2.5">
				<span class="text-sm font-semibold text-slate-500">{m.diet_period_target()}</span>
				<span class="font-bold text-slate-900">
					{nf.format(dietPeriod.target_kcal)} kcal
					{#if dietPeriod.maintenance_kcal}<span class="text-xs font-normal text-emerald-600"> · {m.diet_period_adopted()}</span>{/if}
				</span>
			</div>

			{#if periodAdaptive && periodAdaptive.has_enough_data && periodAdaptive.estimated_maintenance_kcal}
				<div class="mt-4 rounded-2xl border border-emerald-100 bg-emerald-50 p-3">
					<p class="text-sm font-semibold text-emerald-800">
						{m.diet_period_measured({ kcal: nf.format(periodAdaptive.estimated_maintenance_kcal) })}
					</p>
					<button
						type="button"
						disabled={periodBusy}
						onclick={() => renewPeriod(true)}
						class="mt-2 flex h-11 w-full items-center justify-center gap-2 rounded-2xl bg-emerald-600 font-bold text-white active:bg-emerald-700 disabled:opacity-50"
					>
						{#if periodBusy}<Spinner class="h-5 w-5" />{/if}
						{m.diet_period_renew_adopt()}
					</button>
				</div>
			{/if}

			<button
				type="button"
				disabled={periodBusy}
				onclick={() => renewPeriod(false)}
				class="mt-2 flex h-11 w-full items-center justify-center rounded-2xl border-2 border-slate-200 font-semibold text-slate-600 active:bg-slate-50 disabled:opacity-50"
			>
				{m.diet_period_renew_restart()}
			</button>
		</div>
	</div>
{/if}

{#if showSupplementManager}
	<div
		class="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
		role="button"
		tabindex="-1"
		onclick={() => (showSupplementManager = false)}
		onkeydown={(e) => e.key === 'Escape' && (showSupplementManager = false)}
	>
		<div
			class="w-full max-w-md rounded-3xl bg-white p-5"
			role="dialog"
			tabindex="-1"
			onclick={(e) => e.stopPropagation()}
			onkeydown={() => {}}
		>
			<div class="mb-4 flex items-center justify-between">
				<h2 class="text-lg font-bold text-slate-900">{m.supplements_title()}</h2>
				<button
					type="button"
					onclick={() => (showSupplementManager = false)}
					aria-label={m.close()}
					class="grid h-9 w-9 place-items-center rounded-full bg-slate-100 text-slate-500 active:bg-slate-200"
				>
					<svg viewBox="0 0 24 24" class="h-5 w-5" fill="none" stroke="currentColor" stroke-width="2"><path d="M6 6l12 12M18 6L6 18" stroke-linecap="round" /></svg>
				</button>
			</div>

			<div class="space-y-2">
				<input
					bind:value={suppName}
					placeholder={m.supp_name_placeholder()}
					maxlength="60"
					class="h-12 w-full rounded-2xl border-2 border-slate-200 px-4 text-base outline-none focus:border-emerald-600"
				/>
				<div class="flex gap-2">
					<input
						bind:value={suppDose}
						placeholder={m.supp_dose_placeholder()}
						maxlength="40"
						class="h-12 min-w-0 flex-1 rounded-2xl border-2 border-slate-200 px-4 text-base outline-none focus:border-emerald-600"
					/>
					<button
						type="button"
						onclick={saveSupplement}
						disabled={!suppName.trim() || suppFormBusy}
						class="flex h-12 shrink-0 items-center gap-2 rounded-2xl bg-emerald-600 px-5 font-bold text-white active:bg-emerald-700 disabled:opacity-50"
					>
						{#if suppFormBusy}<Spinner class="h-5 w-5" />{/if}
						{suppEditingId !== null ? m.save() : m.supp_add()}
					</button>
				</div>
				{#if suppEditingId !== null}
					<button
						type="button"
						onclick={() => {
							suppEditingId = null;
							suppName = '';
							suppDose = '';
						}}
						class="text-sm font-semibold text-slate-500">{m.cancel()}</button
					>
				{/if}
			</div>

			{#if supplements && supplements.items.length > 0}
				<div class="mt-4 space-y-2">
					{#each supplements.items as s (s.id)}
						<div class="flex items-center gap-2 rounded-2xl bg-slate-50 px-3 py-2">
							<div class="min-w-0 flex-1">
								<p class="truncate text-sm font-semibold text-slate-800">{s.name}</p>
								{#if s.dose}<p class="text-xs text-slate-500">{s.dose}</p>{/if}
							</div>
							{#if confirmingDeleteSupp === s.id}
								<button
									type="button"
									onclick={() => removeSupplement(s.id)}
									class="rounded-xl bg-red-600 px-3 py-1.5 text-xs font-bold text-white active:bg-red-700"
									>{m.confirm_delete()}</button
								>
								<button
									type="button"
									onclick={() => (confirmingDeleteSupp = null)}
									class="rounded-xl px-2 py-1.5 text-xs font-semibold text-slate-500">{m.cancel()}</button
								>
							{:else}
								<button
									type="button"
									onclick={() => editSupplement(s)}
									aria-label={m.edit()}
									class="grid h-8 w-8 place-items-center rounded-lg text-slate-400 active:bg-slate-100"
								>
									<svg viewBox="0 0 24 24" class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 20h9M16.5 3.5a2.1 2.1 0 013 3L7 19l-4 1 1-4z" stroke-linecap="round" stroke-linejoin="round" /></svg>
								</button>
								<button
									type="button"
									onclick={() => (confirmingDeleteSupp = s.id)}
									aria-label={m.confirm_delete()}
									class="grid h-8 w-8 place-items-center rounded-lg text-slate-400 active:bg-slate-100"
								>
									<svg viewBox="0 0 24 24" class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 7h16M9 7V5h6v2M6 7l1 13h10l1-13" stroke-linecap="round" stroke-linejoin="round" /></svg>
								</button>
							{/if}
						</div>
					{/each}
				</div>
			{/if}
		</div>
	</div>
{/if}

<!-- Calendario: navegar dias; dias com lancamento ficam marcados -->
{#if showCalendar}
	<CalendarModal
		value={day}
		marked={loggedDays}
		max={today}
		onmonth={loadMonthMarks}
		onselect={(d) => (day = d)}
		onclose={() => (showCalendar = false)}
	/>
{/if}

<!-- Adicionar alimento/receita sem sair da tela: modal que fica aberta para varios itens -->
{#if addingToMeal}
	<AddEntryModal
		meal={addingToMeal}
		{day}
		label={mealDisplayLabel(addingToMeal)}
		onClose={() => (addingToMeal = null)}
		onAdded={reloadSilent}
	/>
{/if}

<!-- Visualizar a receita sugerida antes de incluir (read-only) -->
{#if viewOpen}
	<RecipeViewModal
		recipe={viewRecipe}
		loading={viewLoading}
		onClose={closeRecipeView}
		actionLabel={m.add_to_meal()}
		onAction={addFromView}
		actionBusy={addBusy}
	/>
{/if}
