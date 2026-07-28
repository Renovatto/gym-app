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

		<div class="flex flex-wrap gap-1.5">
			{#each ACTIVITY_KINDS as k (k)}
				<button
					type="button"
					onclick={() => (kind = k)}
					class="rounded-full border-2 px-3 py-1.5 text-xs font-bold {kind === k
						? 'border-emerald-600 bg-emerald-600 text-white'
						: 'border-slate-200 bg-white text-slate-700 active:bg-slate-100'}"
				>
					{activityKindLabel(k)}
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
						class="h-10 rounded-xl text-sm font-bold {intensity === level
							? 'bg-emerald-600 text-white'
							: 'bg-white text-slate-600'}"
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
