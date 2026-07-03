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

<div class="flex items-center gap-3">
	<button
		type="button"
		aria-label="-"
		class="h-14 w-14 shrink-0 rounded-2xl border-2 border-slate-200 bg-white text-2xl font-bold text-slate-700 active:bg-slate-100"
		onclick={() => nudge(-1)}>−</button
	>
	<div class="flex flex-1 items-baseline justify-center gap-1">
		<input
			inputmode="decimal"
			class="w-24 border-none bg-transparent text-center text-3xl font-bold text-slate-900 outline-none"
			value={value.toFixed(decimals)}
			onchange={onInput}
		/>
		{#if unit}<span class="text-lg text-slate-500">{unit}</span>{/if}
	</div>
	<button
		type="button"
		aria-label="+"
		class="h-14 w-14 shrink-0 rounded-2xl border-2 border-slate-200 bg-white text-2xl font-bold text-slate-700 active:bg-slate-100"
		onclick={() => nudge(1)}>+</button
	>
</div>
