<script lang="ts">
	import { untrack } from 'svelte';
	import { ApiError, api, type CycleInput, type CycleMode, type CyclePhase, type CycleStatus } from '$lib/api';
	import ChoiceChips from '$lib/components/ChoiceChips.svelte';
	import Stepper from '$lib/components/Stepper.svelte';
	import { errorMessage } from '$lib/errors';
	import { showToast } from '$lib/toast.svelte';
	import { m } from '$lib/paraglide/messages';

	// Um formulario so para os dois lugares que configuram o ciclo (Perfil e a modal
	// do card na Dieta) - duplicar seria pedir para as duas telas divergirem.
	let {
		value,
		day,
		onSaved
	}: {
		value: CycleStatus;
		day: string; // dia LOCAL de quem usa (a estimativa por data depende dele)
		onSaved: (updated: CycleStatus) => void;
	} = $props();

	// O formulario parte do que esta salvo e dali em diante e da pessoa: untrack
	// deixa explicito que so o valor INICIAL vem do prop (mesmo padrao de
	// CalendarModal e FeedbackModal). Sem isso, um refresh do estado la fora
	// apagaria o que ela acabou de digitar.
	let mode = $state<CycleMode>(untrack(() => value.mode));
	// no modo manual a fase resolvida E a fase marcada; um bom ponto de partida
	let phase = $state<CyclePhase>(untrack(() => value.phase) ?? 'menstrual');
	let lastPeriod = $state(untrack(() => value.last_period_date) ?? '');
	let cycleLength = $state(untrack(() => value.cycle_length_days));
	let saving = $state(false);

	const canSave = $derived(mode === 'manual' || lastPeriod.length > 0);

	async function save(): Promise<void> {
		if (!canSave || saving) return;
		saving = true;
		const payload: CycleInput = {
			enabled: true,
			mode,
			phase: mode === 'manual' ? phase : null,
			last_period_date: mode === 'by_date' ? lastPeriod : null,
			cycle_length_days: cycleLength
		};
		try {
			const updated = await api.saveCycle(day, payload);
			showToast(m.cycle_saved_toast());
			onSaved(updated);
		} catch (e) {
			showToast(errorMessage(e instanceof ApiError ? e.code : 'GENERIC_ERROR'));
		} finally {
			saving = false;
		}
	}
</script>

<div class="space-y-4">
	<div>
		<p class="mb-2 text-sm font-semibold text-slate-600">{m.cycle_mode_label()}</p>
		<ChoiceChips
			columns={2}
			bind:value={mode}
			options={[
				{ value: 'manual', label: m.cycle_mode_manual() },
				{ value: 'by_date', label: m.cycle_mode_by_date() }
			]}
		/>
		<!-- Nao lembrar a data e o caso comum, nao a excecao: dizer isso aqui evita
			 que a pessoa desista achando que precisa de um dado que ela nao tem. -->
		<p class="mt-2 text-xs text-slate-400">{m.cycle_mode_hint()}</p>
	</div>

	{#if mode === 'manual'}
		<div>
			<p class="mb-2 text-sm font-semibold text-slate-600">{m.cycle_phase_label()}</p>
			<ChoiceChips
				columns={2}
				bind:value={phase}
				options={[
					{ value: 'menstrual', label: m.cycle_phase_menstrual() },
					{ value: 'follicular', label: m.cycle_phase_follicular() },
					{ value: 'ovulatory', label: m.cycle_phase_ovulatory() },
					{ value: 'luteal', label: m.cycle_phase_luteal() }
				]}
			/>
		</div>
	{:else}
		<div>
			<label class="mb-2 block text-sm font-semibold text-slate-600" for="cycle-last-period">
				{m.cycle_last_period_label()}
			</label>
			<input
				id="cycle-last-period"
				type="date"
				bind:value={lastPeriod}
				max={day}
				class="h-12 w-full rounded-2xl border-2 border-slate-200 bg-white px-4 outline-none focus:border-emerald-600"
			/>
			<!-- "ultimo periodo" lia como "o do mes passado": a duvida some dizendo o
				 caso de quem esta menstruada AGORA, que e quando se costuma configurar. -->
			<p class="mt-1.5 text-xs text-slate-400">{m.cycle_last_period_hint()}</p>
			<button
				type="button"
				onclick={() => (lastPeriod = day)}
				class="mt-2 w-full rounded-2xl border-2 border-emerald-200 py-2.5 text-sm font-bold text-emerald-700 active:bg-emerald-50"
			>
				{m.cycle_started_today()}
			</button>
		</div>
		<div>
			<p class="mb-2 text-sm font-semibold text-slate-600">{m.cycle_length_label()}</p>
			<Stepper bind:value={cycleLength} min={21} max={40} />
			<!-- "duracao do ciclo" era lido como "quantos dias eu sangro". A dica separa
				 as duas coisas e dispensa a pessoa de saber o numero (28 e o padrao). -->
			<p class="mt-1.5 text-xs text-slate-400">{m.cycle_length_hint()}</p>
		</div>
	{/if}

	<button
		type="button"
		disabled={!canSave || saving}
		onclick={save}
		class="h-12 w-full rounded-2xl bg-emerald-600 font-bold text-white active:bg-emerald-700 disabled:opacity-40"
	>
		{m.cycle_save()}
	</button>
</div>
