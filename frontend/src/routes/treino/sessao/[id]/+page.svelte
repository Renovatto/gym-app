<script lang="ts">
	import { goto } from '$app/navigation';
	import { page } from '$app/state';
	import { slide } from 'svelte/transition';
	import { api, type Exercise, type RoutineItem } from '$lib/api';
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
			<div class="shrink-0 rounded-2xl bg-ink px-3 py-2 text-center">
				<p class="font-mono text-lg leading-none font-bold text-white tabular-nums">
					{formatTime(elapsed)}
				</p>
				<p class="mt-0.5 text-[10px] font-semibold text-slate-400 uppercase">{m.total_time()}</p>
			</div>
		</div>
		<div class="mt-3 h-2 overflow-hidden rounded-full bg-slate-200">
			<div
				class="h-full rounded-full bg-emerald-600 transition-all"
				style="width: {totalCount ? (doneCount / totalCount) * 100 : 0}%"
			></div>
		</div>
		<p class="mt-1 text-sm text-slate-500">{doneCount} / {totalCount} {m.sets_label()}</p>
	</header>

	<div class="space-y-4">
		{#each blocks as block, blockIndex (block.item.id)}
			{@const doneSets = block.sets.filter((s) => s.done).length}
			{@const allDone = doneSets === block.sets.length}
			{@const isCurrent = blockIndex === currentIndex}
			<section
				class="rounded-3xl bg-white p-4 shadow-sm transition-all
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
						<span class="grid h-8 w-8 shrink-0 place-items-center rounded-full bg-emerald-600 text-sm font-bold text-white">✓</span>
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
								<div class="flex items-center justify-between rounded-2xl bg-emerald-50 px-3 py-2">
									<span class="text-sm font-bold text-emerald-900">
										{#if block.isCardio}
											{m.cardio_label()} · {row.duration} {m.minutes_short()}
										{:else}
											{m.set_word()} {row.setNumber} · {row.weight} kg × {row.reps}
										{/if}
									</span>
									<button
										type="button"
										aria-label={m.done()}
										disabled={row.saving}
										onclick={() => toggleSet(block, row)}
										class="grid h-9 w-9 shrink-0 place-items-center rounded-xl bg-emerald-600 text-lg font-bold text-white"
									>
										✓
									</button>
								</div>
							{:else}
								<div class="rounded-2xl bg-slate-50 p-3">
									<div class="mb-2 flex items-center justify-between">
										<span class="text-sm font-bold text-slate-500">
											{block.isCardio ? m.cardio_label() : `${m.set_word()} ${row.setNumber}`}
										</span>
										<button
											type="button"
											aria-label={m.done()}
											disabled={row.saving}
											onclick={() => toggleSet(block, row)}
											class="grid h-10 w-10 shrink-0 place-items-center rounded-xl border-2 border-slate-200 bg-white text-xl font-bold text-slate-300 transition-colors"
										>
											✓
										</button>
									</div>
									{#if block.isCardio}
										<div>
											<p class="mb-1 text-xs font-semibold text-slate-500">{m.duration_label()}</p>
											<Stepper bind:value={row.duration} min={1} max={300} step={1} unit={m.minutes_short()} />
										</div>
									{:else}
										<div class="grid grid-cols-2 gap-3">
											<div>
												<p class="mb-1 text-xs font-semibold text-slate-500">{m.weight()} (kg)</p>
												<Stepper bind:value={row.weight} min={0} max={1000} step={2.5} decimals={1} />
											</div>
											<div>
												<p class="mb-1 text-xs font-semibold text-slate-500">{m.reps_label()}</p>
												<Stepper bind:value={row.reps} min={0} max={100} />
											</div>
										</div>
									{/if}
								</div>
							{/if}
						{/each}
						{#if !block.isCardio}
							<button
								type="button"
								onclick={() => addSet(block)}
								class="h-11 w-full rounded-2xl border-2 border-dashed border-slate-200 text-sm font-bold text-slate-500 active:bg-slate-50"
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
		class="mt-5 h-14 w-full rounded-2xl bg-ink text-lg font-bold text-white active:bg-ink-2 disabled:opacity-50
			{restActive ? 'mb-24' : ''}"
	>
		{m.finish_workout()}
	</button>
{/if}

{#if restActive}
	<div class="fixed inset-x-0 bottom-0 z-20 bg-ink pb-[env(safe-area-inset-bottom)] text-white">
		<div class="h-1 bg-ink-2">
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
					class="h-12 rounded-2xl bg-ink-2 px-4 font-bold active:bg-slate-500"
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
{/if}

{#if photoOf}
	<ExercisePhotoModal exercise={photoOf} onClose={() => (photoOf = null)} />
{/if}
