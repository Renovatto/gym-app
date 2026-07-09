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

	// Usado na digitacao manual: so respeita min/max, sem forcar multiplo do
	// step - digitar "3" com step=2.5 deve salvar 3, nao arredondar pra 2.5.
	function clampRange(v: number): number {
		return Math.min(max, Math.max(min, v));
	}

	// Usado pelos botoes +/-: alem do min/max, arredonda pro multiplo do step
	// (mantem os incrementos "redondos": 2.5, 5, 7.5...).
	function clampToStep(v: number): number {
		return clampRange(Math.round(v / step) * step);
	}

	function set(v: number): void {
		value = Number(v.toFixed(decimals));
		onchange?.(value);
	}

	function nudge(direction: 1 | -1): void {
		set(clampToStep(value + direction * step));
	}

	function onInput(event: Event): void {
		const raw = (event.currentTarget as HTMLInputElement).value.replace(',', '.');
		const parsed = Number(raw);
		if (!Number.isNaN(parsed)) set(clampRange(parsed));
	}

	// Enquanto digita, remove tudo que nao seja numero, virgula, ponto ou sinal.
	// Bloqueia letras direto no campo (o teclado do celular ja e numerico via inputmode).
	function stripNonNumeric(event: Event): void {
		const input = event.currentTarget as HTMLInputElement;
		const cleaned = input.value.replace(/[^0-9.,-]/g, '');
		if (cleaned !== input.value) input.value = cleaned;
	}

</script>

{#if size === 'sm'}
	<!-- compacto: o valor ocupa a linha inteira (nunca corta, mesmo com "20.5") e os
	     botoes ficam numa linha abaixo, largos. Bom quando ha varios steppers lado a lado. -->
	<div class="flex flex-col gap-1">
		<div class="flex items-baseline justify-center gap-0.5">
			<input
				inputmode="decimal"
				class="w-full min-w-0 border-none bg-transparent text-center text-lg font-bold text-slate-900 outline-none"
				value={value.toFixed(decimals)}
				onfocus={(e) => e.currentTarget.select()}
				oninput={stripNonNumeric}
				onchange={onInput}
			/>
			{#if unit}<span class="shrink-0 text-xs text-slate-400">{unit}</span>{/if}
		</div>
		<div class="flex gap-1">
			<button
				type="button"
				aria-label="-"
				class="h-9 flex-1 rounded-lg border-2 border-slate-200 bg-white text-lg font-bold text-slate-700 active:bg-slate-100"
				onclick={() => nudge(-1)}>−</button
			>
			<button
				type="button"
				aria-label="+"
				class="h-9 flex-1 rounded-lg border-2 border-slate-200 bg-white text-lg font-bold text-slate-700 active:bg-slate-100"
				onclick={() => nudge(1)}>+</button
			>
		</div>
	</div>
{:else}
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
				onfocus={(e) => e.currentTarget.select()}
				oninput={stripNonNumeric}
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
{/if}
