<script lang="ts">
	import { api, type ActivityIntensity, type StandaloneActivityKind } from '$lib/api';
	import { ACTIVITY_DISTANCE_KINDS, ACTIVITY_KINDS, activityIntensityLabel, activityKindLabel } from '$lib/labels';
	import Stepper from '$lib/components/Stepper.svelte';
	import { showToast } from '$lib/toast.svelte';
	import { m } from '$lib/paraglide/messages';

	let { day, onClose, onAdded }: { day: string; onClose: () => void; onAdded: () => void } = $props();

	function nowHHMM(): string {
		const d = new Date();
		return `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`;
	}

	let kind = $state<StandaloneActivityKind>('running');
	let intensity = $state<ActivityIntensity>('moderate');
	let timeOfDay = $state(nowHHMM());
	let durationMin = $state(30);
	let distanceKm = $state(5);
	let kcal = $state(0);
	// "First touch": o campo de estimativa e um Stepper editavel desde o inicio (sem
	// botao "ajustar" separado). kcalTouched so vira true quando o proprio usuario
	// mexe no numero (Stepper.onchange) - assim a atualizacao automatica ao trocar
	// tipo/intensidade/duracao nao se confunde com uma edicao manual.
	let kcalTouched = $state(false);
	let saving = $state(false);

	const showsDistance = $derived(ACTIVITY_DISTANCE_KINDS.includes(kind));
	const INTENSITIES: ActivityIntensity[] = ['light', 'moderate', 'hard'];

	// Selecionado: fundo leve + borda/texto na cor - mesmo tratamento visual do
	// prototipo aprovado (nao preenchido solido, senao o icone perde contraste).
	const INTENSITY_STYLES: Record<ActivityIntensity, string> = {
		light: 'border-green-300 bg-green-50 text-green-700',
		moderate: 'border-amber-300 bg-amber-50 text-amber-800',
		hard: 'border-red-300 bg-red-50 text-red-800'
	};

	const ACTIVITY_ICON_PATHS: Record<StandaloneActivityKind, string> = {
		running: 'M13 17l-2-5-3 2-3-6M4 20l4-9 4 3 4-9 4 5',
		cycling: 'M5 18a3 3 0 100-6 3 3 0 000 6zM19 18a3 3 0 100-6 3 3 0 000 6zM5 15l4-7h4l3 7M9 8h4',
		walking: 'M13 4a1 1 0 100 2 1 1 0 000-2zM9 20l2-6 2 2 1 4M8 12l2-3 3 1 2 4',
		yoga: 'M12 4a1 1 0 100 2 1 1 0 000-2zM7 20l3-6 2 2 2-2 3 6M9 12l1-3h4l1 3',
		pilates: 'M4 12h16M8 6l4 6-4 6M16 6l-4 6 4 6',
		boxing: 'M6 14l4-4 4 4 4-8M6 18h12',
		swimming: 'M3 16c1.5 1 3 1 4.5 0s3-1 4.5 0 3 1 4.5 0 3-1 4.5 0M8 10l8-4 2 4-8 4z',
		dance: 'M12 3a1 1 0 100 2 1 1 0 000-2zM9 21l2-6-2-2 1-4 4 1 3 4-3 2 1 5',
		other: 'M12 8v4l3 3M12 21a9 9 0 100-18 9 9 0 000 18z'
	};

	let estimateToken = 0;
	$effect(() => {
		if (kcalTouched) return;
		const token = ++estimateToken;
		api.getActivityEstimate(kind, intensity, durationMin).then((r) => {
			if (token !== estimateToken) return;
			kcal = r.kcal;
		});
	});

	function useAutoEstimate(): void {
		kcalTouched = false;
	}

	async function save(): Promise<void> {
		saving = true;
		try {
			await api.addActivity({
				entry_date: day,
				time_of_day: timeOfDay,
				kind,
				duration_min: durationMin,
				intensity,
				distance_km: showsDistance ? distanceKm : null,
				kcal: kcalTouched ? kcal : null
			});
			showToast(m.activity_added());
			kcalTouched = false;
			onAdded();
		} finally {
			saving = false;
		}
	}
