<script lang="ts">
	import type { AchievementsResult } from '$lib/api';
	import { achievementText } from '$lib/achievementsContent';
	import { titleName } from '$lib/titleContent';
	import { showToast } from '$lib/toast.svelte';
	import { m } from '$lib/paraglide/messages';
	import { getLocale } from '$lib/paraglide/runtime';

	/*
	 * Tela de fim do treino. Antes, se o treino nao desbloqueava nenhuma medalha, o fim
	 * era mudo (so um toast). Aqui TODO treino mostra o que ele moveu: a semana, a
	 * proxima medalha de treinos, o nivel e as missoes - o incentivo vem de ver o
	 * progresso andar, nao so de desbloquear.
	 *
	 * Fundo verde escuro fixo (igual nos dois temas): e uma tela de comemoracao, com
	 * identidade propria, como a celebracao das medalhas.
	 */

	let {
		routineName,
		durationSeconds,
		setsDone,
		exercisesDone,
		achievements,
		onDone
	}: {
		routineName: string;
		durationSeconds: number;
		setsDone: number;
		exercisesDone: number;
		achievements: AchievementsResult | null;
		onDone: () => void;
	} = $props();

	const locale = getLocale();
	const minutes = $derived(Math.max(1, Math.round(durationSeconds / 60)));
	const workoutNumber = $derived(achievements ? Math.round(achievements.title_progress_current) : null);

	const goal = $derived(achievements?.streak_week_goal ?? 0);
	const doneThisWeek = $derived(achievements?.workouts_this_week ?? 0);
	// Este treino foi exatamente o que fechou a meta da semana: a sequencia subiu +1.
	const securedNow = $derived(achievements !== null && doneThisWeek === goal);
	const weekSecured = $derived(achievements !== null && doneThisWeek >= goal);
	// treinos que ainda faltam para a semana contar (nunca negativo)
	const workoutsMissing = $derived(Math.max(0, goal - doneThisWeek));

	// Os 7 dias da semana (seg-dom): cada um mostra a inicial do dia e o estado - treinou
	// (check), hoje, perdido (passou sem treino) ou ainda por vir.
	type WeekDot = { label: string; state: 'done' | 'today' | 'missed' | 'future' };
	const weekDots = $derived.by((): WeekDot[] => {
		if (!achievements) return [];
		const trained = new Set(achievements.week_workout_days);
		const weekdayFormat = new Intl.DateTimeFormat(locale, { weekday: 'narrow' });
		const now = new Date();
		const todayKey = toDayKey(now);
		const monday = new Date(now);
		monday.setDate(now.getDate() - ((now.getDay() + 6) % 7));
		return Array.from({ length: 7 }, (_, index) => {
			const date = new Date(monday);
			date.setDate(monday.getDate() + index);
			const key = toDayKey(date);
			let state: WeekDot['state'];
			if (trained.has(key)) state = 'done';
			else if (key === todayKey) state = 'today';
			else if (key < todayKey) state = 'missed';
			else state = 'future';
			return { label: weekdayFormat.format(date), state };
		});
	});

	function toDayKey(date: Date): string {
		return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`;
	}

	// Proxima medalha de TREINOS (a que este treino acabou de mover).
	const nextWorkoutMedal = $derived(
		achievements?.achievements.find((a) => a.metric === 'total_workouts' && !a.unlocked) ?? null
	);
	const medalRemaining = $derived(
		nextWorkoutMedal ? Math.max(0, nextWorkoutMedal.progress_goal - nextWorkoutMedal.progress_current) : 0
	);
	// Anel da medalha: circunferencia = 2 * pi * raio; o trecho pintado e a fracao feita.
	const RING_RADIUS = 31;
	const ringCircumference = 2 * Math.PI * RING_RADIUS;
	const ringFilled = $derived(
		nextWorkoutMedal
			? (Math.min(1, nextWorkoutMedal.progress_current / nextWorkoutMedal.progress_goal)) * ringCircumference
			: 0
	);

	const levelPct = $derived(
		achievements?.title_progress_next
			? Math.min(100, (achievements.title_progress_current / achievements.title_progress_next) * 100)
			: 100
	);
	const nextTitleName = $derived(
		achievements && achievements.title_progress_next !== null
			? titleName(locale, achievements.title_tier + 1)
			: null
	);

	const missionsDone = $derived(
		achievements?.weekly_missions.filter((mission) => mission.current >= mission.goal).length ?? 0
	);
	const trainMissionDone = $derived(
		achievements?.weekly_missions.some((mission) => mission.code === 'train' && mission.current >= mission.goal) ??
			false
	);

	// Quebra de linha manual (Canvas nao tem isso nativo): mede palavra a palavra.
	function wrapLines(ctx: CanvasRenderingContext2D, text: string, maxWidth: number): string[] {
		const lines: string[] = [];
		let line = '';
		for (const word of text.split(' ')) {
			const test = line ? `${line} ${word}` : word;
			if (ctx.measureText(test).width > maxWidth && line) {
				lines.push(line);
				line = word;
			} else {
				line = test;
			}
		}
		if (line) lines.push(line);
		return lines;
	}

	// Imagem do resumo (o app nao tem um arquivo pronto): reproduz a tela inteira - numero
	// do treino, totais, semana com os dias, medalha com o anel, nivel e missoes - na mesma
	// identidade verde. A altura acompanha o que existe: sem dados de conquistas, so o topo.
	async function buildSummaryImage(): Promise<Blob> {
		const width = 900;
		const margin = 60;
		const contentWidth = width - margin * 2;
		const hasWeek = achievements !== null;
		const hasMedal = nextWorkoutMedal !== null;
		const height = 620 + (hasWeek ? 350 : 0) + (hasMedal ? 220 : 0) + (hasWeek ? 230 : 0) + 110;

		const canvas = document.createElement('canvas');
		canvas.width = width;
		canvas.height = height;
		const ctx = canvas.getContext('2d');
		if (!ctx) throw new Error('canvas unsupported');

		const box = (x: number, y: number, w: number, h: number, radius: number, fill: string | CanvasGradient) => {
			ctx.fillStyle = fill;
			ctx.beginPath();
			ctx.roundRect(x, y, w, h, radius);
			ctx.fill();
		};

		const bg = ctx.createLinearGradient(0, 0, 0, height);
		bg.addColorStop(0, '#047857');
		bg.addColorStop(0.5, '#064e3b');
		bg.addColorStop(1, '#022c22');
		ctx.fillStyle = bg;
		ctx.fillRect(0, 0, width, height);

		// --- topo: kicker, numero do treino, nome da rotina
		ctx.textAlign = 'center';
		ctx.fillStyle = '#6ee7b7';
		ctx.font = '800 30px system-ui, sans-serif';
		ctx.fillText(m.workout_summary_kicker().toUpperCase(), width / 2, 100);
		ctx.fillStyle = '#ffffff';
		ctx.font = '900 210px system-ui, sans-serif';
		ctx.fillText(workoutNumber !== null ? `#${workoutNumber}` : '\u2713', width / 2, 300);
		ctx.fillStyle = '#a7f3d0';
		ctx.font = '600 38px system-ui, sans-serif';
		ctx.fillText(routineName, width / 2, 365);

		// --- totais: duracao, series, exercicios
		const stats = [
			{ value: `${minutes} min`, label: m.workout_summary_duration() },
			{ value: String(setsDone), label: m.workout_summary_sets() },
			{ value: String(exercisesDone), label: m.workout_summary_exercises() }
		];
		const statWidth = (contentWidth - 2 * 30) / 3;
		stats.forEach((stat, index) => {
			const x = margin + index * (statWidth + 30);
			box(x, 420, statWidth, 130, 28, 'rgba(255,255,255,0.1)');
			ctx.fillStyle = '#ffffff';
			ctx.font = '900 54px system-ui, sans-serif';
			ctx.fillText(stat.value, x + statWidth / 2, 490);
			ctx.fillStyle = '#a7f3d0';
			ctx.font = '600 26px system-ui, sans-serif';
			ctx.fillText(stat.label, x + statWidth / 2, 528);
		});

		let y = 590;
		if (achievements) {
			// --- semana: titulo, contagem e os 7 dias
			const weekHeight = 320;
			if (weekSecured) {
				const orange = ctx.createLinearGradient(margin, y, margin + contentWidth, y + weekHeight);
				orange.addColorStop(0, '#f97316');
				orange.addColorStop(1, '#f59e0b');
				box(margin, y, contentWidth, weekHeight, 44, orange);
			} else {
				box(margin, y, contentWidth, weekHeight, 44, 'rgba(255,255,255,0.1)');
			}
			ctx.textAlign = 'left';
			ctx.font = '72px system-ui, sans-serif';
			ctx.fillText('\u{1F525}', margin + 36, y + 100);
			ctx.fillStyle = weekSecured ? '#fff7ed' : '#6ee7b7';
			ctx.font = '800 26px system-ui, sans-serif';
			ctx.fillText(
				(weekSecured ? m.workout_summary_week_secured() : m.workout_summary_week_progress()).toUpperCase(),
				margin + 150,
				y + 62
			);
			ctx.fillStyle = '#ffffff';
			ctx.font = '900 46px system-ui, sans-serif';
			ctx.fillText(
				weekSecured
					? m.workout_summary_streak_weeks({ count: achievements.weekly_streak })
					: m.workout_summary_week_count({ done: doneThisWeek, goal }),
				margin + 150,
				y + 112
			);
			if (!weekSecured) {
				ctx.fillStyle = '#fed7aa';
				ctx.font = '600 26px system-ui, sans-serif';
				ctx.fillText(
					workoutsMissing === 1
						? m.workout_summary_week_missing_one()
						: m.workout_summary_week_missing_many({ count: workoutsMissing }),
					margin + 150,
					y + 150
				);
			}
			if (securedNow) {
				box(margin + contentWidth - 130, y + 40, 96, 56, 28, 'rgba(255,255,255,0.28)');
				ctx.fillStyle = '#ffffff';
				ctx.textAlign = 'center';
				ctx.font = '900 34px system-ui, sans-serif';
				ctx.fillText('+1', margin + contentWidth - 82, y + 79);
			}

			// os 7 dias: check (treinou), tracejado (hoje), x (passou), apagado (por vir)
			const dotStep = (contentWidth - 60) / 7;
			weekDots.forEach((dot, index) => {
				const cx = margin + 30 + dotStep * index + dotStep / 2;
				const cy = y + 230;
				ctx.textAlign = 'center';
				if (dot.state === 'done') {
					ctx.fillStyle = '#ffffff';
					ctx.beginPath();
					ctx.arc(cx, cy, 34, 0, Math.PI * 2);
					ctx.fill();
					ctx.strokeStyle = '#ea580c';
					ctx.lineWidth = 8;
					ctx.lineCap = 'round';
					ctx.lineJoin = 'round';
					ctx.beginPath();
					ctx.moveTo(cx - 13, cy);
					ctx.lineTo(cx - 3, cy + 11);
					ctx.lineTo(cx + 14, cy - 11);
					ctx.stroke();
				} else if (dot.state === 'today') {
					ctx.strokeStyle = 'rgba(255,255,255,0.85)';
					ctx.lineWidth = 5;
					ctx.setLineDash([10, 9]);
					ctx.beginPath();
					ctx.arc(cx, cy, 32, 0, Math.PI * 2);
					ctx.stroke();
					ctx.setLineDash([]);
				} else if (dot.state === 'missed') {
					ctx.fillStyle = 'rgba(0,0,0,0.22)';
					ctx.beginPath();
					ctx.arc(cx, cy, 34, 0, Math.PI * 2);
					ctx.fill();
					ctx.strokeStyle = 'rgba(255,255,255,0.6)';
					ctx.lineWidth = 7;
					ctx.lineCap = 'round';
					ctx.beginPath();
					ctx.moveTo(cx - 11, cy - 11);
					ctx.lineTo(cx + 11, cy + 11);
					ctx.moveTo(cx + 11, cy - 11);
					ctx.lineTo(cx - 11, cy + 11);
					ctx.stroke();
				} else {
					ctx.fillStyle = 'rgba(255,255,255,0.15)';
					ctx.beginPath();
					ctx.arc(cx, cy, 34, 0, Math.PI * 2);
					ctx.fill();
				}
				ctx.fillStyle = dot.state === 'done' || dot.state === 'today' ? '#ffffff' : 'rgba(255,255,255,0.55)';
				ctx.font = '800 24px system-ui, sans-serif';
				ctx.fillText(dot.label.toUpperCase(), cx, cy + 66);
			});
			y += weekHeight + 30;
		}

		if (achievements && nextWorkoutMedal) {
			// --- proxima medalha: anel de progresso + texto
			const medalHeight = 190;
			box(margin, y, contentWidth, medalHeight, 44, '#ffffff');
			const ringX = margin + 40 + 62;
			const ringY = y + medalHeight / 2;
			const fraction = Math.min(1, nextWorkoutMedal.progress_current / nextWorkoutMedal.progress_goal);
			ctx.lineWidth = 14;
			ctx.lineCap = 'round';
			ctx.strokeStyle = '#f1f5f9';
			ctx.beginPath();
			ctx.arc(ringX, ringY, 56, 0, Math.PI * 2);
			ctx.stroke();
			ctx.strokeStyle = '#10b981';
			ctx.beginPath();
			ctx.arc(ringX, ringY, 56, -Math.PI / 2, -Math.PI / 2 + Math.PI * 2 * fraction);
			ctx.stroke();
			ctx.textAlign = 'center';
			ctx.textBaseline = 'middle';
			ctx.font = '58px system-ui, sans-serif';
			ctx.fillStyle = '#000000';
			ctx.fillText(nextWorkoutMedal.icon, ringX, ringY + 4);
			ctx.textBaseline = 'alphabetic';

			const textX = margin + 40 + 124 + 36;
			const textWidth = margin + contentWidth - 30 - textX;
			ctx.textAlign = 'left';
			ctx.fillStyle = '#059669';
			ctx.font = '800 24px system-ui, sans-serif';
			ctx.fillText(
				m
					.workout_summary_medal_progress({
						current: Math.floor(nextWorkoutMedal.progress_current),
						goal: nextWorkoutMedal.progress_goal
					})
					.toUpperCase(),
				textX,
				y + 62
			);
			ctx.fillStyle = '#0f172a';
			ctx.font = '900 34px system-ui, sans-serif';
			const medalTitle =
				medalRemaining === 1
					? m.workout_summary_medal_next_one()
					: m.workout_summary_medal_next_many({ count: medalRemaining });
			const titleLines = wrapLines(ctx, medalTitle, textWidth).slice(0, 2);
			titleLines.forEach((line, lineIndex) => ctx.fillText(line, textX, y + 104 + lineIndex * 40));
			ctx.fillStyle = '#64748b';
			ctx.font = '600 26px system-ui, sans-serif';
			ctx.fillText(achievementText(locale, nextWorkoutMedal.code).name, textX, y + 104 + titleLines.length * 40 + 4);
			y += medalHeight + 30;
		}

		if (achievements) {
			// --- nivel e missoes lado a lado
			const cardHeight = 200;
			const cardWidth = (contentWidth - 30) / 2;
			ctx.textAlign = 'left';

			box(margin, y, cardWidth, cardHeight, 40, 'rgba(255,255,255,0.1)');
			ctx.fillStyle = '#6ee7b7';
			ctx.font = '800 22px system-ui, sans-serif';
			ctx.fillText(m.workout_summary_level().toUpperCase(), margin + 30, y + 50);
			ctx.fillStyle = '#ffffff';
			ctx.font = '800 30px system-ui, sans-serif';
			ctx.fillText(
				nextTitleName ? m.workout_summary_level_next({ name: nextTitleName }) : titleName(locale, achievements.title_tier),
				margin + 30,
				y + 92
			);
			box(margin + 30, y + 116, cardWidth - 60, 14, 7, 'rgba(255,255,255,0.15)');
			box(margin + 30, y + 116, Math.max(14, ((cardWidth - 60) * levelPct) / 100), 14, 7, '#6ee7b7');
			if (achievements.title_progress_next !== null) {
				ctx.fillStyle = '#a7f3d0';
				ctx.font = '600 24px system-ui, sans-serif';
				ctx.fillText(
					`${Math.round(achievements.title_progress_current)}/${achievements.title_progress_next}`,
					margin + 30,
					y + 168
				);
			}

			const missionX = margin + cardWidth + 30;
			box(missionX, y, cardWidth, cardHeight, 40, trainMissionDone ? '#fbbf24' : 'rgba(255,255,255,0.1)');
			ctx.fillStyle = trainMissionDone ? '#422006' : '#6ee7b7';
			ctx.font = '800 22px system-ui, sans-serif';
			ctx.fillText(
				(trainMissionDone ? m.workout_summary_mission_done() : m.missions_title()).toUpperCase(),
				missionX + 30,
				y + 50
			);
			ctx.fillStyle = trainMissionDone ? '#422006' : '#ffffff';
			ctx.font = '800 30px system-ui, sans-serif';
			const missionTitle = trainMissionDone
				? m.mission_train({ goal })
				: m.workout_summary_missions_count({ done: missionsDone, total: achievements.weekly_missions.length });
			wrapLines(ctx, missionTitle, cardWidth - 60)
				.slice(0, 2)
				.forEach((line, lineIndex) => ctx.fillText(line, missionX + 30, y + 92 + lineIndex * 38));
			if (trainMissionDone) {
				ctx.font = '700 24px system-ui, sans-serif';
				ctx.fillText(
					m.workout_summary_missions_count({ done: missionsDone, total: achievements.weekly_missions.length }),
					missionX + 30,
					y + 168
				);
			}
			y += cardHeight + 30;
		}

		ctx.textAlign = 'center';
		ctx.globalAlpha = 0.7;
		ctx.fillStyle = '#a7f3d0';
		ctx.font = '700 26px system-ui, sans-serif';
		ctx.fillText(m.app_name().toUpperCase(), width / 2, height - 44);
		ctx.globalAlpha = 1;

		return new Promise((resolve, reject) => {
			canvas.toBlob((blob) => (blob ? resolve(blob) : reject(new Error('toBlob failed'))), 'image/png');
		});
	}

	// Compartilhar em cadeia, do melhor para o mais simples, e SEMPRE termina com um
	// aviso: 1) imagem + texto pelo menu nativo; 2) so o texto; 3) copiar; 4) baixar a
	// imagem. A versao anterior so tentava o texto e, sem a API de compartilhar (ex.:
	// app aberto por http na rede local), falhava calada.
	async function shareSummary(): Promise<void> {
		// Texto com as mesmas informacoes da imagem (para apps que so aceitam texto e para
		// quem copia): linha do treino, semana e, quando existe, a proxima medalha.
		const lines: string[] = [
			m.workout_summary_share_text({
				routine: routineName,
				minutes,
				sets: setsDone,
				streak: achievements?.weekly_streak ?? 0,
				app: m.app_name()
			})
		];
		if (achievements) {
			lines.push(
				weekSecured
					? `${m.workout_summary_week_secured()}: ${m.workout_summary_streak_weeks({ count: achievements.weekly_streak })}`
					: `${m.workout_summary_week_progress()}: ${m.workout_summary_week_count({ done: doneThisWeek, goal })}`
			);
			if (nextWorkoutMedal) {
				lines.push(
					`${medalRemaining === 1 ? m.workout_summary_medal_next_one() : m.workout_summary_medal_next_many({ count: medalRemaining })} (${achievementText(locale, nextWorkoutMedal.code).name})`
				);
			}
			lines.push(
				`${m.workout_summary_level()}: ${nextTitleName ? m.workout_summary_level_next({ name: nextTitleName }) : titleName(locale, achievements.title_tier)}`,
				m.workout_summary_missions_count({ done: missionsDone, total: achievements.weekly_missions.length })
			);
		}
		const text = lines.join('\n');
		let blob: Blob | null = null;
		try {
			blob = await buildSummaryImage();
		} catch {
			// sem imagem ainda da para compartilhar o texto
		}
		try {
			if (blob) {
				const file = new File([blob], 'treino.png', { type: 'image/png' });
				if (navigator.canShare?.({ files: [file] })) {
					await navigator.share({ files: [file], text });
					return;
				}
			}
			if (navigator.share) {
				await navigator.share({ text });
				return;
			}
		} catch (err) {
			if (err instanceof DOMException && err.name === 'AbortError') return; // cancelou o menu nativo
			// qualquer outra falha do menu nativo cai nas alternativas abaixo
		}
		let copied = false;
		try {
			await navigator.clipboard.writeText(text);
			copied = true;
		} catch {
			// sem area de transferencia (contexto nao seguro): resta baixar a imagem
		}
		if (blob) {
			const url = URL.createObjectURL(blob);
			const link = document.createElement('a');
			link.href = url;
			link.download = 'treino.png';
			link.click();
			URL.revokeObjectURL(url);
		}
		showToast(copied || blob ? m.achievement_share_copied() : m.error_generic());
	}

	// Confete que cai sem parar enquanto a tela estiver aberta. Posicao, tamanho, cor e
	// velocidade sao calculados do indice (e nao sorteados) para a chuva ser sempre a
	// mesma e nao mudar a cada render. O atraso NEGATIVO faz cada peca ja nascer em um
	// ponto diferente da queda: o efeito comeca cheio, sem esperar as pecas descerem.
	const CONFETTI_COLORS = ['#fbbf24', '#f472b6', '#38bdf8', '#6ee7b7', '#fb923c', '#a78bfa'];
	const CONFETTI = Array.from({ length: 48 }, (_, i) => ({
		left: `${(i * 37 + 11) % 100}%`,
		color: CONFETTI_COLORS[i % CONFETTI_COLORS.length],
		round: i % 3 === 0,
		size: 6 + (i % 4) * 2,
		duration: 5 + (i % 6) * 0.9, // segundos para atravessar a tela
		delay: -((i * 0.71) % 7), // negativo: ja em queda ao abrir
		drift: ((i % 9) - 4) * 14, // deriva lateral em px
		spin: (i % 2 === 0 ? 1 : -1) * (360 + (i % 5) * 180) // graus girados na queda
	}));
