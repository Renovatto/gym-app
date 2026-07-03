<script lang="ts">
	import type { WeightLog } from '$lib/api';
	import { getLocale } from '$lib/paraglide/runtime';

	let { logs }: { logs: WeightLog[] } = $props();

	// viewBox fixo; a linha usa vector-effect para não engrossar ao esticar.
	const W = 320;
	const H = 150;
	const PAD_X = 12;
	const PAD_TOP = 16;
	const PAD_BOTTOM = 18;

	const df = new Intl.DateTimeFormat(getLocale(), { day: '2-digit', month: '2-digit' });

	const geometry = $derived.by(() => {
		if (logs.length === 0) return null;
		const values = logs.map((l) => l.weight_kg);
		const min = Math.min(...values);
		const max = Math.max(...values);
		// margem de 1kg (ou metade do range) para a linha não colar nas bordas
		const pad = Math.max(1, (max - min) * 0.5);
		const lo = min - pad;
		const hi = max + pad;
		const span = hi - lo || 1;

		const innerW = W - PAD_X * 2;
		const innerH = H - PAD_TOP - PAD_BOTTOM;

		const points = logs.map((log, i) => {
			const x = logs.length === 1 ? W / 2 : PAD_X + (innerW * i) / (logs.length - 1);
			const y = PAD_TOP + innerH * (1 - (log.weight_kg - lo) / span);
			return { x, y, log };
		});

		const line = points.map((p) => `${p.x},${p.y}`).join(' ');
		const area = `${PAD_X},${H - PAD_BOTTOM} ${line} ${points[points.length - 1].x},${H - PAD_BOTTOM}`;
		return { points, line, area, lo, hi };
	});
</script>

{#if geometry}
	<svg viewBox="0 0 {W} {H}" class="w-full" role="img" aria-label="weight trend">
		<defs>
			<linearGradient id="weightFill" x1="0" y1="0" x2="0" y2="1">
				<stop offset="0%" stop-color="#059669" stop-opacity="0.18" />
				<stop offset="100%" stop-color="#059669" stop-opacity="0" />
			</linearGradient>
		</defs>

		<polygon points={geometry.area} fill="url(#weightFill)" />
		<polyline
			points={geometry.line}
			fill="none"
			stroke="#059669"
			stroke-width="2"
			stroke-linejoin="round"
			stroke-linecap="round"
			vector-effect="non-scaling-stroke"
		/>
		{#each geometry.points as p (p.log.id)}
			<circle cx={p.x} cy={p.y} r="3.5" fill="#059669" stroke="white" stroke-width="1.5" />
		{/each}

		{#if geometry.points.length > 1}
			<text x={PAD_X} y={H - 5} class="fill-slate-400 text-[9px]">
				{df.format(new Date(geometry.points[0].log.logged_at))}
			</text>
			<text x={W - PAD_X} y={H - 5} text-anchor="end" class="fill-slate-400 text-[9px]">
				{df.format(new Date(geometry.points[geometry.points.length - 1].log.logged_at))}
			</text>
		{/if}
	</svg>
{/if}
