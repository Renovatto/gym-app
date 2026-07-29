<script lang="ts">
	import { untrack } from 'svelte';
	import { m } from '$lib/paraglide/messages';
	import { getLocale } from '$lib/paraglide/runtime';

	// value: dia selecionado (YYYY-MM-DD). marked: dias com evento (mesmo formato).
	// markedAlt: segundo tipo de evento, marcado em outra cor no mesmo dia (os dois
	// pontinhos convivem). legend/legendAlt: o que cada cor significa.
	// max: ultimo dia selecionavel (ex.: hoje). onselect/onclose: callbacks.
	// onmonth: avisa quando o mes visivel muda (o pai carrega as marcacoes do mes).
	let {
		value,
		marked = new Set<string>(),
		markedAlt = new Set<string>(),
		legend,
		legendAlt,
		max,
		onselect,
		onclose,
		onmonth
	}: {
		value: string;
		marked?: Set<string>;
		markedAlt?: Set<string>;
		legend?: string;
		legendAlt?: string;
		max?: string;
		onselect: (date: string) => void;
		onclose: () => void;
		onmonth?: (year: number, month: number) => void;
	} = $props();

	function pad(n: number): string {
		return String(n).padStart(2, '0');
	}
	function isoOf(year: number, monthIndex: number, day: number): string {
		return `${year}-${pad(monthIndex + 1)}-${pad(day)}`;
	}

	// mes visivel inicial vem do dia selecionado; depois o usuario navega livremente
	// (por isso lemos value so uma vez, sem reatividade, com untrack).
	const initial = untrack(() => new Date(value + 'T12:00:00'));
	let viewYear = $state(initial.getFullYear());
	let viewMonth = $state(initial.getMonth());

	const locale = getLocale();
	const monthFormatter = new Intl.DateTimeFormat(locale, { month: 'long', year: 'numeric' });
	// cabecalhos dos dias da semana (domingo a sabado) traduzidos
	const weekdayLabels = Array.from({ length: 7 }, (_, i) =>
		new Intl.DateTimeFormat(locale, { weekday: 'short' }).format(new Date(2023, 0, 1 + i))
	);

	const monthLabel = $derived(monthFormatter.format(new Date(viewYear, viewMonth, 1)));
	const daysInMonth = $derived(new Date(viewYear, viewMonth + 1, 0).getDate());
	const firstWeekday = $derived(new Date(viewYear, viewMonth, 1).getDay());

	function shiftMonth(delta: number): void {
		const d = new Date(viewYear, viewMonth + delta, 1);
		viewYear = d.getFullYear();
		viewMonth = d.getMonth();
	}

	// avisa o pai sempre que o mes visivel muda (para carregar as marcacoes)
	$effect(() => {
		onmonth?.(viewYear, viewMonth + 1);
	});

	function pick(day: number): void {
		const iso = isoOf(viewYear, viewMonth, day);
		if (max && iso > max) return; // nao seleciona dia futuro
		onselect(iso);
		onclose();
	}
</script>

<div
	class="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
	role="button"
	tabindex="-1"
	onclick={onclose}
	onkeydown={(e) => e.key === 'Escape' && onclose()}
>
	<div
		class="w-full max-w-sm rounded-3xl bg-white p-5"
		role="dialog"
		tabindex="-1"
		onclick={(e) => e.stopPropagation()}
		onkeydown={() => {}}
	>
		<div class="mb-4 flex items-center justify-between">
			<button
				type="button"
				aria-label={m.previous_day()}
				onclick={() => shiftMonth(-1)}
				class="grid h-10 w-10 place-items-center rounded-full bg-slate-100 text-slate-500 active:bg-slate-200"
			>
				<svg viewBox="0 0 24 24" class="h-5 w-5" fill="none" stroke="currentColor" stroke-width="2"><path d="M15 6l-6 6 6 6" stroke-linecap="round" stroke-linejoin="round" /></svg>
			</button>
			<span class="font-bold text-slate-800 capitalize">{monthLabel}</span>
			<button
				type="button"
				aria-label={m.next_day()}
				onclick={() => shiftMonth(1)}
				class="grid h-10 w-10 place-items-center rounded-full bg-slate-100 text-slate-500 active:bg-slate-200"
			>
				<svg viewBox="0 0 24 24" class="h-5 w-5" fill="none" stroke="currentColor" stroke-width="2"><path d="M9 6l6 6-6 6" stroke-linecap="round" stroke-linejoin="round" /></svg>
			</button>
		</div>

		<div class="grid grid-cols-7 gap-1 text-center">
			{#each weekdayLabels as label (label)}
				<span class="py-1 text-xs font-bold text-slate-400 capitalize">{label.slice(0, 3)}</span>
			{/each}

			<!-- espacos vazios antes do dia 1 -->
			{#each Array(firstWeekday) as _, i (i)}
				<span></span>
			{/each}

			{#each Array(daysInMonth) as _, i (i)}
				{@const day = i + 1}
				{@const iso = isoOf(viewYear, viewMonth, day)}
				{@const isSelected = iso === value}
				{@const isMarked = marked.has(iso)}
				{@const isMarkedAlt = markedAlt.has(iso)}
				{@const isFuture = max ? iso > max : false}
				<button
					type="button"
					disabled={isFuture}
					onclick={() => pick(day)}
					class="relative mx-auto grid h-10 w-10 place-items-center rounded-full text-sm font-semibold transition-colors
						{isSelected
						? 'bg-emerald-600 text-white'
						: isFuture
							? 'text-slate-300'
							: 'text-slate-700 active:bg-slate-100'}"
				>
					{day}
					{#if (isMarked || isMarkedAlt) && !isSelected}
						<span class="absolute bottom-1 left-1/2 flex -translate-x-1/2 gap-0.5">
							{#if isMarked}
								<span class="h-1.5 w-1.5 rounded-full bg-emerald-500"></span>
							{/if}
							{#if isMarkedAlt}
								<span class="h-1.5 w-1.5 rounded-full bg-sky-500"></span>
							{/if}
						</span>
					{/if}
				</button>
			{/each}
		</div>

		{#if legend || legendAlt}
			<div class="mt-4 flex flex-wrap items-center justify-center gap-x-4 gap-y-1 text-[11px] font-semibold text-slate-500">
				{#if legend}
					<span class="flex items-center gap-1.5">
						<span class="h-1.5 w-1.5 rounded-full bg-emerald-500"></span>{legend}
					</span>
				{/if}
				{#if legendAlt}
					<span class="flex items-center gap-1.5">
						<span class="h-1.5 w-1.5 rounded-full bg-sky-500"></span>{legendAlt}
					</span>
				{/if}
			</div>
		{/if}
	</div>
</div>
