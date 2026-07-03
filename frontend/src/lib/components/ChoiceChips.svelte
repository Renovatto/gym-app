<script lang="ts" generics="T extends string">
	interface Option {
		value: T;
		label: string;
		hint?: string;
	}

	let {
		options,
		value = $bindable(),
		columns = 1,
		onselect
	}: {
		options: Option[];
		value: T | null;
		columns?: 1 | 2 | 3;
		onselect?: (value: T) => void;
	} = $props();
</script>

<div class="grid gap-2" class:grid-cols-2={columns === 2} class:grid-cols-3={columns === 3}>
	{#each options as option (option.value)}
		<button
			type="button"
			class="min-h-14 rounded-2xl border-2 px-4 py-3 text-left transition-colors
				{value === option.value
				? 'border-emerald-600 bg-emerald-50 text-emerald-900'
				: 'border-slate-200 bg-white text-slate-700 active:bg-slate-100'}"
			onclick={() => {
				value = option.value;
				onselect?.(option.value);
			}}
		>
			<span class="block font-semibold">{option.label}</span>
			{#if option.hint}
				<span class="mt-0.5 block text-sm text-slate-500">{option.hint}</span>
			{/if}
		</button>
	{/each}
</div>
