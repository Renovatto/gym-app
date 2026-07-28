<script lang="ts">
	import { macroTones } from '$lib/macros';
	import { getLocale } from '$lib/paraglide/runtime';

	// P/C/G compacto e colorido (ex.: "P: 14 C: 5 G: 12"), usado em qualquer lugar que
	// mostre a composicao de um alimento/receita/lancamento - o macro cuja fatia de
	// calorias e desproporcional fica em destaque, so pra chamar atencao.
	let { protein_g, carbs_g, fat_g, class: className = '' }: {
		protein_g: number;
		carbs_g: number;
		fat_g: number;
		class?: string;
	} = $props();

	const nf = new Intl.NumberFormat(getLocale(), { maximumFractionDigits: 0 });
	const tones = $derived(macroTones(protein_g, carbs_g, fat_g));
</script>

<span class="inline-flex items-center gap-1.5 tabular-nums {className}">
	<span>P: {nf.format(protein_g)}</span>
	<span class={tones.carbs === 'high' ? 'font-bold text-red-600' : ''}>C: {nf.format(carbs_g)}</span>
	<span class={tones.fat === 'high' ? 'font-bold text-red-600' : ''}>G: {nf.format(fat_g)}</span>
</span>
