<script lang="ts">
	import { api, localDay, type AchievementsResult } from '$lib/api';
	import { achievementText } from '$lib/achievementsContent';
	import { showToast } from '$lib/toast.svelte';
	import { m } from '$lib/paraglide/messages';
	import { getLocale } from '$lib/paraglide/runtime';

	let data = $state<AchievementsResult | null>(null);
	let loading = $state(true);
	const locale = getLocale();

	async function load(): Promise<void> {
		data = await api.getAchievements(localDay(), new Date().getTimezoneOffset());
		loading = false;
		// celebra conquistas recem-desbloqueadas
		if (data.newly_unlocked.length > 0) {
			showToast(m.achievement_unlocked());
		}
	}

	const unlockedCount = $derived(data ? data.achievements.filter((a) => a.unlocked).length : 0);

	$effect(() => {
		load();
	});
</script>

<div class="mb-4 flex items-center gap-2">
	<a
		href="/progresso"
		aria-label={m.back()}
		class="grid h-10 w-10 place-items-center rounded-full bg-white text-slate-500 shadow-sm"
	>
		<svg viewBox="0 0 24 24" class="h-5 w-5" fill="none" stroke="currentColor" stroke-width="2">
			<path d="M15 6l-6 6 6 6" stroke-linecap="round" stroke-linejoin="round" />
		</svg>
	</a>
	<h1 class="text-2xl font-bold">{m.achievements_title()}</h1>
</div>

{#if loading}
	<div class="flex justify-center py-16">
		<div class="h-8 w-8 animate-spin rounded-full border-4 border-emerald-600 border-t-transparent"></div>
	</div>
{:else if data}
	<!-- Streak semanal em destaque -->
	<section class="mb-4 rounded-3xl bg-gradient-to-br from-orange-500 to-amber-500 p-5 text-white">
		<div class="flex items-center gap-4">
			<span class="text-5xl">🔥</span>
			<div>
				<p class="text-4xl leading-none font-black">{data.weekly_streak}</p>
				<p class="text-sm font-semibold text-amber-50">{m.weeks_streak()}</p>
			</div>
		</div>
		<p class="mt-3 text-sm text-amber-50">
			{m.workouts_this_week_label()}: <span class="font-bold">{data.workouts_this_week}</span>
		</p>
	</section>

	<p class="mb-2 px-1 text-xs font-bold tracking-wide text-slate-400 uppercase">
		{m.medals_label()} · {unlockedCount}/{data.achievements.length}
	</p>
	<div class="grid grid-cols-2 gap-3">
		{#each data.achievements as ach (ach.code)}
			{@const text = achievementText(locale, ach.code)}
			{@const pct = Math.min(100, (ach.progress_current / ach.progress_goal) * 100)}
			<div
				class="rounded-3xl border-2 p-4 text-center transition-colors
					{ach.unlocked ? 'border-emerald-200 bg-white' : 'border-slate-100 bg-slate-50'}"
			>
				<span class="text-4xl {ach.unlocked ? '' : 'opacity-30 grayscale'}">{ach.icon}</span>
				<p class="mt-2 text-sm font-bold {ach.unlocked ? 'text-slate-900' : 'text-slate-400'}">
					{text.name}
				</p>
				{#if ach.unlocked}
					<p class="mt-0.5 text-xs text-slate-500">{text.description}</p>
				{:else}
					<div class="mt-2 h-1.5 overflow-hidden rounded-full bg-slate-200">
						<div class="h-full rounded-full bg-emerald-500" style="width: {pct}%"></div>
					</div>
					<p class="mt-1 text-xs text-slate-400">{ach.progress_current}/{ach.progress_goal}</p>
				{/if}
			</div>
		{/each}
	</div>
{/if}
