<script lang="ts">
	import { api, type GoalsOut } from '$lib/api';
	import { session } from '$lib/session.svelte';
	import WaterCard from '$lib/components/WaterCard.svelte';
	import { m } from '$lib/paraglide/messages';
	import { getLocale } from '$lib/paraglide/runtime';

	let goals = $state<GoalsOut | null>(null);

	$effect(() => {
		if (session.user?.has_profile) {
			api.getGoals().then((g) => (goals = g));
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
	<section class="rounded-3xl bg-white p-6 shadow-sm">
		<p class="text-sm font-semibold text-slate-500">{m.daily_target()}</p>
		<p class="mt-1 text-5xl font-black tracking-tight">
			{nf.format(goals.target_kcal)}
			<span class="text-lg font-semibold text-slate-400">kcal</span>
		</p>
		<div class="mt-5 grid grid-cols-3 gap-2 border-t border-slate-100 pt-4">
			<div>
				<p class="text-xs font-semibold text-slate-500">{m.protein()}</p>
				<p class="text-xl font-bold">
					{goals.protein_g}<span class="text-sm font-medium text-slate-400">g</span>
				</p>
			</div>
			<div>
				<p class="text-xs font-semibold text-slate-500">{m.carbs()}</p>
				<p class="text-xl font-bold">
					{goals.carbs_g}<span class="text-sm font-medium text-slate-400">g</span>
				</p>
			</div>
			<div>
				<p class="text-xs font-semibold text-slate-500">{m.fat()}</p>
				<p class="text-xl font-bold">
					{goals.fat_g}<span class="text-sm font-medium text-slate-400">g</span>
				</p>
			</div>
		</div>
	</section>

	<div class="mt-3">
		<WaterCard />
	</div>

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

	<section class="mt-3 rounded-3xl border-2 border-dashed border-slate-200 p-6 text-center">
		<p class="font-semibold text-slate-600">{m.workout_coming()}</p>
		<p class="mt-1 text-sm text-slate-400">{m.phase_hint()}</p>
	</section>
{:else}
	<div class="flex justify-center py-16">
		<div
			class="h-8 w-8 animate-spin rounded-full border-4 border-emerald-600 border-t-transparent"
		></div>
	</div>
{/if}
