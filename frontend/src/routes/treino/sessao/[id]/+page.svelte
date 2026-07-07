<script lang="ts">
	import { goto } from '$app/navigation';
	import { page } from '$app/state';
	import { slide } from 'svelte/transition';
	import { api, localDay, type Exercise, type RoutineItem } from '$lib/api';
	import ExercisePhotoModal from '$lib/components/ExercisePhotoModal.svelte';
	import Stepper from '$lib/components/Stepper.svelte';
	import { showToast } from '$lib/toast.svelte';
	import { m } from '$lib/paraglide/messages';

	interface SetRow {
		setNumber: number;
		reps: number;
		weight: number;
		duration: number;
		done: boolean;
		logId: number | null;
		saving: boolean;
	}
	interface ExerciseBlock {
		item: RoutineItem;
		isCardio: boolean;
		sets: SetRow[];
		collapsed: boolean;
	}

	const sessionId = $derived(Number(page.params.id));

	let blocks = $state<ExerciseBlock[]>([]);
	let routineName = $state('');
	let loading = $state(true);
	let finishing = $state(false);
	let photoOf = $state<Exercise | null>(null);

	// relógio único: tempo total da sessão + contagem do descanso
	let startedAtMs = $state(0);
	let now = $state(Date.now());
	let restRemaining = $state(0);
	let restTotal = $state(0);
	let restActive = $state(false);

	function formatTime(totalSeconds: number): string {
		const s = Math.max(0, Math.floor(totalSeconds));
		const h = Math.floor(s / 3600);
		const mm = String(Math.floor((s % 3600) / 60)).padStart(2, '0');
		const ss = String(s % 60).padStart(2, '0');
		return h > 0 ? `${h}:${mm}:${ss}` : `${mm}:${ss}`;
	}

	const elapsed = $derived(startedAtMs > 0 ? (now - startedAtMs) / 1000 : 0);

	function beep(): void {
		try {
			const ctx = new AudioContext();
			const osc = ctx.createOscillator();
			const gain = ctx.createGain();
			osc.connect(gain);
			gain.connect(ctx.destination);
			osc.frequency.value = 880;
			gain.gain.setValueAtTime(0.3, ctx.currentTime);
			gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.5);
			osc.start();
			osc.stop(ctx.currentTime + 0.5);
		} catch {
			// áudio bloqueado: vibração já cobre
		}
	}

	function startRest(seconds: number): void {
		restTotal = seconds;
		restRemaining = seconds;
		restActive = true;
	}

	function stopRest(): void {
		restActive = false;
		restRemaining = 0;
	}

	$effect(() => {
		const timer = setInterval(() => {
			now = Date.now();
			if (restActive) {
				restRemaining -= 1;
				if (restRemaining <= 0) {
					restActive = false;
					restRemaining = 0;
					navigator.vibrate?.(400);
					beep();
				}
			}
		}, 1000);
		return () => clearInterval(timer);
	});

	async function load(): Promise<void> {
		const session = await api.getSession(sessionId);
		routineName = session.routine_name ?? m.free_workout();
		// backend envia UTC sem sufixo Z
		startedAtMs = new Date(session.started_at + 'Z').getTime();
		if (session.routine_id === null) {
			blocks = [];
			loading = false;
			return;
		}
		const routine = await api.getRoutine(session.routine_id);
		blocks = routine.items.map((item) => {
			const isCardio = item.exercise.kind === 'cardio';
			const prefill = item.last_weight_kg ?? item.target_weight_kg ?? 0;
			// cardio normalmente é uma "série" só (a duração total)
			const setCount = isCardio ? 1 : item.target_sets;
			const sets: SetRow[] = Array.from({ length: setCount }, (_, i) => {
				const logged = session.sets.find(
					(s) => s.exercise_id === item.exercise.id && s.set_number === i + 1
				);
				return {
					setNumber: i + 1,
					reps: logged?.reps ?? item.target_reps,
					weight: logged?.weight_kg ?? prefill,
					duration: logged?.duration_min ?? item.target_duration_min ?? 20,
					done: logged?.done ?? false,
					logId: logged?.id ?? null,
					saving: false
				};
			});
			// bloco já 100% concluído (sessão retomada) começa minimizado
			return { item, isCardio, sets, collapsed: sets.every((s) => s.done) };
		});
		loading = false;
	}

	function addSet(block: ExerciseBlock): void {
		const last = block.sets[block.sets.length - 1];
		block.sets.push({
			setNumber: block.sets.length + 1,
			reps: last?.reps ?? block.item.target_reps,
			weight: last?.weight ?? 0,
			duration: last?.duration ?? block.item.target_duration_min ?? 20,
			done: false,
			logId: null,
			saving: false
		});
		block.collapsed = false;
	}

	async function toggleSet(block: ExerciseBlock, row: SetRow): Promise<void> {
		if (row.saving) return;
		row.saving = true;
		try {
			if (!row.done) {
				const log = await api.logSet(sessionId, {
					exercise_id: block.item.exercise.id,
					set_number: row.setNumber,
					reps: block.isCardio ? 0 : row.reps,
					weight_kg: block.isCardio ? 0 : row.weight,
					duration_min: block.isCardio ? row.duration : null,
					done: true
				});
				row.logId = log.id;
				row.done = true;
				// exercício 100% concluído minimiza; descanso roda entre séries e exercícios
				if (block.sets.every((s) => s.done)) {
					block.collapsed = true;
				}
				if (!block.isCardio) {
					startRest(block.item.rest_seconds || 90);
				}
			} else if (row.logId !== null) {
				await api.deleteSet(sessionId, row.logId);
				row.logId = null;
				row.done = false;
			}
		} finally {
			row.saving = false;
		}
	}

	async function finish(): Promise<void> {
		finishing = true;
		stopRest();
		try {
			await api.finishSession(sessionId);
			showToast(m.workout_finished_in({ time: formatTime(elapsed) }));
			// avalia conquistas: se desbloqueou algo novo com este treino, celebra
			try {
				const result = await api.getAchievements(localDay(), new Date().getTimezoneOffset());
				if (result.newly_unlocked.length > 0) {
					setTimeout(() => showToast(m.achievement_unlocked()), 2600);
				}
			} catch {
				// conquistas sao um extra: nunca bloqueiam o fim do treino
			}
			await goto('/treino');
		} finally {
			finishing = false;
		}
	}

	$effect(() => {
		load();
	});

	const doneCount = $derived(
		blocks.reduce((acc, b) => acc + b.sets.filter((s) => s.done).length, 0)
	);
	const totalCount = $derived(blocks.reduce((acc, b) => acc + b.sets.length, 0));
	// exercício "atual": primeiro com série pendente
	const currentIndex = $derived(blocks.findIndex((b) => b.sets.some((s) => !s.done)));

	// Modo foco: mostra um exercicio por vez, grande, sem perder a lista rolavel por tras.
	// E aditivo (nao substitui a lista): abre sobre ela e fecha voltando ao mesmo lugar.
	let focusMode = $state(false);
	let focusIndex = $state(0);

	function openFocus(): void {
		// abre no exercicio atual (primeiro pendente); se tudo feito, no primeiro
		focusIndex = currentIndex === -1 ? 0 : currentIndex;
		focusMode = true;
	}

	const focusBlock = $derived(blocks[focusIndex] ?? null);
	// serie pendente atual do exercicio em foco (null quando todas ja concluidas)
	const focusRow = $derived(focusBlock ? (focusBlock.sets.find((s) => !s.done) ?? null) : null);
	const focusAllDone = $derived(focusBlock ? focusBlock.sets.every((s) => s.done) : false);

	async function completeFocusSet(): Promise<void> {
		if (!focusBlock || !focusRow) return;
		await toggleSet(focusBlock, focusRow);
		// exercicio terminou: avanca sozinho para o proximo com serie pendente
		if (focusBlock.sets.every((s) => s.done)) {
			const next = blocks.findIndex((b, i) => i > focusIndex && b.sets.some((s) => !s.done));
			if (next !== -1) focusIndex = next;
		}
	}

	function focusPrev(): void {
		if (focusIndex > 0) focusIndex -= 1;
	}
	function focusNext(): void {
		if (focusIndex < blocks.length - 1) focusIndex += 1;
	}
