<script lang="ts">
	import type { AchievementsResult } from '$lib/api';
	import { achievementText } from '$lib/achievementsContent';
	import { m } from '$lib/paraglide/messages';
	import { getLocale } from '$lib/paraglide/runtime';

	/*
	 * Cartao "sua semana" da tela inicial: sequencia de semanas, os 7 dias da semana
	 * (seg-dom) e a proxima medalha.
	 *
	 * Os dias que ja passaram sem treino levam um X de carimbo - de proposito chamativo:
	 * perder um dia precisa ser visivel para a pessoa nao deixar o proximo passar. O
	 * carimbo so "cai" animado na primeira vez que aquele dia aparece perdido; depois
	 * fica parado, para nao virar bronca repetida a cada abertura do app.
	 */

	let { data, today, trainHref }: { data: AchievementsResult; today: string; trainHref: string } =
		$props();

	const locale = getLocale();
	const MISSED_STAMP_SEEN_KEY = 'gymapp.missedStampSeen';

	// Data local "YYYY-MM-DD" -> Date ao meio-dia (evita o fuso empurrar o dia).
	function parseLocalDay(day: string): Date {
		return new Date(day + 'T12:00:00');
	}

	function toLocalDay(date: Date): string {
		const month = String(date.getMonth() + 1).padStart(2, '0');
		const dayOfMonth = String(date.getDate()).padStart(2, '0');
		return `${date.getFullYear()}-${month}-${dayOfMonth}`;
	}

	const narrowWeekday = new Intl.DateTimeFormat(locale, { weekday: 'narrow' });
	const longWeekday = new Intl.DateTimeFormat(locale, { weekday: 'long' });

	type DayState = 'done' | 'missed' | 'today' | 'future';

	// Os 7 dias da semana ISO (segunda a domingo), a mesma semana do streak no backend.
	const weekDays = $derived.by(() => {
		const todayDate = parseLocalDay(today);
		// getDay(): domingo = 0; (getDay() + 6) % 7 = dias desde a segunda
		const monday = new Date(todayDate);
		monday.setDate(todayDate.getDate() - ((todayDate.getDay() + 6) % 7));
		const trained = new Set(data.week_workout_days);
		return Array.from({ length: 7 }, (_, index) => {
			const date = new Date(monday);
			date.setDate(monday.getDate() + index);
			const day = toLocalDay(date);
			let state: DayState;
			if (trained.has(day)) state = 'done';
			else if (day < today) state = 'missed';
			else if (day === today) state = 'today';
			else state = 'future';
			return { day, state, label: narrowWeekday.format(date), index };
		});
	});

	// O balao "passou em branco" aponta so o dia perdido mais recente: um por vez nao
	// polui o cartao quando a semana tem mais de uma falta.
	const latestMissed = $derived([...weekDays].reverse().find((d) => d.state === 'missed') ?? null);

	const latestMissedName = $derived.by(() => {
		if (!latestMissed) return '';
		const name = longWeekday.format(parseLocalDay(latestMissed.day));
		return name.charAt(0).toUpperCase() + name.slice(1);
	});

	// Carimbo animado so na primeira vez que esse dia aparece perdido neste aparelho.
	let stampAnimated = $state(false);
	$effect(() => {
		if (!latestMissed) return;
		try {
			const seen = localStorage.getItem(MISSED_STAMP_SEEN_KEY);
			if (seen === null || seen < latestMissed.day) {
				stampAnimated = true;
				localStorage.setItem(MISSED_STAMP_SEEN_KEY, latestMissed.day);
			}
		} catch {
			// sem armazenamento (aba privada): o carimbo so aparece parado
		}
	});

	const goal = $derived(data.streak_week_goal);
	const doneThisWeek = $derived(data.workouts_this_week);
	const weekSecured = $derived(doneThisWeek >= goal);
	// Treinos que faltam para a semana contar (meta - feitos, nunca negativo).
	const workoutsMissing = $derived(Math.max(0, goal - doneThisWeek));
	// Dias que sobram na semana contando hoje (domingo = 1).
	const daysLeft = $derived(7 - (weekDays.find((d) => d.day === today)?.index ?? 6));
	const stillPossible = $derived(workoutsMissing <= daysLeft);
	// Com a semana ainda aberta, weekly_streak so conta as semanas anteriores; bater a
	// meta agora leva a sequencia para +1.
	const nextStreak = $derived(data.weekly_streak + 1);

	const riskTitle = $derived.by(() => {
		if (data.weekly_streak === 0) {
			return workoutsMissing === 1
				? m.week_card_start_one()
				: m.week_card_start_many({ count: workoutsMissing });
		}
		return workoutsMissing === 1
			? m.week_card_missing_one({ next: nextStreak })
			: m.week_card_missing_many({ count: workoutsMissing, next: nextStreak });
	});

	// Proxima medalha: a bloqueada mais perto da meta. As de "menos X kg" ficam de
	// fora da tela inicial - peso nao e comportamento, e para quem quer ganhar massa
	// essa medalha nem faz sentido.
	const nextMedal = $derived.by(() => {
		const candidates = data.achievements.filter(
			(a) => !a.unlocked && a.progress_goal > 0 && a.metric !== 'weight_lost_kg'
		);
		if (candidates.length === 0) return null;
		return candidates.reduce((best, a) =>
			a.progress_current / a.progress_goal > best.progress_current / best.progress_goal ? a : best
		);
	});
	const nextMedalPct = $derived(
		nextMedal ? Math.min(100, (nextMedal.progress_current / nextMedal.progress_goal) * 100) : 0
	);
