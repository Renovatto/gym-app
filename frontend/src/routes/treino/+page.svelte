<script lang="ts">
	import { slide } from 'svelte/transition';
	import { goto } from '$app/navigation';
	import {
		api,
		localDay,
		type Exercise,
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
	import LogActivityModal from '$lib/components/LogActivityModal.svelte';
	import { activityKindLabel } from '$lib/labels';
	import { showToast } from '$lib/toast.svelte';
	import SkeletonScreen from '$lib/components/SkeletonScreen.svelte';
	import { m } from '$lib/paraglide/messages';
	import { getLocale } from '$lib/paraglide/runtime';

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

	let routines = $state<Routine[]>([]);
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

	async function openVariation(routineId: number): Promise<void> {
		variationSourceId = routineId;
		variationLoading = routineId;
		try {
			variation = await api.getRoutineVariation(routineId);
		} finally {
			variationLoading = null;
		}
	}

	async function anotherVariation(): Promise<void> {
		if (variationSourceId === null) return;
		variation = await api.getRoutineVariation(variationSourceId);
	}

	function variationItems(): RoutineItemInput[] {
		if (!variation) return [];
		return variation.items.map((it) => ({
			exercise_id: it.new_exercise.id,
			target_sets: it.target_sets,
			target_reps: it.target_reps,
			target_weight_kg: it.target_weight_kg,
			target_duration_min: it.target_duration_min,
			rest_seconds: it.rest_seconds
		}));
	}

	async function saveVariation(): Promise<void> {
		if (!variation) return;
		variationBusy = true;
		try {
			await api.updateRoutine(variation.routine_id, variation.name, variationItems());
			variation = null;
			await load();
			showToast(m.vary_saved());
		} finally {
			variationBusy = false;
		}
	}

	async function useVariationToday(): Promise<void> {
		if (!variation) return;
		variationBusy = true;
		try {
			const label = new Date().toLocaleDateString(getLocale(), { day: '2-digit', month: '2-digit' });
			const name = `${variation.name} — ${m.variation_word()} ${label}`.slice(0, 80);
			const created = await api.createRoutine(name, variationItems());
			variation = null;
			await start(created.id);
		} finally {
			variationBusy = false;
		}
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
	let showTemplates = $state(false);
	let completingId = $state<number | null>(null);

	const df = new Intl.DateTimeFormat(getLocale(), { day: '2-digit', month: 'short' });
	const nf = new Intl.NumberFormat(getLocale());

	async function load(): Promise<void> {
		[routines, sessions, activeSession, periodization, todayActivities, activityDays] =
			await Promise.all([
				api.getRoutines(),
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
		try {
			await api.createFromTemplate(frequency);
			showTemplates = false;
			await load();
			showToast(m.toast_created());
		} finally {
			creatingTemplate = false;
		}
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
		load();
	});


	// O historico mostrava so os 8 mais recentes e nao havia como chegar no resto -
	// treino antigo ficava sem jeito de abrir nem de excluir.
	const HISTORY_PREVIEW = 8;
	let historyExpanded = $state(false);
	const visibleHistory = $derived(
		historyExpanded ? finishedSessions : finishedSessions.slice(0, HISTORY_PREVIEW)
	);

	// dias com treino concluido, marcados no calendario (visualizacao do historico)
	const trainedDays = $derived(new Set(finishedSessions.map((s) => s.started_at.slice(0, 10))));
	// dias com atividade avulsa: marcados na segunda cor, podem coincidir com treino
	const activityDaysSet = $derived(new Set(activityDays));
</script>

<div class="mb-6 flex items-center justify-between gap-2">
	<h1 class="text-2xl font-bold">{m.tab_workout()}</h1>
	<div class="flex items-center gap-2">
		<button
			type="button"
			aria-label={m.workout_calendar()}
			title={m.workout_calendar()}
			onclick={() => (showCalendar = true)}
			class="grid h-9 w-9 place-items-center rounded-full bg-white text-slate-500 shadow-sm active:bg-slate-100"
		>
			<svg viewBox="0 0 24 24" class="h-5 w-5" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="4" width="18" height="17" rx="2" /><path d="M3 9h18M8 2v4M16 2v4" stroke-linecap="round" /></svg>
		</button>
		<a
			href="/treino/catalogo"
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
		{#if showTemplates}
			<p class="mt-3 text-xs text-slate-400">{m.template_adds_hint()}</p>
			<button
				type="button"
				onclick={() => (showTemplates = false)}
				class="mt-2 text-sm font-semibold text-slate-500"
			>
				{m.cancel()}
			</button>
		{/if}
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
		{@render templatePicker()}
		<div class="mt-3 text-center">
			<a href="/treino/rotina/nova" class="text-sm font-semibold text-emerald-700">
				{m.create_routine_manual()}
			</a>
		</div>
	{:else}
		{#if showTemplates}
			<div
				class="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
				role="button"
				tabindex="-1"
				onclick={() => (showTemplates = false)}
				onkeydown={(e) => e.key === 'Escape' && (showTemplates = false)}
			>
				<div
					class="w-full max-w-md"
					role="dialog"
					tabindex="-1"
					onclick={(e) => e.stopPropagation()}
					onkeydown={() => {}}
				>
					{@render templatePicker()}
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

		<!-- O PROXIMO do ciclo em destaque: abre a tela, aperta um botao, zero decisao.
			 Some quando ha treino em andamento (o cartao de retomar ja e o principal). -->
		{#if nextRoutine && !activeSession}
			{@const lastWhen =
				lastFinishedWithRoutine?.routine_id != null
					? recencyLabel(lastFinishedWithRoutine.routine_id)
					: null}
			<section class="relative mb-3 rounded-3xl border-2 border-emerald-500 bg-white p-5 shadow-sm">
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

		<div class="mt-3 flex gap-2">
			<a
				href="/treino/rotina/nova"
				class="flex h-12 flex-1 items-center justify-center rounded-2xl border-2 border-slate-200 bg-white font-semibold text-slate-700 active:bg-slate-100"
			>
				{m.new_routine()}
			</a>
			<button
				type="button"
				onclick={() => (showTemplates = !showTemplates)}
				class="flex h-12 flex-1 items-center justify-center rounded-2xl border-2 border-slate-200 bg-white font-semibold text-slate-700 active:bg-slate-100"
			>
				{m.use_template()}
			</button>
		</div>
	{/if}

	{#if finishedSessions.length > 0}
		<section class="mt-6">
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
			<button
				type="button"
				onclick={startFromPreview}
				class="mt-3 h-12 w-full shrink-0 rounded-2xl bg-emerald-600 font-bold text-white active:bg-emerald-700"
			>
				{m.start_workout()}
			</button>
		</div>
	</div>
{/if}

<!-- Variar o treino: previa (de -> para) e escolher usar hoje ou salvar -->
{#if variation}
	<div
		class="fixed inset-0 z-40 flex items-center justify-center bg-black/50 p-4"
		role="button"
		tabindex="-1"
		onclick={() => (variation = null)}
		onkeydown={(e) => e.key === 'Escape' && (variation = null)}
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
					onclick={() => (variation = null)}
					class="grid h-9 w-9 shrink-0 place-items-center rounded-full bg-slate-100 text-slate-500 active:bg-slate-200"
				>
					<svg viewBox="0 0 24 24" class="h-5 w-5" fill="none" stroke="currentColor" stroke-width="2"><path d="M6 6l12 12M18 6L6 18" stroke-linecap="round" /></svg>
				</button>
			</div>
			<p class="mb-3 text-sm text-slate-500">{variation.name}</p>
			<div class="space-y-1.5 overflow-y-auto">
				{#each variation.items as it, i (i)}
					<button
						type="button"
						onclick={() => (photoOf = it.new_exercise)}
						class="flex w-full items-center gap-3 rounded-2xl bg-slate-50 p-2 text-left active:bg-slate-100"
					>
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
				{/each}
			</div>
			<button
				type="button"
				onclick={anotherVariation}
				class="mt-3 flex h-10 w-full shrink-0 items-center justify-center gap-2 rounded-2xl border-2 border-slate-200 text-sm font-bold text-slate-600 active:bg-slate-100"
			>
				<svg viewBox="0 0 24 24" class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 4v6h6M20 20v-6h-6M20 8a8 8 0 00-14-3M4 16a8 8 0 0014 3" stroke-linecap="round" stroke-linejoin="round" /></svg>
				{m.vary_another()}
			</button>
			<div class="mt-2 flex shrink-0 gap-2">
				<button
					type="button"
					disabled={variationBusy}
					onclick={useVariationToday}
					class="h-12 flex-1 rounded-2xl border-2 border-emerald-200 font-bold text-emerald-700 active:bg-emerald-50 disabled:opacity-50"
				>
					{m.vary_today()}
				</button>
				<button
					type="button"
					disabled={variationBusy}
					onclick={saveVariation}
					class="h-12 flex-1 rounded-2xl bg-emerald-600 font-bold text-white active:bg-emerald-700 disabled:opacity-50"
				>
					{m.vary_save()}
				</button>
			</div>
		</div>
	</div>
{/if}

{#if photoOf}
	<ExercisePhotoModal exercise={photoOf} onClose={() => (photoOf = null)} />
{/if}