</script>

{#if loading}
	<div class="flex justify-center py-16">
		<div class="h-8 w-8 animate-spin rounded-full border-4 border-emerald-600 border-t-transparent"></div>
	</div>
{:else}
	<header class="sticky top-0 z-10 -mx-4 mb-4 bg-slate-50/90 px-4 pt-2 pb-3 backdrop-blur">
		<div class="flex items-center gap-2">
			<a
				href="/treino"
				aria-label={m.back()}
				class="grid h-10 w-10 shrink-0 place-items-center rounded-full bg-white text-slate-500 shadow-sm"
			>
				<svg viewBox="0 0 24 24" class="h-5 w-5" fill="none" stroke="currentColor" stroke-width="2">
					<path d="M15 6l-6 6 6 6" stroke-linecap="round" stroke-linejoin="round" />
				</svg>
			</a>
			<div class="min-w-0 flex-1">
				<p class="text-sm font-semibold text-emerald-600">{m.workout_in_progress()}</p>
				<h1 class="truncate text-2xl font-bold">{routineName}</h1>
			</div>
		</div>
		<div class="mt-3 h-2 overflow-hidden rounded-full bg-slate-200">
			<div
				class="h-full rounded-full bg-emerald-600 transition-all"
				style="width: {totalCount ? (doneCount / totalCount) * 100 : 0}%"
			></div>
		</div>
		<div class="mt-1 flex items-center justify-between gap-2">
			<p class="text-sm text-slate-500">{doneCount} / {totalCount} {m.sets_label()}</p>
			{#if blocks.length > 0 && currentIndex !== -1}
				<button
					type="button"
					onclick={openFocus}
					class="flex shrink-0 items-center gap-1.5 rounded-full border border-[#ffffff24] bg-ink-2 px-3 py-1.5 text-xs font-bold text-[#fff] active:bg-slate-500"
				>
					<svg viewBox="0 0 24 24" class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="2">
						<circle cx="12" cy="12" r="7" /><circle cx="12" cy="12" r="2.5" />
					</svg>
					{m.focus_mode()}
				</button>
			{/if}
		</div>
	</header>

	<div class="space-y-3">
		{#each blocks as block, blockIndex (block.item.id)}
			{@const doneSets = block.sets.filter((s) => s.done).length}
			{@const allDone = doneSets === block.sets.length}
			{@const isCurrent = blockIndex === currentIndex}
			<section
				class="rounded-2xl bg-white p-3 shadow-sm transition-all
					{isCurrent ? 'ring-2 ring-emerald-500' : ''}
					{allDone ? 'opacity-60' : ''}"
			>
				<div class="flex items-center gap-3 {block.collapsed ? '' : 'mb-3'}">
					<button
						type="button"
						aria-label={m.view_photo()}
						onclick={() => (photoOf = block.item.exercise)}
						class="grid h-12 w-12 shrink-0 place-items-center overflow-hidden rounded-xl bg-slate-100"
					>
						{#if block.item.exercise.media_urls.length > 0}
							<img src={block.item.exercise.media_urls[0]} alt="" class="h-full w-full object-cover" loading="lazy" />
						{:else}
							<svg viewBox="0 0 24 24" class="h-5 w-5 text-slate-400" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="3" /><path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7-10-7-10-7z" /></svg>
						{/if}
					</button>
					<button
						type="button"
						class="min-w-0 flex-1 text-left"
						onclick={() => (block.collapsed = !block.collapsed)}
					>
						<p class="truncate font-bold text-slate-900">{block.item.exercise.name}</p>
						<p class="text-sm text-slate-500">
							{#if block.collapsed}
								{doneSets}/{block.sets.length} {m.sets_label()}
							{:else if block.isCardio}
								{m.cardio_label()}
							{:else}
								{block.item.target_sets} × {block.item.target_reps}
								{#if block.item.last_weight_kg !== null}
									· {m.last_time()}: {block.item.last_weight_kg} kg
								{/if}
							{/if}
						</p>
					</button>
					{#if allDone}
						<span class="grid h-8 w-8 shrink-0 place-items-center rounded-full bg-emerald-600 text-sm font-bold text-[#fff]">✓</span>
					{/if}
					<button
						type="button"
						aria-label={block.collapsed ? m.expand() : m.collapse()}
						onclick={() => (block.collapsed = !block.collapsed)}
						class="grid h-8 w-8 shrink-0 place-items-center text-slate-400"
					>
						<svg viewBox="0 0 24 24" class="h-5 w-5 transition-transform {block.collapsed ? '' : 'rotate-180'}" fill="none" stroke="currentColor" stroke-width="2">
							<path d="M6 9l6 6 6-6" stroke-linecap="round" stroke-linejoin="round" />
						</svg>
					</button>
				</div>

				{#if !block.collapsed}
					<div class="space-y-2" transition:slide={{ duration: 200 }}>
						{#each block.sets as row (row.setNumber)}
							{#if row.done}
								<!-- série concluída: linha compacta; tocar no ✓ desfaz -->
								<div class="flex items-center gap-2 rounded-2xl bg-emerald-50 px-2 py-1.5">
									<span class="grid h-8 w-8 shrink-0 place-items-center rounded-lg bg-white/60 text-xs font-bold text-emerald-700">
										{block.isCardio ? '♥' : row.setNumber}
									</span>
									<span class="min-w-0 flex-1 truncate text-sm font-bold text-emerald-900">
										{#if block.isCardio}
											{row.duration} {m.minutes_short()}
										{:else}
											{row.weight} kg × {row.reps}
										{/if}
									</span>
									<button
										type="button"
										aria-label={m.done()}
										disabled={row.saving}
										onclick={() => toggleSet(block, row)}
										class="grid h-9 w-9 shrink-0 place-items-center rounded-xl bg-emerald-600 text-base font-bold text-[#fff]"
									>
										✓
									</button>
								</div>
							{:else}
								<!-- série pendente: uma linha com os steppers compactos e o ✓ para concluir -->
								<div class="flex items-center gap-2 rounded-2xl bg-slate-50 px-2 py-1.5">
									{#if block.isCardio}
										<span class="shrink-0 pl-1 text-xs font-bold text-slate-400">{m.duration_label()}</span>
										<div class="min-w-0 flex-1">
											<Stepper size="sm" bind:value={row.duration} min={1} max={300} step={1} unit={m.minutes_short()} />
										</div>
									{:else}
										<span class="grid h-8 w-8 shrink-0 place-items-center rounded-lg bg-white text-xs font-bold text-slate-500">
											{row.setNumber}
										</span>
										<div class="min-w-0 flex-1">
											<Stepper size="sm" bind:value={row.weight} min={0} max={1000} step={2.5} decimals={1} unit="kg" />
										</div>
										<div class="min-w-0 flex-1">
											<Stepper size="sm" bind:value={row.reps} min={0} max={100} unit={m.reps_short()} />
										</div>
									{/if}
									<button
										type="button"
										aria-label={m.done()}
										disabled={row.saving}
										onclick={() => toggleSet(block, row)}
										class="grid h-9 w-9 shrink-0 place-items-center rounded-xl border-2 border-slate-200 bg-white text-base font-bold text-slate-300 transition-colors"
									>
										✓
									</button>
								</div>
							{/if}
						{/each}
						{#if !block.isCardio}
							<button
								type="button"
								onclick={() => addSet(block)}
								class="h-10 w-full rounded-2xl border-2 border-dashed border-slate-200 text-sm font-bold text-slate-500 active:bg-slate-50"
							>
								+ {m.add_set()}
							</button>
						{/if}
					</div>
				{/if}
			</section>
		{/each}
	</div>

	<button
		type="button"
		disabled={finishing}
		onclick={finish}
		class="mt-5 h-14 w-full rounded-2xl bg-ink text-lg font-bold text-[#fff] active:bg-ink-2 disabled:opacity-50
			{restActive ? 'mb-28' : 'mb-20'}"
	>
		{m.finish_workout()}
	</button>
{/if}

{#if focusMode && focusBlock}
	<!-- Modo foco: overlay de um exercicio por vez, por cima da lista (z-30) -->
	<div
		class="fixed inset-0 z-30 flex flex-col bg-slate-50"
		style="padding-bottom: {restActive ? '92px' : '0'}"
	>
		<header class="flex items-center gap-2 px-4 pt-3 pb-2">
			<button
				type="button"
				aria-label={m.back()}
				onclick={() => (focusMode = false)}
				class="grid h-10 w-10 shrink-0 place-items-center rounded-full bg-white text-slate-500 shadow-sm"
			>
				<svg viewBox="0 0 24 24" class="h-5 w-5" fill="none" stroke="currentColor" stroke-width="2">
					<path d="M6 6l12 12M18 6L6 18" stroke-linecap="round" />
				</svg>
			</button>
			<p class="min-w-0 flex-1 text-center text-sm font-bold text-slate-500">
				{m.exercise_n_of_total({ current: focusIndex + 1, total: blocks.length })}
			</p>
			<div class="shrink-0 rounded-2xl bg-ink-2 px-3 py-1.5 text-center">
				<p class="font-mono text-base leading-none font-bold text-[#fff] tabular-nums">
					{formatTime(elapsed)}
				</p>
			</div>
		</header>

		<!-- pontinhos de progresso entre exercicios -->
		<div class="flex justify-center gap-1.5 px-4 pb-1">
			{#each blocks as b, i (b.item.id)}
				{@const bd = b.sets.every((s) => s.done)}
				<span
					class="h-1.5 rounded-full transition-all
						{i === focusIndex ? 'w-6 bg-emerald-600' : bd ? 'w-1.5 bg-emerald-400' : 'w-1.5 bg-slate-300'}"
				></span>
			{/each}
		</div>

		<div class="flex-1 overflow-y-auto px-4 pt-2 pb-4">
			<button
				type="button"
				aria-label={m.view_photo()}
				onclick={() => (photoOf = focusBlock.item.exercise)}
				class="grid h-44 w-full place-items-center overflow-hidden rounded-3xl bg-slate-100"
			>
				{#if focusBlock.item.exercise.media_urls.length > 0}
					<img src={focusBlock.item.exercise.media_urls[0]} alt="" class="h-full w-full object-cover" />
				{:else}
					<svg viewBox="0 0 24 24" class="h-12 w-12 text-slate-300" fill="none" stroke="currentColor" stroke-width="1.5">
						<path d="M6 8v8M18 8v8M3 10v4M21 10v4M8 12h8" stroke-linecap="round" />
					</svg>
				{/if}
			</button>

			<h2 class="mt-4 text-center text-2xl font-bold text-slate-900">{focusBlock.item.exercise.name}</h2>

			{#if focusAllDone}
				<p class="mt-1 text-center text-sm font-semibold text-emerald-600">{m.exercise_completed()}</p>
			{:else if focusBlock.isCardio}
				<p class="mt-1 text-center text-sm font-semibold text-slate-500">{m.cardio_label()}</p>
			{:else}
				<!-- progresso das series deste exercicio: uma barrinha por serie
				     (feita = verde cheio, atual = verde suave, pendente = cinza) -->
				<div class="mx-auto mt-2 max-w-sm">
					<div class="mb-1.5 flex items-center justify-between text-xs font-semibold text-slate-500">
						<span>
							{m.set_n_of_total({
								current: focusRow?.setNumber ?? focusBlock.sets.length,
								total: focusBlock.sets.length
							})}
						</span>
						{#if focusBlock.item.last_weight_kg !== null}
							<span>{m.last_time()}: {focusBlock.item.last_weight_kg} kg</span>
						{/if}
					</div>
					<div class="flex gap-1.5">
						{#each focusBlock.sets as s (s.setNumber)}
							<span
								class="h-2 flex-1 rounded-full transition-colors
									{s.done ? 'bg-emerald-500' : s === focusRow ? 'bg-emerald-500/45' : 'bg-slate-200'}"
							></span>
						{/each}
					</div>
				</div>
			{/if}

			{#if focusRow}
				<div class="mx-auto mt-5 max-w-sm space-y-4">
					{#if focusBlock.isCardio}
						<div>
							<p class="mb-1.5 text-center text-xs font-bold text-slate-500 uppercase">{m.duration_label()}</p>
							<Stepper bind:value={focusRow.duration} min={1} max={300} step={1} unit={m.minutes_short()} />
						</div>
					{:else}
						<div>
							<p class="mb-1.5 text-center text-xs font-bold text-slate-500 uppercase">{m.weight()} (kg)</p>
							<Stepper bind:value={focusRow.weight} min={0} max={1000} step={2.5} decimals={1} />
						</div>
						<div>
							<p class="mb-1.5 text-center text-xs font-bold text-slate-500 uppercase">{m.reps_label()}</p>
							<Stepper bind:value={focusRow.reps} min={0} max={100} />
						</div>
					{/if}
				</div>
			{/if}

			{#if focusBlock.sets.some((s) => s.done)}
				<div class="mx-auto mt-5 max-w-sm space-y-1.5">
					{#each focusBlock.sets.filter((s) => s.done) as doneRow (doneRow.setNumber)}
						<div class="flex items-center gap-2 rounded-xl bg-emerald-50 px-3 py-1.5 text-sm font-bold text-emerald-900">
							<span class="text-emerald-600">✓</span>
							{#if focusBlock.isCardio}
								{doneRow.duration} {m.minutes_short()}
							{:else}
								{m.set_word()} {doneRow.setNumber} · {doneRow.weight} kg × {doneRow.reps}
							{/if}
						</div>
					{/each}
				</div>
			{/if}
		</div>

		<div class="border-t border-slate-200 bg-slate-50 px-4 pt-3 pb-[calc(env(safe-area-inset-bottom)+12px)]">
			{#if focusRow}
				<button
					type="button"
					disabled={focusRow.saving}
					onclick={completeFocusSet}
					class="h-14 w-full rounded-2xl bg-emerald-600 text-lg font-bold text-[#fff] active:bg-emerald-700 disabled:opacity-50"
				>
					{m.complete_set()}
				</button>
			{:else}
				<div class="grid h-14 w-full place-items-center rounded-2xl bg-emerald-50 text-lg font-bold text-emerald-700">
					{m.exercise_completed()} ✓
				</div>
			{/if}
			<div class="mt-2.5 flex gap-2">
				<button
					type="button"
					disabled={focusIndex === 0}
					onclick={focusPrev}
					class="flex h-11 flex-1 items-center justify-center gap-1 rounded-2xl border-2 border-slate-200 bg-white font-semibold text-slate-600 active:bg-slate-100 disabled:opacity-40"
				>
					<svg viewBox="0 0 24 24" class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="2">
						<path d="M15 6l-6 6 6 6" stroke-linecap="round" stroke-linejoin="round" />
					</svg>
					{m.prev_exercise()}
				</button>
				<button
					type="button"
					disabled={focusIndex >= blocks.length - 1}
					onclick={focusNext}
					class="flex h-11 flex-1 items-center justify-center gap-1 rounded-2xl border-2 border-slate-200 bg-white font-semibold text-slate-600 active:bg-slate-100 disabled:opacity-40"
				>
					{m.next_exercise()}
					<svg viewBox="0 0 24 24" class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="2">
						<path d="M9 6l6 6-6 6" stroke-linecap="round" stroke-linejoin="round" />
					</svg>
				</button>
			</div>
		</div>
	</div>
{/if}

{#if restActive}
	<!-- Barra inferior no estado DESCANSO: assume o mesmo lugar do tempo total.
	     z-40 (acima da lista e do Modo foco z-30). bg-ink-2 para aparecer tambem no escuro. -->
	<div class="fixed inset-x-0 bottom-0 z-40 border-t border-black/10 bg-ink-2 pb-[env(safe-area-inset-bottom)] text-[#fff]">
		<div class="h-1 bg-black/20">
			<div
				class="h-full bg-emerald-400 transition-all duration-1000 ease-linear"
				style="width: {restTotal > 0 ? (restRemaining / restTotal) * 100 : 0}%"
			></div>
		</div>
		<div class="mx-auto flex max-w-md items-center justify-between gap-3 px-4 py-3">
			<div>
				<p class="text-[10px] font-semibold text-slate-400 uppercase">{m.rest_label()}</p>
				<p
					class="font-mono text-3xl leading-none font-black tabular-nums
						{restRemaining <= 5 ? 'animate-pulse text-emerald-400' : ''}"
				>
					{formatTime(restRemaining)}
				</p>
			</div>
			<div class="flex gap-2">
				<button
					type="button"
					onclick={() => {
						restRemaining += 30;
						restTotal += 30;
					}}
					class="h-12 rounded-2xl bg-[#ffffff1f] px-4 font-bold active:bg-[#ffffff38]"
				>
					{m.plus_30s()}
				</button>
				<button
					type="button"
					onclick={stopRest}
					class="h-12 rounded-2xl bg-emerald-600 px-5 font-bold active:bg-emerald-700"
				>
					{m.skip()}
				</button>
			</div>
		</div>
	</div>
{:else if !focusMode}
	<!-- Barra inferior no estado TEMPO TOTAL: slim, so na lista (no Modo foco o tempo fica no cabecalho do overlay) -->
	<div class="fixed inset-x-0 bottom-0 z-30 border-t border-black/10 bg-ink-2 pb-[env(safe-area-inset-bottom)] text-[#fff]">
		<div class="mx-auto flex max-w-md items-center justify-center gap-2.5 px-4 py-3">
			<svg viewBox="0 0 24 24" class="h-4 w-4 text-slate-400" fill="none" stroke="currentColor" stroke-width="2">
				<circle cx="12" cy="12" r="9" /><path d="M12 8v4l2.5 2" stroke-linecap="round" stroke-linejoin="round" />
			</svg>
			<span class="text-[10px] font-semibold text-slate-400 uppercase">{m.total_time()}</span>
			<span class="font-mono text-xl font-bold text-[#fff] tabular-nums">{formatTime(elapsed)}</span>
		</div>
	</div>
{/if}

{#if photoOf}
	<ExercisePhotoModal exercise={photoOf} onClose={() => (photoOf = null)} />
{/if}
