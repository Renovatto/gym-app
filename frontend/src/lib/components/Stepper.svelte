<script lang="ts">
	let {
		value = $bindable(),
		min = 0,
		max = 999,
		step = 1,
		unit = '',
		decimals = 0,
		onchange
	}: {
		value: number;
		min?: number;
		max?: number;
		step?: number;
		unit?: string;
		decimals?: number;
		onchange?: (value: number) => void;
	} = $props();

	function clamp(v: number): number {
		return Math.min(max, Math.max(min, Math.round(v / step) * step));
	}

	function set(v: number): void {
		value = Number(v.toFixed(decimals));
		onchange?.(value);
	}

	function nudge(direction: 1 | -1): void {
		set(clamp(value + direction * step));
	}

	function onInput(event: Event): void {
		const raw = (event.currentTarget as HTMLInputElement).value.replace(',', '.');
		const parsed = Number(raw);
		if (!Number.isNaN(parsed)) set(clamp(parsed));
	}
</script>

<div class="flex items-center gap-1.5">
	<button
		type="button"
		aria-label="-"
		class="h-12 w-12 shrink-0 rounded-xl border-2 border-slate-200 bg-white text-2xl font-bold text-slate-700 active:bg-slate-100"
		onclick={() => nudge(-1)}>−</button
	>
	<div class="flex min-w-0 flex-1 items-baseline justify-center gap-0.5">
		<input
			inputmode="decimal"
			class="w-full min-w-0 border-none bg-transparent text-center text-2xl font-bold text-slate-900 outline-none"
			value={value.toFixed(decimals)}
			onchange={onInput}
		/>
		{#if unit}<span class="shrink-0 text-xs text-slate-400">{unit}</span>{/if}
	</div>
	<button
		type="button"
		aria-label="+"
		class="h-12 w-12 shrink-0 rounded-xl border-2 border-slate-200 bg-white text-2xl font-bold text-slate-700 active:bg-slate-100"
		onclick={() => nudge(1)}>+</button
	>
</div>
