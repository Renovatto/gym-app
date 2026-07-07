<script lang="ts">
	let {
		value = $bindable(),
		min = 0,
		max = 999,
		step = 1,
		unit = '',
		decimals = 0,
		size = 'md',
		onchange
	}: {
		value: number;
		min?: number;
		max?: number;
		step?: number;
		unit?: string;
		decimals?: number;
		// md: controle padrao (formularios). sm: compacto para caber dois numa linha (execucao do treino).
		size?: 'md' | 'sm';
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

	// Enquanto digita, remove tudo que nao seja numero, virgula, ponto ou sinal.
	// Bloqueia letras direto no campo (o teclado do celular ja e numerico via inputmode).
	function stripNonNumeric(event: Event): void {
		const input = event.currentTarget as HTMLInputElement;
		const cleaned = input.value.replace(/[^0-9.,-]/g, '');
		if (cleaned !== input.value) input.value = cleaned;
	}

	// Classes por tamanho: md mantem o visual original; sm encolhe botao e fonte.
	const wrapClass = $derived(size === 'sm' ? 'flex items-center gap-1' : 'flex items-center gap-1.5');
	const buttonClass = $derived(
		size === 'sm'
			? 'h-9 w-9 shrink-0 rounded-lg border-2 border-slate-200 bg-white text-lg font-bold text-slate-700 active:bg-slate-100'
			: 'h-12 w-12 shrink-0 rounded-xl border-2 border-slate-200 bg-white text-2xl font-bold text-slate-700 active:bg-slate-100'
	);
	const inputClass = $derived(
		size === 'sm'
			? 'w-full min-w-0 border-none bg-transparent text-center text-base font-bold text-slate-900 outline-none'
			: 'w-full min-w-0 border-none bg-transparent text-center text-2xl font-bold text-slate-900 outline-none'
	);
</script>

<div class={wrapClass}>
	<button type="button" aria-label="-" class={buttonClass} onclick={() => nudge(-1)}>−</button>
	<div class="flex min-w-0 flex-1 items-baseline justify-center gap-0.5">
		<input
			inputmode="decimal"
			class={inputClass}
			value={value.toFixed(decimals)}
			oninput={stripNonNumeric}
			onchange={onInput}
		/>
		{#if unit}<span class="shrink-0 text-xs text-slate-400">{unit}</span>{/if}
	</div>
	<button type="button" aria-label="+" class={buttonClass} onclick={() => nudge(1)}>+</button>
</div>
