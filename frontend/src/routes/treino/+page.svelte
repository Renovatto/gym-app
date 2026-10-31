<script lang="ts">
	import { closeOnBack } from '$lib/modalBack';
	import { slide } from 'svelte/transition';
import { beforeNavigate, goto } from '$app/navigation';
	import {
		api,
		ApiError,
		localDay,
		type Exercise,
		type RoutineDifficulty,
		type WorkoutEquipmentMode,
		type RoutineGeneration,
		type RoutineGenerationPreview,
		type Routine,
		type RoutineItemInput,
		type RoutinePeriodization,
		type RoutineVariation,
		type SessionSummary,
		type StandaloneActivity,
		type WorkoutDayDetail,
		type WorkoutSession
	} from '$lib/api';
	import CalendarModal from '$lib/components/CalendarModal.svelte';
	import ExercisePhotoModal from '$lib/components/ExercisePhotoModal.svelte';
	import ExerciseBrowser from '$lib/components/ExerciseBrowser.svelte';
	import Stepper from '$lib/components/Stepper.svelte';
	import LogActivityModal from '$lib/components/LogActivityModal.svelte';
	import { activityKindLabel, levelLabel } from '$lib/labels';
	import { showToast } from '$lib/toast.svelte';
	import SkeletonScreen from '$lib/components/SkeletonScreen.svelte';
	import { m } from '$lib/paraglide/messages';
	import { errorMessage } from '$lib/errors';
	import { getLocale } from '$lib/paraglide/runtime';
	import { isShowingAnchor } from '$lib/tour.svelte';

	let showCalendar = $state(false);
	// visualizacao (somente leitura) do dia selecionado no calendario: treino de
	// academia e atividade avulsa aparecem juntos, cada um com sua cor.
	let dayWorkouts = $state<WorkoutDayDetail[] | null>(null);
	let dayActivities = $state<StandaloneActivity[]>([]);
	let dayWorkoutDate = $state('');

	async function openDayWorkout(date: string): Promise<void> {
		dayWorkoutDate = date;
		[dayWorkouts, dayActivities] = await Promise.all([
			api.getWorkoutsByDay(date, new Date().getTimezoneOffset()),
			api.getActivities(date)
		]);
	}

	function closeDayWorkout(): void {
		dayWorkouts = null;
		dayActivities = [];
	}

	// Excluir direto pelo dia do calendario. Sem isso ha registro que o app nao deixa
	// apagar de jeito nenhum: treino mais antigo que os ultimos do historico, e
	// atividade avulsa de qualquer dia que nao seja hoje.
	let confirmingDayWorkout = $state<number | null>(null);
	let confirmingDayActivity = $state<number | null>(null);

	async function refreshOpenDay(): Promise<void> {
		await load(); // atualiza historico e as marcas do calendario
		await openDayWorkout(dayWorkoutDate);
		// dia ficou sem nada: manter a modal aberta e vazia nao ajuda ninguem
		if (dayWorkouts?.length === 0 && dayActivities.length === 0) closeDayWorkout();
	}

	async function deleteDayWorkout(sessionId: number): Promise<void> {
		confirmingDayWorkout = null;
		await api.deleteSession(sessionId);
		await refreshOpenDay();
		showToast(m.toast_deleted());
	}

	async function deleteDayActivity(activityId: number): Promise<void> {
		confirmingDayActivity = null;
		await api.deleteActivity(activityId);
		await refreshOpenDay();
		showToast(m.toast_deleted());
	}

	// A API devolve ativas e arquivadas juntas; a tela separa as duas listas. Tudo o
	// que fala de ciclo (proximo treino, periodizacao, lista principal) usa so as ativas.
	let allRoutines = $state<Routine[]>([]);
	const routines = $derived(allRoutines.filter((r) => !r.archived_at));
	const archivedRoutines = $derived(allRoutines.filter((r) => r.archived_at));

	// Exemplo de rotina arquivada, so durante o passo do tutorial que aponta para
	// "Arquivadas" - quando a conta e nova e nunca arquivou nada, mostra a secao de
	// verdade com um exemplo, em vez de a secao inteira desaparecer da tela.
	const DEMO_ARCHIVED = [
		{
			id: -1,
			name: m.tour_demo_archived_routine_name(),
			position: 0,
			items: [1, 2, 3, 4] as unknown as Routine['items'],
			archived_at: new Date(Date.now() - 30 * 86400000).toISOString()
		}
	] as unknown as Routine[];
	const demoArchivedActive = $derived(
		isShowingAnchor('workout-archived') && archivedRoutines.length === 0
	);
	const displayArchived = $derived(demoArchivedActive ? DEMO_ARCHIVED : archivedRoutines);

	// Arquivadas comecam fechadas (accordion). O tutorial precisa mostrar a lista
	// aberta quando aponta para ela, entao o passo do tour tambem abre.
	let archivedExpanded = $state(false);
	const archivedOpen = $derived(archivedExpanded || demoArchivedActive);
	let sessions = $state<SessionSummary[]>([]);
	let activeSession = $state<WorkoutSession | null>(null);
	let periodization = $state<RoutinePeriodization[]>([]);
	let todayActivities = $state<StandaloneActivity[]>([]);
	// dias com atividade avulsa, para marcar no calendario numa cor propria
	let activityDays = $state<string[]>([]);
	let loading = $state(true);

	let showLogActivity = $state(false);
	let confirmingDeleteActivity = $state<number | null>(null);
	const activityKcalTotal = $derived(todayActivities.reduce((sum, a) => sum + a.kcal, 0));

	async function reloadActivities(): Promise<void> {
		[todayActivities, activityDays] = await Promise.all([
			api.getActivities(localDay()),
			api.getActivityDays()
		]);
	}

	async function deleteActivityEntry(id: number): Promise<void> {
		confirmingDeleteActivity = null;
		await api.deleteActivity(id);
		await reloadActivities();
		showToast(m.toast_deleted());
	}

	// Explorar uma rotina (leitura) antes de iniciar: fotos e alvos de cada exercicio.
	let previewRoutine = $state<Routine | null>(null);
	let photoOf = $state<Exercise | null>(null);

	function startFromPreview(): void {
		if (!previewRoutine) return;
		const id = previewRoutine.id;
		previewRoutine = null;
		start(id);
	}

	// Variar o treino: exercicios diferentes do mesmo grupo muscular (previa + escolher).
	let variation = $state<RoutineVariation | null>(null);
	let variationSourceId = $state<number | null>(null);
	let variationLoading = $state<number | null>(null);
	let variationBusy = $state(false);
	let variationApplyUnknown = $state(false);
	let variationOperationKey = $state<string | null>(null);
	let variationApplyIntent = $state<{ type: 'renew' } | { type: 'copy'; archiveOriginal: boolean } | null>(null);
	let variationCopyName = $state('');
	let variationSetupOpen = $state(false);
	let variationLevel = $state<RoutineDifficulty>('intermediate');
	let variationEquipment = $state<WorkoutEquipmentMode>('mixed');
	let variationSetupMode = $state<'single' | 'bulk'>('single');
	let selectedRenewalIds = $state<number[]>([]);
	let variationSwapTarget = $state<{ routineId: number; itemIndex: number; bulk: boolean } | null>(null);

	function openVariation(routineId: number): void {
		variationSourceId = routineId;
		variation = null;
		variationSetupOpen = true;
		variationSetupMode = 'single';
		choosingVariationFate = false;
	}

	function closeVariation(): void {
		if (variationBusy || variationApplyUnknown) return;
		variation = null;
		choosingVariationFate = false;
		resetVariationApply();
	}

	async function generateVariationPreview(): Promise<void> {
		if (variationSetupMode === 'single' && variationSourceId === null) return;
		if (variationSetupMode === 'bulk' && selectedRenewalIds.length === 0) return;
		variationLoading = variationSourceId ?? -1;
		bulkRenewalLoading = variationSetupMode === 'bulk';
		const selectedLevel = variationLevel;
		const selectedEquipment = variationEquipment;
		try {
			if (variationSetupMode === 'single') {
				variation = await api.getRoutineVariation(
					variationSourceId!,
					selectedLevel,
					selectedEquipment
				);
				resetVariationApply();
			} else {
				const selected = selectedRenewalIds;
				bulkRenewal = await Promise.all(
					selected.map((routineId) =>
						api.getRoutineVariation(routineId, selectedLevel, selectedEquipment)
					)
				);
			}
			variationSetupOpen = false;
		} catch (error) {
			showToast(errorMessage(error instanceof ApiError ? error.code : 'GENERIC_ERROR'));
		} finally {
			variationLoading = null;
			bulkRenewalLoading = false;
		}
	}

	async function anotherVariation(): Promise<void> {
		if (variationSourceId === null || variationBusy || variationApplyUnknown) return;
		variationBusy = true;
		try {
			variation = await api.getRoutineVariation(
				variationSourceId,
				variationLevel,
				variationEquipment
			);
			resetVariationApply();
		} catch (error) {
			showToast(errorMessage(error instanceof ApiError ? error.code : 'GENERIC_ERROR'));
		} finally {
			variationBusy = false;
		}
	}

	function resetVariationApply(): void {
		variationApplyUnknown = false;
		variationOperationKey = null;
		variationApplyIntent = null;
		variationCopyName = '';
	}

	function exerciseMatchesPreferences(
		exercise: Exercise,
		level: RoutineDifficulty,
		equipmentMode: WorkoutEquipmentMode
	): boolean {
		const allowedLevels: Record<RoutineDifficulty, string[]> = {
			beginner: ['beginner'],
			intermediate: ['beginner', 'intermediate'],
			advanced: ['beginner', 'intermediate', 'expert']
		};
		const allowedEquipment: Record<WorkoutEquipmentMode, string[]> = {
			free_weights: ['barbell', 'dumbbell', 'kettlebell', 'bodyweight'],
			machines: ['machine', 'cable'],
			mixed: ['barbell', 'dumbbell', 'kettlebell', 'bodyweight', 'machine', 'cable']
		};
		return (
			exercise.level !== null &&
			allowedLevels[level].includes(exercise.level) &&
			allowedEquipment[equipmentMode].includes(exercise.equipment)
		);
	}

	function chooseVariationReplacement(exercise: Exercise): void {
		if (!variationSwapTarget) return;
		if (!exerciseMatchesPreferences(exercise, variationLevel, variationEquipment)) {
			showToast(m.routine_exercise_outside_preferences());
			return;
		}
		const { routineId, itemIndex, bulk } = variationSwapTarget;
		if (bulk && bulkRenewal) {
			bulkRenewal = bulkRenewal.map((routineVariation) =>
				routineVariation.routine_id !== routineId
					? routineVariation
					: {
							...routineVariation,
							items: routineVariation.items.map((item, index) =>
								index === itemIndex
									? { ...item, new_exercise: exercise, matches_preferences: true }
									: item
							)
						}
			);
			bulkOperationKey = null;
			bulkApplyUnknown = false;
		} else if (variation?.routine_id === routineId) {
			variation = {
				...variation,
				items: variation.items.map((item, index) =>
					index === itemIndex
						? { ...item, new_exercise: exercise, matches_preferences: true }
						: item
				)
			};
			resetVariationApply();
		}
		variationSwapTarget = null;
	}

	function variationSwapSelectedIds(): Set<number> {
		if (!variationSwapTarget) return new Set();
		if (variationSwapTarget.bulk) {
			const source = bulkRenewal?.find((item) => item.routine_id === variationSwapTarget!.routineId);
			return new Set(
				(source?.items ?? [])
					.filter((_, index) => index !== variationSwapTarget!.itemIndex)
					.map((item) => item.new_exercise.id)
			);
		}
		return new Set(
			(variation?.items ?? [])
				.filter((_, index) => index !== variationSwapTarget!.itemIndex)
				.map((item) => item.new_exercise.id)
		);
	}

	// itens de rotina a partir da variacao (troca o exercicio, mantem series/alvos)
	function variationToItems(source: RoutineVariation): RoutineItemInput[] {
		return source.items.map((it) => ({
			exercise_id: it.new_exercise.id,
			target_sets: it.target_sets,
			target_reps: it.target_reps,
			target_weight_kg: it.target_weight_kg,
			target_duration_min: it.target_duration_min,
			rest_seconds: it.rest_seconds
		}));
	}

	function variationItems(): RoutineItemInput[] {
		return variation ? variationToItems(variation) : [];
	}

	async function saveVariation(): Promise<void> {
		if (!variation) return;
		if (variationApplyIntent === null) variationApplyIntent = { type: 'renew' };
		if (variationApplyIntent.type !== 'renew') return;
		await applyVariationIntent();
	}

	// "Usar hoje" cria uma rotina NOVA a partir da variacao. Sem escolher o destino da
	// original, as duas ficam no ciclo e a lista cresce a cada variacao - por isso o
	// passo de decisao antes de criar.
	let choosingVariationFate = $state(false);

	async function useVariationToday(archiveOriginal: boolean): Promise<void> {
		if (!variation) return;
		if (variationApplyIntent === null) {
			variationApplyIntent = { type: 'copy', archiveOriginal };
			const label = new Date().toLocaleDateString(getLocale(), { day: '2-digit', month: '2-digit' });
			variationCopyName = `${variation.name} — ${m.variation_word()} ${label}`.slice(0, 80);
		}
		if (
			variationApplyIntent.type !== 'copy' ||
			variationApplyIntent.archiveOriginal !== archiveOriginal
		) return;
		await applyVariationIntent();
	}

	async function applyVariationIntent(): Promise<void> {
		if (!variation || !variationApplyIntent || variationBusy) return;
		variationBusy = true;
		variationOperationKey ??= crypto.randomUUID();
		try {
			const intent = variationApplyIntent;
			const source = allRoutines.find((routine) => routine.id === variation!.routine_id);
			if (!source) throw new ApiError('ROUTINE_PLAN_STALE', 409);
			const isRenewal = intent.type === 'renew';
			const archiveOriginal = intent.type === 'copy' && intent.archiveOriginal;
			if (isRenewal || archiveOriginal) {
				if (source.archived_at) throw new ApiError('ROUTINE_PLAN_STALE', 409);
			}
			const result = await api.applyRoutinePlan({
				operation_key: variationOperationKey,
				destination: 'append',
				routines: [
					isRenewal
						? { routine_id: source.id, name: variation.name, items: variationItems() }
						: { name: variationCopyName, items: variationItems() }
				],
				archive_ids: archiveOriginal ? [source.id] : [],
				expected_sources: { [source.id]: source.revision },
				source_ids: !isRenewal && !archiveOriginal ? [source.id] : []
			});
			variation = null;
			choosingVariationFate = false;
			resetVariationApply();
			if (!isRenewal && intent.archiveOriginal) showToast(m.routine_archived_toast());
			if (isRenewal) {
				showToast(m.vary_saved());
				await refreshAfterRoutineApply();
				return;
			}
			try {
				await start(result.routines[0].id);
			} catch {
				showToast(m.routine_created_start_failed());
			}
			await refreshAfterRoutineApply();
		} catch (error) {
			if (error instanceof ApiError && error.code === 'NETWORK_ERROR') {
				variationApplyUnknown = true;
			} else {
				resetVariationApply();
			}
			showToast(errorMessage(error instanceof ApiError ? error.code : 'GENERIC_ERROR'));
		} finally {
			variationBusy = false;
		}
	}

	// Renovar o ciclo inteiro de uma vez: uma variacao por rotina vencida, revisadas
	// juntas e confirmadas num toque so, em vez de abrir rotina por rotina.
	let bulkRenewal = $state<RoutineVariation[] | null>(null);
	let bulkRenewalLoading = $state(false);
	let bulkRenewalBusy = $state(false);
	// rotina cuja variacao esta sendo sorteada de novo (desabilita so o botao dela)
	let rerollingRoutineId = $state<number | null>(null);
	let bulkOperationKey = $state<string | null>(null);
	let bulkApplyUnknown = $state(false);

	async function openBulkRenewal(): Promise<void> {
		selectedPeriod = null;
		selectedRenewalIds = renewableRoutines.map((period) => period.routine_id);
		variationSetupMode = 'bulk';
		variationSetupOpen = true;
		bulkRenewal = null;
		bulkOperationKey = null;
		bulkApplyUnknown = false;
	}

	async function rerollBulkVariation(index: number): Promise<void> {
		if (!bulkRenewal) return;
		const routineId = bulkRenewal[index].routine_id;
		rerollingRoutineId = routineId;
		try {
			const fresh = await api.getRoutineVariation(routineId, variationLevel, variationEquipment);
			if (bulkRenewal) {
				bulkRenewal[index] = fresh;
				bulkOperationKey = null;
				bulkApplyUnknown = false;
			}
		} finally {
			rerollingRoutineId = null;
		}
	}

	async function confirmBulkRenewal(): Promise<void> {
		if (!bulkRenewal || bulkApplyUnknown && !bulkOperationKey) return;
		bulkRenewalBusy = true;
		try {
			const count = bulkRenewal.length;
			const sources = bulkRenewal.map((variation) =>
				allRoutines.find((routine) => routine.id === variation.routine_id)
			);
			if (sources.some((routine) => !routine)) throw new ApiError('ROUTINE_PLAN_STALE', 409);
			bulkOperationKey ??= crypto.randomUUID();
			await api.applyRoutinePlan({
				operation_key: bulkOperationKey,
				destination: 'append',
				routines: bulkRenewal.map((routineVariation) => ({
					routine_id: routineVariation.routine_id,
					name: routineVariation.name,
					items: variationToItems(routineVariation)
				})),
				expected_sources: Object.fromEntries(
					sources.map((routine) => [routine!.id, routine!.revision])
				)
			});
			bulkRenewal = null;
			bulkOperationKey = null;
			bulkApplyUnknown = false;
			showToast(m.renew_all_toast({ count }));
			await refreshAfterRoutineApply();
		} catch (error) {
			if (error instanceof ApiError && error.code === 'NETWORK_ERROR') {
				bulkApplyUnknown = true;
			} else {
				bulkOperationKey = null;
				bulkApplyUnknown = false;
			}
			showToast(errorMessage(error instanceof ApiError ? error.code : 'GENERIC_ERROR'));
		} finally {
			bulkRenewalBusy = false;
		}
	}

	function closeBulkRenewal(): void {
		if (bulkRenewalBusy || bulkApplyUnknown) return;
		bulkRenewal = null;
		bulkOperationKey = null;
	}

	// Rotina "vencida" (passou do mesociclo): sinaliza hora de variar o estimulo.
	const dueRoutine = $derived(periodization.find((p) => p.due));
	const periodizationFor = (routineId: number): RoutinePeriodization | undefined =>
		periodization.find((p) => p.routine_id === routineId);
	// detalhes do ciclo (validade) da rotina clicada
	let selectedPeriod = $state<RoutinePeriodization | null>(null);
	function fmtDate(iso: string): string {
		return df.format(new Date(iso + 'T12:00:00'));
	}
	let creatingTemplate = $state(false);
	let templatePreview = $state<RoutineGenerationPreview | null>(null);
	let templateFrequency = $state(3);
	let templateLevel = $state<RoutineDifficulty>('beginner');
	let templateEquipment = $state<WorkoutEquipmentMode>('mixed');
	let templatePreviewPreferences = $state<{
		level: RoutineDifficulty;
		equipment: WorkoutEquipmentMode;
	} | null>(null);
	let templateDestination = $state<'append' | 'replace'>('append');
	let templateSwapTarget = $state<{ routineIndex: number; itemIndex: number } | null>(null);
	let templateApplyBusy = $state(false);
	let templateApplyUnknown = $state(false);
	let templateOperationKey = $state<string | null>(null);
	let templatePreviewSourceIds = $state<number[]>([]);
	let templatePreviewSourceRevisions = $state<Record<number, string>>({});
	// null = fechado; 'choose' = escolher como montar; 'template' = escolher a frequencia
	let addWorkoutStep = $state<'choose' | 'template' | null>(null);
	let completingId = $state<number | null>(null);

	const df = new Intl.DateTimeFormat(getLocale(), { day: '2-digit', month: 'short' });
	const nf = new Intl.NumberFormat(getLocale());

	async function load(): Promise<void> {
		[allRoutines, sessions, activeSession, periodization, todayActivities, activityDays] =
			await Promise.all([
				api.getRoutines(true),
				api.getSessions(),
				api.getActiveSession(),
				api.getTrainingPeriodization(localDay()),
				api.getActivities(localDay()),
				api.getActivityDays()
			]);
		loading = false;
	}

	let confirmingDiscard = $state(false);

	async function discardActive(): Promise<void> {
		if (!activeSession) return;
		await api.deleteSession(activeSession.id);
		confirmingDiscard = false;
		await load();
		showToast(m.toast_deleted());
	}

	async function useTemplate(frequency: number): Promise<void> {
		creatingTemplate = true;
		const selectedLevel = templateLevel;
		const selectedEquipment = templateEquipment;
		try {
			templateFrequency = frequency;
			const preview = await api.previewRoutines(frequency, selectedLevel, selectedEquipment);
			templatePreview = preview;
			templatePreviewPreferences = { level: selectedLevel, equipment: selectedEquipment };
			templateDestination = routines.length > 0 ? 'append' : 'replace';
			templatePreviewSourceIds = routines.map((routine) => routine.id);
			templatePreviewSourceRevisions = Object.fromEntries(
				routines.map((routine) => [routine.id, routine.revision])
			);
			templateOperationKey = crypto.randomUUID();
			templateApplyUnknown = false;
			addWorkoutStep = null;
		} finally {
			creatingTemplate = false;
		}
	}

	function updateTemplateItem(
		routineIndex: number,
		itemIndex: number,
		changes: Partial<RoutineGeneration['items'][number]>
	): void {
		if (!templatePreview) return;
		const nextRoutines = templatePreview.routines.map((routine, currentRoutineIndex) => ({
			...routine,
			items: routine.items.map((item, currentItemIndex) =>
				currentRoutineIndex === routineIndex && currentItemIndex === itemIndex
					? { ...item, ...changes }
					: item
			)
		}));
		templatePreview = { ...templatePreview, routines: nextRoutines };
		templateOperationKey = crypto.randomUUID();
		templateApplyUnknown = false;
	}

	function toggleRenewalSelection(routineId: number): void {
		selectedRenewalIds = selectedRenewalIds.includes(routineId)
			? selectedRenewalIds.filter((selectedId) => selectedId !== routineId)
			: [...selectedRenewalIds, routineId];
	}

	function resetTemplateOperationKey(): void {
		if (templateApplyUnknown) return;
		templateOperationKey = crypto.randomUUID();
	}

	function closeTemplatePreview(): void {
		if (templateApplyBusy || templateApplyUnknown) return;
		templatePreview = null;
		templatePreviewPreferences = null;
		templateSwapTarget = null;
		templateOperationKey = null;
	}

	function chooseTemplateReplacement(exercise: Exercise): void {
		if (!templateSwapTarget) return;
		const current = templatePreview?.routines[templateSwapTarget.routineIndex]?.items[
			templateSwapTarget.itemIndex
		];
		if (!current) return;
		if (
			current.exercise.muscle_group !== exercise.muscle_group ||
			current.exercise.kind !== exercise.kind
		) {
			showToast(m.routine_exercise_same_group_type());
			return;
		}
		const preferences = templatePreviewPreferences;
		if (
			!preferences ||
			!exerciseMatchesPreferences(exercise, preferences.level, preferences.equipment)
		) {
			showToast(m.routine_exercise_outside_preferences());
			return;
		}
		const { routineIndex, itemIndex } = templateSwapTarget;
		const existing = templatePreview?.routines[routineIndex]?.items ?? [];
		if (existing.some((item, index) => index !== itemIndex && item.exercise.id === exercise.id)) {
			return;
		}
		updateTemplateItem(routineIndex, itemIndex, { exercise, target_weight_kg: null });
		templateSwapTarget = null;
	}

	function templateSwapSelectedIds(): Set<number> {
		if (!templateSwapTarget || !templatePreview) return new Set();
		return new Set(
			templatePreview.routines[templateSwapTarget.routineIndex].items
				.filter((_, index) => index !== templateSwapTarget!.itemIndex)
				.map((item) => item.exercise.id)
		);
	}

	async function applyTemplatePreview(): Promise<void> {
		if (!templatePreview || !templateOperationKey || templateApplyBusy) return;
		templateApplyBusy = true;
		try {
			await api.applyRoutinePlan({
				operation_key: templateOperationKey,
				destination: templateDestination,
				routines: templatePreview.routines.map((routine) => ({
					name: routine.name,
					items: routine.items.map((item) => ({
						exercise_id: item.exercise.id,
						slot_id: item.slot_id,
						target_sets: item.target_sets,
						target_reps: item.target_reps,
						target_weight_kg: item.target_weight_kg,
						target_duration_min: item.target_duration_min,
						rest_seconds: item.rest_seconds
					}))
				})),
				expected_active_ids: templateDestination === 'replace' ? templatePreviewSourceIds : [],
				expected_sources:
					templateDestination === 'replace' ? templatePreviewSourceRevisions : {},
				generation: {
					frequency: templateFrequency,
					level: templatePreviewPreferences?.level ?? templateLevel,
					equipment_mode: templatePreviewPreferences?.equipment ?? templateEquipment
				}
			});
			templatePreview = null;
			templatePreviewPreferences = null;
			templateOperationKey = null;
			templateApplyUnknown = false;
			showToast(m.toast_created());
			await refreshAfterRoutineApply();
		} catch (error) {
			if (error instanceof ApiError && error.code === 'NETWORK_ERROR') {
				templateApplyUnknown = true;
			} else {
				showToast(errorMessage(error instanceof ApiError ? error.code : 'GENERIC_ERROR'));
			}
		} finally {
			templateApplyBusy = false;
		}
	}

	async function refreshAfterRoutineApply(): Promise<void> {
		try {
			await load();
		} catch (error) {
			showToast(errorMessage(error instanceof ApiError ? error.code : 'GENERIC_ERROR'));
		}
	}

	// --- Arquivar rotinas -------------------------------------------------
	// Arquivar tira a rotina do ciclo sem apagar nada: exercicios e alvos ficam
	// guardados, o historico segue intacto e da para reativar quando quiser.

	let confirmingUnarchive = $state<number | null>(null);
	let confirmingDeleteArchived = $state<number | null>(null);
	let confirmingArchiveAll = $state(false);
	let archiveBusy = $state(false);

	async function unarchive(routineId: number): Promise<void> {
		confirmingUnarchive = null;
		archiveBusy = true;
		try {
			await api.unarchiveRoutine(routineId);
			await load();
			showToast(m.routine_unarchived_toast());
		} finally {
			archiveBusy = false;
		}
	}

	async function deleteArchived(routineId: number): Promise<void> {
		confirmingDeleteArchived = null;
		archiveBusy = true;
		try {
			await api.deleteRoutine(routineId);
			await load();
			showToast(m.toast_deleted());
		} finally {
			archiveBusy = false;
		}
	}

	async function archiveAll(routineIds: number[]): Promise<void> {
		confirmingArchiveAll = false;
		archiveBusy = true;
		try {
			await api.archiveRoutines(routineIds);
			await load();
			showToast(m.routines_archived_toast({ count: routineIds.length }));
		} finally {
			archiveBusy = false;
		}
	}

	// Oferta de trocar de ciclo: so aparece quando ha sinal REAL de programa novo -
	// entrou rotina com 0 semanas E sobraram rotinas que ja passaram da validade.
	// Sem isso, a pergunta cairia toda vez que alguem so soma o dia C ao ABC.
	const staleRoutines = $derived(periodization.filter((p) => p.due));
	// vencidas que da para variar: rotina sem exercicio nao tem o que trocar
	const renewableRoutines = $derived(
		staleRoutines.filter((p) => (routines.find((r) => r.id === p.routine_id)?.items.length ?? 0) > 0)
	);
	// com uma so vencida o fluxo individual ja resolve; o lote vale a partir de duas
	const canRenewAll = $derived(renewableRoutines.length >= 2);
	const hasFreshRoutine = $derived(periodization.some((p) => p.weeks_active === 0));

	const OFFER_DISMISSED_KEY = 'treino:archive-offer-dismissed';
	// guarda QUAIS rotinas foram dispensadas: se o conjunto de vencidas mudar, a
	// oferta volta; se for o mesmo, "Manter" continua valendo e nao incomoda de novo.
	let dismissedStaleIds = $state('');
	const staleIdsKey = $derived(
		staleRoutines
			.map((p) => p.routine_id)
			.sort((a, b) => a - b)
			.join(',')
	);
	const showArchiveOffer = $derived(
		staleRoutines.length > 0 && hasFreshRoutine && dismissedStaleIds !== staleIdsKey
	);

	function dismissArchiveOffer(): void {
		dismissedStaleIds = staleIdsKey;
		localStorage.setItem(OFFER_DISMISSED_KEY, staleIdsKey);
	}

	// Iniciar e marcar feito pedem confirmacao (evita inicio/duplicata por clique acidental)
	let confirmingStart = $state<number | null>(null);
	let confirmingDone = $state<number | null>(null);
	// Dia do treino que esta sendo marcado como feito. Comeca sempre em hoje - so
	// muda quando a pessoa escolhe uma data para lancar um treino esquecido.
	let doneDay = $state(localDay());

	function openDoneConfirm(routineId: number): void {
		doneDay = localDay();
		confirmingDone = routineId;
	}

	async function start(routineId: number): Promise<void> {
		confirmingStart = null;
		const session = await api.startSession(routineId);
		await goto(`/treino/sessao/${session.id}`);
	}

	async function markDone(routineId: number): Promise<void> {
		const day = doneDay;
		const isPastDay = day !== localDay();
		confirmingDone = null;
		completingId = routineId;
		try {
			await api.completeRoutine(routineId, isPastDay ? day : undefined);
			await load();
			showToast(
				isPastDay
					? m.workout_done_past_toast({ date: fmtDate(day) })
					: m.workout_done_toast()
			);
		} finally {
			completingId = null;
		}
	}

	// Excluir um treino do historico (sempre com confirmacao)
	let confirmingDeleteHistory = $state<number | null>(null);

	async function deleteHistory(sessionId: number): Promise<void> {
		confirmingDeleteHistory = null;
		await api.deleteSession(sessionId);
		await load();
		showToast(m.toast_deleted());
	}

	const finishedSessions = $derived(sessions.filter((s) => s.finished_at));

	// Exemplo de historico, so durante o passo do tutorial que aponta para
	// "Historico" - mesma ideia do exemplo de rotina arquivada, acima.
	const DEMO_HISTORY = [
		{
			id: -1,
			routine_id: null,
			routine_name: m.tour_demo_history_routine_a(),
			started_at: new Date(Date.now() - 2 * 86400000).toISOString(),
			finished_at: new Date(Date.now() - 2 * 86400000 + 3000000).toISOString(),
			total_sets: 18,
			total_volume_kg: 2140
		},
		{
			id: -2,
			routine_id: null,
			routine_name: m.tour_demo_history_routine_b(),
			started_at: new Date(Date.now() - 4 * 86400000).toISOString(),
			finished_at: new Date(Date.now() - 4 * 86400000 + 2700000).toISOString(),
			total_sets: 15,
			total_volume_kg: 1860
		}
	] as unknown as SessionSummary[];
	const demoHistoryActive = $derived(
		isShowingAnchor('workout-history') && finishedSessions.length === 0
	);

	// --- Proximo treino do ciclo ------------------------------------------
	// A ordem das rotinas na tela E o ciclo (A -> B -> C -> A). O proximo e a rotina
	// seguinte a do ultimo treino concluido. Treino livre e atividade avulsa nao
	// avancam a fila; rotina excluida (ou fila nunca iniciada) recomeca do topo.

	// ultima sessao concluida que aponta para uma rotina AINDA existente
	// (finishedSessions vem do backend do mais recente para o mais antigo)
	const lastFinishedWithRoutine = $derived(
		finishedSessions.find(
			(s) => s.routine_id !== null && routines.some((r) => r.id === s.routine_id)
		) ?? null
	);

	const nextRoutine = $derived.by(() => {
		const startable = routines.filter((r) => r.items.length > 0);
		if (startable.length === 0) return null;
		const lastId = lastFinishedWithRoutine?.routine_id;
		const lastIndex = lastId != null ? routines.findIndex((r) => r.id === lastId) : -1;
		if (lastIndex === -1) return startable[0];
		// anda a partir da seguinte, pulando rotinas vazias (nao da para inicia-las)
		for (let step = 1; step <= routines.length; step++) {
			const candidate = routines[(lastIndex + step) % routines.length];
			if (candidate.items.length > 0) return candidate;
		}
		return null;
	});

	// dia (YYYY-MM-DD) da ultima vez que cada rotina foi treinada
	const lastDoneDayByRoutine = $derived.by(() => {
		const map = new Map<number, string>();
		for (const s of finishedSessions) {
			if (s.routine_id !== null && !map.has(s.routine_id)) {
				map.set(s.routine_id, s.started_at.slice(0, 10));
			}
		}
		return map;
	});

	const weekdayFmt = new Intl.DateTimeFormat(getLocale(), { weekday: 'short' });

	// "hoje" / "ontem" / "seg." / "12 de jul." - quando foi a ultima vez. E o que faz
	// a fila fazer sentido de relance ("treinei A ontem, entao hoje e B").
	function recencyLabel(routineId: number): string | null {
		const day = lastDoneDayByRoutine.get(routineId);
		if (!day) return null;
		const today = localDay();
		if (day === today) return m.recency_today();
		// meio-dia evita a virada de fuso na conta de diferenca de dias
		const diffDays = Math.round(
			(new Date(today + 'T12:00:00').getTime() - new Date(day + 'T12:00:00').getTime()) / 86400000
		);
		if (diffDays === 1) return m.recency_yesterday();
		if (diffDays < 7) return weekdayFmt.format(new Date(day + 'T12:00:00'));
		return df.format(new Date(day + 'T12:00:00'));
	}

	// rotinas fora do destaque ficam compactas; tocar expande uma por vez
	let expandedRoutine = $state<number | null>(null);

	$effect(() => {
		dismissedStaleIds = localStorage.getItem(OFFER_DISMISSED_KEY) ?? '';
		load();
	});


	// O historico mostrava so os 8 mais recentes e nao havia como chegar no resto -
	// treino antigo ficava sem jeito de abrir nem de excluir.
	const HISTORY_PREVIEW = 8;
	let historyExpanded = $state(false);
	const visibleHistory = $derived(
		demoHistoryActive
			? DEMO_HISTORY
			: historyExpanded
				? finishedSessions
				: finishedSessions.slice(0, HISTORY_PREVIEW)
	);

	// dias com treino concluido, marcados no calendario (visualizacao do historico)
	const trainedDays = $derived(new Set(finishedSessions.map((s) => s.started_at.slice(0, 10))));
	// dias com atividade avulsa: marcados na segunda cor, podem coincidir com treino
	const activityDaysSet = $derived(new Set(activityDays));

	// Voltar fecha a modal aberta em vez de sair da tela (ver lib/modalBack.ts).
	$effect(() => {
		if (selectedPeriod) return closeOnBack(() => (selectedPeriod = null));
	});
	$effect(() => {
		if (dayWorkouts) return closeOnBack(() => (dayWorkouts = null));
	});
	// Estas duas modais trocam de conteudo sem fechar ("Comecar rapido" muda o passo,
	// "outra variacao" troca a variacao). O efeito depende so de ABERTA/FECHADA: se
	// dependesse do valor, cada troca fecharia e reabriria a trava do Voltar, e o
	// back() dessa reabertura fechava a modal - o botao parecia nao fazer nada.
	const variationOpen = $derived(variation !== null);
	const bulkRenewalOpen = $derived(bulkRenewal !== null);
	const workoutSetupOpen = $derived(addWorkoutStep !== null || templatePreview !== null);

	function closeWorkoutSetupOnBack(): void {
		if (templatePreview !== null) {
			closeTemplatePreview();
			return;
		}
		addWorkoutStep = null;
	}
	// A escolha do formato e a previa sao etapas da mesma jornada/modal. Um unico
	// trap evita que o cleanup da primeira etapa consuma o historico da previa.
	$effect(() => {
		if (workoutSetupOpen) return closeOnBack(closeWorkoutSetupOnBack);
	});
	$effect(() => {
		if (previewRoutine) return closeOnBack(() => (previewRoutine = null));
	});
	$effect(() => {
		if (variationOpen) return closeOnBack(closeVariation);
	});
	$effect(() => {
		if (bulkRenewalOpen) return closeOnBack(closeBulkRenewal);
	});
	$effect(() => {
		if (variationSetupOpen) return closeOnBack(() => (variationSetupOpen = false));
	});
	$effect(() => {
		if (templateSwapTarget) return closeOnBack(() => (templateSwapTarget = null));
	});
	$effect(() => {
		if (variationSwapTarget) return closeOnBack(() => (variationSwapTarget = null));
	});

	beforeNavigate(({ cancel }) => {
		if (!templateApplyUnknown && !variationApplyUnknown && !bulkApplyUnknown) return;
		cancel();
		showToast(m.routine_apply_unknown());
	});
