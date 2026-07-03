<script lang="ts">
	import { api, localDay, type DiaryDay, type GoalsOut, type WorkoutSession } from '$lib/api';
	import { session } from '$lib/session.svelte';
	import WaterCard from '$lib/components/WaterCard.svelte';
	import MacroSummary from '$lib/components/MacroSummary.svelte';
	import { m } from '$lib/paraglide/messages';
	import { getLocale } from '$lib/paraglide/runtime';

	let goals = $state<GoalsOut | null>(null);
	let diary = $state<DiaryDay | null>(null);
	let activeSession = $state<WorkoutSession | null>(null);

	const dietOn = $derived(session.profile?.diet_enabled ?? false);

	$effect(() => {
		if (session.user?.has_profile) {
			api.getGoals().then((g) => (goals = g));
			api.getActiveSession().then((s) => (activeSession = s));
			if (dietOn) api.getDiary(localDay()).then((d) => (diary = d));
		}
	});

	const nf = new Intl.NumberFormat(getLocale());

	const objectiveLabel = $derived(
		{
			gain_muscle: m.objective_gain_muscle(),
			lose_fat: m.objective_lose_fat(),
			recomp: m.objective_recomp(),
			maintain: m.objective_maintain()
		}[session.profile?.objective ?? 'maintain']
	);
</script>

<header class="mb-6">
	<h1 class="text-2xl font-bold">{m.today_title()}</h1>
	<p class="text-slate-500">{objectiveLabel}</p>
</header>

{#if goals}
	{#if dietOn}
		{#if diary}
			<MacroSummary totals={diary.totals} goals={diary.goals} />
			<a
				href="/dieta"
				class="mt-3 flex h-12 w-full items-center justify-center rounded-2xl bg-emerald-600 font-bold text-white active:bg-emerald-700"
			>
				+ {m.add_food()}
			</a>
		{/if}
	{:else}
		<section class="rounded-3xl bg-white p-6 shadow-sm">
			<p class="text-sm font-semibold text-slate-500">{m.daily_target()}</p>
			<p class="mt-1 text-5xl font-black tracking-tight">
				{nf.format(goals.target_kcal)}
				<span class="text-lg font-semibold text-slate-400">kcal</span>
			</p>
			<div class="mt-5 grid grid-cols-3 gap-2 border-t border-slate-100 pt-4">
				<div>
					<p class="text-xs font-semibold text-slate-500">{m.protein()}</p>
					<p class="text-xl font-bold">{goals.protein_g}<span class="text-sm font-medium text-slate-400">g</span></p>
				</div>
				<div>
					<p class="text-xs font-semibold text-slate-500">{m.carbs()}</p>
					<p class="text-xl font-bold">{goals.carbs_g}<span class="text-sm font-medium text-slate-400">g</span></p>
				</div>
				<div>
					<p class="text-xs font-semibold text-slate-500">{m.fat()}</p>
					<p class="text-xl font-bold">{goals.fat_g}<span class="text-sm font-medium text-slate-400">g</span></p>
				</div>
			</div>
		</section>
	{/if}

	<div class="mt-3">
		<WaterCard />
	</div>

	<a
		href={activeSession ? `/treino/sessao/${activeSession.id}` : '/treino'}
		class="mt-3 flex items-center justify-between rounded-3xl p-5 shadow-sm
			{activeSession ? 'bg-emerald-600 text-white active:bg-emerald-700' : 'bg-white active:bg-slate-50'}"
	>
		<div class="flex items-center gap-3">
			<span
				class="grid h-11 w-11 place-items-center rounded-2xl
					{activeSession ? 'bg-emerald-500 text-white' : 'bg-emerald-50 text-emerald-600'}"
			>
				<svg viewBox="0 0 24 24" class="h-6 w-6" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M6.5 6.5v11M17.5 6.5v11M3 9.5v5M21 9.5v5M6.5 12h11" /></svg>
			</span>
			<div>
				{#if activeSession}
					<p class="font-bold">{m.resume_workout()}</p>
					<p class="text-sm text-emerald-100">
						{activeSession.routine_name ?? m.free_workout()}
					</p>
				{:else}
					<p class="font-bold text-slate-900">{m.tab_workout()}</p>
					<p class="text-sm text-slate-500">{m.go_to_workouts()}</p>
				{/if}
			</div>
		</div>
		<svg viewBox="0 0 24 24" class="h-5 w-5 {activeSession ? 'text-emerald-200' : 'text-slate-300'}" fill="none" stroke="currentColor" stroke-width="2"><path d="M9 6l6 6-6 6" stroke-linecap="round" stroke-linejoin="round" /></svg>
	</a>

	<section class="mt-3 grid grid-cols-3 gap-3">
		<div class="rounded-3xl bg-white p-4 shadow-sm">
			<p class="text-xs font-semibold text-slate-500">{m.bmi()}</p>
			<p class="mt-1 text-xl font-bold">{nf.format(goals.bmi)}</p>
		</div>
		<div class="rounded-3xl bg-white p-4 shadow-sm">
			<p class="text-xs font-semibold text-slate-500">{m.tdee()}</p>
			<p class="mt-1 text-xl font-bold">{nf.format(goals.tdee_kcal)}</p>
		</div>
		<div class="rounded-3xl bg-white p-4 shadow-sm">
			<p class="text-xs font-semibold text-slate-500">{m.bmr()}</p>
			<p class="mt-1 text-xl font-bold">{nf.format(goals.bmr_kcal)}</p>
		</div>
	</section>
{:else}
	<div class="flex justify-center py-16">
		<div class="h-8 w-8 animate-spin rounded-full border-4 border-emerald-600 border-t-transparent"></div>
	</div>
{/if}