</script>

<div class="fixed inset-0 z-40 overflow-y-auto bg-slate-50">
	<div class="mx-auto max-w-md px-4 pt-4 pb-24">
		<div class="mb-4 flex items-center justify-between gap-2">
			<h1 class="text-xl font-bold">{m.activity_modal_title()}</h1>
			<button
				type="button"
				onclick={onClose}
				class="shrink-0 rounded-full bg-emerald-600 px-5 py-2.5 text-sm font-bold text-white active:bg-emerald-700"
			>
				{m.done()}
			</button>
		</div>

		<div class="grid grid-cols-3 gap-2">
			{#each ACTIVITY_KINDS as k (k)}
				<button
					type="button"
					onclick={() => (kind = k)}
					class="flex aspect-square flex-col items-center justify-center gap-1.5 rounded-2xl border-2 {kind === k
						? 'border-emerald-600 bg-emerald-50 text-emerald-700'
						: 'border-slate-200 bg-white text-slate-600 active:bg-slate-50'}"
				>
					<svg
						viewBox="0 0 24 24"
						class="h-7 w-7"
						fill="none"
						stroke="currentColor"
						stroke-width="1.8"
						stroke-linecap="round"
						stroke-linejoin="round"
					>
						<path d={ACTIVITY_ICON_PATHS[k]} />
					</svg>
					<span class="text-[11px] font-bold">{activityKindLabel(k)}</span>
				</button>
			{/each}
		</div>

		<div class="mt-4 grid grid-cols-2 gap-3">
			<div>
				<label class="mb-1.5 block text-xs font-bold text-slate-500" for="activity-time">
					{m.activity_time_label()}
				</label>
				<input
					id="activity-time"
					type="time"
					bind:value={timeOfDay}
					class="h-12 w-full rounded-xl border-2 border-slate-200 px-3 text-center text-lg font-bold text-slate-900"
				/>
			</div>
			<div>
				<span class="mb-1.5 block text-xs font-bold text-slate-500">{m.activity_duration_label()}</span>
				<Stepper bind:value={durationMin} min={5} max={300} step={5} />
			</div>
		</div>

		<div class="mt-4">
			<span class="mb-1.5 block text-xs font-bold text-slate-500">{m.activity_intensity_label()}</span>
			<div class="grid grid-cols-3 gap-1.5">
				{#each INTENSITIES as level (level)}
					<button
						type="button"
						onclick={() => (intensity = level)}
						class="h-11 rounded-xl border-2 text-sm font-bold {intensity === level
							? INTENSITY_STYLES[level]
							: 'border-slate-200 bg-white text-slate-600'}"
					>
						{activityIntensityLabel(level)}
					</button>
				{/each}
			</div>
		</div>

		{#if showsDistance}
			<div class="mt-4">
				<span class="mb-1.5 block text-xs font-bold text-slate-500">{m.activity_distance_label()}</span>
				<Stepper bind:value={distanceKm} min={0} max={200} step={0.5} decimals={1} unit="km" />
			</div>
		{/if}

		<div class="mt-4">
			<span class="mb-1.5 block text-xs font-bold text-slate-500">{m.activity_estimate_label()}</span>
			<Stepper
				bind:value={kcal}
				min={0}
				max={3000}
				step={5}
				unit="kcal"
				onchange={() => (kcalTouched = true)}
			/>
			<p class="mt-1.5 text-[11px] text-slate-400">
				{kcalTouched ? m.activity_estimate_manual_hint() : m.activity_estimate_auto_hint()}
			</p>
			{#if kcalTouched}
				<button type="button" onclick={useAutoEstimate} class="mt-1 text-[11px] font-bold text-emerald-700">
					{m.activity_use_auto_estimate()}
				</button>
			{/if}
		</div>

		<button
			type="button"
			disabled={saving}
			onclick={save}
			class="mt-6 h-12 w-full rounded-2xl bg-emerald-600 text-sm font-bold text-white active:bg-emerald-700 disabled:opacity-50"
		>
			{m.activity_save()}
		</button>
	</div>
</div>
