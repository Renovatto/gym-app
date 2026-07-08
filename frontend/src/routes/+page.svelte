<script lang="ts">
	import {
		api,
		localDay,
		type CoachResult,
		type DiaryDay,
		type GoalsOut,
		type WorkoutSession
	} from '$lib/api';
	import { session } from '$lib/session.svelte';
	import WaterCard from '$lib/components/WaterCard.svelte';
	import MacroSummary from '$lib/components/MacroSummary.svelte';
	import { m } from '$lib/paraglide/messages';
	import { getLocale } from '$lib/paraglide/runtime';

	let goals = $state<GoalsOut | null>(null);
	let diary = $state<DiaryDay | null>(null);
	let activeSession = $state<WorkoutSession | null>(null);
	let coach = $state<CoachResult | null>(null);
	// Modal de info: mesmo componente para IMC (detalhado, com tabela) e TDEE/BMR
	// (rapido, 1-2 frases) - consistencia de interacao entre os 3 cards.
	let infoModal = $state<'bmi' | 'tdee' | 'bmr' | null>(null);

	const dietOn = $derived(session.profile?.diet_enabled ?? false);

	$effect(() => {
		if (session.user?.has_profile) {
			api.getGoals().then((g) => (goals = g));
			api.getActiveSession().then((s) => (activeSession = s));
			api.getCoach(localDay(), new Date().getTimezoneOffset()).then((c) => (coach = c));
			if (dietOn) api.getDiary(localDay()).then((d) => (diary = d));
		}
	});

	const nf = new Intl.NumberFormat(getLocale());

	// IMC (indice de massa corporal): classificacao da OMS calculada no backend
	// (goals.py, fonte unica da formula/faixas). Aqui so mapeamos o codigo para
	// cor "semaforo" + mensagem descontraida + faixa (para o modal explicativo).
	const BMI_CATEGORIES = {
		underweight: { tone: 'warn' as const, label: m.bmi_cat_underweight_label(), text: m.bmi_cat_underweight_text(), range: m.bmi_range_underweight() },
		normal: { tone: 'good' as const, label: m.bmi_cat_normal_label(), text: m.bmi_cat_normal_text(), range: m.bmi_range_normal() },
		overweight: { tone: 'warn' as const, label: m.bmi_cat_overweight_label(), text: m.bmi_cat_overweight_text(), range: m.bmi_range_overweight() },
		obese_1: { tone: 'bad' as const, label: m.bmi_cat_obese1_label(), text: m.bmi_cat_obese1_text(), range: m.bmi_range_obese1() },
		obese_2: { tone: 'bad' as const, label: m.bmi_cat_obese2_label(), text: m.bmi_cat_obese2_text(), range: m.bmi_range_obese2() },
		obese_3: { tone: 'bad' as const, label: m.bmi_cat_obese3_label(), text: m.bmi_cat_obese3_text(), range: m.bmi_range_obese3() }
	};
	const bmiInfo = $derived(goals ? BMI_CATEGORIES[goals.bmi_category] : null);
	const bmiToneClass = $derived(
		bmiInfo?.tone === 'good'
			? 'bg-emerald-50 text-emerald-800'
			: bmiInfo?.tone === 'warn'
				? 'bg-amber-50 text-amber-800'
				: 'bg-red-50 text-red-700'
	);
	// Borda sutil (tom 200, nao saturado) no card do IMC, na mesma cor do selo.
	const bmiBorderClass = $derived(
		bmiInfo?.tone === 'good'
			? 'border-emerald-200'
			: bmiInfo?.tone === 'warn'
				? 'border-amber-200'
				: 'border-red-200'
	);

	// Texto traduzido de cada dica do coach (por codigo).
	function coachNoteText(code: string): string {
		return (
			{
				LOG_FOOD: m.coach_log_food(),
				LOW_PROTEIN: m.coach_low_protein(),
				DRINK_WATER: m.coach_drink_water(),
				TRAIN: m.coach_train(),
				VISCERAL_TIP: m.coach_visceral_tip()
			}[code] ?? ''
		);
	}

	// Mostra o lembrete de pesagem se nunca pesou ou nao pesou hoje.
	const showWeighReminder = $derived(
		coach !== null && (coach.days_since_weigh_in === null || coach.days_since_weigh_in >= 1)
	);

	const objectiveLabel = $derived(
		{
			gain_muscle: m.objective_gain_muscle(),
			lose_fat: m.objective_lose_fat(),
			recomp: m.objective_recomp(),
			maintain: m.objective_maintain()
		}[session.profile?.objective ?? 'maintain']
	);

	const firstName = $derived(session.profile?.first_name?.trim() ?? '');

	// Aniversario: hoje bate com o dia e mes da data de nascimento.
	const isBirthday = $derived.by(() => {
		const birthdate = session.profile?.birthdate;
		if (!birthdate) return false;
		const d = new Date(birthdate + 'T12:00:00');
		const today = new Date();
		return d.getMonth() === today.getMonth() && d.getDate() === today.getDate();
	});