</script>

<div class="mb-6 flex items-center justify-between gap-2">
	<h1 class="text-2xl font-bold">{m.tab_workout()}</h1>
	<div class="flex items-center gap-2">
		<button
			type="button"
			data-tour="workout-calendar"
			aria-label={m.workout_calendar()}
			title={m.workout_calendar()}
			onclick={() => (showCalendar = true)}
			class="grid h-9 w-9 place-items-center rounded-full bg-white text-slate-500 shadow-sm active:bg-slate-100"
		>
			<svg viewBox="0 0 24 24" class="h-5 w-5" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="4" width="18" height="17" rx="2" /><path d="M3 9h18M8 2v4M16 2v4" stroke-linecap="round" /></svg>
		</button>
		<a
			href="/treino/catalogo"
			data-tour="workout-catalog"
			class="rounded-full bg-white px-4 py-2 text-sm font-semibold text-emerald-700 shadow-sm"
		>
			{m.exercise_catalog()}
		</a>
	</div>
</div>

<!-- Atividade avulsa: yoga, corrida, bike etc. fora do treino de academia. So
	 registro/historico por enquanto - nao entra na meta calorica do dia (o fator
	 de atividade do TDEE ja embute o exercicio medio, ver services/goals.py). O
	 botao fica no topo (acao rapida); o resultado do dia fica la embaixo, junto
	 do historico de treino. -->
