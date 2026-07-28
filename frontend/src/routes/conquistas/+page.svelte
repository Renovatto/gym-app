<script lang="ts">
	import { api, localDay, type AchievementItem, type AchievementsResult } from '$lib/api';
	import { achievementText } from '$lib/achievementsContent';
	import { titleIcon, titleName } from '$lib/titleContent';
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

	// "Quase la": a conquista NAO desbloqueada mais perto da meta (cria antecipacao).
	const closestToUnlock = $derived.by(() => {
		if (!data) return null;
		const locked = data.achievements.filter((a) => !a.unlocked && a.progress_goal > 0);
		if (locked.length === 0) return null;
		return locked.reduce((best, a) =>
			a.progress_current / a.progress_goal > best.progress_current / best.progress_goal ? a : best
		);
	});
	const closestPct = $derived(
		closestToUnlock ? Math.min(100, (closestToUnlock.progress_current / closestToUnlock.progress_goal) * 100) : 0
	);

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
	<!-- Titulo evolutivo: nunca ligado a peso/corpo, so a total de treinos -->
	<section class="mb-3 flex items-center gap-3 rounded-3xl bg-white p-4 shadow-sm">
		<span class="grid h-14 w-14 shrink-0 place-items-center rounded-2xl bg-emerald-50 text-3xl">
			{titleIcon(data.title_tier)}
		</span>
		<div class="min-w-0 flex-1">
			<p class="font-bold text-slate-900">{titleName(locale, data.title_tier)}</p>
			{#if data.title_progress_next !== null}
				<div class="mt-1.5 h-1.5 overflow-hidden rounded-full bg-slate-100">
					<div
						class="h-full rounded-full bg-emerald-500"
						style="width: {Math.min(100, (data.title_progress_current / data.title_progress_next) * 100)}%"
					></div>
				</div>
				<p class="mt-1 text-xs text-slate-400">
					{m.title_progress_next({
						current: nf.format(data.title_progress_current),
						goal: nf.format(data.title_progress_next)
					})}
				</p>
			{:else}
				<p class="mt-0.5 text-xs text-slate-400">{m.title_max_level()}</p>
			{/if}
		</div>
	</section>

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

	<!-- Quase la: a conquista mais perto da meta, para criar antecipacao -->
	{#if closestToUnlock}
		{@const closestText = achievementText(locale, closestToUnlock.code)}
		<section class="mb-4 rounded-3xl border-2 border-emerald-200 bg-emerald-50 p-4">
			<p class="mb-2 flex items-center gap-1 text-xs font-bold text-emerald-700 uppercase">
				<svg viewBox="0 0 24 24" class="h-3.5 w-3.5" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M13 2 3 14h7l-1 8 11-14h-8z" stroke-linecap="round" stroke-linejoin="round" /></svg>
				{m.almost_there_label()}
			</p>
			<div class="flex items-center gap-3">
				<span class="text-3xl opacity-60 grayscale">{closestToUnlock.icon}</span>
				<div class="min-w-0 flex-1">
					<p class="text-sm font-bold text-slate-900">{closestText.name}</p>
					<div class="mt-1.5 h-1.5 overflow-hidden rounded-full bg-white">
						<div class="h-full rounded-full bg-emerald-500" style="width: {closestPct}%"></div>
					</div>
					<p class="mt-1 text-xs text-emerald-700">
						{nf.format(closestToUnlock.progress_current)}/{nf.format(closestToUnlock.progress_goal)}
					</p>
				</div>
			</div>
		</section>
	{/if}

	<p class="mb-2 px-1 text-xs font-bold tracking-wide text-slate-400 uppercase">
		{m.medals_label()} · {unlockedCount}/{data.achievements.length}
	</p>
	<div class="grid grid-cols-2 gap-3">
		{#each data.achievements as ach (ach.code)}
			{@const text = achievementText(locale, ach.code)}
			{@const pct = Math.min(100, (ach.progress_current / ach.progress_goal) * 100)}
			<button
				type="button"
				onclick={() => openAchievement(ach)}
				class="rounded-3xl border-2 p-4 text-center transition-colors
					{ach.unlocked ? 'border-emerald-200 bg-white active:bg-emerald-50' : 'border-slate-100 bg-slate-50 active:bg-slate-100'}"
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
			</button>
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
