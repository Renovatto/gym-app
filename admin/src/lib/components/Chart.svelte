<script lang="ts">
	import * as echarts from 'echarts';
	import { themeState } from '$lib/theme.svelte';

	/**
	 * Envelope do ECharts. Toda a configuracao vem de fora (`option`) porque cada
	 * tela sabe o que esta desenhando; aqui so mora o ciclo de vida: criar,
	 * atualizar, redimensionar e destruir.
	 */
	let {
		option,
		height = 260
	}: {
		option: echarts.EChartsOption;
		height?: number;
	} = $props();

	let host: HTMLDivElement;
	let chart: echarts.ECharts | null = null;

	$effect(() => {
		// Ler o tema aqui prende o efeito a ele: trocar claro/escuro recria o
		// grafico com as cores novas, em vez de deixar a paleta antiga colada.
		themeState.current;

		chart?.dispose();
		chart = echarts.init(host, undefined, { renderer: 'canvas' });
		chart.setOption(option);

		// O ECharts nao acompanha mudanca de tamanho do container sozinho; sem isto
		// o grafico fica com a largura do primeiro render ao abrir/fechar o trilho.
		const observer = new ResizeObserver(() => chart?.resize());
		observer.observe(host);

		return () => {
			observer.disconnect();
			chart?.dispose();
			chart = null;
		};
	});

	$effect(() => {
		// notMerge: false mantem o estado de interacao (zoom, serie escondida na
		// legenda) quando so os dados mudam.
		chart?.setOption(option, { notMerge: false });
	});
</script>

<div bind:this={host} style="width:100%;height:{height}px"></div>