</script>

<header class="mb-6">
	<h1 class="text-2xl font-bold">
		{firstName ? m.today_greeting({ name: firstName }) : m.today_title()}
	</h1>
	<p class="text-slate-500">{objectiveLabel}</p>
</header>

<!-- Surpresa de aniversario -->
{#if isBirthday}
	<section
		class="relative mb-3 overflow-hidden rounded-3xl bg-gradient-to-br from-emerald-500 to-sky-500 p-5 text-white"
	>
		<p class="text-3xl">🎉🎂🎈</p>
		<p class="mt-1 text-lg font-black">
			{firstName ? m.birthday_title_named({ name: firstName }) : m.birthday_title()}
		</p>
		<p class="mt-1 text-sm text-emerald-50">{m.birthday_message()}</p>
	</section>
{/if}

<!-- Lembrete de pesagem (com orientacao de melhor hora) -->
{#if showWeighReminder}
	<a href="/progresso?novo=1" class="mb-3 flex items-start gap-3 rounded-3xl bg-sky-50 p-4 active:bg-sky-100">
		<span class="grid h-10 w-10 shrink-0 place-items-center rounded-2xl bg-sky-100 text-sky-600">
			<svg viewBox="0 0 24 24" class="h-6 w-6" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 3a9 9 0 100 18 9 9 0 000-18zM12 8v4l3 2" stroke-linecap="round" stroke-linejoin="round" /></svg>
		</span>
		<div class="min-w-0 flex-1">
			<p class="font-bold text-sky-900">{m.weigh_reminder_title()}</p>
			<p class="text-xs text-sky-700">{m.weigh_reminder_hint()}</p>
		</div>
		<span class="shrink-0 self-center text-sm font-bold text-sky-700">{m.weigh_reminder_cta()}</span>
	</a>
{/if}

<!-- Dicas do coach (por regras) -->
{#if coach && coach.notes.length > 0}
	<section class="mb-3 rounded-3xl bg-white p-4 shadow-sm">
		<p class="mb-2 text-xs font-bold text-slate-400 uppercase">{m.coach_notes_title()}</p>
		<ul class="space-y-2">
			{#each coach.notes as note (note.code)}
				<li class="flex gap-2 text-sm">
					<span
						class="mt-1.5 h-2 w-2 shrink-0 rounded-full {note.severity === 'warn'
							? 'bg-amber-500'
							: 'bg-emerald-500'}"
					></span>
					<span class="text-slate-700">{coachNoteText(note.code)}</span>
				</li>
			{/each}
		</ul>
	</section>
{/if}

{#if goals}
	{#if dietOn}
		{#if diary}
			<MacroSummary totals={diary.totals} goals={diary.goals} addHref="/dieta/adicionar?meal=snack" />
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

	<section class="mt-3 rounded-3xl border-2 bg-white p-4 shadow-sm {bmiBorderClass}">
		<div class="flex items-center justify-between">
			<p class="text-xs font-semibold text-slate-500">{m.bmi()}</p>
			<button
				type="button"
				aria-label={m.bmi_info_title()}
				title={m.bmi_info_title()}
				onclick={() => (infoModal = 'bmi')}
				class="grid h-6 w-6 place-items-center rounded-full bg-slate-100 text-xs font-black text-slate-500 active:bg-slate-200"
			>
				?
			</button>
		</div>
		<div class="mt-1 flex items-baseline gap-2">
			<p class="text-2xl font-black">{nf.format(goals.bmi)}</p>
			{#if bmiInfo}
				<span class="text-xs font-bold text-slate-400">{bmiInfo.label}</span>
			{/if}
		</div>
		{#if bmiInfo}
			<p class="mt-2 rounded-2xl px-3 py-2 text-xs font-semibold {bmiToneClass}">
				{bmiInfo.text}
			</p>
		{/if}
	</section>

	<section class="mt-3 grid grid-cols-2 gap-3">
		<div class="rounded-3xl bg-white p-4 shadow-sm">
			<div class="flex items-center justify-between">
				<p class="text-xs font-semibold text-slate-500">{m.tdee()}</p>
				<button
					type="button"
					aria-label={m.tdee_info_title()}
					title={m.tdee_info_title()}
					onclick={() => (infoModal = 'tdee')}
					class="grid h-5 w-5 shrink-0 place-items-center rounded-full bg-slate-100 text-[10px] font-black text-slate-500 active:bg-slate-200"
				>
					?
				</button>
			</div>
			<p class="mt-1 text-xl font-bold">{nf.format(goals.tdee_kcal)}</p>
		</div>
		<div class="rounded-3xl bg-white p-4 shadow-sm">
			<div class="flex items-center justify-between">
				<p class="text-xs font-semibold text-slate-500">{m.bmr()}</p>
				<button
					type="button"
					aria-label={m.bmr_info_title()}
					title={m.bmr_info_title()}
					onclick={() => (infoModal = 'bmr')}
					class="grid h-5 w-5 shrink-0 place-items-center rounded-full bg-slate-100 text-[10px] font-black text-slate-500 active:bg-slate-200"
				>
					?
				</button>
			</div>
			<p class="mt-1 text-xl font-bold">{nf.format(goals.bmr_kcal)}</p>
		</div>
	</section>
{:else}
	<div class="flex justify-center py-16">
		<div class="h-8 w-8 animate-spin rounded-full border-4 border-emerald-600 border-t-transparent"></div>
	</div>
{/if}

<!-- Info dos cards de metricas: IMC (detalhado, com tabela da OMS) e TDEE/BMR (rapido).
     Os 3 compartilham o mesmo componente/interacao e terminam apontando para o Guia. -->
{#if infoModal}
	<div
		class="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
		role="button"
		tabindex="-1"
		onclick={() => (infoModal = null)}
		onkeydown={(e) => e.key === 'Escape' && (infoModal = null)}
	>
		<div
			class="w-full max-w-md rounded-3xl bg-white p-5"
			role="dialog"
			tabindex="-1"
			onclick={(e) => e.stopPropagation()}
			onkeydown={() => {}}
		>
			<div class="flex items-center justify-between gap-2">
				<h2 class="text-lg font-bold text-slate-900">
					{infoModal === 'bmi' ? m.bmi_info_title() : infoModal === 'tdee' ? m.tdee_info_title() : m.bmr_info_title()}
				</h2>
				<button
					type="button"
					aria-label={m.close()}
					onclick={() => (infoModal = null)}
					class="grid h-9 w-9 shrink-0 place-items-center rounded-full bg-slate-100 text-slate-500 active:bg-slate-200"
				>
					<svg viewBox="0 0 24 24" class="h-5 w-5" fill="none" stroke="currentColor" stroke-width="2"><path d="M6 6l12 12M18 6L6 18" stroke-linecap="round" /></svg>
				</button>
			</div>

			{#if infoModal === 'bmi'}
				<p class="mt-1 font-mono text-sm text-slate-500">{m.bmi_info_formula()}</p>

				<p class="mt-4 text-xs font-bold text-slate-400 uppercase">{m.bmi_info_table_title()}</p>
				<div class="mt-2 overflow-hidden rounded-2xl border-2 border-slate-100">
					{#each Object.entries(BMI_CATEGORIES) as [code, cat], i (code)}
						<div
							class="flex items-center justify-between gap-2 px-3 py-2.5 text-sm
								{i > 0 ? 'border-t border-slate-100' : ''}
								{goals?.bmi_category === code ? 'bg-slate-50' : ''}"
						>
							<span class="flex items-center gap-2 font-semibold text-slate-700">
								<span
									class="h-2.5 w-2.5 shrink-0 rounded-full
										{cat.tone === 'good' ? 'bg-emerald-500' : cat.tone === 'warn' ? 'bg-amber-500' : 'bg-red-500'}"
								></span>
								{cat.label}
							</span>
							<span class="text-slate-400">{cat.range}</span>
						</div>
					{/each}
				</div>

				<div class="mt-4 rounded-2xl bg-sky-50 p-4">
					<p class="text-sm font-bold text-sky-900">{m.bmi_caveat_title()}</p>
					<p class="mt-1 text-sm text-sky-800">{m.bmi_caveat_text()}</p>
				</div>
			{:else}
				<p class="mt-2 text-sm text-slate-600">
					{infoModal === 'tdee' ? m.tdee_info_text() : m.bmr_info_text()}
				</p>
			{/if}

			<p class="mt-4 text-center text-xs text-slate-400">
				{m.guide_pointer_text()}
				<a href="/guia" class="font-bold text-emerald-700">{m.guide_pointer_link()}</a>
			</p>

			<button
				type="button"
				onclick={() => (infoModal = null)}
				class="mt-3 h-12 w-full rounded-2xl bg-emerald-600 font-bold text-[#fff] active:bg-emerald-700"
			>
				{m.close()}
			</button>
		</div>
	</div>
{/if}