</script>

<section class="mb-3 overflow-hidden rounded-3xl bg-white shadow-sm">
	<div class="flex items-center gap-3.5 bg-gradient-to-br from-orange-500 to-amber-500 px-4 py-3.5 text-[#fff]">
		<span class="grid h-14 w-14 shrink-0 place-items-center rounded-2xl bg-[#fff]/20 text-3xl">🔥</span>
		<div class="min-w-0 flex-1">
			<p class="text-4xl leading-none font-black">{data.weekly_streak}</p>
			<p class="mt-0.5 text-sm font-bold text-[#fff7ed]">{m.weeks_streak()}</p>
		</div>
		<div class="text-right">
			<p class="text-2xl leading-none font-black">
				{doneThisWeek}<span class="text-base text-[#ffedd5]">/{goal}</span>
			</p>
			<p class="mt-0.5 text-[11px] font-bold text-[#ffedd5]">{m.week_card_this_week()}</p>
		</div>
	</div>

	<div class="p-4">
		<div class="relative grid grid-cols-7 gap-1 {latestMissed ? 'pt-9' : ''}">
			{#if latestMissed}
				<!-- balao sobre o dia perdido mais recente; a seta fica em cima da coluna dele -->
				<div
					class="absolute top-0 z-10 rounded-xl bg-ink px-2.5 py-1 text-[11px] font-black whitespace-nowrap text-[#fff]
						{latestMissed.index <= 3 ? '' : '-translate-x-full'}"
					style="left: {latestMissed.index <= 3
						? `calc(${(latestMissed.index / 7) * 100}% + 2px)`
						: `calc(${((latestMissed.index + 1) / 7) * 100}% - 2px)`}"
				>
					{m.week_missed_day({ day: latestMissedName })}
					<span
						class="absolute -bottom-1 h-2.5 w-2.5 rotate-45 bg-ink {latestMissed.index <= 3 ? 'left-4' : 'right-4'}"
					></span>
				</div>
			{/if}

			{#each weekDays as weekDay (weekDay.day)}
				<div class="flex flex-col items-center gap-1.5">
					{#if weekDay.state === 'done'}
						<span
							class="grid h-10 w-10 place-items-center rounded-full bg-gradient-to-br from-orange-500 to-amber-500 text-[#fff] shadow-md shadow-orange-500/30"
						>
							<svg viewBox="0 0 24 24" class="h-5 w-5" fill="none" stroke="currentColor" stroke-width="3.2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12l5 5 9-10" /></svg>
						</span>
						<span class="text-[11px] font-extrabold text-slate-600 uppercase">{weekDay.label}</span>
					{:else if weekDay.state === 'missed'}
						<!-- carimbo: quadrado vermelho torto, aro branco, X grosso -->
						<span
							class="-my-0.5 grid h-11 w-11 -rotate-8 place-items-center rounded-2xl bg-rose-600 shadow-lg ring-3 shadow-rose-600/40 ring-rose-200
								{stampAnimated && weekDay.day === latestMissed?.day ? 'missed-stamp' : ''}"
							role="img"
							aria-label={m.week_missed_label()}
						>
							<svg viewBox="0 0 24 24" class="h-7 w-7" fill="none" stroke="#fff" stroke-width="4.2" stroke-linecap="round"><path d="M6 6.5l12 11M17.5 6L6.5 18" /></svg>
						</span>
						<span class="text-[10px] font-black text-rose-600 uppercase">{m.week_missed_label()}</span>
					{:else if weekDay.state === 'today'}
						<span
							class="grid h-10 w-10 place-items-center rounded-full border-[2.5px] border-dashed border-orange-500 bg-orange-50 text-orange-600 ring-4 ring-orange-100"
						>
							<svg viewBox="0 0 24 24" class="h-5 w-5" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round"><path d="M6.5 6.5v11M17.5 6.5v11M3 9.5v5M21 9.5v5M6.5 12h11" /></svg>
						</span>
						<span class="text-[11px] font-black text-orange-600">{m.week_card_today()}</span>
					{:else}
						<span class="h-10 w-10 rounded-full bg-slate-100"></span>
						<span class="text-[11px] font-bold text-slate-400 uppercase">{weekDay.label}</span>
					{/if}
				</div>
			{/each}
		</div>

		{#if weekSecured}
			<div class="mt-4 rounded-2xl bg-emerald-50 px-3.5 py-3">
				<p class="font-extrabold text-emerald-800">{m.week_card_secured_title()}</p>
				<p class="text-xs font-semibold text-emerald-700">
					{m.week_card_secured_hint({ count: data.weekly_streak })}
				</p>
			</div>
		{:else if stillPossible}
			<div class="mt-4 flex items-center gap-3 rounded-2xl bg-orange-50 px-3.5 py-3">
				<div class="min-w-0 flex-1">
					<p class="text-sm font-extrabold text-orange-800">{riskTitle}</p>
					<p class="text-xs font-semibold text-orange-700">
						{daysLeft === 1 ? m.week_card_last_day() : m.week_card_days_left({ days: daysLeft })}
					</p>
				</div>
				<a
					href={trainHref}
					class="grid h-11 shrink-0 place-items-center rounded-2xl bg-orange-600 px-4 text-sm font-extrabold text-[#fff] active:bg-orange-700"
				>
					{m.week_card_train()}
				</a>
			</div>
		{:else}
			<div class="mt-4 rounded-2xl bg-slate-100 px-3.5 py-3">
				<p class="text-sm font-extrabold text-slate-700">{m.week_card_lost_title()}</p>
				<p class="text-xs font-semibold text-slate-500">{m.week_card_lost_hint()}</p>
			</div>
		{/if}

		{#if nextMedal}
			{@const medalText = achievementText(locale, nextMedal.code)}
			<a href="/conquistas" class="mt-2.5 flex items-center gap-3 rounded-2xl bg-emerald-50 px-3.5 py-3 active:bg-emerald-100">
				<span class="text-3xl opacity-60 grayscale">{nextMedal.icon}</span>
				<span class="min-w-0 flex-1">
					<span class="flex justify-between gap-2 text-sm">
						<strong class="truncate text-slate-900">{m.week_card_next_medal({ name: medalText.name })}</strong>
						<span class="shrink-0 font-extrabold text-emerald-700">
							{Math.floor(nextMedal.progress_current)}/{nextMedal.progress_goal}
						</span>
					</span>
					<span class="mt-1.5 block h-1.5 overflow-hidden rounded-full bg-white">
						<span class="block h-full rounded-full bg-emerald-500" style="width: {nextMedalPct}%"></span>
					</span>
				</span>
				<svg viewBox="0 0 24 24" class="h-4 w-4 shrink-0 text-emerald-600" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M9 6l6 6-6 6" stroke-linecap="round" stroke-linejoin="round" /></svg>
			</a>
		{/if}
	</div>
</section>

<style>
	/* Carimbo caindo: entra grande e transparente, bate na mesa (passa um pouco do
	   tamanho final) e assenta torto em -8 graus, como um carimbo de verdade. */
	.missed-stamp {
		animation: missed-stamp-drop 520ms cubic-bezier(0.2, 0.9, 0.3, 1.3) both;
	}

	@keyframes missed-stamp-drop {
		0% {
			opacity: 0;
			transform: scale(2.2) rotate(-24deg);
		}
		60% {
			opacity: 1;
			transform: scale(0.88) rotate(-6deg);
		}
		100% {
			transform: scale(1) rotate(-8deg);
		}
	}

	@media (prefers-reduced-motion: reduce) {
		.missed-stamp {
			animation: none;
		}
	}
</style>
