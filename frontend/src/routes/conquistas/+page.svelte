<script lang="ts">
	import { closeOnBack } from '$lib/modalBack';
	import { api, localDay, type AchievementItem, type AchievementsResult, type WeeklyMission } from '$lib/api';
	import { achievementText } from '$lib/achievementsContent';
	import { TITLE_TIER_COUNT, titleIcon, titleName } from '$lib/titleContent';
	import { celebrateAchievement, triggerAchievementCelebrations } from '$lib/celebrationTrigger';
	import { scenePalette } from '$lib/celebrationDefs';
	import { showToast } from '$lib/toast.svelte';
	import { m } from '$lib/paraglide/messages';
	import { getLocale } from '$lib/paraglide/runtime';

	let data = $state<AchievementsResult | null>(null);
	let loading = $state(true);
	const locale = getLocale();
	const nf = new Intl.NumberFormat(locale);

	async function load(): Promise<void> {
		data = await api.getAchievements(localDay(), new Date().getTimezoneOffset());
		loading = false;
		// celebra (subiu de nivel ou conquista) com a animacao cheia; so cai no toast
		// generico se nada de especial aconteceu mas mesmo assim algo foi desbloqueado
		// (nao deveria acontecer, mas fica de rede de seguranca).
		const celebrated = triggerAchievementCelebrations(data);
		if (!celebrated && data.newly_unlocked.length > 0) {
			showToast(m.achievement_unlocked());
		}
	}

	const unlockedCount = $derived(data ? data.achievements.filter((a) => a.unlocked).length : 0);

	// Medalha ainda bloqueada: toca no card pra ver o progresso em destaque. Medalha
	// desbloqueada nao usa esta modal - toca e ja abre direto a animacao de celebracao
	// (poupa um clique), com o botao de compartilhar dentro da propria animacao.
	let openedAchievement = $state<AchievementItem | null>(null);

	function openAchievement(ach: AchievementItem): void {
		if (ach.unlocked) {
			celebrateAchievement(ach, locale, (scene) => shareAchievement(ach, scene));
		} else {
			openedAchievement = ach;
		}
	}

	// Quebra de linha manual (Canvas nao tem isso nativo): mede palavra a palavra e
	// so pula linha quando estoura a largura disponivel.
	function wrapCanvasText(
		ctx: CanvasRenderingContext2D, text: string, cx: number, y: number, maxWidth: number, lineHeight: number
	): void {
		const words = text.split(' ');
		let line = '';
		let cursorY = y;
		for (const word of words) {
			const test = line ? `${line} ${word}` : word;
			if (ctx.measureText(test).width > maxWidth && line) {
				ctx.fillText(line, cx, cursorY);
				line = word;
				cursorY += lineHeight;
			} else {
				line = test;
			}
		}
		if (line) ctx.fillText(line, cx, cursorY);
	}

	// Gera a imagem da medalha (nao existe um arquivo real por conquista - o "icone"
	// e so um emoji). Desenha uma MEDALHA de verdade (fita + aro dourado + disco) nas
	// cores do CENARIO sorteado para a animacao, para a imagem sair da mesma familia
	// visual da celebracao que a pessoa acabou de ver (ver SCENE_PALETTE).
	async function buildAchievementImage(ach: AchievementItem, scene: string): Promise<Blob> {
		const text = achievementText(locale, ach.code);
		const palette = scenePalette(scene);
		const size = 900;
		const canvas = document.createElement('canvas');
		canvas.width = size;
		canvas.height = size;
		const ctx = canvas.getContext('2d');
		if (!ctx) throw new Error('canvas unsupported');

		// mesmo sentido do gradiente do cenario em CSS: claro no topo, escuro embaixo
		const bg = ctx.createLinearGradient(0, 0, 0, size);
		bg.addColorStop(0, palette.from);
		bg.addColorStop(1, palette.to);
		ctx.fillStyle = bg;
		ctx.fillRect(0, 0, size, size);

		const medalCx = size / 2;
		const medalCy = 330;
		const outerR = 190;

		// brilho suave atras da medalha
		const glow = ctx.createRadialGradient(medalCx, medalCy, 40, medalCx, medalCy, outerR + 120);
		glow.addColorStop(0, 'rgba(255,255,255,0.28)');
		glow.addColorStop(1, 'rgba(255,255,255,0)');
		ctx.fillStyle = glow;
		ctx.fillRect(0, 0, size, size);

		// aneis em volta da medalha, como os .ce-ring da animacao (na cor de destaque)
		ctx.strokeStyle = palette.kick;
		for (const [radius, alpha] of [[outerR + 26, 0.55] as const, [outerR + 58, 0.25] as const]) {
			ctx.globalAlpha = alpha;
			ctx.lineWidth = 4;
			ctx.beginPath();
			ctx.arc(medalCx, medalCy, radius, 0, Math.PI * 2);
			ctx.stroke();
		}
		ctx.globalAlpha = 1;

		ctx.textAlign = 'center';
		ctx.fillStyle = palette.kick;
		ctx.font = '700 26px system-ui, sans-serif';
		ctx.fillText(m.achievement_unlocked_kicker().toUpperCase(), size / 2, 80);

		// fita da medalha (2 tiras atras do disco, levemente abertas em V)
		ctx.save();
		ctx.translate(medalCx - 55, medalCy + 70);
		ctx.rotate(-0.18);
		ctx.fillStyle = '#f59e0b';
		ctx.fillRect(-40, 0, 80, 230);
		ctx.restore();
		ctx.save();
		ctx.translate(medalCx + 55, medalCy + 70);
		ctx.rotate(0.18);
		ctx.fillStyle = '#d97706';
		ctx.fillRect(-40, 0, 80, 230);
		ctx.restore();

		// aro dourado
		ctx.beginPath();
		ctx.arc(medalCx, medalCy, outerR, 0, Math.PI * 2);
		const ring = ctx.createLinearGradient(medalCx - outerR, medalCy - outerR, medalCx + outerR, medalCy + outerR);
		ring.addColorStop(0, '#fde68a');
		ring.addColorStop(0.5, '#f59e0b');
		ring.addColorStop(1, '#b45309');
		ctx.fillStyle = ring;
		ctx.fill();

		// disco interno
		ctx.beginPath();
		ctx.arc(medalCx, medalCy, outerR - 22, 0, Math.PI * 2);
		ctx.fillStyle = '#fffbeb';
		ctx.fill();

		// emoji da conquista, centralizado no disco
		ctx.textBaseline = 'middle';
		ctx.font = '190px system-ui, sans-serif';
		ctx.fillText(ach.icon, medalCx, medalCy + 8);
		ctx.textBaseline = 'alphabetic';

		// brilho (reflexo) no canto superior do disco
		ctx.beginPath();
		ctx.arc(medalCx, medalCy, outerR - 22, Math.PI * 1.1, Math.PI * 1.55);
		ctx.lineWidth = 14;
		ctx.strokeStyle = 'rgba(255,255,255,0.6)';
		ctx.stroke();

		// nome e descricao, fora do disco/fita, direto no fundo (cores do cenario)
		ctx.fillStyle = palette.ink;
		ctx.font = '800 50px system-ui, sans-serif';
		ctx.fillText(text.name, size / 2, 700);

		ctx.fillStyle = palette.sub;
		ctx.font = '500 28px system-ui, sans-serif';
		wrapCanvasText(ctx, text.description, size / 2, 750, size - 220, 36);

		ctx.globalAlpha = 0.7;
		ctx.fillStyle = palette.sub;
		ctx.font = '700 24px system-ui, sans-serif';
		ctx.fillText(m.app_name().toUpperCase(), size / 2, size - 50);
		ctx.globalAlpha = 1;

		return new Promise((resolve, reject) => {
			canvas.toBlob((blob) => (blob ? resolve(blob) : reject(new Error('toBlob failed'))), 'image/png');
		});
	}

	async function shareAchievement(ach: AchievementItem, scene: string): Promise<void> {
		const text = achievementText(locale, ach.code);
		const message = m.achievement_share_text({ name: text.name, description: text.description, app: m.app_name() });
		try {
			const blob = await buildAchievementImage(ach, scene);
			const file = new File([blob], `conquista-${ach.code}.png`, { type: 'image/png' });
			if (navigator.canShare?.({ files: [file] })) {
				await navigator.share({ files: [file], text: message });
				return;
			}
			if (navigator.share) {
				await navigator.share({ text: message });
				return;
			}
			// Sem Web Share API (ex.: desktop): baixa a imagem e copia o texto junto
			const url = URL.createObjectURL(blob);
			const a = document.createElement('a');
			a.href = url;
			a.download = file.name;
			a.click();
			URL.revokeObjectURL(url);
			await navigator.clipboard.writeText(message);
			showToast(m.achievement_share_copied());
		} catch (err) {
			if (err instanceof DOMException && err.name === 'AbortError') return; // usuario cancelou o share nativo
			await navigator.clipboard.writeText(message).catch(() => {});
			showToast(m.achievement_share_copied());
		}
	}

	// Trilhas: cada categoria vira um caminho de medalhas em ordem de meta, com a
	// proxima destacada. Substitui a grade solta de 21 medalhas - numa grade a pessoa
	// nao enxerga "onde esta" nem o que vem depois. Peso e pesagens sao trilhas
	// separadas porque medem coisas diferentes (resultado x habito).
	type AchievementTrail = { key: string; title: string; items: AchievementItem[] };
	const TRAIL_DEFS: { key: string; title: () => string; match: (a: AchievementItem) => boolean }[] = [
		{ key: 'workout', title: m.trail_workouts, match: (a) => a.metric === 'total_workouts' },
		{ key: 'streak', title: m.trail_streak, match: (a) => a.category === 'streak' },
		{ key: 'diet', title: m.trail_diet, match: (a) => a.metric === 'diet_days' },
		{ key: 'weigh', title: m.trail_weigh_ins, match: (a) => a.metric === 'weigh_ins' },
		{ key: 'weight', title: m.trail_weight, match: (a) => a.metric === 'weight_lost_kg' }
	];
	const trails = $derived.by((): AchievementTrail[] => {
		if (!data) return [];
		const achievements = data.achievements;
		return TRAIL_DEFS.map((def) => ({
			key: def.key,
			title: def.title(),
			items: achievements.filter(def.match)
		})).filter((trail) => trail.items.length > 0);
	});

	// A proxima medalha da trilha: a primeira ainda bloqueada.
	function trailNext(trail: AchievementTrail): AchievementItem | null {
		return trail.items.find((a) => !a.unlocked) ?? null;
	}

	// Quanto da linha da trilha esta pintado (0 a 1). A linha vai do centro da 1a
	// medalha ao centro da ultima; cada trecho entre duas medalhas vale 1/(n-1).
	// O trecho atual e preenchido pela fracao do caminho entre a meta anterior e a
	// proxima: (atual - meta_anterior) / (proxima_meta - meta_anterior). A meta anterior
	// so vale se for da mesma metrica (na trilha de sequencia as metricas se misturam).
	function trailFill(trail: AchievementTrail): number {
		const total = trail.items.length;
		if (total < 2) return trail.items[0]?.unlocked ? 1 : 0;
		const unlockedCount = trail.items.findIndex((a) => !a.unlocked);
		if (unlockedCount === -1) return 1;
		const next = trail.items[unlockedCount];
		const previous = unlockedCount > 0 ? trail.items[unlockedCount - 1] : null;
		const previousGoal = previous && previous.metric === next.metric ? previous.progress_goal : 0;
		const span = next.progress_goal - previousGoal;
		const partial = span > 0 ? Math.min(1, Math.max(0, (next.progress_current - previousGoal) / span)) : 0;
		return Math.min(1, Math.max(0, (unlockedCount - 1 + partial) / (total - 1)));
	}

	// Rotulo de meta embaixo das medalhas so quando a trilha inteira mede a mesma coisa.
	function trailHasSingleMetric(trail: AchievementTrail): boolean {
		return trail.items.every((a) => a.metric === trail.items[0].metric);
	}

	function missionText(code: WeeklyMission['code'], goal: number): string {
		return { train: m.mission_train, weigh: m.mission_weigh, diet: m.mission_diet }[code]({ goal });
	}

	const levelPct = $derived(
		data?.title_progress_next
			? Math.min(100, (data.title_progress_current / data.title_progress_next) * 100)
			: 100
	);

	$effect(() => {
		load();
	});

	// Voltar fecha a modal aberta em vez de sair da tela (ver lib/modalBack.ts).
	$effect(() => {
		if (openedAchievement) return closeOnBack(() => (openedAchievement = null));
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
	<!-- Nivel (titulo evolutivo): nunca ligado a peso/corpo, so ao total de treinos.
		 Fundo verde fixo nos dois temas, como a tela de fim do treino. -->
	<section class="mb-5 rounded-3xl bg-gradient-to-br from-[#047857] to-[#065f46] p-5 text-[#fff]">
		<div class="flex items-center gap-3.5">
			<span class="grid h-16 w-16 shrink-0 place-items-center rounded-2xl bg-[#fff]/15 text-4xl">
				{titleIcon(data.title_tier)}
			</span>
			<div class="min-w-0">
				<p class="text-xs font-bold text-[#a7f3d0]">
					{m.level_of({ level: data.title_tier + 1, total: TITLE_TIER_COUNT })}
				</p>
				<p class="text-2xl font-black">{titleName(locale, data.title_tier)}</p>
			</div>
		</div>
		<div class="mt-4 h-2 overflow-hidden rounded-full bg-[#fff]/20">
			<div class="h-full rounded-full bg-[#6ee7b7]" style="width: {levelPct}%"></div>
		</div>
		<p class="mt-2 text-sm text-[#d1fae5]">
			{#if data.title_progress_next !== null}
				{m.level_progress_to({
					current: nf.format(data.title_progress_current),
					goal: nf.format(data.title_progress_next),
					name: titleName(locale, data.title_tier + 1)
				})}
			{:else}
				{m.title_max_level()}
			{/if}
		</p>
		<div class="mt-4 grid grid-cols-3 gap-2 text-center">
			<div class="rounded-2xl bg-[#fff]/10 p-2.5">
				<p class="text-xl font-black">🔥 {data.weekly_streak}</p>
				<p class="text-[11px] text-[#a7f3d0]">{m.weeks_streak()}</p>
			</div>
			<div class="rounded-2xl bg-[#fff]/10 p-2.5">
				<p class="text-xl font-black">{unlockedCount}/{data.achievements.length}</p>
				<p class="text-[11px] text-[#a7f3d0]">{m.medals_label()}</p>
			</div>
			<div class="rounded-2xl bg-[#fff]/10 p-2.5">
				<p class="text-xl font-black">{data.workouts_this_week}/{data.streak_week_goal}</p>
				<p class="text-[11px] text-[#a7f3d0]">{m.week_card_this_week()}</p>
			</div>
		</div>
	</section>

	<!-- Missoes da semana: zeram toda segunda, dao algo a ganhar entre as medalhas -->
	<p class="mb-2 px-1 text-xs font-bold tracking-wide text-slate-400 uppercase">
		{m.missions_title()} · {m.missions_until_sunday()}
	</p>
	<section class="mb-5 rounded-3xl bg-white px-4 py-1.5 shadow-sm">
		{#each data.weekly_missions as mission, index (mission.code)}
			{@const done = mission.current >= mission.goal}
			{@const pct = Math.min(100, (mission.current / mission.goal) * 100)}
			<div class="flex items-center gap-3 py-3 {index > 0 ? 'border-t border-slate-100' : ''}">
				{#if done}
					<span class="grid h-7 w-7 shrink-0 place-items-center rounded-full bg-emerald-500 text-[#fff]">
						<svg viewBox="0 0 24 24" class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12l5 5 9-10" /></svg>
					</span>
				{:else}
					<span class="h-7 w-7 shrink-0 rounded-full border-2 border-slate-300"></span>
				{/if}
				<div class="min-w-0 flex-1">
					<p class="text-sm font-bold {done ? 'text-slate-400 line-through' : 'text-slate-900'}">
						{missionText(mission.code, mission.goal)}
					</p>
					{#if !done}
						<div class="mt-1.5 h-1.5 overflow-hidden rounded-full bg-slate-100">
							<div
								class="h-full rounded-full {mission.code === 'train' ? 'bg-orange-500' : 'bg-emerald-500'}"
								style="width: {pct}%"
							></div>
						</div>
					{/if}
				</div>
				<span class="shrink-0 text-sm font-extrabold {done ? 'text-emerald-600' : 'text-slate-600'}">
					{Math.min(mission.current, mission.goal)}/{mission.goal}
				</span>
			</div>
		{/each}
	</section>

	<!-- Trilhas de medalhas -->
	<p class="mb-2 px-1 text-xs font-bold tracking-wide text-slate-400 uppercase">{m.trails_title()}</p>
	<div class="space-y-2.5">
		{#each trails as trail (trail.key)}
			{@const next = trailNext(trail)}
			{@const fill = trailFill(trail)}
			{@const isStreakTrail = trail.key === 'streak'}
			<section class="rounded-3xl bg-white p-4 shadow-sm">
				<div class="flex items-baseline justify-between gap-2">
					<p class="font-extrabold text-slate-900">{trail.title}</p>
					<p class="truncate text-xs font-bold {isStreakTrail ? 'text-orange-600' : 'text-emerald-700'}">
						{#if next}
							{m.trail_next({
								current: nf.format(Math.floor(next.progress_current * 10) / 10),
								goal: nf.format(next.progress_goal)
							})}
						{:else}
							{m.trail_complete()}
						{/if}
					</p>
				</div>
				<div class="relative mt-4 flex items-center justify-between">
					<!-- linha de fundo e linha pintada, do centro da 1a ao centro da ultima medalha -->
					<div class="absolute inset-x-[22px] top-1/2 h-1 -translate-y-1/2 rounded-full bg-slate-200"></div>
					<div
						class="absolute top-1/2 left-[22px] h-1 -translate-y-1/2 rounded-full {isStreakTrail ? 'bg-orange-500' : 'bg-emerald-500'}"
						style="width: calc((100% - 44px) * {fill})"
					></div>
					{#each trail.items as ach (ach.code)}
						{@const isNext = next?.code === ach.code}
						<button
							type="button"
							onclick={() => openAchievement(ach)}
							aria-label={achievementText(locale, ach.code).name}
							class="relative grid shrink-0 place-items-center rounded-full text-2xl active:scale-95
								{ach.unlocked
									? 'h-11 w-11 bg-amber-100 ring-3 ring-amber-500'
									: isNext
										? `trail-next h-13 w-13 bg-white ring-3 outline-6 ${isStreakTrail ? 'ring-orange-500 outline-orange-100' : 'ring-emerald-500 outline-emerald-100'}`
										: 'h-11 w-11 bg-slate-100'}"
						>
							<span class={ach.unlocked ? '' : isNext ? 'grayscale-[60%]' : 'opacity-40 grayscale'}>{ach.icon}</span>
						</button>
					{/each}
				</div>
				{#if trailHasSingleMetric(trail)}
					<div class="mt-1.5 flex justify-between">
						{#each trail.items as ach (ach.code)}
							<span
								class="text-center text-[10px] font-bold {next?.code === ach.code ? 'w-13' : 'w-11'}
									{next?.code === ach.code ? (isStreakTrail ? 'text-orange-600' : 'text-emerald-700') : 'text-slate-400'}"
							>
								{nf.format(ach.progress_goal)}
							</span>
						{/each}
					</div>
				{/if}
			</section>
		{/each}
	</div>
{/if}

<!-- Medalha ainda bloqueada, so o progresso em destaque (desbloqueada abre a
	 celebracao direto, ver openAchievement) -->
{#if openedAchievement}
	{@const opened = openedAchievement}
	{@const openedText = achievementText(locale, opened.code)}
	{@const openedPct = Math.min(100, (opened.progress_current / opened.progress_goal) * 100)}
	<div
		class="fixed inset-0 z-40 flex items-center justify-center bg-black/50 p-4"
		role="button"
		tabindex="-1"
		onclick={() => (openedAchievement = null)}
		onkeydown={(e) => e.key === 'Escape' && (openedAchievement = null)}
	>
		<div
			class="w-full max-w-sm rounded-3xl bg-white p-6 text-center"
			role="dialog"
			tabindex="-1"
			onclick={(e) => e.stopPropagation()}
			onkeydown={() => {}}
		>
			<span class="text-7xl opacity-30 grayscale">{opened.icon}</span>
			<p class="mt-3 text-lg font-black text-slate-400">{openedText.name}</p>
			<div class="mt-3 h-2 overflow-hidden rounded-full bg-slate-100">
				<div class="h-full rounded-full bg-emerald-500" style="width: {openedPct}%"></div>
			</div>
			<p class="mt-1.5 text-xs text-slate-400">{opened.progress_current}/{opened.progress_goal}</p>
			<button
				type="button"
				onclick={() => (openedAchievement = null)}
				class="mt-5 text-sm font-semibold text-slate-400"
			>
				{m.close()}
			</button>
		</div>
	</div>
{/if}

<style>
	/* A proxima medalha da trilha "respira" devagar para chamar o olho sem piscar.
	   :global porque a classe entra por string montada no template (o Svelte nao a
	   enxerga para aplicar o escopo). */
	:global(.trail-next) {
		animation: trail-next-breathe 2.4s ease-in-out infinite;
	}
	@keyframes trail-next-breathe {
		50% {
			transform: scale(1.06);
		}
	}
	@media (prefers-reduced-motion: reduce) {
		:global(.trail-next) {
			animation: none;
		}
	}
</style>