</script>

<div
	class="fixed inset-0 z-60 overflow-y-auto bg-gradient-to-b from-[#047857] via-[#064e3b] to-[#022c22] text-[#fff]"
	role="dialog"
	aria-modal="true"
	aria-label={m.workout_summary_kicker()}
>
	<!-- camada propria e fixa: o confete nao rola junto com o conteudo -->
	<div class="pointer-events-none fixed inset-0 overflow-hidden" aria-hidden="true">
		{#each CONFETTI as piece, index (index)}
			<span
				class="summary-confetti absolute top-0 {piece.round ? 'rounded-full' : 'rounded-sm'}"
				style="left: {piece.left}; width: {piece.size}px; height: {piece.round ? piece.size : piece.size * 1.7}px; background: {piece.color}; animation-duration: {piece.duration}s; animation-delay: {piece.delay}s; --drift: {piece.drift}px; --spin: {piece.spin}deg"
			></span>
		{/each}
	</div>

	<div class="relative mx-auto flex min-h-full max-w-md flex-col px-4 pt-[calc(1.75rem+env(safe-area-inset-top))] pb-[calc(1.25rem+env(safe-area-inset-bottom))]">
		<div class="text-center">
			<p class="text-xs font-extrabold tracking-[0.1em] text-[#6ee7b7] uppercase">{m.workout_summary_kicker()}</p>
			{#if workoutNumber !== null}
				<p class="summary-pop mt-1.5 text-7xl leading-none font-black tracking-tight">#{workoutNumber}</p>
			{/if}
			<p class="mt-1.5 text-sm text-[#a7f3d0]">{routineName}</p>
		</div>

		<div class="mt-5 grid grid-cols-3 gap-2 text-center">
			<div class="rounded-2xl bg-[#fff]/10 p-2.5">
				<p class="text-xl font-black">{minutes}<span class="text-xs font-bold"> min</span></p>
				<p class="text-[11px] text-[#a7f3d0]">{m.workout_summary_duration()}</p>
			</div>
			<div class="rounded-2xl bg-[#fff]/10 p-2.5">
				<p class="text-xl font-black">{setsDone}</p>
				<p class="text-[11px] text-[#a7f3d0]">{m.workout_summary_sets()}</p>
			</div>
			<div class="rounded-2xl bg-[#fff]/10 p-2.5">
				<p class="text-xl font-black">{exercisesDone}</p>
				<p class="text-[11px] text-[#a7f3d0]">{m.workout_summary_exercises()}</p>
			</div>
		</div>

		{#if achievements}
			<!-- Semana / sequencia -->
			<section
				class="mt-4 rounded-3xl p-4 {weekSecured
					? 'bg-gradient-to-br from-[#f97316] to-[#f59e0b] shadow-xl shadow-[#f97316]/35'
					: 'bg-[#fff]/10'}"
			>
				<div class="flex items-center gap-3">
					<span class="text-4xl">🔥</span>
					<div class="min-w-0 flex-1">
						<p class="text-xs font-extrabold text-[#fff7ed] uppercase">
							{weekSecured ? m.workout_summary_week_secured() : m.workout_summary_week_progress()}
						</p>
						<p class="text-xl font-black">
							{weekSecured
								? m.workout_summary_streak_weeks({ count: achievements.weekly_streak })
								: m.workout_summary_week_count({ done: doneThisWeek, goal })}
						</p>
						{#if !weekSecured}
							<p class="text-xs text-[#fed7aa]">
								{workoutsMissing === 1
									? m.workout_summary_week_missing_one()
									: m.workout_summary_week_missing_many({ count: workoutsMissing })}
							</p>
						{/if}
					</div>
					{#if securedNow}
						<span class="summary-pop rounded-full bg-[#fff]/25 px-2.5 py-1 text-sm font-black">+1</span>
					{/if}
				</div>
				<div class="mt-3.5 grid grid-cols-7 gap-1">
					{#each weekDots as dot, index (index)}
						<div class="flex flex-col items-center gap-1">
							{#if dot.state === 'done'}
								<span class="grid h-8 w-8 place-items-center rounded-full bg-[#fff] text-[#ea580c] shadow-md">
									<svg viewBox="0 0 24 24" class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="3.4" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12l5 5 9-10" /></svg>
								</span>
							{:else if dot.state === 'today'}
								<span class="h-8 w-8 rounded-full border-2 border-dashed border-[#fff]/80"></span>
							{:else if dot.state === 'missed'}
								<span class="grid h-8 w-8 place-items-center rounded-full bg-[#000]/20 text-[#fff]/60">
									<svg viewBox="0 0 24 24" class="h-3.5 w-3.5" fill="none" stroke="currentColor" stroke-width="3.4" stroke-linecap="round"><path d="M7 7l10 10M17 7L7 17" /></svg>
								</span>
							{:else}
								<span class="h-8 w-8 rounded-full bg-[#fff]/15"></span>
							{/if}
							<span class="text-[10px] font-extrabold uppercase {dot.state === 'done' || dot.state === 'today' ? 'text-[#fff]' : 'text-[#fff]/55'}">{dot.label}</span>
						</div>
					{/each}
				</div>
			</section>

			<!-- Proxima medalha de treinos, com anel de progresso -->
			{#if nextWorkoutMedal}
				<section class="mt-2.5 flex items-center gap-3.5 rounded-3xl bg-[#fff] p-4 text-[#0f172a]">
					<div class="relative h-[72px] w-[72px] shrink-0">
						<svg viewBox="0 0 72 72" class="absolute inset-0 h-full w-full -rotate-90">
							<circle cx="36" cy="36" r={RING_RADIUS} fill="none" stroke="#f1f5f9" stroke-width="7" />
							<circle
								class="summary-ring"
								cx="36"
								cy="36"
								r={RING_RADIUS}
								fill="none"
								stroke="#10b981"
								stroke-width="7"
								stroke-linecap="round"
								stroke-dasharray="{ringFilled} {ringCircumference}"
							/>
						</svg>
						<span class="absolute inset-[13px] grid place-items-center rounded-full bg-[#fffbeb] text-2xl">
							{nextWorkoutMedal.icon}
						</span>
					</div>
					<div class="min-w-0">
						<p class="text-xs font-extrabold text-[#059669] uppercase">
							{m.workout_summary_medal_progress({
								current: Math.floor(nextWorkoutMedal.progress_current),
								goal: nextWorkoutMedal.progress_goal
							})}
						</p>
						<p class="text-lg leading-tight font-black">
							{medalRemaining === 1
								? m.workout_summary_medal_next_one()
								: m.workout_summary_medal_next_many({ count: medalRemaining })}
						</p>
						<p class="text-sm text-[#64748b]">{achievementText(locale, nextWorkoutMedal.code).name}</p>
					</div>
				</section>
			{/if}

			<div class="mt-2.5 grid grid-cols-2 gap-2.5">
				<section class="rounded-3xl bg-[#fff]/10 p-3.5">
					<p class="text-[11px] font-extrabold text-[#6ee7b7] uppercase">{m.workout_summary_level()}</p>
					<p class="mt-0.5 truncate font-extrabold">
						{nextTitleName
							? m.workout_summary_level_next({ name: nextTitleName })
							: titleName(locale, achievements.title_tier)}
					</p>
					<div class="mt-2 h-1.5 overflow-hidden rounded-full bg-[#fff]/15">
						<div class="h-full rounded-full bg-[#6ee7b7]" style="width: {levelPct}%"></div>
					</div>
					{#if achievements.title_progress_next !== null}
						<p class="mt-1.5 text-xs text-[#a7f3d0]">
							{Math.round(achievements.title_progress_current)}/{achievements.title_progress_next}
						</p>
					{/if}
				</section>
				<section class="rounded-3xl p-3.5 {trainMissionDone ? 'bg-[#fbbf24] text-[#422006]' : 'bg-[#fff]/10'}">
					<p class="text-[11px] font-extrabold uppercase {trainMissionDone ? '' : 'text-[#6ee7b7]'}">
						{trainMissionDone ? m.workout_summary_mission_done() : m.missions_title()}
					</p>
					<p class="mt-0.5 font-extrabold">
						{trainMissionDone ? m.mission_train({ goal }) : m.workout_summary_missions_count({ done: missionsDone, total: achievements.weekly_missions.length })}
					</p>
					{#if trainMissionDone}
						<p class="mt-2 text-xs font-bold">
							{m.workout_summary_missions_count({ done: missionsDone, total: achievements.weekly_missions.length })}
						</p>
					{/if}
				</section>
			</div>
		{/if}

		<div class="min-h-6 flex-1"></div>

		<button
			type="button"
			onclick={onDone}
			class="mt-4 h-13 w-full rounded-2xl bg-[#fff] text-base font-extrabold text-[#065f46] active:bg-[#ecfdf5]"
		>
			{m.workout_summary_done()}
		</button>
		<button
			type="button"
			onclick={shareSummary}
			class="mt-2 flex h-11 w-full items-center justify-center gap-2 text-sm font-bold text-[#a7f3d0]"
		>
			<svg viewBox="0 0 24 24" class="h-4.5 w-4.5" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3v12M7 8l5-5 5 5M5 14v5a2 2 0 002 2h10a2 2 0 002-2v-5" /></svg>
			{m.workout_summary_share()}
		</button>
	</div>
</div>

<style>
	/* Numero e "+1" entram com um pulinho; confete cai um pouco e assenta. */
	.summary-pop {
		animation: summary-pop 480ms cubic-bezier(0.2, 0.9, 0.3, 1.4) both;
	}
	@keyframes summary-pop {
		from {
			opacity: 0;
			transform: scale(0.5);
		}
	}

	/* Queda infinita: sai acima da tela, atravessa ate abaixo dela girando e derivando
	   para o lado, e recomeca. */
	.summary-confetti {
		animation-name: summary-confetti-fall;
		animation-timing-function: linear;
		animation-iteration-count: infinite;
		will-change: transform;
	}
	@keyframes summary-confetti-fall {
		from {
			transform: translate3d(0, -8vh, 0) rotate(0deg);
		}
		to {
			transform: translate3d(var(--drift), 108vh, 0) rotate(var(--spin));
		}
	}

	/* Anel da medalha desenha do zero ate o progresso atual. */
	.summary-ring {
		animation: summary-ring-draw 900ms 200ms ease-out both;
	}
	@keyframes summary-ring-draw {
		from {
			stroke-dasharray: 0 999;
		}
	}

	@media (prefers-reduced-motion: reduce) {
		.summary-pop,
		.summary-ring {
			animation: none;
		}
		/* sem movimento nao ha "chuva": as pecas sumiriam presas no topo, entao saem */
		.summary-confetti {
			display: none;
		}
	}
</style>
