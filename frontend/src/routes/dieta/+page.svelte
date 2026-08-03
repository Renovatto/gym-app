<script lang="ts">
	import {
		api,
		localDay,
		type CyclePhase,
		type CycleStatus,
		type DiaryDay,
		type DiaryEntry,
		type DiaryGap,
		type FoodSuggestion,
		type MealPlan,
		type MealPlanMeal,
		type MealType,
		type Recipe,
		type RecipeSuggestion,
		type RecipeView,
		type SubstituteItem,
		type Substitutes,
		type Supplement,
		type SupplementsDay,
		type DietPeriod,
		type AdaptiveTdee
	} from '$lib/api';
	import CycleConfig from '$lib/components/CycleConfig.svelte';
	import MacroSummary from '$lib/components/MacroSummary.svelte';
	import Stepper from '$lib/components/Stepper.svelte';
	import Spinner from '$lib/components/Spinner.svelte';
	import CalendarModal from '$lib/components/CalendarModal.svelte';
	import AddEntryModal from '$lib/components/AddEntryModal.svelte';
	import BuildMealModal from '$lib/components/BuildMealModal.svelte';
	import RecipeViewModal from '$lib/components/RecipeViewModal.svelte';
	import MacroBreakdown from '$lib/components/MacroBreakdown.svelte';
	import { slide } from 'svelte/transition';
	import { showToast } from '$lib/toast.svelte';
	import { mealTypeLabel } from '$lib/labels';
	import SkeletonScreen from '$lib/components/SkeletonScreen.svelte';
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
	// qual renovacao esta pedindo confirmacao (nenhuma delas dispara direto no clique)
	let confirmingRenew = $state<'adopt' | 'restart' | null>(null);
	const pdf = new Intl.DateTimeFormat(getLocale(), { day: '2-digit', month: 'short' });
	function fmtPeriodDate(iso: string): string {
		return pdf.format(new Date(iso + 'T12:00:00'));
	}
	function closePeriodModal(): void {
		showPeriodModal = false;
		confirmingRenew = null;
	}
	function objectiveLabel(obj: string): string {
		if (obj === 'gain_muscle') return m.objective_gain_muscle();
		if (obj === 'lose_fat') return m.objective_lose_fat();
		if (obj === 'recomp') return m.objective_recomp();
		return m.objective_maintain();
	}
	function openPeriodModal(): void {
		// periodAdaptive ja vem fresco do reloadSilent (mesma origem do badge do card)
		showPeriodModal = true;
	}

	// Meta sugerida difere da atual -> tem informacao nova do TDEE adaptativo para ver.
	// Exige can_adopt: sem isso o badge levaria a pessoa a abrir a modal e nao achar botao.
	const hasNewSuggestion = $derived(
		!!periodAdaptive?.has_enough_data &&
			periodAdaptive.can_adopt &&
			periodAdaptive.suggested_target_kcal !== null &&
			periodAdaptive.suggested_target_kcal !== periodAdaptive.current_target_kcal
	);
	async function renewPeriod(adopt: boolean): Promise<void> {
		if (periodBusy) return;
		confirmingRenew = null;
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

	// Edicao de receita em GRAMAS: a modal de adicionar ja oferece as duas unidades,
	// mas a de editar so oferecia porcoes - entao quem lancava em gramas nao
	// conseguia mais mexer na mesma unidade que usou. A conversao precisa do peso
	// de uma porcao, que so a receita tem; buscamos a lista uma vez e guardamos.
	let recipesCache: Recipe[] | null = null;
	let editQtyMode = $state<'servings' | 'grams'>('servings');
	let editGrams = $state(0);
	let editGramsPerServing = $state(0);

	// quantidade que vai para a API: sempre em PORCOES, porque e assim que o
	// lancamento de receita e guardado. Em modo gramas convertemos na hora.
	const editEffectiveQty = $derived(
		editQtyMode === 'grams' && editGramsPerServing > 0
			? editGrams / editGramsPerServing
			: editQty
	);

	async function loadRecipeScale(recipeId: number): Promise<void> {
		if (recipesCache === null) recipesCache = await api.getRecipes();
		const recipe = recipesCache.find((r) => r.id === recipeId);
		if (!recipe || recipe.servings <= 0) return;
		const totalG = recipe.ingredients.reduce((sum, i) => sum + i.grams, 0);
		editGramsPerServing = totalG / recipe.servings;
	}

	function openEdit(entry: DiaryEntry): void {
		editing = entry;
		editQty = entry.quantity;
		editQtyMode = 'servings';
		editGrams = 0;
		editGramsPerServing = 0;
		confirmingDeleteEntry = false;
		subs = null;
		if (entry.source === 'recipe' && entry.recipe_id !== null) {
			void loadRecipeScale(entry.recipe_id).then(() => {
				if (editGramsPerServing <= 0) return;
				editGrams = Math.round(entry.quantity * editGramsPerServing);
				// Quantidade quebrada so aparece quando o lancamento foi feito em GRAMAS
				// (300 g viram 1,0344... porcoes). Abrir em porcoes nesse caso mostraria
				// a fracao crua e obrigaria a pessoa a converter de cabeca - abrimos na
				// unidade que ela realmente usou.
				if (Math.abs(entry.quantity - Math.round(entry.quantity)) > 0.001) {
					editQtyMode = 'grams';
				}
			});
		}
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
			await api.updateDiaryEntry(editing.id, editEffectiveQty);
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
			? Math.round((editing.macros.kcal / editing.quantity) * editEffectiveQty)
			: 0
	);
	const editPreviewMacros = $derived.by(() => {
		const factor =
			editing && editing.quantity > 0 ? editEffectiveQty / editing.quantity : 0;
		return {
			protein_g: (editing?.macros.protein_g ?? 0) * factor,
			carbs_g: (editing?.macros.carbs_g ?? 0) * factor,
			fat_g: (editing?.macros.fat_g ?? 0) * factor
		};
	});

	// Como a quantidade de um lancamento aparece na lista.
	function entryQuantityLabel(entry: DiaryEntry): string {
		const servings = entry.source === 'recipe' ? entry.quantity : null;
		// porcao redonda vira contexto; quebrada e so o resto de um lancamento feito
		// em gramas e nao ajuda ninguem a entender o prato
		const roundServings =
			servings !== null && Math.abs(servings - Math.round(servings)) < 0.01
				? Math.round(servings)
				: null;
		if (entry.grams === null) {
			// receita sem como converter (foi excluida): resta a porcao
			if (servings === null) return '';
			const unit = servings === 1 ? m.serving_singular() : m.serving_plural();
			return `${nf.format(servings)} ${unit}`;
		}
		const grams = `${nf.format(Math.round(entry.grams))} g`;
		if (roundServings === null) return grams;
		const unit = roundServings === 1 ? m.serving_singular() : m.serving_plural();
		return `${grams} (${nf.format(roundServings)} ${unit})`;
	}

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
			api.getDiaryGap(day, 4, mealByTime()),
			api.getMealPlan(day),
			api.getSupplements(day),
			api.getDietPeriod(day)
		]);
		try {
			// alimenta o badge de "nova sugestao" do card de Periodo da dieta
			periodAdaptive = await api.getAdaptiveTdee(day, new Date().getTimezoneOffset());
		} catch {
			// extra: sem dados suficientes ainda, o card fica sem badge
		}
		try {
			// fase resolvida para o DIA EXIBIDO (ontem mostra a fase de ontem)
			cycle = await api.getCycle(day);
			maybePlayAura();
		} catch {
			// acompanhamento indisponivel: a tela vive sem o card
		}
	}

	async function load(): Promise<void> {
		loading = true;
		await reloadSilent();
		loading = false;
	}

	// --- Ciclo menstrual (opt-in): card + aura ------------------------------
	let cycle = $state<CycleStatus | null>(null);
	let cycleModal = $state(false);
	// A aura "acende e assenta": percorre a borda da tela ao abrir a Dieta e se
	// recolhe para a borda do card. Uma vez por dia por sessao - efeito especial
	// que roda a cada toque de aba viraria papel de parede.
	let auraPlaying = $state(false);
	const AURA_KEY = 'gymapp.diet.cycleAuraDay';

	function maybePlayAura(): void {
		if (!cycle?.enabled || !cycle.phase || day !== today) return;
		// na fase menstrual a moldura ja fica permanente: um pulso por cima seria
		// o mesmo efeito duas vezes
		if (cycle.phase === 'menstrual') return;
		try {
			if (sessionStorage.getItem(AURA_KEY) === today) return;
			sessionStorage.setItem(AURA_KEY, today);
		} catch {
			// sessionStorage bloqueado: toca mesmo assim
		}
		auraPlaying = true;
		setTimeout(() => (auraPlaying = false), 2600);
	}

	// A aura de tela inteira PERMANENTE fica so na fase menstrual - decisao do usuario,
	// que a imagina como a fase mais critica. Nas outras fases continua o pulso de 2,6 s
	// ao abrir (maybePlayAura). Fora de hoje nao acende: a moldura fala do agora.
	const auraPermanent = $derived(
		!!cycle?.enabled && cycle.phase === 'menstrual' && day === today
	);

	function cyclePhaseLabel(phase: CyclePhase): string {
		return {
			menstrual: m.cycle_phase_menstrual(),
			follicular: m.cycle_phase_follicular(),
			ovulatory: m.cycle_phase_ovulatory(),
			luteal: m.cycle_phase_luteal()
		}[phase];
	}

	function cycleFocusLabel(phase: CyclePhase): string {
		return {
			menstrual: m.cycle_focus_menstrual(),
			follicular: m.cycle_focus_follicular(),
			ovulatory: m.cycle_focus_ovulatory(),
			luteal: m.cycle_focus_luteal()
		}[phase];
	}

	// Modal de adicionar alimento/receita (fica aberta para lancar varios itens).
	let addingToMeal = $state<MealType | null>(null);
	let showBuildMeal = $state(false);

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

	// Repetir o dia anterior copia varios lancamentos de uma vez: sempre confirma antes.
	let confirmingRepeatDay = $state(false);
	let confirmingRepeatMeal = $state<MealType | null>(null);

	async function repeatPrevious(): Promise<void> {
		confirmingRepeatDay = false;
		await api.copyPreviousDay(day, shiftDay(day, -1));
		await load();
		showToast(m.day_copied());
	}

	async function repeatMeal(meal: MealType): Promise<void> {
		confirmingRepeatMeal = null;
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
	const EXTRA_MEALS: MealType[] = ['snack', 'pre_workout', 'post_workout', 'supper', 'other'];
	// Ordem em que os cards aparecem. E preferencia GERAL da pessoa (vale para todos
	// os dias), nao estado do dia: quem lanca o jantar antes do lanche quer essa
	// ordem amanha tambem. Comeca na sequencia cronologica classica.
	const DEFAULT_MEAL_ORDER: MealType[] = [
		'breakfast', 'pre_workout', 'post_workout', 'lunch', 'snack', 'dinner', 'supper', 'other'
	];
	const MEAL_ORDER_KEY = 'gymapp.diet.mealOrder';
	const DAY_STATE_KEY = 'gymapp.diet.dayMeals';
	const CUSTOM_HISTORY_KEY = 'gymapp.diet.customMealNames';

	// Icone por refeicao: os principais usam metafora de horario (nascer do sol,
	// talher, lua) e os extras usam o objeto (halter, maca, caneca).
	const MEAL_ICON_PATHS: Record<MealType, string> = {
		breakfast: 'M12 2v3M4.9 7.9l2.1 2.1M19.1 7.9l-2.1 2.1M2 18h20M6.5 18a5.5 5.5 0 0 1 11 0',
		pre_workout: 'M6.5 7v10M17.5 7v10M3.5 9.5v5M20.5 9.5v5M6.5 12h11',
		post_workout: 'M9 2.5h6v3H9zM9.5 5.5h5l1 13a2.5 2.5 0 0 1-2.5 2.5h-2a2.5 2.5 0 0 1-2.5-2.5zM9.2 12h6.1',
		lunch: 'M7 3v6a2 2 0 1 0 4 0V3M9 11v10M17.5 3c-1.6 1.2-2.3 3-2.3 5.2 0 1.7.9 2.8 2.3 2.8v10',
		snack: 'M12 8.5c-1-1-2.8-1.6-4.4-.6C5.8 9 5.3 11.2 6.2 14c.9 2.8 2.4 5.5 3.8 5.5.8 0 1.2-.4 2-.4s1.2.4 2 .4c1.4 0 2.9-2.7 3.8-5.5.9-2.8.4-5-1.4-6.1-1.6-1-3.4-.4-4.4.6ZM12 8.5V5.5M12 5.5c0-1.4 1-2.5 2.5-2.5',
		dinner: 'M20 14.5A8.5 8.5 0 0 1 9.5 4a8.5 8.5 0 1 0 10.5 10.5Z',
		supper: 'M5 10h10v5a3 3 0 0 1-3 3H8a3 3 0 0 1-3-3v-5ZM15 12h1.5a2 2 0 0 1 0 4H15M8 3.5c0 1.5 1 1.5 1 3M12 3.5c0 1.5 1 1.5 1 3',
		other: 'M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18ZM12 8.5v7M8.5 12h7'
	};
	// Tom do icone acompanhando a hora do dia: manha ambar, tarde azul, noite indigo.
	const MEAL_ICON_TINTS: Record<MealType, string> = {
		breakfast: 'bg-amber-100 text-amber-600',
		pre_workout: 'bg-violet-100 text-violet-600',
		post_workout: 'bg-rose-100 text-rose-600',
		lunch: 'bg-sky-100 text-sky-600',
		snack: 'bg-lime-100 text-lime-600',
		dinner: 'bg-indigo-100 text-indigo-600',
		supper: 'bg-slate-200 text-slate-500',
		other: 'bg-emerald-100 text-emerald-600'
	};

	// Le a preferencia salva tolerando versao antiga ou corrompida: mantem so os
	// tipos conhecidos e completa no fim os que faltarem.
	function loadMealOrder(): MealType[] {
		try {
			const raw: unknown = JSON.parse(localStorage.getItem(MEAL_ORDER_KEY) ?? 'null');
			if (Array.isArray(raw)) {
				const known = raw.filter((meal): meal is MealType =>
					DEFAULT_MEAL_ORDER.includes(meal as MealType)
				);
				const missing = DEFAULT_MEAL_ORDER.filter((meal) => !known.includes(meal));
				if (known.length > 0) return [...known, ...missing];
			}
		} catch {
			// preferencia corrompida: volta para a ordem cronologica
		}
		return [...DEFAULT_MEAL_ORDER];
	}
	let mealOrder = $state<MealType[]>(loadMealOrder());

	function saveMealOrder(): void {
		localStorage.setItem(MEAL_ORDER_KEY, JSON.stringify($state.snapshot(mealOrder)));
	}

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
		mealOrder.filter((meal) => dayMeals.added.includes(meal) || mealHasEntries(meal))
	);
	const miniPrincipals = $derived(
		PRINCIPAL_MEALS.filter((meal) => !materializedMeals.includes(meal))
	);
	const chooserExtras = $derived(
		EXTRA_MEALS.filter((meal) => !materializedMeals.includes(meal))
	);

	function addMealCard(meal: MealType, customLabel: string | null = null): void {
		if (!dayMeals.added.includes(meal)) dayMeals.added = [...dayMeals.added, meal];
		// refeicao recem-adicionada vai para o fim da fila: a ordem na tela passa a
		// ser a ordem em que a pessoa lancou, e nao um enfileiramento fixo por horario.
		mealOrder = [...mealOrder.filter((mt) => mt !== meal), meal];
		saveMealOrder();
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

	// --- Arrastar para reordenar ---------------------------------------------
	// A lista nao se reorganiza durante o arrasto: so uma linha mostra onde o card
	// vai cair, e a troca acontece ao soltar. Assim as posicoes medidas no inicio
	// continuam validas ate o fim - se os cards se movessem junto, o alvo mudaria
	// de lugar debaixo do dedo.
	let mealCardEls = $state<Partial<Record<MealType, HTMLElement>>>({});
	let draggingMeal = $state<MealType | null>(null);
	let dropIndex = $state<number | null>(null);
	let dragMidpoints: number[] = [];

	function startMealDrag(meal: MealType, event: PointerEvent): void {
		const from = materializedMeals.indexOf(meal);
		if (from < 0) return;
		dragMidpoints = materializedMeals.map((mt) => {
			const el = mealCardEls[mt];
			if (!el) return Number.POSITIVE_INFINITY;
			const rect = el.getBoundingClientRect();
			return rect.top + rect.height / 2;
		});
		draggingMeal = meal;
		dropIndex = from;
		(event.currentTarget as HTMLElement).setPointerCapture(event.pointerId);
	}

	function moveMealDrag(event: PointerEvent): void {
		if (draggingMeal === null) return;
		event.preventDefault();
		// posicao de destino = quantos cards ficaram acima do dedo
		dropIndex = dragMidpoints.filter((mid) => mid < event.clientY).length;
	}

	function endMealDrag(): void {
		const meal = draggingMeal;
		const target = dropIndex;
		draggingMeal = null;
		dropIndex = null;
		if (meal === null || target === null) return;
		const from = materializedMeals.indexOf(meal);
		if (from < 0) return;
		const others = materializedMeals.filter((mt) => mt !== meal);
		// o indice medido ainda conta o proprio card arrastado; tirando-o da lista,
		// tudo que estava depois dele sobe uma posicao.
		const insertAt = target > from ? target - 1 : target;
		if (insertAt === from) return;
		const reordered = [...others.slice(0, insertAt), meal, ...others.slice(insertAt)];
		// as refeicoes ainda nao materializadas ficam na frente da preferencia: elas
		// vao para o fim no momento em que a pessoa adicionar o card.
		mealOrder = [...mealOrder.filter((mt) => !reordered.includes(mt)), ...reordered];
		saveMealOrder();
		showToast(m.meal_order_saved());
	}

	// Linha de destino: escondida quando o card cairia exatamente onde ja esta.
	function isDropTarget(index: number): boolean {
		if (draggingMeal === null || dropIndex === null) return false;
		const from = materializedMeals.indexOf(draggingMeal);
		if (dropIndex === from || dropIndex === from + 1) return false;
		return dropIndex === index;
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
	// Acordeao: a lista de sugestoes (alimentos/receitas) comeca oculta - o card mostra
	// so o resumo do que falta, sem lotar a tela; o toque no destaque abre a lista.
	let showGapSuggestions = $state(false);
	const gapSuggestionCount = $derived(
		gap ? gap.suggestions.length + gap.recipe_suggestions.length : 0
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
	<SkeletonScreen hero cards={4} cardLines={1} />
{:else if diary}
	<MacroSummary totals={diary.totals} goals={diary.goals} />

	<!-- Ciclo menstrual (opt-in): a borda gradiente e o "assentado" da aura que
		 percorre a tela ao abrir - o efeito escolhido no artefato (acende e assenta).
		 So existe com o acompanhamento ligado; a informacao nunca depende do efeito
		 (movimento reduzido desliga a animacao e fica a borda parada). -->
	{#if cycle?.enabled}
		<div class="cycle-card relative mt-3 rounded-2xl bg-white p-3.5 shadow-sm">
			{#if cycle.phase}
				<button
					type="button"
					onclick={() => (cycleModal = true)}
					class="absolute top-3 right-3.5 text-xs font-bold text-[#6658fe] active:opacity-70"
				>
					{m.cycle_adjust()}
				</button>
				<div class="flex items-baseline gap-2 pr-16">
					<p class="font-bold text-slate-900">{cyclePhaseLabel(cycle.phase)}</p>
					{#if cycle.day_in_cycle !== null}
						<span class="text-xs font-semibold text-slate-400">
							{m.cycle_day_label({ day: cycle.day_in_cycle })} · {m.cycle_estimated()}
						</span>
					{/if}
				</div>
				<p class="mt-0.5 text-xs text-slate-500">{cycleFocusLabel(cycle.phase)}</p>
				<!-- Alimentos DE VERDADE do catalogo, ja dimensionados para o que falta
					 do dia. O texto acima diz o porque; estas pilulas dizem o que comer,
					 e mudam quando a fase muda - que era o que faltava para a fase deixar
					 de ser enfeite. -->
				{#if cycle.suggestions.length > 0}
					<div class="mt-2 flex flex-wrap gap-1.5">
						{#each cycle.suggestions as s (s.food.id)}
							<span class="rounded-full bg-slate-100 px-2.5 py-1 text-[11px] font-semibold text-slate-600">
								{s.food.name} · {nf.format(Math.round(s.grams))} g
							</span>
						{/each}
					</div>
				{/if}
				{#if cycle.estimate_stale}
					<p class="mt-1.5 rounded-lg bg-amber-50 px-2 py-1 text-[11px] font-semibold text-amber-700">
						{m.cycle_stale_hint()}
					</p>
				{/if}
			{:else}
				<!-- ligado no perfil mas sem fase (ex.: religou sem configurar) -->
				<button
					type="button"
					onclick={() => (cycleModal = true)}
					class="flex w-full items-center justify-between text-left"
				>
					<span class="text-sm font-semibold text-slate-700">{m.cycle_configure()}</span>
					<svg viewBox="0 0 24 24" class="h-4 w-4 shrink-0 text-slate-300" fill="none" stroke="currentColor" stroke-width="2"><path d="M9 6l6 6-6 6" stroke-linecap="round" stroke-linejoin="round" /></svg>
				</button>
			{/if}
		</div>
	{/if}

	{#if dietPeriod}
		<button
			type="button"
			onclick={openPeriodModal}
			class="mt-3 flex w-full items-center gap-2.5 rounded-2xl border px-3 py-2.5 text-left {dietPeriod.due
				? 'border-amber-200 bg-amber-50'
				: hasNewSuggestion
					? 'border-emerald-200 bg-emerald-50'
					: 'border-slate-200 bg-white'}"
		>
			<svg viewBox="0 0 24 24" class="h-5 w-5 shrink-0 {dietPeriod.due ? 'text-amber-600' : hasNewSuggestion ? 'text-emerald-600' : 'text-slate-400'}" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="4" width="18" height="17" rx="2" /><path d="M3 9h18M8 2v4M16 2v4" stroke-linecap="round" /></svg>
			<span class="min-w-0 flex-1">
				<span class="block text-sm font-semibold {dietPeriod.due ? 'text-amber-800' : hasNewSuggestion ? 'text-emerald-800' : 'text-slate-700'}">
					{m.diet_period_label()}
				</span>
				<span class="block truncate text-xs {dietPeriod.due ? 'text-amber-600' : hasNewSuggestion ? 'text-emerald-600' : 'text-slate-500'}">
					{#if dietPeriod.due}
						{m.diet_period_due()}
					{:else if hasNewSuggestion}
						{m.diet_period_new_suggestion()}
					{:else}
						{m.diet_period_review({ date: fmtPeriodDate(dietPeriod.review_on) })}
					{/if}
					· {objectiveLabel(dietPeriod.objective)}
				</span>
			</span>
			{#if hasNewSuggestion}
				<span class="grid h-5 min-w-[20px] shrink-0 place-items-center rounded-full bg-emerald-600 px-1.5 text-xs font-bold text-white">1</span>
			{/if}
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
			<button
				type="button"
				onclick={() => (showGapSuggestions = !showGapSuggestions)}
				class="mt-3 flex w-full items-center justify-center gap-2 rounded-2xl bg-emerald-600 py-2.5 text-sm font-bold text-white shadow-sm active:bg-emerald-700"
			>
				{showGapSuggestions ? m.gap_suggestions_hide() : m.gap_suggestions_show({ n: gapSuggestionCount })}
				<svg viewBox="0 0 24 24" class="h-4 w-4 transition-transform {showGapSuggestions ? 'rotate-180' : ''}" fill="none" stroke="currentColor" stroke-width="2"><path d="M6 9l6 6 6-6" stroke-linecap="round" stroke-linejoin="round" /></svg>
			</button>
			{#if showGapSuggestions}
				<div class="mt-2 space-y-2">
					{#each gap.suggestions as s (s.food.id)}
						<div class="flex items-center gap-2 rounded-2xl bg-white px-3 py-2">
							<div class="min-w-0 flex-1">
								<p class="flex items-center gap-1 truncate text-sm font-semibold text-slate-800">
									{#if s.from_phase}
										<!-- recomendacao que muda sozinha, sem dizer por que, e magica -
											 e magica nao se confere. O selo mostra de onde veio. -->
										<span class="shrink-0 rounded-full bg-rose-50 px-2 py-0.5 text-[10px] font-bold text-rose-700">
											{m.cycle_badge()}
										</span>
									{/if}
									<span class="truncate">{s.food.name}</span>
								</p>
								<p class="text-xs text-slate-500">{suggestionHint(s)}</p>
							</div>
							<button
								type="button"
								aria-label={m.sub_action()}
								disabled={loadingSuggSubs}
								onclick={() => openSuggestionSubs(s, mealByTime())}
								class="grid h-9 w-9 shrink-0 place-items-center rounded-xl border-2 border-slate-200 text-slate-500 active:bg-slate-100 disabled:opacity-50"
							>
								<svg viewBox="0 0 24 24" class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M2 18h1.4c1.3 0 2.5-.6 3.3-1.7l6.1-8.6c.7-1.1 2-1.7 3.3-1.7H22" /><path d="m18 2 4 4-4 4" /><path d="M2 6h1.9c1.5 0 2.9.9 3.6 2.2" /><path d="M22 18h-5.9c-1.3 0-2.6-.7-3.3-1.8l-.5-.8" /><path d="m18 14 4 4-4 4" /></svg>
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
			{/if}
		</section>
	{/if}

	{#if gap && gap.primary !== 'no_goal' && gap.primary !== 'complete'}
		<button
			type="button"
			onclick={() => (showBuildMeal = true)}
			class="mt-3 flex w-full items-center justify-center gap-2 rounded-2xl border-2 border-dashed border-slate-300 bg-white py-3 text-sm font-bold text-slate-700 active:bg-slate-50"
		>
			<svg viewBox="0 0 24 24" class="h-4.5 w-4.5 text-slate-500" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 9h18l-1.5 10.5a2 2 0 0 1-2 1.5H6.5a2 2 0 0 1-2-1.5L3 9Z" /><path d="M8 9V6a4 4 0 0 1 8 0v3" /></svg>
			{m.pantry_cta()}
		</button>
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
					<span class="mx-auto grid h-8 w-8 place-items-center rounded-xl {MEAL_ICON_TINTS[meal]}">
						<svg viewBox="0 0 24 24" class="h-4.5 w-4.5" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d={MEAL_ICON_PATHS[meal]} /></svg>
					</span>
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
					<span class="mx-auto grid h-8 w-8 place-items-center rounded-xl bg-emerald-100 text-emerald-600">
						<svg viewBox="0 0 24 24" class="h-4.5 w-4.5" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d={MEAL_ICON_PATHS.other} /></svg>
					</span>
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
		{#each materializedMeals as meal, index (meal)}
			{@const group = mealGroup(meal)}
			{@const plan = mealPlanFor(meal)}
			{@const isOpen = openMeal === meal}
			{#if isDropTarget(index)}
				<div class="h-1 rounded-full bg-emerald-500"></div>
			{/if}
			<section
				bind:this={mealCardEls[meal]}
				class="overflow-hidden rounded-3xl bg-white shadow-sm transition-shadow {draggingMeal === meal
					? 'opacity-60 ring-2 ring-emerald-400'
					: ''}"
			>
				<!-- cabecalho: toca para minimizar/expandir (acordeao: um aberto por vez).
					 A alca a esquerda arrasta para reordenar e fica fora do botao. -->
				<div class="flex items-center pr-4">
					<div
						role="button"
						tabindex="-1"
						aria-label={m.meal_reorder()}
						title={m.meal_reorder()}
						onpointerdown={(e) => startMealDrag(meal, e)}
						onpointermove={moveMealDrag}
						onpointerup={endMealDrag}
						onpointercancel={endMealDrag}
						onkeydown={() => {}}
						class="grid h-12 w-8 shrink-0 cursor-grab touch-none place-items-center text-slate-300 active:text-emerald-600"
					>
						<svg viewBox="0 0 24 24" class="h-5 w-5" fill="currentColor"><circle cx="9" cy="6" r="1.5" /><circle cx="15" cy="6" r="1.5" /><circle cx="9" cy="12" r="1.5" /><circle cx="15" cy="12" r="1.5" /><circle cx="9" cy="18" r="1.5" /><circle cx="15" cy="18" r="1.5" /></svg>
					</div>
					<button
						type="button"
						onclick={() => toggleMealOpen(meal)}
						class="flex min-w-0 flex-1 items-center gap-2.5 py-4 pl-1 text-left"
					>
						<span class="grid h-9 w-9 shrink-0 place-items-center rounded-xl {MEAL_ICON_TINTS[meal]}">
							<svg viewBox="0 0 24 24" class="h-5 w-5" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d={MEAL_ICON_PATHS[meal]} /></svg>
						</span>
						<h2 class="min-w-0 flex-1 truncate font-bold text-slate-900">{mealDisplayLabel(meal)}</h2>
						<!-- kcal em cima e P/C/G embaixo (mesmo MacroBreakdown do resto do app):
							 da para conferir a refeicao sem precisar abrir o acordeao -->
						<span class="flex shrink-0 flex-col items-end">
							<span class="text-sm font-semibold text-slate-400">
								{group ? nf.format(Math.round(group.subtotal.kcal)) : 0} kcal
							</span>
							{#if group && group.entries.length > 0}
								<MacroBreakdown
									protein_g={group.subtotal.protein_g}
									carbs_g={group.subtotal.carbs_g}
									fat_g={group.subtotal.fat_g}
									class="text-[11px] text-slate-400"
								/>
							{/if}
						</span>
						<svg viewBox="0 0 24 24" class="h-5 w-5 shrink-0 text-slate-300 transition-transform {isOpen ? 'rotate-180' : ''}" fill="none" stroke="currentColor" stroke-width="2"><path d="M6 9l6 6 6-6" stroke-linecap="round" stroke-linejoin="round" /></svg>
					</button>
				</div>
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
										<!-- Grama e a unidade universal e comparavel, entao ela e o
											 numero. A porcao vira contexto entre parenteses, e so
											 quando o valor e redondo: "1,034 porcoes" e resto de
											 conversao, nao informacao. -->
										{entryQuantityLabel(entry)}
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
									<p class="flex items-center gap-1 truncate text-sm font-semibold text-slate-800">
									{#if s.from_phase}
										<!-- recomendacao que muda sozinha, sem dizer por que, e magica -
											 e magica nao se confere. O selo mostra de onde veio. -->
										<span class="shrink-0 rounded-full bg-rose-50 px-2 py-0.5 text-[10px] font-bold text-rose-700">
											{m.cycle_badge()}
										</span>
									{/if}
									<span class="truncate">{s.food.name}</span>
								</p>
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
									<svg viewBox="0 0 24 24" class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M2 18h1.4c1.3 0 2.5-.6 3.3-1.7l6.1-8.6c.7-1.1 2-1.7 3.3-1.7H22" /><path d="m18 2 4 4-4 4" /><path d="M2 6h1.9c1.5 0 2.9.9 3.6 2.2" /><path d="M22 18h-5.9c-1.3 0-2.6-.7-3.3-1.8l-.5-.8" /><path d="m18 14 4 4-4 4" /></svg>
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
				{:else if confirmingRepeatMeal === meal}
					<!-- repetir esta refeicao do dia anterior: confirma antes -->
					<div class="mt-2 flex items-center gap-2 rounded-2xl bg-emerald-50 p-2">
						<span class="min-w-0 flex-1 pl-2 text-sm font-semibold text-emerald-800">{m.repeat_meal_confirm()}</span>
						<button
							type="button"
							onclick={() => repeatMeal(meal)}
							class="h-10 shrink-0 rounded-xl bg-emerald-600 px-4 text-sm font-bold text-white active:bg-emerald-700"
						>
							{m.confirm()}
						</button>
						<button
							type="button"
							onclick={() => (confirmingRepeatMeal = null)}
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
								onclick={() => (confirmingRepeatMeal = meal)}
								class="grid h-11 w-11 shrink-0 place-items-center rounded-2xl border-2 border-slate-200 text-slate-500 active:bg-slate-100"
							>
								<svg viewBox="0 0 24 24" class="h-5 w-5" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 3v5h5" /><path d="M3.05 13A9 9 0 1 0 6 5.3L3 8" /><path d="M12 7v5l3 2" /></svg>
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
		{#if isDropTarget(materializedMeals.length)}
			<div class="h-1 rounded-full bg-emerald-500"></div>
		{/if}
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
		{#if confirmingRepeatDay}
			<!-- repetir TODO o dia anterior (copia varias refeicoes): confirma antes -->
			<div class="mt-4 flex items-center gap-2 rounded-2xl bg-emerald-50 p-2">
				<span class="min-w-0 flex-1 pl-2 text-sm font-semibold text-emerald-800">{m.repeat_day_confirm()}</span>
				<button
					type="button"
					onclick={repeatPrevious}
					class="h-11 shrink-0 rounded-xl bg-emerald-600 px-4 text-sm font-bold text-white active:bg-emerald-700"
				>
					{m.confirm()}
				</button>
				<button
					type="button"
					onclick={() => (confirmingRepeatDay = false)}
					class="h-11 shrink-0 rounded-xl px-3 text-sm font-semibold text-slate-500 active:bg-slate-100"
				>
					{m.cancel()}
				</button>
			</div>
		{:else}
			<button
				type="button"
				onclick={() => (confirmingRepeatDay = true)}
				class="mt-4 flex h-12 w-full items-center justify-center gap-2 rounded-2xl border-2 border-slate-200 bg-white font-semibold text-slate-700 active:bg-slate-100"
			>
				<svg viewBox="0 0 24 24" class="h-5 w-5 text-slate-500" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 3v5h5" /><path d="M3.05 13A9 9 0 1 0 6 5.3L3 8" /><path d="M12 7v5l3 2" /></svg>
				{m.repeat_previous_day()}
			</button>
		{/if}
	{/if}

	<a
		href="/dieta/receitas"
		class="mt-3 flex h-12 w-full items-center justify-center rounded-2xl border-2 border-slate-200 bg-white font-semibold text-slate-700 active:bg-slate-100"
	>
		{m.foods_and_recipes()}
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
				<p class="mb-1 text-sm text-slate-500">{editPreview} kcal</p>
				<MacroBreakdown
					protein_g={editPreviewMacros.protein_g}
					carbs_g={editPreviewMacros.carbs_g}
					fat_g={editPreviewMacros.fat_g}
					class="mb-4 text-xs text-slate-400"
				/>
				{#if editing.source === 'recipe'}
					<!-- as duas unidades, como na modal de adicionar: quem lancou em gramas
						 precisa conseguir editar em gramas -->
					{#if editGramsPerServing > 0}
						<div class="mb-3 flex justify-center gap-2">
							<button
								type="button"
								onclick={() => (editQtyMode = 'servings')}
								class="rounded-full border-2 px-3 py-1.5 text-sm font-semibold {editQtyMode ===
								'servings'
									? 'border-emerald-600 bg-emerald-50 text-emerald-800'
									: 'border-slate-200 text-slate-600'}"
							>
								{m.by_servings()}
							</button>
							<button
								type="button"
								onclick={() => (editQtyMode = 'grams')}
								class="rounded-full border-2 px-3 py-1.5 text-sm font-semibold {editQtyMode ===
								'grams'
									? 'border-emerald-600 bg-emerald-50 text-emerald-800'
									: 'border-slate-200 text-slate-600'}"
							>
								{m.by_grams()}
							</button>
						</div>
					{/if}
					{#if editQtyMode === 'grams'}
						<p class="mb-1 text-center text-xs text-slate-400">
							{m.recipe_grams_equiv({
								servings: nf.format(Math.round(editEffectiveQty * 100) / 100)
							})}
						</p>
						<Stepper bind:value={editGrams} min={1} max={3000} step={10} unit="g" />
					{:else}
						<!-- decimals=2: lancamento feito em gramas vira porcao fracionaria, e
							 arredondar para inteiro aqui mudaria a quantidade sem avisar -->
						<Stepper
							bind:value={editQty}
							min={0.1}
							max={20}
							step={0.5}
							decimals={2}
							unit={m.serving_plural()}
						/>
					{/if}
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
		onclick={closePeriodModal}
		onkeydown={(e) => e.key === 'Escape' && closePeriodModal()}
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
					onclick={closePeriodModal}
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

			<!-- CTA de adotar: so aparece quando a estimativa pode virar meta. Quando nao
			     pode, o numero e o motivo ficam na tela de Progresso, que e a de analise. -->
			{#if periodAdaptive && periodAdaptive.has_enough_data && periodAdaptive.can_adopt && periodAdaptive.estimated_maintenance_kcal}
				<div class="mt-4 rounded-2xl border border-emerald-100 bg-emerald-50 p-3">
					<p class="text-sm font-semibold text-emerald-800">
						{m.diet_period_measured({ kcal: nf.format(periodAdaptive.estimated_maintenance_kcal) })}
					</p>
					{#if confirmingRenew === 'adopt'}
						<div class="mt-2 flex items-center gap-2 rounded-xl bg-white p-1.5">
							<span class="min-w-0 flex-1 pl-1.5 text-xs font-semibold text-emerald-800">{m.diet_period_renew_confirm()}</span>
							<button
								type="button"
								disabled={periodBusy}
								onclick={() => renewPeriod(true)}
								class="flex h-10 shrink-0 items-center justify-center gap-1.5 rounded-lg bg-emerald-600 px-3 text-sm font-bold text-white active:bg-emerald-700 disabled:opacity-50"
							>
								{#if periodBusy}<Spinner class="h-4 w-4" />{/if}
								{m.confirm()}
							</button>
							<button
								type="button"
								onclick={() => (confirmingRenew = null)}
								class="h-10 shrink-0 rounded-lg px-2 text-sm font-semibold text-slate-500 active:bg-slate-100"
							>
								{m.cancel()}
							</button>
						</div>
					{:else}
						<button
							type="button"
							disabled={periodBusy}
							onclick={() => (confirmingRenew = 'adopt')}
							class="mt-2 flex h-11 w-full items-center justify-center gap-2 rounded-2xl bg-emerald-600 font-bold text-white active:bg-emerald-700 disabled:opacity-50"
						>
							{m.diet_period_renew_adopt()}
						</button>
					{/if}
				</div>
			{/if}

			{#if confirmingRenew === 'restart'}
				<div class="mt-2 flex items-center gap-2 rounded-xl bg-slate-50 p-1.5">
					<span class="min-w-0 flex-1 pl-1.5 text-xs font-semibold text-slate-600">{m.diet_period_renew_confirm()}</span>
					<button
						type="button"
						disabled={periodBusy}
						onclick={() => renewPeriod(false)}
						class="flex h-10 shrink-0 items-center justify-center gap-1.5 rounded-lg bg-slate-700 px-3 text-sm font-bold text-white active:bg-slate-800 disabled:opacity-50"
					>
						{#if periodBusy}<Spinner class="h-4 w-4" />{/if}
						{m.confirm()}
					</button>
					<button
						type="button"
						onclick={() => (confirmingRenew = null)}
						class="h-10 shrink-0 rounded-lg px-2 text-sm font-semibold text-slate-500 active:bg-slate-100"
					>
						{m.cancel()}
					</button>
				</div>
			{:else}
				<button
					type="button"
					disabled={periodBusy}
					onclick={() => (confirmingRenew = 'restart')}
					class="mt-2 flex h-11 w-full items-center justify-center rounded-2xl border-2 border-slate-200 font-semibold text-slate-600 active:bg-slate-50 disabled:opacity-50"
				>
					{m.diet_period_renew_restart()}
				</button>
			{/if}
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

<!-- Montar refeicao com o que tem em casa: seleciona alimentos e ve na hora o que
	 da pra cozinhar (receitas + alimentos avulsos), sem etapa de "ver sugestoes" -->
{#if showBuildMeal}
	<BuildMealModal
		{day}
		meal={mealByTime()}
		onClose={() => (showBuildMeal = false)}
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

{#if auraPermanent}
	<!-- Moldura permanente da fase menstrual: mais fina e mais lenta que o pulso, para
		 conviver com o uso. aria-hidden porque e puro efeito - a fase ja esta escrita
		 no card, entao nada se perde para quem usa leitor de tela. -->
	<div class="cycle-aura cycle-aura--calm" aria-hidden="true"><i></i><i></i></div>
{:else if auraPlaying}
	<!-- Pulso de 2,6 s ao abrir, nas demais fases (ver maybePlayAura). -->
	<div class="cycle-aura" aria-hidden="true"><i></i><i></i><i></i></div>
{/if}

{#if cycleModal && cycle}
	<div
		class="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
		role="button"
		tabindex="-1"
		onclick={() => (cycleModal = false)}
		onkeydown={(e) => e.key === 'Escape' && (cycleModal = false)}
	>
		<div
			class="w-full max-w-md rounded-3xl bg-white p-5"
			role="dialog"
			tabindex="-1"
			onclick={(e) => e.stopPropagation()}
			onkeydown={() => {}}
		>
			<div class="mb-4 flex items-start justify-between gap-2">
				<h2 class="text-lg font-bold text-slate-900">{m.cycle_optin_label()}</h2>
				<button
					type="button"
					aria-label={m.close()}
					onclick={() => (cycleModal = false)}
					class="grid h-9 w-9 shrink-0 place-items-center rounded-full bg-slate-100 text-slate-500 active:bg-slate-200"
				>
					<svg viewBox="0 0 24 24" class="h-5 w-5" fill="none" stroke="currentColor" stroke-width="2"><path d="M6 6l12 12M18 6L6 18" stroke-linecap="round" /></svg>
				</button>
			</div>
			<CycleConfig
				value={cycle}
				day={today}
				onSaved={(c) => {
					cycleModal = false;
					// A modal salva ancorada em HOJE (a validacao da data precisa do hoje
					// real), mas o card mostra o DIA EXIBIDO. Adotar a resposta direto
					// faria o card de ontem exibir o dia do ciclo de hoje.
					if (day === today) {
						cycle = c;
						return;
					}
					api
						.getCycle(day)
						.then((resolved) => (cycle = resolved))
						.catch(() => {});
				}}
			/>
		</div>
	</div>
{/if}

<style>
	/* Borda gradiente viva do card do ciclo (o "assentado" da aura). Duas camadas:
	   o anel nitido e uma copia borrada por tras, respirando devagar. O truque do
	   mask-composite recorta so a moldura, deixando o miolo do card intacto. */
	.cycle-card::before,
	.cycle-card::after {
		content: '';
		position: absolute;
		inset: 0;
		border-radius: 1rem;
		padding: 2px;
		pointer-events: none;
		background: linear-gradient(120deg, #6658fe, #c33764, #6658fe, #c33764);
		background-size: 300% 300%;
		-webkit-mask: linear-gradient(#000 0 0) content-box, linear-gradient(#000 0 0);
		mask: linear-gradient(#000 0 0) content-box, linear-gradient(#000 0 0);
		-webkit-mask-composite: xor;
		mask-composite: exclude;
		animation: cycle-slide 6s linear infinite;
	}
	.cycle-card::after {
		filter: blur(6px);
		animation: cycle-slide 6s linear infinite, cycle-breathe 3.2s ease-in-out infinite;
	}

	/* A aura de tela inteira: mesma moldura, tres camadas cada vez mais borradas,
	   acende ao abrir e apaga sozinha (animation forwards + timeout no script). */
	.cycle-aura {
		position: fixed;
		/* Respeita as areas seguras: o app usa viewport-fit=cover (app.html), entao
		   inset:0 puro enfiaria a moldura sob o notch e atras do indicador de home. */
		inset: env(safe-area-inset-top) env(safe-area-inset-right)
			env(safe-area-inset-bottom) env(safe-area-inset-left);
		/* O shell e uma coluna max-w-md centrada (+layout.svelte): sem este limite a
		   moldura abracaria a janela inteira no desktop, e nao o app. */
		max-width: 28rem;
		margin-inline: auto;
		border-radius: 1.5rem;
		z-index: 60;
		pointer-events: none;
		animation: cycle-ignite 2.6s ease-out forwards;
	}
	.cycle-aura i {
		position: absolute;
		inset: 0;
		border-radius: 1.5rem;
		padding: 3px;
		background: linear-gradient(120deg, #6658fe, #c33764, #8b5cf6, #6658fe);
		background-size: 300% 300%;
		-webkit-mask: linear-gradient(#000 0 0) content-box, linear-gradient(#000 0 0);
		mask: linear-gradient(#000 0 0) content-box, linear-gradient(#000 0 0);
		-webkit-mask-composite: xor;
		mask-composite: exclude;
		animation: cycle-slide 2.6s linear;
	}
	.cycle-aura i:nth-child(2) {
		filter: blur(10px);
	}
	.cycle-aura i:nth-child(3) {
		filter: blur(26px);
		opacity: 0.8;
	}

	/* Versao permanente: o que impressiona por 2 segundos cansa em 10 minutos. Borda
	   mais fina, giro quatro vezes mais lento, duas camadas em vez de tres e brilho
	   pela metade - presente, sem competir com os numeros. */
	.cycle-aura--calm {
		z-index: 5; /* acima do conteudo, ABAIXO de aba (10), modal (50) e toast (60) */
		opacity: 0.45;
		animation: none;
	}
	.cycle-aura--calm i {
		padding: 2px;
		animation: cycle-slide 10s linear infinite;
	}
	.cycle-aura--calm i:nth-child(2) {
		filter: blur(8px);
	}

	@keyframes cycle-slide {
		to {
			background-position: 300% 0;
		}
	}
	@keyframes cycle-breathe {
		0%,
		100% {
			opacity: 0.2;
		}
		50% {
			opacity: 0.7;
		}
	}
	@keyframes cycle-ignite {
		0% {
			opacity: 0;
		}
		12% {
			opacity: 1;
		}
		70% {
			opacity: 1;
		}
		100% {
			opacity: 0;
		}
	}

	/* Quem pede menos movimento nao perde informacao: as bordas ficam paradas. O pulso
	   some (ele e so chegada); a permanente FICA, porque sinaliza a fase - some-la
	   esconderia um dado de quem so pediu menos animacao. */
	@media (prefers-reduced-motion: reduce) {
		.cycle-card::before,
		.cycle-card::after {
			animation: none;
		}
		.cycle-aura {
			display: none;
		}
		.cycle-aura--calm {
			display: block;
		}
		.cycle-aura--calm i {
			animation: none;
		}
	}
</style>
