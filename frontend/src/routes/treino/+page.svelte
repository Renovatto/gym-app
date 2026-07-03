<script lang="ts">
	import { goto } from '$app/navigation';
	import { api, type Routine, type SessionSummary } from '$lib/api';
	import { m } from '$lib/paraglide/messages';
	import { getLocale } from '$lib/paraglide/runtime';

	let routines = $state<Routine[]>([]);
	let sessions = $state<SessionSummary[]>([]);
	let loading = $state(true);
	let creatingTemplate = $state(false);

	const df = new Intl.DateTimeFormat(getLocale(), { day: '2-digit', month: 'short' });
	const nf = new Intl.NumberFormat(getLocale());

	async function load(): Promise<void> {
		[routines, sessions] = await Promise.all([api.getRoutines(), api.getSessions()]);
		loading = false;
	}

	async function useTemplate(frequency: number): Promise<void> {
		creatingTemplate = true;
		try {
			await api.createFromTemplate(frequency);
			await load();
		} finally {
			creatingTemplate = false;
		}
	}

	async function start(routineId: number): Promise<void> {
		const session = await api.startSession(routineId);
		await goto(`/treino/sessao/${session.id}`);
	}

	$effect(() => {
		load();
	});

	const finishedSessions = $derived(sessions.filter((s) => s.finished_at));
</script>

<div class="mb-6 flex items-center justify-between">
	<h1 class="text-2xl font-bold">{m.tab_workout()}</h1>
	<a
		href="/treino/catalogo"
		class="rounded-full bg-white px-4 py-2 text-sm font-semibold text-emerald-700 shadow-sm"
	>
		{m.exercise_catalog()}
	</a>
</div>

{#if loading}
	<div class="flex justify-center py-16">
		<div class="h-8 w-8 animate-spin rounded-full border-4 border-emerald-600 border-t-transparent"></div>
	</div>
{:else}
	{#if routines.length === 0}
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
		</section>
		<div class="mt-3 text-center">
			<a href="/treino/rotina/nova" class="text-sm font-semibold text-emerald-700">
				{m.create_routine_manual()}
			</a>
		</div>
	{:else}
		<div class="space-y-3">
			{#each routines as routine (routine.id)}
				<section class="rounded-3xl bg-white p-5 shadow-sm">
					<div class="flex items-start justify-between gap-2">
						<div class="min-w-0">
							<h2 class="truncate text-lg font-bold text-slate-900">{routine.name}</h2>
							<p class="text-sm text-slate-500">
								{routine.items.length}
								{routine.items.length === 1 ? m.exercise_singular() : m.exercise_plural()}
							</p>
						</div>
						<a
							href="/treino/rotina/{routine.id}"
							class="shrink-0 text-sm font-semibold text-slate-400"
						>
							{m.edit()}
						</a>
					</div>
					<div class="mt-2 flex flex-wrap gap-1">
						{#each routine.items.slice(0, 4) as item (item.id)}
							<span class="rounded-full bg-slate-100 px-2.5 py-1 text-xs font-medium text-slate-600">
								{item.exercise.name}
							</span>
						{/each}
						{#if routine.items.length > 4}
							<span class="rounded-full bg-slate-100 px-2.5 py-1 text-xs font-medium text-slate-400">
								+{routine.items.length - 4}
							</span>
						{/if}
					</div>
					<button
						type="button"
						onclick={() => start(routine.id)}
						disabled={routine.items.length === 0}
						class="mt-4 h-12 w-full rounded-2xl bg-emerald-600 font-bold text-white active:bg-emerald-700 disabled:opacity-40"
					>
						{m.start_workout()}
					</button>
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
