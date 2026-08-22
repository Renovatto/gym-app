<script lang="ts" generics="T extends string">
	// Pilula pequena e arredondada, o mesmo padrao dos filtros da biblioteca de receitas.
	// Use quando as opcoes sao muitas e o rotulo cabe numa linha; para escolha com dica
	// embaixo do rotulo o componente continua sendo o ChoiceChips.
	interface Option {
		value: T;
		label: string;
	}

	// clearLabel: rotulo da pilula que limpa a selecao (ex.: "Todas"). Quando ele existe
	// a escolha e um filtro, entao tocar de novo na pilula ativa tambem limpa. Sem ele a
	// escolha e obrigatoria e o toque so troca de opcao.
	let {
		options,
		value = $bindable(),
		clearLabel,
		onselect
	}: {
		options: Option[];
		value: T | null;
		clearLabel?: string;
		onselect?: (value: T | null) => void;
	} = $props();

	function select(option: T | null): void {
		value = option;
		onselect?.(option);
	}
</script>

<div class="flex flex-wrap gap-1.5">
	{#if clearLabel !== undefined}
		<button
			type="button"
			onclick={() => select(null)}
			class="rounded-full border-2 px-3 py-1.5 text-sm font-semibold {value === null
				? 'border-emerald-600 bg-emerald-50 text-emerald-800'
				: 'border-slate-200 text-slate-600'}"
		>
			{clearLabel}
		</button>
	{/if}
	{#each options as option (option.value)}
		<button
			type="button"
			onclick={() => select(clearLabel !== undefined && value === option.value ? null : option.value)}
			class="rounded-full border-2 px-3 py-1.5 text-sm font-semibold {value === option.value
				? 'border-emerald-600 bg-emerald-50 text-emerald-800'
				: 'border-slate-200 text-slate-600'}"
		>
			{option.label}
		</button>
	{/each}
</div>
