<script lang="ts">
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
		type WorkoutDayDetail,
		type WorkoutSession
	} from '$lib/api';
	import CalendarModal from '$lib/components/CalendarModal.svelte';
	import ExercisePhotoModal from '$lib/components/ExercisePhotoModal.svelte';
	import { showToast } from '$lib/toast.svelte';
	import { m } from '$lib/paraglide/messages';
	import { getLocale } from '$lib/paraglide/runtime';

	let showCalendar = $state(false);
	// visualizacao (somente leitura) do treino de um dia selecionado no calendario
	let dayWorkouts = $state<WorkoutDayDetail[] | null>(null);
	let dayWorkoutDate = $state('');

	async function openDayWorkout(date: string): Promise<void> {
		dayWorkoutDate = date;
		dayWorkouts = await api.getWorkoutsByDay(date, new Date().getTimezoneOffset());
	}

	let routines = $state<Routine[]>([]);
	let sessions = $state<SessionSummary[]>([]);
	let activeSession = $state<WorkoutSession | null>(null);
	let periodization = $state<RoutinePeriodization[]>([]);
	let loading = $state(true);

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
	let creatingTemplate = $state(false);
	let showTemplates = $state(false);
	let completingId = $state<number | null>(null);

	const df = new Intl.DateTimeFormat(getLocale(), { day: '2-digit', month: 'short' });
	const nf = new Intl.NumberFormat(getLocale());

	async function load(): Promise<void> {
		[routines, sessions, activeSession, periodization] = await Promise.all([
			api.getRoutines(),
			api.getSessions(),
			api.getActiveSession(),
			api.getTrainingPeriodization(localDay())
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

	async function start(routineId: number): Promise<void> {
		const session = await api.startSession(routineId);
		await goto(`/treino/sessao/${session.id}`);
	}

	async function markDone(routineId: number): Promise<void> {
		completingId = routineId;
		try {
			await api.completeRoutine(routineId);
			await load();
			showToast(m.workout_done_toast());
		} finally {
			completingId = null;
		}
	}

	// rotinas com sessão concluída hoje (mostra selo "feito hoje")
	const doneTodayNames = $derived(
		new Set(
			sessions
				.filter((s) => s.finished_at && s.started_at.slice(0, 10) === localDay())
				.map((s) => s.routine_name)
		)
	);

	$effect(() => {
		load();
	});

	const finishedSessions = $derived(sessions.filter((s) => s.finished_at));

	// dias com treino concluido, marcados no calendario (visualizacao do historico)
	const trainedDays = $derived(new Set(finishedSessions.map((s) => s.started_at.slice(0, 10))));
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

{#if dueRoutine}
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

{#if showCalendar}
	<CalendarModal
		value={localDay()}
		marked={trainedDays}
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
		onclick={() => (dayWorkouts = null)}
		onkeydown={(e) => e.key === 'Escape' && (dayWorkouts = null)}
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
					onclick={() => (dayWorkouts = null)}
					class="grid h-10 w-10 shrink-0 place-items-center rounded-full bg-slate-100 text-slate-500 active:bg-slate-200"
				>
					<svg viewBox="0 0 24 24" class="h-5 w-5" fill="none" stroke="currentColor" stroke-width="2"><path d="M6 6l12 12M18 6L6 18" stroke-linecap="round" /></svg>
				</button>
			</div>

			{#if dayWorkouts.length === 0}
				<p class="py-6 text-center text-sm text-slate-400">{m.no_workout_that_day()}</p>
			{:else}
				<div class="space-y-4">
					{#each dayWorkouts as workout (workout.session_id)}
						<div>
							<p class="font-bold text-emerald-700">{workout.routine_name ?? m.free_workout()}</p>
							<p class="mb-2 text-xs text-slate-400">
								{workout.total_sets}
								{m.sets_label()} · {nf.format(workout.total_volume_kg)} kg
							</p>
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
	<div class="flex justify-center py-16">
		<div class="h-8 w-8 animate-spin rounded-full border-4 border-emerald-600 border-t-transparent"></div>
	</div>
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
		<div class="space-y-3">
			{#each routines as routine (routine.id)}
				<section class="rounded-3xl bg-white p-5 shadow-sm">
					<div class="flex items-start justify-between gap-2">
						<div class="min-w-0">
							<div class="flex items-center gap-2">
								<h2 class="truncate text-lg font-bold text-slate-900">{routine.name}</h2>
								{#if doneTodayNames.has(routine.name)}
									<span class="shrink-0 rounded-full bg-emerald-100 px-2 py-0.5 text-xs font-bold text-emerald-700">
										✓ {m.done_today()}
									</span>
								{/if}
							</div>
							<p class="text-sm text-slate-500">
								{routine.items.length}
								{routine.items.length === 1 ? m.exercise_singular() : m.exercise_plural()}
							</p>
						</div>
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
									<svg viewBox="0 0 24 24" class="h-5 w-5" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M4 17c5 0 5-10 11-10" /><path d="M4 7c5 0 5 10 11 10" /><path d="M12 4l3 3-3 3" /><path d="M12 20l3-3-3-3" /></svg>
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
					</div>
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
					<div class="mt-4 flex gap-2">
						<button
							type="button"
							onclick={() => start(routine.id)}
							disabled={routine.items.length === 0}
							class="h-12 flex-[2] rounded-2xl bg-emerald-600 font-bold text-white active:bg-emerald-700 disabled:opacity-40"
						>
							{m.start_workout()}
						</button>
						<button
							type="button"
							onclick={() => markDone(routine.id)}
							disabled={routine.items.length === 0 || completingId === routine.id}
							class="h-12 flex-1 rounded-2xl border-2 border-emerald-200 font-bold text-emerald-700 active:bg-emerald-50 disabled:opacity-40"
						>
							{completingId === routine.id ? '…' : m.mark_done()}
						</button>
					</div>
				</section>
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
				{#each finishedSessions.slice(0, 8) as session, i (session.id)}
					<div class="flex items-center justify-between px-5 py-3.5 {i > 0 ? 'border-t border-slate-100' : ''}">
						<div>
							<p class="font-semibold text-slate-900">{session.routine_name ?? m.free_workout()}</p>
							<p class="text-sm text-slate-500">
								{session.total_sets} {m.sets_label()} · {nf.format(session.total_volume_kg)} kg
							</p>
						</div>
						<span class="text-sm text-slate-400">{df.format(new Date(session.started_at))}</span>
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