<button
	type="button"
	data-tour="workout-activity"
	onclick={() => (showLogActivity = true)}
	class="mb-4 flex w-full items-center justify-center gap-2 rounded-2xl border-2 border-dashed border-slate-300 bg-white py-3 text-sm font-bold text-slate-700 active:bg-slate-50"
>
	<svg viewBox="0 0 24 24" class="h-4.5 w-4.5 text-slate-500" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 12h4l2 6 4-14 2 8h6" /></svg>
	{m.activity_cta()}
</button>

{#if showLogActivity}
	<LogActivityModal
		day={localDay()}
		onClose={() => (showLogActivity = false)}
		onAdded={reloadActivities}
	/>
{/if}

<!-- so avisa quando a rotina vencida e a DA VEZ: aviso de rotina que a pessoa nem
	 vai treinar hoje e ruido (a pilula ambar dela continua la ao expandir) -->
{#if dueRoutine && dueRoutine.routine_id === nextRoutine?.id}
	<div class="mb-4 flex items-start gap-3 rounded-3xl border-2 border-amber-200 bg-amber-50 p-4">
		<span class="grid h-9 w-9 shrink-0 place-items-center rounded-xl bg-amber-500 text-white">
			<svg viewBox="0 0 24 24" class="h-5 w-5" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 4v6h6M20 20v-6h-6M20 8a8 8 0 00-14-3M4 16a8 8 0 0014 3" stroke-linecap="round" stroke-linejoin="round" /></svg>
		</span>
		<div class="min-w-0">
			<p class="text-sm font-bold text-amber-700">{m.periodization_title()}</p>
			<p class="mt-0.5 text-sm text-amber-700">
				{m.periodization_text({ name: dueRoutine.name, weeks: dueRoutine.weeks_active })}
			</p>
			<button
				type="button"
				disabled={bulkRenewalLoading || variationLoading !== null}
				onclick={() => (canRenewAll ? openBulkRenewal() : openVariation(dueRoutine.routine_id))}
				class="mt-2 h-10 rounded-2xl bg-amber-500 px-4 text-sm font-bold text-white active:bg-amber-600 disabled:opacity-50"
			>
				{canRenewAll ? m.renew_all_action({ count: renewableRoutines.length }) : m.renew_now()}
			</button>
		</div>
	</div>
{/if}

<!-- Detalhes do ciclo (validade) da rotina: inicio, validade e semanas -->
{#if selectedPeriod}
	<div
		class="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
		role="button"
		tabindex="-1"
		onclick={() => (selectedPeriod = null)}
		onkeydown={(e) => e.key === 'Escape' && (selectedPeriod = null)}
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
					<p class="text-xs font-bold uppercase tracking-wide text-slate-400">{m.cycle_title()}</p>
					<h2 class="truncate text-lg font-bold text-slate-900">{selectedPeriod.name}</h2>
				</div>
				<button
					type="button"
					aria-label={m.close()}
					onclick={() => (selectedPeriod = null)}
					class="grid h-9 w-9 shrink-0 place-items-center rounded-full bg-slate-100 text-slate-500 active:bg-slate-200"
				>
					<svg viewBox="0 0 24 24" class="h-5 w-5" fill="none" stroke="currentColor" stroke-width="2"><path d="M6 6l12 12M18 6L6 18" stroke-linecap="round" /></svg>
				</button>
			</div>

			<div class="grid grid-cols-2 gap-3">
				<div class="rounded-2xl bg-slate-50 p-3">
					<p class="text-xs font-semibold text-slate-500">{m.cycle_started()}</p>
					<p class="mt-0.5 font-bold text-slate-900">{fmtDate(selectedPeriod.started_on)}</p>
				</div>
				<div class="rounded-2xl p-3 {selectedPeriod.due ? 'bg-amber-50' : 'bg-slate-50'}">
					<p class="text-xs font-semibold {selectedPeriod.due ? 'text-amber-600' : 'text-slate-500'}">
						{m.cycle_valid_through()}
					</p>
					<p class="mt-0.5 font-bold {selectedPeriod.due ? 'text-amber-700' : 'text-slate-900'}">
						{fmtDate(selectedPeriod.renew_on)}
					</p>
				</div>
			</div>

			<p class="mt-3 text-sm text-slate-500">
				{#if selectedPeriod.due}
					{m.cycle_due_text({ weeks: selectedPeriod.weeks_active })}
				{:else}
					{m.cycle_active_text({
						active: selectedPeriod.weeks_active,
						remaining: selectedPeriod.weeks_remaining
					})}
				{/if}
			</p>

			<button
				type="button"
				onclick={() => {
					if (!selectedPeriod) return;
					const id = selectedPeriod.routine_id;
					selectedPeriod = null;
					openVariation(id);
				}}
				class="mt-4 flex h-12 w-full items-center justify-center gap-2 rounded-2xl font-bold text-white {selectedPeriod.due
					? 'bg-amber-500 active:bg-amber-600'
					: 'bg-emerald-600 active:bg-emerald-700'}"
			>
				<svg viewBox="0 0 24 24" class="h-5 w-5" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M4 17c5 0 5-10 11-10" /><path d="M4 7c5 0 5 10 11 10" /><path d="M12 4l3 3-3 3" /><path d="M12 20l3-3-3-3" /></svg>
				{m.cycle_renew_action()}
			</button>
			{#if selectedPeriod.due && canRenewAll}
				<button
					type="button"
					disabled={bulkRenewalLoading}
					onclick={openBulkRenewal}
					class="mt-2 h-12 w-full rounded-2xl border-2 border-amber-300 font-semibold text-amber-800 active:bg-amber-100 disabled:opacity-50"
				>
					{m.renew_all_action({ count: renewableRoutines.length })}
				</button>
			{/if}
		</div>
	</div>
{/if}

{#if showCalendar}
	<CalendarModal
		value={localDay()}
		marked={trainedDays}
		markedAlt={activityDaysSet}
		legend={m.calendar_legend_workout()}
		legendAlt={m.calendar_legend_activity()}
		max={localDay()}
		onselect={openDayWorkout}
		onclose={() => (showCalendar = false)}
	/>
{/if}

<!-- Treino do dia selecionado (somente visualizacao) -->
{#if dayWorkouts !== null}
	<div
		class="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
		role="button"
		tabindex="-1"
		onclick={closeDayWorkout}
		onkeydown={(e) => e.key === 'Escape' && closeDayWorkout()}
	>
		<div
			class="max-h-[90dvh] w-full max-w-md overflow-y-auto rounded-3xl bg-white p-6"
			role="dialog"
			tabindex="-1"
			onclick={(e) => e.stopPropagation()}
			onkeydown={() => {}}
		>
			<div class="mb-3 flex items-start justify-between">
				<h2 class="text-lg font-bold text-slate-900">
					{df.format(new Date(dayWorkoutDate + 'T12:00:00'))}
				</h2>
				<button
					type="button"
					aria-label={m.close()}
					onclick={closeDayWorkout}
					class="grid h-10 w-10 shrink-0 place-items-center rounded-full bg-slate-100 text-slate-500 active:bg-slate-200"
				>
					<svg viewBox="0 0 24 24" class="h-5 w-5" fill="none" stroke="currentColor" stroke-width="2"><path d="M6 6l12 12M18 6L6 18" stroke-linecap="round" /></svg>
				</button>
			</div>

			{#if dayWorkouts.length === 0 && dayActivities.length === 0}
				<p class="py-6 text-center text-sm text-slate-400">{m.no_entry_that_day()}</p>
			{:else}
				<div class="space-y-4">
					{#each dayWorkouts as workout (workout.session_id)}
						<div>
							<div class="flex items-start gap-2">
								<div class="min-w-0 flex-1">
									<p class="font-bold text-emerald-700">{workout.routine_name ?? m.free_workout()}</p>
									<p class="mb-2 text-xs text-slate-400">
										{workout.total_sets}
										{m.sets_label()}
									</p>
								</div>
								<button
									type="button"
									aria-label={m.delete_confirm_button()}
									onclick={() => (confirmingDayWorkout = workout.session_id)}
									class="grid h-8 w-8 shrink-0 place-items-center rounded-lg text-slate-300 active:bg-slate-100 active:text-red-500"
								>
									<svg viewBox="0 0 24 24" class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 7h16M9 7V5h6v2M6 7l1 13h10l1-13" stroke-linecap="round" stroke-linejoin="round" /></svg>
								</button>
							</div>
							{#if confirmingDayWorkout === workout.session_id}
								<div class="mb-2 flex items-center gap-2 rounded-xl bg-red-50 p-2">
									<p class="min-w-0 flex-1 text-xs font-semibold text-red-700">{m.confirm_delete()}</p>
									<button
										type="button"
										onclick={() => deleteDayWorkout(workout.session_id)}
										class="shrink-0 rounded-lg bg-red-600 px-3 py-1.5 text-xs font-bold text-white active:bg-red-700"
									>
										{m.delete_confirm_button()}
									</button>
									<button
										type="button"
										onclick={() => (confirmingDayWorkout = null)}
										class="shrink-0 rounded-lg px-2 py-1.5 text-xs font-semibold text-slate-500"
									>
										{m.cancel()}
									</button>
								</div>
							{/if}
							<div class="space-y-2">
								{#each workout.exercises as ex (ex.exercise_name)}
									<div class="rounded-2xl bg-slate-50 p-3">
										<p class="text-sm font-bold text-slate-800">{ex.exercise_name}</p>
										<div class="mt-1 flex flex-wrap gap-1.5">
											{#each ex.sets as set (set.set_number)}
												<span class="rounded-lg bg-white px-2 py-1 text-xs font-semibold text-slate-600">
													{#if ex.is_cardio}
														{set.duration_min} {m.minutes_short()}
													{:else}
														{nf.format(set.weight_kg)}kg × {set.reps}
													{/if}
												</span>
											{/each}
										</div>
									</div>
								{/each}
							</div>
						</div>
					{/each}

					<!-- Atividade avulsa do mesmo dia, na cor do calendario (azul) para
						 diferenciar do treino de academia sem separar em outra tela. -->
					{#if dayActivities.length > 0}
						<div>
							<p class="font-bold text-sky-700">{m.day_activities_title()}</p>
							<div class="mt-2 space-y-2">
								{#each dayActivities as activity (activity.id)}
									<div class="rounded-2xl bg-sky-50 p-3">
										<div class="flex items-start gap-2">
											<div class="min-w-0 flex-1">
												<p class="text-sm font-bold text-slate-800">{activityKindLabel(activity.kind)}</p>
												<p class="mt-0.5 text-xs text-slate-500">
													{activity.time_of_day} · {activity.duration_min}
													{m.minutes_short()}
													{#if activity.distance_km}· {nf.format(activity.distance_km)} km{/if}
													· {nf.format(Math.round(activity.kcal))} kcal
												</p>
											</div>
											<button
												type="button"
												aria-label={m.delete_confirm_button()}
												onclick={() => (confirmingDayActivity = activity.id)}
												class="grid h-8 w-8 shrink-0 place-items-center rounded-lg text-slate-400 active:bg-white active:text-red-500"
											>
												<svg viewBox="0 0 24 24" class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 7h16M9 7V5h6v2M6 7l1 13h10l1-13" stroke-linecap="round" stroke-linejoin="round" /></svg>
											</button>
										</div>
										{#if confirmingDayActivity === activity.id}
											<div class="mt-2 flex items-center gap-2 rounded-xl bg-red-50 p-2">
												<p class="min-w-0 flex-1 text-xs font-semibold text-red-700">{m.confirm_delete()}</p>
												<button
													type="button"
													onclick={() => deleteDayActivity(activity.id)}
													class="shrink-0 rounded-lg bg-red-600 px-3 py-1.5 text-xs font-bold text-white active:bg-red-700"
												>
													{m.delete_confirm_button()}
												</button>
												<button
													type="button"
													onclick={() => (confirmingDayActivity = null)}
													class="shrink-0 rounded-lg px-2 py-1.5 text-xs font-semibold text-slate-500"
												>
													{m.cancel()}
												</button>
											</div>
										{/if}
									</div>
								{/each}
							</div>
						</div>
					{/if}
				</div>
			{/if}
		</div>
	</div>
{/if}

{#snippet templatePicker()}
	<section class="rounded-3xl bg-white p-6 shadow-sm">
		<h2 class="text-lg font-bold text-slate-900">{m.no_routines_title()}</h2>
		<p class="mt-1 text-sm text-slate-500">{m.no_routines_text()}</p>
		<p class="mt-5 mb-2 text-sm font-semibold text-slate-600">{m.workout_level_label()}</p>
		<div class="grid grid-cols-3 gap-2">
			{#each ['beginner', 'intermediate', 'advanced'] as level (level)}
				<button
					type="button"
					disabled={creatingTemplate}
					aria-pressed={templateLevel === level}
					onclick={() => (templateLevel = level as RoutineDifficulty)}
					class="min-h-11 rounded-xl border px-2 text-xs font-semibold {templateLevel === level
						? 'workout-action border-emerald-700'
						: 'border-slate-200 bg-white text-slate-600'} disabled:opacity-50"
				>
					{level === 'advanced' ? m.level_expert() : levelLabel(level as 'beginner' | 'intermediate')}
				</button>
			{/each}
		</div>
		<p class="mt-4 mb-2 text-sm font-semibold text-slate-600">{m.workout_equipment_label()}</p>
		<div class="grid grid-cols-3 gap-2">
			{#each ['free_weights', 'machines', 'mixed'] as equipmentMode (equipmentMode)}
				<button
					type="button"
					disabled={creatingTemplate}
					aria-pressed={templateEquipment === equipmentMode}
					onclick={() => (templateEquipment = equipmentMode as WorkoutEquipmentMode)}
					class="min-h-11 rounded-xl border px-2 text-xs font-semibold {templateEquipment === equipmentMode
						? 'workout-action border-emerald-700'
						: 'border-slate-200 bg-white text-slate-600'} disabled:opacity-50"
				>
					{equipmentMode === 'free_weights'
						? m.workout_equipment_free_weights()
						: equipmentMode === 'machines'
							? m.workout_equipment_machines()
							: m.workout_equipment_mixed()}
				</button>
			{/each}
		</div>
		<p class="mt-5 mb-2 text-sm font-semibold text-slate-600">{m.pick_frequency()}</p>
		<div class="grid grid-cols-2 gap-2">
			{#each [2, 3, 4, 5] as freq (freq)}
				<button
					type="button"
					disabled={creatingTemplate}
					onclick={() => useTemplate(freq)}
					class="min-h-16 rounded-2xl border-2 border-emerald-100 bg-emerald-50 p-3 text-left font-bold text-emerald-800 active:bg-emerald-100 disabled:opacity-50"
				>
					<span class="block text-xl">{freq}×</span>
					<span class="text-xs font-medium text-emerald-600">{m.days_per_week()}</span>
				</button>
			{/each}
		</div>
		{#if addWorkoutStep === 'template'}
			<p class="mt-3 text-xs text-slate-400">{m.template_adds_hint()}</p>
			<!-- volta para a escolha, nao fecha tudo: quem entrou por "Comecar rapido"
				 pode trocar para "Montar do zero" sem reabrir a modal -->
			<button
				type="button"
				onclick={() => (addWorkoutStep = 'choose')}
				class="mt-2 text-sm font-semibold text-slate-500"
			>
				{m.cancel()}
			</button>
		{/if}
	</section>
{/snippet}

<!-- Primeiro passo de "Novo treino": um botao so na tela, e a escolha de COMO
	 montar acontece aqui, com o que cada caminho faz escrito por extenso. -->
{#snippet addWorkoutChooser()}
	<section class="rounded-3xl bg-white p-6 shadow-sm">
		<h2 class="text-lg font-bold text-slate-900">{m.add_workout_how()}</h2>
		<div class="mt-4 grid gap-2">
			<button
				type="button"
				onclick={() => (addWorkoutStep = 'template')}
				class="min-h-16 rounded-2xl border-2 border-emerald-100 bg-emerald-50 p-3 text-left font-bold text-emerald-800 active:bg-emerald-100"
			>
				<span class="block text-base">{m.add_workout_quick()}</span>
				<span class="mt-0.5 block text-xs font-medium text-emerald-600">
					{m.add_workout_quick_text()}
				</span>
			</button>
			<a
				href="/treino/rotina/nova"
				class="block min-h-16 rounded-2xl border-2 border-emerald-100 bg-emerald-50 p-3 text-left font-bold text-emerald-800 active:bg-emerald-100"
			>
				<span class="block text-base">{m.add_workout_scratch()}</span>
				<span class="mt-0.5 block text-xs font-medium text-emerald-600">
					{m.add_workout_scratch_text()}
				</span>
			</a>
		</div>
		<button
			type="button"
			onclick={() => (addWorkoutStep = null)}
			class="mt-3 text-sm font-semibold text-slate-500"
		>
			{m.cancel()}
		</button>
	</section>
{/snippet}

{#if loading}
	<SkeletonScreen cards={3} cardLines={2} />
{:else}
	{#if activeSession}
		<section class="mb-3 rounded-3xl bg-emerald-600 p-5 text-white shadow-sm">
			<p class="text-sm font-semibold text-emerald-100">{m.workout_in_progress()}</p>
			<p class="truncate text-lg font-bold">{activeSession.routine_name ?? m.free_workout()}</p>
			{#if confirmingDiscard}
				<p class="mt-3 text-sm text-emerald-50">{m.confirm_delete()}</p>
				<div class="mt-2 flex gap-2">
					<button
						type="button"
						onclick={() => (confirmingDiscard = false)}
						class="h-11 flex-1 rounded-2xl bg-white font-bold text-emerald-700 active:bg-emerald-50"
					>
						{m.cancel()}
					</button>
					<button
						type="button"
						onclick={discardActive}
						class="h-11 flex-1 rounded-2xl border-2 border-emerald-300 font-semibold text-white active:bg-emerald-700"
					>
						{m.delete_confirm_button()}
					</button>
				</div>
			{:else}
				<div class="mt-3 flex gap-2">
					<a
						href="/treino/sessao/{activeSession.id}"
						class="flex h-11 flex-[2] items-center justify-center rounded-2xl bg-white font-bold text-emerald-700 active:bg-emerald-50"
					>
						{m.resume_workout()}
					</a>
					<button
						type="button"
						onclick={() => (confirmingDiscard = true)}
						class="h-11 flex-1 rounded-2xl border-2 border-emerald-400 font-semibold text-white active:bg-emerald-700"
					>
						{m.discard()}
					</button>
				</div>
			{/if}
		</section>
	{/if}
	{#if routines.length === 0}
		<div data-tour="workout-create">{@render templatePicker()}</div>
		<div class="mt-3 text-center">
			<a href="/treino/rotina/nova" class="text-sm font-semibold text-emerald-700">
				{m.create_routine_manual()}
			</a>
		</div>
	{:else}
		{#if addWorkoutStep}
			<div
				class="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
				role="button"
				tabindex="-1"
				onclick={() => (addWorkoutStep = null)}
				onkeydown={(e) => e.key === 'Escape' && (addWorkoutStep = null)}
			>
				<div
					class="w-full max-w-md"
					role="dialog"
					tabindex="-1"
					onclick={(e) => e.stopPropagation()}
					onkeydown={() => {}}
				>
					{#if addWorkoutStep === 'choose'}
						{@render addWorkoutChooser()}
					{:else}
						{@render templatePicker()}
					{/if}
				</div>
			</div>
		{/if}
		{#snippet periodPill(routine: Routine)}
			{@const period = periodizationFor(routine.id)}
			{#if period}
				<button
					type="button"
					onclick={() => (selectedPeriod = period)}
					class="mt-1.5 inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-semibold {period.due
						? 'bg-amber-50 text-amber-700'
						: 'bg-slate-100 text-slate-500'}"
				>
					<svg viewBox="0 0 24 24" class="h-3.5 w-3.5" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="4" width="18" height="17" rx="2" /><path d="M3 9h18M8 2v4M16 2v4" stroke-linecap="round" /></svg>
					{#if period.due}
						{m.cycle_renew_badge()}
					{:else}
						{m.cycle_valid_until({ date: fmtDate(period.renew_on) })}
					{/if}
				</button>
			{/if}
		{/snippet}

		{#snippet routineTools(routine: Routine)}
			<div class="flex shrink-0 items-center gap-3">
				{#if routine.items.length > 0}
					<button
						type="button"
						aria-label={m.vary_this_workout()}
						title={m.vary_this_workout()}
						disabled={variationLoading === routine.id}
						onclick={() => openVariation(routine.id)}
						class="grid h-9 w-9 place-items-center rounded-full text-emerald-700 active:bg-emerald-50 disabled:opacity-50"
					>
						<svg viewBox="0 0 24 24" class="h-5 w-5" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M4 4v6h6M20 20v-6h-6M20 8a8 8 0 00-14-3M4 16a8 8 0 0014 3" /></svg>
					</button>
				{/if}
				<a
					href="/treino/rotina/{routine.id}"
					aria-label={m.edit()}
					title={m.edit()}
					class="grid h-9 w-9 place-items-center rounded-full text-slate-400 active:bg-slate-100"
				>
					<svg viewBox="0 0 24 24" class="h-5 w-5" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 20h9M16.5 3.5a2.1 2.1 0 013 3L7 19l-4 1 1-4z" /></svg>
				</a>
			</div>
		{/snippet}

		{#snippet routineThumbs(routine: Routine)}
			{#if routine.items.length > 0}
				<button
					type="button"
					aria-label={m.view_workout_details()}
					title={m.view_workout_details()}
					onclick={() => (previewRoutine = routine)}
					class="mt-3 flex w-full items-center gap-1.5 text-left"
				>
					{#each routine.items.slice(0, 4) as item (item.id)}
						{#if item.exercise.media_urls.length > 0}
							<img
								src={item.exercise.media_urls[0]}
								alt={item.exercise.name}
								title={item.exercise.name}
								loading="lazy"
								class="h-12 w-12 rounded-xl border border-slate-100 object-cover"
							/>
						{:else}
							<span
								class="grid h-12 w-12 place-items-center rounded-xl bg-slate-100 text-xs font-bold text-slate-400"
							>
								{item.exercise.name.slice(0, 2)}
							</span>
						{/if}
					{/each}
					{#if routine.items.length > 4}
						<span class="grid h-12 w-12 place-items-center rounded-xl bg-slate-100 text-xs font-bold text-slate-500">
							+{routine.items.length - 4}
						</span>
					{/if}
					<span class="ml-auto grid h-9 w-9 shrink-0 place-items-center text-emerald-700">
						<svg viewBox="0 0 24 24" class="h-5 w-5" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="3" /><path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7-10-7-10-7z" /></svg>
					</span>
				</button>
			{/if}
		{/snippet}

		{#snippet routineActions(routine: Routine, primary: boolean)}
			{#if !activeSession}
				<!-- com sessao ativa, os botoes somem: nao da pra iniciar de novo -->
				{#if confirmingStart === routine.id}
					<div class="mt-4 flex items-center gap-2 rounded-2xl bg-emerald-50 p-2">
						<span class="min-w-0 flex-1 pl-2 text-sm font-semibold text-emerald-800">{m.workout_start_confirm()}</span>
						<button
							type="button"
							onclick={() => start(routine.id)}
							class="h-10 shrink-0 rounded-xl bg-emerald-600 px-4 font-bold text-white active:bg-emerald-700"
						>
							{m.start_workout()}
						</button>
						<button
							type="button"
							onclick={() => (confirmingStart = null)}
							class="h-10 shrink-0 rounded-xl px-3 text-sm font-semibold text-slate-500 active:bg-slate-100"
						>
							{m.cancel()}
						</button>
					</div>
				{:else if confirmingDone === routine.id}
					<!-- confirmar + escolher o dia: por padrao hoje, mas da pra lancar
						 um treino que a pessoa fez e esqueceu de registrar -->
					<div class="mt-4 rounded-2xl bg-emerald-50 p-3">
						<p class="pl-1 text-sm font-semibold text-emerald-800">{m.workout_done_confirm()}</p>
						<label
							class="mt-2.5 block pl-1 text-[11px] font-bold text-emerald-700"
							for="done-day-{routine.id}"
						>
							{m.workout_done_date_label()}
						</label>
						<input
							id="done-day-{routine.id}"
							type="date"
							bind:value={doneDay}
							max={localDay()}
							class="mt-1 h-11 w-full rounded-xl border-2 px-3 text-center font-bold text-slate-900 {doneDay !==
							localDay()
								? 'border-amber-300 bg-amber-50'
								: 'border-emerald-200 bg-white'}"
						/>
						<div class="mt-2.5 flex gap-2">
							<button
								type="button"
								onclick={() => markDone(routine.id)}
								class="h-10 flex-1 rounded-xl bg-emerald-600 px-4 font-bold text-white active:bg-emerald-700"
							>
								{m.mark_done()}
							</button>
							<button
								type="button"
								onclick={() => (confirmingDone = null)}
								class="h-10 shrink-0 rounded-xl px-3 text-sm font-semibold text-slate-500 active:bg-slate-100"
							>
								{m.cancel()}
							</button>
						</div>
					</div>
				{:else}
					<!-- so o PROXIMO tem botao cheio: primario repetido em todo cartao
						 deixa de ser primario -->
					<div class="mt-4 flex gap-2">
						<button
							type="button"
							onclick={() => (confirmingStart = routine.id)}
							disabled={routine.items.length === 0}
							class="h-12 flex-[2] rounded-2xl font-bold disabled:opacity-40 {primary
								? 'bg-emerald-600 text-white active:bg-emerald-700'
								: 'border-2 border-emerald-200 text-emerald-700 active:bg-emerald-50'}"
						>
							{m.start_workout()}
						</button>
						<button
							type="button"
							onclick={() => openDoneConfirm(routine.id)}
							disabled={routine.items.length === 0 || completingId === routine.id}
							class="h-12 flex-1 rounded-2xl border-2 border-slate-200 font-semibold text-slate-600 active:bg-slate-50 disabled:opacity-40"
						>
							{completingId === routine.id ? '…' : m.mark_done()}
						</button>
					</div>
				{/if}
			{/if}
		{/snippet}

		<!-- Oferta de limpar o ciclo anterior. So aparece com sinal real de programa
			 novo, e "Manter" e dispensa definitiva para este conjunto de vencidas. -->
		{#if showArchiveOffer}
			<section class="mb-3 rounded-3xl border-2 border-amber-200 bg-amber-50 p-4">
				<h2 class="font-bold text-amber-900">{m.archive_offer_title()}</h2>
				<p class="mt-1 text-sm text-amber-800">
					{m.archive_offer_body({ count: staleRoutines.length })}
				</p>
				<div class="mt-3 flex gap-2">
					<button
						type="button"
						onclick={dismissArchiveOffer}
						class="h-11 flex-1 rounded-2xl border-2 border-amber-300 font-semibold text-amber-800 active:bg-amber-100"
					>
						{m.archive_offer_keep()}
					</button>
					<button
						type="button"
						disabled={archiveBusy}
						onclick={() => archiveAll(staleRoutines.map((p) => p.routine_id))}
						class="h-11 flex-1 rounded-2xl bg-amber-600 font-semibold text-white active:bg-amber-700 disabled:opacity-50"
					>
						{m.archive_offer_confirm()}
					</button>
				</div>
			</section>
		{/if}

		<!-- O PROXIMO do ciclo em destaque: abre a tela, aperta um botao, zero decisao.
			 Some quando ha treino em andamento (o cartao de retomar ja e o principal). -->
		{#if nextRoutine && !activeSession}
			{@const lastWhen =
				lastFinishedWithRoutine?.routine_id != null
					? recencyLabel(lastFinishedWithRoutine.routine_id)
					: null}
			<section
				data-tour="workout-next"
				class="relative mb-3 rounded-3xl border-2 border-emerald-500 bg-white p-5 shadow-sm"
			>
				<span class="absolute -top-3 left-4 rounded-full bg-emerald-600 px-2.5 py-1 text-[10px] font-black tracking-wider text-white uppercase">
					{m.next_workout_badge()}
				</span>
				<div class="mt-1 flex items-start justify-between gap-2">
					<div class="min-w-0">
						<h2 class="truncate text-lg font-bold text-slate-900">{nextRoutine.name}</h2>
						<p class="text-sm text-slate-500">
							{nextRoutine.items.length}
							{nextRoutine.items.length === 1 ? m.exercise_singular() : m.exercise_plural()}
						</p>
						{@render periodPill(nextRoutine)}
						{#if lastFinishedWithRoutine && lastWhen}
							<!-- o MOTIVO de este ser o proximo, escrito -->
							<p class="mt-1.5 text-xs font-semibold text-slate-500">
								{m.last_workout_line({
									name: lastFinishedWithRoutine.routine_name ?? m.free_workout(),
									when: lastWhen
								})}
							</p>
						{/if}
					</div>
					{@render routineTools(nextRoutine)}
				</div>
				{@render routineThumbs(nextRoutine)}
				{@render routineActions(nextRoutine, true)}
			</section>
		{/if}

		<div class="space-y-3">
			{#each routines as routine (routine.id)}
				{#if !(nextRoutine && !activeSession && routine.id === nextRoutine.id)}
					{@const isOpen = expandedRoutine === routine.id}
					{@const recency = recencyLabel(routine.id)}
					<!-- compacta: nome + quando foi a ultima vez. Tocar expande o cartao
						 completo (miniaturas, variacao, edicao, periodizacao, iniciar). -->
					<section class="overflow-hidden rounded-3xl bg-white shadow-sm">
						<button
							type="button"
							onclick={() => (expandedRoutine = isOpen ? null : routine.id)}
							class="flex w-full items-center gap-2.5 p-4 text-left"
						>
							<div class="min-w-0 flex-1">
								<h2 class="truncate font-bold text-slate-900">{routine.name}</h2>
								<p class="text-xs text-slate-500">
									{routine.items.length}
									{routine.items.length === 1 ? m.exercise_singular() : m.exercise_plural()}
								</p>
							</div>
							{#if recency}
								<span class="shrink-0 rounded-full bg-emerald-100 px-2 py-0.5 text-xs font-bold text-emerald-700">
									✓ {recency}
								</span>
							{/if}
							<svg viewBox="0 0 24 24" class="h-5 w-5 shrink-0 text-slate-300 transition-transform {isOpen ? 'rotate-180' : ''}" fill="none" stroke="currentColor" stroke-width="2"><path d="M6 9l6 6 6-6" stroke-linecap="round" stroke-linejoin="round" /></svg>
						</button>
						{#if isOpen}
							<div class="px-4 pb-4" transition:slide={{ duration: 200 }}>
								<div class="flex items-center justify-between gap-2">
									<div>{@render periodPill(routine)}</div>
									{@render routineTools(routine)}
								</div>
								{@render routineThumbs(routine)}
								{@render routineActions(routine, false)}
							</div>
						{/if}
					</section>
				{/if}
			{/each}
		</div>

		<button
			type="button"
			data-tour="workout-create"
			onclick={() => (addWorkoutStep = 'choose')}
			class="mt-3 flex h-12 w-full items-center justify-center rounded-2xl border-2 border-slate-200 bg-white font-semibold text-slate-700 active:bg-slate-100"
		>
			{m.new_workout()}
		</button>

		<!-- Trocar o programa inteiro (o ABC sai junto) numa acao so, em vez de
			 arquivar rotina por rotina. Acao de impacto: confirma antes. -->
		{#if routines.length >= 2}
			{#if confirmingArchiveAll}
				<p class="mt-3 rounded-xl bg-slate-100 px-4 py-3 text-sm font-medium text-slate-700">
					{m.archive_current_routines_confirm({ count: routines.length })}
				</p>
				<div class="mt-2 flex gap-2">
					<button
						type="button"
						onclick={() => (confirmingArchiveAll = false)}
						class="h-12 flex-1 rounded-2xl border-2 border-slate-200 font-semibold text-slate-700 active:bg-slate-100"
					>
						{m.cancel()}
					</button>
					<button
						type="button"
						disabled={archiveBusy}
						onclick={() => archiveAll(routines.map((r) => r.id))}
						class="h-12 flex-1 rounded-2xl bg-slate-700 font-semibold text-white active:bg-slate-800 disabled:opacity-50"
					>
						{m.archive_current_routines()}
					</button>
				</div>
			{:else}
				<button
					type="button"
					onclick={() => (confirmingArchiveAll = true)}
					class="mt-3 flex w-full items-center justify-center gap-2 rounded-2xl border-2 border-dashed border-slate-300 bg-white py-3 text-sm font-bold text-slate-700 active:bg-slate-50"
				>
					<svg viewBox="0 0 24 24" class="h-4.5 w-4.5 text-slate-500" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 7h18v4H3zM5 11v9h14v-9M10 15h4" /></svg>
					{m.archive_current_routines()}
				</button>
			{/if}
		{/if}
	{/if}

	<!-- Rotinas fora do ciclo: ficam guardadas para consultar, reativar ou excluir.
	     A lista vive fechada (accordion) porque e area de consulta rara: quem tem
	     muitas rotinas arquivadas nao quer rolar por elas toda vez que abre a tela. -->
	{#if archivedRoutines.length > 0 || demoArchivedActive}
		<section class="mt-6" data-tour="workout-archived">
			<button
				type="button"
				onclick={() => (archivedExpanded = !archivedExpanded)}
				class="flex w-full items-center gap-2 py-1 text-sm font-bold text-slate-500 uppercase active:opacity-70"
			>
				<svg viewBox="0 0 24 24" class="h-4 w-4 shrink-0 transition-transform {archivedOpen ? 'rotate-90' : ''}" fill="none" stroke="currentColor" stroke-width="2"><path d="M9 6l6 6-6 6" stroke-linecap="round" stroke-linejoin="round" /></svg>
				{m.archived_routines()} ({displayArchived.length})
			</button>
			{#if archivedOpen}
				<div class="mt-2 overflow-hidden rounded-3xl bg-white shadow-sm">
					{#each displayArchived as routine, i (routine.id)}
						<div class="px-4 py-3 {i > 0 ? 'border-t border-slate-100' : ''}">
							<div class="flex items-center gap-2">
								<div class="min-w-0 flex-1">
									<h3 class="truncate font-semibold text-slate-900">{routine.name}</h3>
									<p class="text-xs text-slate-500">
										{routine.items.length}
										{routine.items.length === 1 ? m.exercise_singular() : m.exercise_plural()}
										{#if routine.archived_at}
											· {m.archived_on({ date: df.format(new Date(routine.archived_at)) })}
										{/if}
									</p>
								</div>
								{#if routine.items.length > 0}
									<button
										type="button"
										aria-label={m.view_workout_details()}
										title={m.view_workout_details()}
										onclick={() => (previewRoutine = routine)}
										class="grid h-8 w-8 shrink-0 place-items-center rounded-full text-slate-400 active:bg-slate-100"
									>
										<svg viewBox="0 0 24 24" class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="3" /><path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7-10-7-10-7z" /></svg>
									</button>
								{/if}
								<button
									type="button"
									onclick={() => {
										confirmingDeleteArchived = null;
										confirmingUnarchive = routine.id;
									}}
									class="shrink-0 rounded-xl border-2 border-emerald-200 px-3 py-1.5 text-xs font-bold text-emerald-700 active:bg-emerald-50"
								>
									{m.unarchive_routine()}
								</button>
								<button
									type="button"
									aria-label={m.delete_confirm_button()}
									title={m.delete_confirm_button()}
									onclick={() => {
										confirmingUnarchive = null;
										confirmingDeleteArchived = routine.id;
									}}
									class="grid h-8 w-8 shrink-0 place-items-center rounded-full text-red-500 active:bg-red-50"
								>
									<svg viewBox="0 0 24 24" class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 6h18M8 6V4h8v2M6 6l1 14h10l1-14" stroke-linecap="round" stroke-linejoin="round" /></svg>
								</button>
							</div>
							{#if confirmingUnarchive === routine.id}
								<p class="mt-3 rounded-xl bg-slate-100 px-4 py-3 text-sm font-medium text-slate-700">
									{m.unarchive_routine_confirm()}
								</p>
								<div class="mt-2 flex gap-2">
									<button
										type="button"
										onclick={() => (confirmingUnarchive = null)}
										class="h-11 flex-1 rounded-2xl border-2 border-slate-200 font-semibold text-slate-700 active:bg-slate-100"
									>
										{m.cancel()}
									</button>
									<button
										type="button"
										disabled={archiveBusy}
										onclick={() => unarchive(routine.id)}
										class="h-11 flex-1 rounded-2xl bg-emerald-600 font-semibold text-white active:bg-emerald-700 disabled:opacity-50"
									>
										{m.unarchive_routine()}
									</button>
								</div>
							{:else if confirmingDeleteArchived === routine.id}
								<p class="mt-3 rounded-xl bg-red-50 px-4 py-3 text-sm font-medium text-red-700">
									{m.confirm_delete()}
								</p>
								<div class="mt-2 flex gap-2">
									<button
										type="button"
										onclick={() => (confirmingDeleteArchived = null)}
										class="h-11 flex-1 rounded-2xl border-2 border-slate-200 font-semibold text-slate-700 active:bg-slate-100"
									>
										{m.cancel()}
									</button>
									<button
										type="button"
										disabled={archiveBusy}
										onclick={() => deleteArchived(routine.id)}
										class="h-11 flex-1 rounded-2xl bg-red-600 font-semibold text-white active:bg-red-700 disabled:opacity-50"
									>
										{m.delete_confirm_button()}
									</button>
								</div>
							{/if}
						</div>
					{/each}
				</div>
			{/if}
		</section>
	{/if}

	{#if finishedSessions.length > 0 || demoHistoryActive}
		<section class="mt-6" data-tour="workout-history">
			<h2 class="mb-2 text-sm font-bold text-slate-500 uppercase">{m.workout_history()}</h2>
			<div class="overflow-hidden rounded-3xl bg-white shadow-sm">
				{#each visibleHistory as session, i (session.id)}
					<div class="flex items-center gap-2 px-5 py-3.5 {i > 0 ? 'border-t border-slate-100' : ''}">
						<div class="min-w-0 flex-1">
							<p class="truncate font-semibold text-slate-900">{session.routine_name ?? m.free_workout()}</p>
							<p class="text-sm text-slate-500">
								{session.total_sets}
								{m.sets_label()}
							</p>
						</div>
						{#if confirmingDeleteHistory === session.id}
							<button
								type="button"
								onclick={() => deleteHistory(session.id)}
								class="shrink-0 rounded-xl bg-red-600 px-3 py-1.5 text-xs font-bold text-white active:bg-red-700"
							>
								{m.delete_confirm_button()}
							</button>
							<button
								type="button"
								onclick={() => (confirmingDeleteHistory = null)}
								class="shrink-0 rounded-xl px-2 py-1.5 text-xs font-semibold text-slate-500"
							>
								{m.cancel()}
							</button>
						{:else}
							<span class="shrink-0 text-sm text-slate-400">{df.format(new Date(session.started_at))}</span>
							<button
								type="button"
								aria-label={m.confirm_delete()}
								onclick={() => (confirmingDeleteHistory = session.id)}
								class="grid h-8 w-8 shrink-0 place-items-center rounded-lg text-slate-300 active:bg-slate-100 active:text-red-500"
							>
								<svg viewBox="0 0 24 24" class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 7h16M9 7V5h6v2M6 7l1 13h10l1-13" stroke-linecap="round" stroke-linejoin="round" /></svg>
							</button>
						{/if}
					</div>
				{/each}
				{#if finishedSessions.length > HISTORY_PREVIEW}
					<button
						type="button"
						onclick={() => (historyExpanded = !historyExpanded)}
						class="w-full border-t border-slate-100 py-3 text-sm font-bold text-emerald-700 active:bg-slate-50"
					>
						{historyExpanded
							? m.show_less()
							: m.show_more_count({ count: finishedSessions.length - HISTORY_PREVIEW })}
					</button>
				{/if}
			</div>
		</section>
	{/if}

	<!-- Atividades avulsas de hoje: fica junto do historico de treino, no final da tela -->
	{#if todayActivities.length > 0}
		<section class="mt-6">
			<div class="mb-2 flex items-center justify-between rounded-2xl bg-slate-900 px-4 py-3">
				<span class="text-xs font-bold tracking-wide text-slate-300 uppercase">{m.activity_today_total()}</span>
				<span class="text-lg font-black text-white">+{nf.format(Math.round(activityKcalTotal))} kcal</span>
			</div>
			<div class="overflow-hidden rounded-3xl bg-white shadow-sm">
				{#each todayActivities as activity, i (activity.id)}
					<div class="flex items-center gap-2 px-5 py-3.5 {i > 0 ? 'border-t border-slate-100' : ''}">
						<div class="min-w-0 flex-1">
							<p class="truncate font-semibold text-slate-900">{activityKindLabel(activity.kind)}</p>
							<p class="text-sm text-slate-500">
								{activity.time_of_day} · {activity.duration_min} min · {nf.format(Math.round(activity.kcal))} kcal
							</p>
						</div>
						{#if confirmingDeleteActivity === activity.id}
							<button
								type="button"
								onclick={() => deleteActivityEntry(activity.id)}
								class="shrink-0 rounded-xl bg-red-600 px-3 py-1.5 text-xs font-bold text-white active:bg-red-700"
							>
								{m.confirm_delete()}
							</button>
							<button
								type="button"
								onclick={() => (confirmingDeleteActivity = null)}
								class="shrink-0 rounded-xl px-2 py-1.5 text-xs font-semibold text-slate-500"
							>
								{m.cancel()}
							</button>
						{:else}
							<button
								type="button"
								aria-label={m.confirm_delete()}
								onclick={() => (confirmingDeleteActivity = activity.id)}
								class="grid h-8 w-8 shrink-0 place-items-center rounded-lg text-slate-300 active:bg-slate-100 active:text-red-500"
							>
								<svg viewBox="0 0 24 24" class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 7h16M9 7V5h6v2M6 7l1 13h10l1-13" stroke-linecap="round" stroke-linejoin="round" /></svg>
							</button>
						{/if}
					</div>
				{/each}
			</div>
		</section>
	{/if}
{/if}

<!-- Explorar a rotina (leitura) antes de iniciar -->
{#if previewRoutine}
	<div
		class="fixed inset-0 z-40 flex items-center justify-center bg-black/50 p-4"
		role="button"
		tabindex="-1"
		onclick={() => (previewRoutine = null)}
		onkeydown={(e) => e.key === 'Escape' && (previewRoutine = null)}
	>
		<div
			class="flex max-h-[85dvh] w-full max-w-md flex-col rounded-3xl bg-white p-5"
			role="dialog"
			tabindex="-1"
			onclick={(e) => e.stopPropagation()}
			onkeydown={() => {}}
		>
			<div class="mb-3 flex items-center justify-between gap-2">
				<h2 class="truncate text-lg font-bold text-slate-900">{previewRoutine.name}</h2>
				<button
					type="button"
					aria-label={m.back()}
					onclick={() => (previewRoutine = null)}
					class="grid h-9 w-9 shrink-0 place-items-center rounded-full bg-slate-100 text-slate-500 active:bg-slate-200"
				>
					<svg viewBox="0 0 24 24" class="h-5 w-5" fill="none" stroke="currentColor" stroke-width="2"><path d="M6 6l12 12M18 6L6 18" stroke-linecap="round" /></svg>
				</button>
			</div>
			<div class="space-y-2 overflow-y-auto">
				{#each previewRoutine.items as item (item.id)}
					<button
						type="button"
						onclick={() => (photoOf = item.exercise)}
						class="flex w-full items-center gap-3 rounded-2xl bg-slate-50 p-2 text-left active:bg-slate-100"
					>
						<span class="grid h-14 w-14 shrink-0 place-items-center overflow-hidden rounded-xl bg-slate-100">
							{#if item.exercise.media_urls.length > 0}
								<img src={item.exercise.media_urls[0]} alt="" class="h-full w-full object-cover" loading="lazy" />
							{:else}
								<svg viewBox="0 0 24 24" class="h-5 w-5 text-slate-400" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="3" /><path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7-10-7-10-7z" /></svg>
							{/if}
						</span>
						<div class="min-w-0 flex-1">
							<p class="truncate font-bold text-slate-900">{item.exercise.name}</p>
							<p class="text-sm text-slate-500">
								{#if item.exercise.kind === 'cardio'}
									{m.cardio_label()}{#if item.target_duration_min} · {item.target_duration_min} {m.minutes_short()}{/if}
								{:else}
									{item.target_sets} × {item.target_reps}{#if item.last_weight_kg !== null} · {m.last_time()}: {item.last_weight_kg} kg{/if}
								{/if}
							</p>
						</div>
						<svg viewBox="0 0 24 24" class="h-4 w-4 shrink-0 text-slate-300" fill="none" stroke="currentColor" stroke-width="2"><path d="M9 6l6 6-6 6" stroke-linecap="round" stroke-linejoin="round" /></svg>
					</button>
				{/each}
			</div>
			<!-- rotina arquivada e so consulta: para treinar de novo, reativar antes -->
			{#if !previewRoutine.archived_at}
				<button
					type="button"
					onclick={startFromPreview}
					class="mt-3 h-12 w-full shrink-0 rounded-2xl bg-emerald-600 font-bold text-white active:bg-emerald-700"
				>
					{m.start_workout()}
				</button>
			{/if}
		</div>
	</div>
{/if}

{#if variationSetupOpen}
	<div class="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4" role="presentation">
		<div class="w-full max-w-md rounded-3xl bg-white p-5 shadow-xl" role="dialog" aria-modal="true" aria-labelledby="variation-setup-title">
			<h2 id="variation-setup-title" class="text-lg font-bold text-slate-900">
				{variationSetupMode === 'single' ? m.vary_title() : m.renew_all_title()}
			</h2>
			<p class="mt-1 text-sm text-slate-500">{m.routine_generation_preferences_title()}</p>
			{#if variationSetupMode === 'single'}
				<p class="mt-1 text-sm font-semibold text-slate-700">{allRoutines.find((routine) => routine.id === variationSourceId)?.name}</p>
			{:else}
				<p class="mt-3 text-sm font-semibold text-slate-700">{m.renew_select_intro()}</p>
				<div class="mt-2 max-h-36 space-y-1 overflow-y-auto">
					{#each renewableRoutines as period (period.routine_id)}
						<label class="flex min-h-11 items-center gap-3 rounded-xl bg-slate-50 px-3 text-sm text-slate-800">
							<input type="checkbox" disabled={bulkRenewalLoading} checked={selectedRenewalIds.includes(period.routine_id)} onchange={() => toggleRenewalSelection(period.routine_id)} />
							<span class="truncate">{period.name}</span>
						</label>
					{/each}
				</div>
			{/if}
			<p class="mt-4 mb-2 text-sm font-semibold text-slate-600">{m.workout_level_label()}</p>
			<div class="grid grid-cols-3 gap-2">
				{#each ['beginner', 'intermediate', 'advanced'] as level (level)}
					<button type="button" disabled={variationLoading !== null || bulkRenewalLoading} aria-pressed={variationLevel === level} onclick={() => (variationLevel = level as RoutineDifficulty)} class="min-h-11 rounded-xl border px-2 text-xs font-semibold {variationLevel === level ? 'workout-action border-emerald-700' : 'border-slate-200 bg-white text-slate-600'} disabled:opacity-50">
						{level === 'advanced' ? m.level_expert() : levelLabel(level as 'beginner' | 'intermediate')}
					</button>
				{/each}
			</div>
			<p class="mt-4 mb-2 text-sm font-semibold text-slate-600">{m.workout_equipment_label()}</p>
			<div class="grid grid-cols-3 gap-2">
				{#each ['free_weights', 'machines', 'mixed'] as equipmentMode (equipmentMode)}
					<button type="button" disabled={variationLoading !== null || bulkRenewalLoading} aria-pressed={variationEquipment === equipmentMode} onclick={() => (variationEquipment = equipmentMode as WorkoutEquipmentMode)} class="min-h-11 rounded-xl border px-2 text-xs font-semibold {variationEquipment === equipmentMode ? 'workout-action border-emerald-700' : 'border-slate-200 bg-white text-slate-600'} disabled:opacity-50">
						{equipmentMode === 'free_weights' ? m.workout_equipment_free_weights() : equipmentMode === 'machines' ? m.workout_equipment_machines() : m.workout_equipment_mixed()}
					</button>
				{/each}
			</div>
			<div class="mt-5 flex gap-2">
				<button type="button" disabled={variationLoading !== null || bulkRenewalLoading} onclick={() => (variationSetupOpen = false)} class="h-12 flex-1 rounded-2xl border-2 border-slate-200 font-semibold text-slate-700">{m.cancel()}</button>
				<button type="button" disabled={variationLoading !== null || bulkRenewalLoading || (variationSetupMode === 'bulk' && selectedRenewalIds.length === 0)} onclick={generateVariationPreview} class="workout-action h-12 flex-1 rounded-2xl font-bold disabled:opacity-50">
					{variationLoading !== null || bulkRenewalLoading ? m.routine_applying() : m.routine_preview_action()}
				</button>
			</div>
		</div>
	</div>
{/if}

<!-- Variar o treino: previa (de -> para) e escolher usar hoje ou salvar -->
{#if variation}
	<div
		class="fixed inset-0 z-40 flex items-center justify-center bg-black/50 p-4"
		role="button"
		tabindex="-1"
		onclick={closeVariation}
		onkeydown={(e) => e.key === 'Escape' && closeVariation()}
	>
		<div
			class="flex max-h-[85dvh] w-full max-w-md flex-col rounded-3xl bg-white p-5"
			role="dialog"
			tabindex="-1"
			onclick={(e) => e.stopPropagation()}
			onkeydown={() => {}}
		>
			<div class="mb-1 flex items-center justify-between gap-2">
				<h2 class="truncate text-lg font-bold text-slate-900">{m.vary_title()}</h2>
				<button
					type="button"
					aria-label={m.back()}
					disabled={variationBusy || variationApplyUnknown}
					onclick={closeVariation}
					class="grid h-9 w-9 shrink-0 place-items-center rounded-full bg-slate-100 text-slate-500 active:bg-slate-200"
				>
					<svg viewBox="0 0 24 24" class="h-5 w-5" fill="none" stroke="currentColor" stroke-width="2"><path d="M6 6l12 12M18 6L6 18" stroke-linecap="round" /></svg>
				</button>
			</div>
			<p class="mb-3 text-sm text-slate-500">{variation.name}</p>
			{#if variation.items.some((item) => !item.matches_preferences)}
				<p class="mb-2 rounded-xl bg-amber-50 p-3 text-sm text-amber-900">{m.routine_variation_partial()}</p>
			{/if}
			<div class="space-y-1.5 overflow-y-auto">
				{#each variation.items as it, i (i)}
					<div class="flex items-center gap-2 rounded-2xl bg-slate-50 p-2">
					<button type="button" onclick={() => (photoOf = it.new_exercise)} class="flex min-w-0 flex-1 items-center gap-3 text-left">
						<span class="grid h-12 w-12 shrink-0 place-items-center overflow-hidden rounded-xl bg-slate-100">
							{#if it.new_exercise.media_urls.length > 0}
								<img src={it.new_exercise.media_urls[0]} alt="" class="h-full w-full object-cover" loading="lazy" />
							{:else}
								<svg viewBox="0 0 24 24" class="h-5 w-5 text-slate-400" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="3" /><path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7-10-7-10-7z" /></svg>
							{/if}
						</span>
						<div class="min-w-0 flex-1">
							<p class="truncate text-xs text-slate-400 line-through">{it.original_exercise.name}</p>
							<p class="truncate text-sm font-bold text-slate-900">{it.new_exercise.name}</p>
						</div>
						<svg viewBox="0 0 24 24" class="h-4 w-4 shrink-0 text-slate-300" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="3" /><path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7-10-7-10-7z" /></svg>
					</button>
					<button type="button" disabled={variationBusy || variationApplyUnknown} onclick={() => (variationSwapTarget = { routineId: variation!.routine_id, itemIndex: i, bulk: false })} class="min-h-10 shrink-0 rounded-xl border border-emerald-200 bg-white px-3 text-xs font-bold text-emerald-800 disabled:opacity-50">{m.replace_exercise()}</button>
					</div>
				{/each}
			</div>
			{#if variationApplyUnknown}
				<p class="mt-3 rounded-xl bg-amber-50 px-4 py-3 text-sm text-amber-900">{m.routine_apply_unknown()}</p>
				<button type="button" disabled={variationBusy} onclick={applyVariationIntent} class="workout-action mt-2 h-12 w-full rounded-2xl font-bold disabled:opacity-50">{variationBusy ? m.routine_applying() : m.routine_retry_same()}</button>
			{:else if choosingVariationFate}
				<p class="mt-3 shrink-0 rounded-xl bg-slate-100 px-4 py-3 text-sm font-medium text-slate-700">
					{m.vary_today_archive_question()}
				</p>
				<div class="mt-2 flex shrink-0 gap-2">
					<button
						type="button"
						disabled={variationBusy || variationApplyUnknown}
						onclick={() => useVariationToday(false)}
						class="h-12 flex-1 rounded-2xl border-2 border-slate-200 font-semibold text-slate-700 active:bg-slate-100 disabled:opacity-50"
					>
						{m.vary_today_keep_both()}
					</button>
					<button
						type="button"
						disabled={variationBusy || variationApplyUnknown}
						onclick={() => useVariationToday(true)}
						class="workout-action h-12 flex-1 rounded-2xl font-bold disabled:opacity-50"
					>
						{m.vary_today_archive_original()}
					</button>
				</div>
			{:else}
			<button
				type="button"
				disabled={variationBusy || variationApplyUnknown}
				onclick={anotherVariation}
				class="mt-3 flex h-10 w-full shrink-0 items-center justify-center gap-2 rounded-2xl border-2 border-slate-200 text-sm font-bold text-slate-600 active:bg-slate-100 disabled:opacity-50"
			>
				<svg viewBox="0 0 24 24" class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 4v6h6M20 20v-6h-6M20 8a8 8 0 00-14-3M4 16a8 8 0 0014 3" stroke-linecap="round" stroke-linejoin="round" /></svg>
				{m.vary_another()}
			</button>
			<div class="mt-2 flex shrink-0 gap-2">
				<button
					type="button"
					disabled={variationBusy || variationApplyUnknown}
					onclick={() => (choosingVariationFate = true)}
					class="h-12 flex-1 rounded-2xl border-2 border-emerald-200 font-bold text-emerald-700 active:bg-emerald-50 disabled:opacity-50"
				>
					{m.vary_today()}
				</button>
				<button
					type="button"
					disabled={variationBusy || variationApplyUnknown}
					onclick={saveVariation}
					class="workout-action h-12 flex-1 rounded-2xl font-bold disabled:opacity-50"
				>
					{m.vary_save()}
				</button>
			</div>
			{/if}
		</div>
	</div>
{/if}

<!-- Renovar o ciclo inteiro: previa de todas as rotinas vencidas e um confirmar so -->
{#if bulkRenewal}
	<div
		class="fixed inset-0 z-40 flex items-center justify-center bg-black/50 p-4"
		role="button"
		tabindex="-1"
		onclick={closeBulkRenewal}
		onkeydown={(e) => e.key === 'Escape' && closeBulkRenewal()}
	>
		<div
			class="flex max-h-[85dvh] w-full max-w-md flex-col rounded-3xl bg-white p-5"
			role="dialog"
			tabindex="-1"
			onclick={(e) => e.stopPropagation()}
			onkeydown={() => {}}
		>
			<div class="mb-1 flex items-center justify-between gap-2">
				<h2 class="truncate text-lg font-bold text-slate-900">{m.renew_all_title()}</h2>
				<button
					type="button"
					aria-label={m.close()}
					disabled={bulkRenewalBusy || bulkApplyUnknown}
					onclick={closeBulkRenewal}
					class="grid h-9 w-9 shrink-0 place-items-center rounded-full bg-slate-100 text-slate-500 active:bg-slate-200"
				>
					<svg viewBox="0 0 24 24" class="h-5 w-5" fill="none" stroke="currentColor" stroke-width="2"><path d="M6 6l12 12M18 6L6 18" stroke-linecap="round" /></svg>
				</button>
			</div>
			<p class="mb-3 text-sm text-slate-500">{m.renew_all_intro()}</p>
			{#if bulkRenewal.some((item) => item.items.some((exercise) => !exercise.matches_preferences))}
				<p class="mb-2 rounded-xl bg-amber-50 p-3 text-sm text-amber-900">{m.routine_variation_partial()}</p>
			{/if}
			<div class="space-y-4 overflow-y-auto">
				{#each bulkRenewal as routineVariation, index (routineVariation.routine_id)}
					<section>
						<div class="mb-1.5 flex items-center justify-between gap-2">
							<h3 class="truncate text-sm font-bold text-slate-900">{routineVariation.name}</h3>
							<button
								type="button"
								aria-label={m.vary_another()}
								title={m.vary_another()}
								disabled={rerollingRoutineId === routineVariation.routine_id || bulkApplyUnknown}
								onclick={() => rerollBulkVariation(index)}
								class="grid h-9 w-9 shrink-0 place-items-center rounded-full text-emerald-700 active:bg-emerald-50 disabled:opacity-50"
							>
								<svg viewBox="0 0 24 24" class="h-5 w-5" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M4 4v6h6M20 20v-6h-6M20 8a8 8 0 00-14-3M4 16a8 8 0 0014 3" /></svg>
							</button>
						</div>
						<div class="space-y-1.5">
							{#each routineVariation.items as it, i (i)}
								<div class="flex items-center gap-2 rounded-2xl bg-slate-50 p-2">
								<button type="button" onclick={() => (photoOf = it.new_exercise)} class="flex min-w-0 flex-1 items-center gap-3 text-left">
									<span class="grid h-10 w-10 shrink-0 place-items-center overflow-hidden rounded-xl bg-slate-100">
										{#if it.new_exercise.media_urls.length > 0}
											<img src={it.new_exercise.media_urls[0]} alt="" class="h-full w-full object-cover" loading="lazy" />
										{:else}
											<svg viewBox="0 0 24 24" class="h-5 w-5 text-slate-400" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="3" /><path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7-10-7-10-7z" /></svg>
										{/if}
									</span>
									<div class="min-w-0 flex-1">
										<p class="truncate text-xs text-slate-400 line-through">{it.original_exercise.name}</p>
										<p class="truncate text-sm font-bold text-slate-900">{it.new_exercise.name}</p>
									</div>
								</button>
								<button type="button" disabled={bulkRenewalBusy || bulkApplyUnknown} onclick={() => (variationSwapTarget = { routineId: routineVariation.routine_id, itemIndex: i, bulk: true })} class="min-h-10 shrink-0 rounded-xl border border-emerald-200 bg-white px-3 text-xs font-bold text-emerald-800 disabled:opacity-50">{m.replace_exercise()}</button>
								</div>
							{/each}
						</div>
					</section>
				{/each}
			</div>
			<div class="mt-3 flex shrink-0 gap-2">
				<button
					type="button"
					disabled={bulkRenewalBusy || bulkApplyUnknown}
					onclick={closeBulkRenewal}
					class="h-12 flex-1 rounded-2xl border-2 border-slate-200 font-semibold text-slate-700 active:bg-slate-100"
				>
								{m.cancel()}
				</button>
				<button
					type="button"
					disabled={bulkRenewalBusy || rerollingRoutineId !== null}
					onclick={confirmBulkRenewal}
					class="workout-action h-12 flex-1 rounded-2xl font-bold disabled:opacity-50"
				>
					{bulkRenewalBusy ? m.routine_applying() : bulkApplyUnknown ? m.routine_retry_same() : m.renew_all_confirm({ count: bulkRenewal.length })}
				</button>
			</div>
		</div>
	</div>
{/if}

{#if templatePreview}
	<div
		class="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-3"
		role="presentation"
		onclick={closeTemplatePreview}
		onkeydown={(event) => event.key === 'Escape' && closeTemplatePreview()}
	>
		<div
			class="flex max-h-[92dvh] w-full max-w-md flex-col rounded-3xl bg-white p-5 shadow-xl"
			role="dialog"
			aria-modal="true"
			aria-labelledby="routine-preview-title"
			tabindex="-1"
			onclick={(event) => event.stopPropagation()}
			onkeydown={() => {}}
		>
			<div class="mb-3 flex items-start justify-between gap-3">
				<div>
					<h2 id="routine-preview-title" class="text-lg font-bold text-slate-900">{m.routine_preview_title()}</h2>
					<p class="text-sm text-slate-500">{templateFrequency}× · {templatePreview.routines.length} {m.workout_routines_count()}</p>
				</div>
				<button
					type="button"
					aria-label={m.close()}
					disabled={templateApplyBusy || templateApplyUnknown}
					onclick={closeTemplatePreview}
					class="grid h-10 w-10 shrink-0 place-items-center rounded-full bg-slate-100 text-slate-600 disabled:opacity-50"
				>
					×
				</button>
			</div>
			{#if templatePreview.omitted_slots > 0}
				<p class="mb-3 rounded-xl bg-amber-50 p-3 text-sm text-amber-900">{m.routine_preview_omitted({ count: templatePreview.omitted_slots })}</p>
			{/if}
			<div class="min-h-0 flex-1 space-y-4 overflow-y-auto pr-1">
				{#each templatePreview.routines as routine, routineIndex (routineIndex)}
					<section class="rounded-2xl border border-slate-200 p-3">
						<label class="mb-2 block text-xs font-semibold text-slate-500" for="routine-preview-name-{routineIndex}">{m.routine_name_label()}</label>
						<input
							id="routine-preview-name-{routineIndex}"
							value={routine.name}
							disabled={templateApplyBusy || templateApplyUnknown}
							oninput={(event) => {
								templatePreview!.routines[routineIndex].name = event.currentTarget.value;
								resetTemplateOperationKey();
							}}
							class="mb-3 h-11 w-full rounded-xl border border-slate-200 bg-white px-3 font-bold text-slate-900 outline-none focus:border-emerald-600 disabled:bg-slate-100"
						/>
						<div class="space-y-3">
							{#each routine.items as item, itemIndex (item.exercise.id)}
								<div class="rounded-xl bg-slate-50 p-3">
									<div class="flex items-center gap-2">
										<p class="min-w-0 flex-1 truncate text-sm font-semibold text-slate-900">{item.exercise.name}</p>
										<button
											type="button"
											disabled={templateApplyBusy || templateApplyUnknown}
											onclick={() => (templateSwapTarget = { routineIndex, itemIndex })}
											class="min-h-10 shrink-0 rounded-xl border border-emerald-200 bg-white px-3 text-xs font-bold text-emerald-800 disabled:opacity-50"
										>
											{m.replace_exercise()}
										</button>
									</div>
									<div class="mt-2 grid grid-cols-2 gap-3">
										<label class="text-xs font-semibold text-slate-500">
											{m.sets_label()}
											<Stepper bind:value={item.target_sets} min={1} max={20} disabled={templateApplyBusy || templateApplyUnknown} onchange={resetTemplateOperationKey} />
										</label>
										<label class="text-xs font-semibold text-slate-500">
											{m.reps_label()}
											<Stepper bind:value={item.target_reps} min={1} max={100} disabled={templateApplyBusy || templateApplyUnknown} onchange={resetTemplateOperationKey} />
										</label>
									</div>
								</div>
							{/each}
						</div>
					</section>
				{/each}
			</div>
			{#if routines.length > 0}
				<div class="mt-3 rounded-2xl bg-slate-50 p-3">
					<p class="mb-2 text-sm font-semibold text-slate-700">{m.routine_destination_label()}</p>
					<div class="grid grid-cols-2 gap-2">
						<button
							type="button"
							aria-pressed={templateDestination === 'append'}
							disabled={templateApplyBusy || templateApplyUnknown}
							onclick={() => {
								templateDestination = 'append';
								resetTemplateOperationKey();
							}}
						class="min-h-11 rounded-xl border px-2 text-sm font-semibold {templateDestination === 'append' ? 'workout-action border-emerald-700' : 'border-slate-200 bg-white text-slate-700'}"
						>
							{m.routine_destination_append()}
						</button>
						<button
							type="button"
							aria-pressed={templateDestination === 'replace'}
							disabled={templateApplyBusy || templateApplyUnknown}
							onclick={() => {
								templateDestination = 'replace';
								resetTemplateOperationKey();
							}}
						class="min-h-11 rounded-xl border px-2 text-sm font-semibold {templateDestination === 'replace' ? 'workout-action border-emerald-700' : 'border-slate-200 bg-white text-slate-700'}"
						>
							{m.routine_destination_replace()}
						</button>
					</div>
					{#if templateDestination === 'replace'}
						<p class="mt-2 text-xs text-slate-600">{m.routine_replace_impact({ count: templatePreviewSourceIds.length })}</p>
						{#if routines.length > 0}
							<ul class="mt-2 list-inside list-disc text-xs text-slate-600">
								{#each routines as routine (routine.id)}<li>{routine.name}</li>{/each}
							</ul>
						{/if}
					{/if}
				</div>
			{/if}
			{#if templateApplyUnknown}
				<p class="mt-3 rounded-xl bg-amber-50 p-3 text-sm text-amber-900">{m.routine_apply_unknown()}</p>
			{/if}
			<div class="mt-3 flex gap-2">
				<button
					type="button"
					disabled={templateApplyBusy || templateApplyUnknown}
					onclick={closeTemplatePreview}
					class="h-12 flex-1 rounded-2xl border-2 border-slate-200 font-semibold text-slate-700 disabled:opacity-50"
				>
					{m.cancel()}
				</button>
				<button
					type="button"
					disabled={templateApplyBusy}
					onclick={applyTemplatePreview}
					class="workout-action h-12 flex-1 rounded-2xl font-bold disabled:opacity-50"
				>
					{templateApplyBusy ? m.routine_applying() : templateApplyUnknown ? m.routine_retry_same() : m.routine_apply_confirm()}
				</button>
			</div>
		</div>
	</div>
{/if}

{#if templateSwapTarget}
	<div class="fixed inset-0 z-[60] flex items-end justify-center bg-black/50 p-3 sm:items-center">
		<div class="max-h-[88dvh] w-full max-w-md overflow-y-auto rounded-3xl bg-slate-100 p-4">
			<div class="mb-3 flex items-center justify-between">
				<h2 class="text-lg font-bold text-slate-900">{m.replace_exercise()}</h2>
				<button type="button" aria-label={m.close()} onclick={() => (templateSwapTarget = null)} class="grid h-10 w-10 place-items-center rounded-full bg-white text-slate-600">×</button>
			</div>
			<ExerciseBrowser
				onPick={chooseTemplateReplacement}
				selectedIds={templateSwapSelectedIds()}
			/>
		</div>
	</div>
{/if}

{#if variationSwapTarget}
	<div class="fixed inset-0 z-[60] flex items-end justify-center bg-black/50 p-3 sm:items-center">
		<div class="max-h-[88dvh] w-full max-w-md overflow-y-auto rounded-3xl bg-slate-100 p-4">
			<div class="mb-3 flex items-center justify-between">
				<h2 class="text-lg font-bold text-slate-900">{m.replace_exercise()}</h2>
				<button type="button" aria-label={m.close()} onclick={() => (variationSwapTarget = null)} class="grid h-10 w-10 place-items-center rounded-full bg-white text-slate-600">×</button>
			</div>
			<ExerciseBrowser onPick={chooseVariationReplacement} selectedIds={variationSwapSelectedIds()} />
		</div>
	</div>
{/if}

{#if photoOf}
	<ExercisePhotoModal exercise={photoOf} onClose={() => (photoOf = null)} />
{/if}
