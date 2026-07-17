<script lang="ts">
	import { page } from '$app/state';
	import { type FeedbackModule } from '$lib/api';
	import FeedbackModal from './FeedbackModal.svelte';
	import { m } from '$lib/paraglide/messages';

	// Botao flutuante de feedback: arrastavel (encosta na borda e lembra a posicao) para
	// nao atrapalhar botoes de acao de nenhuma tela. Toque curto abre; arrasto move.
	const SIZE = 52;
	const MARGIN = 10;
	const BOTTOM_GAP = 88; // folga acima da tab bar (h-16) + safe area
	const KEY = 'gymapp.feedbackFab';
	const DRAG_THRESHOLD = 6; // px para diferenciar toque de arrasto

	let open = $state(false);
	let left = $state(0);
	let top = $state(0);
	let dragging = $state(false);
	let ready = $state(false);

	function clampTop(t: number): number {
		return Math.max(MARGIN, Math.min(t, window.innerHeight - SIZE - BOTTOM_GAP));
	}
	function snapLeft(l: number): number {
		// encosta na borda mais proxima (centro do FAB vs meio da tela)
		return l + SIZE / 2 < window.innerWidth / 2 ? MARGIN : window.innerWidth - SIZE - MARGIN;
	}

	$effect(() => {
		const saved = localStorage.getItem(KEY);
		if (saved) {
			try {
				const p = JSON.parse(saved);
				left = snapLeft(p.left);
				top = clampTop(p.top);
			} catch {
				left = window.innerWidth - SIZE - MARGIN;
				top = clampTop(window.innerHeight - SIZE - BOTTOM_GAP);
			}
		} else {
			left = window.innerWidth - SIZE - MARGIN; // padrao: canto inferior direito
			top = clampTop(window.innerHeight - SIZE - BOTTOM_GAP);
		}
		ready = true;
	});

	// modulo pre-selecionado pela tela atual
	const currentModule = $derived<FeedbackModule>(
		page.url.pathname.startsWith('/treino')
			? 'workout'
			: page.url.pathname.startsWith('/dieta')
				? 'diet'
				: page.url.pathname.startsWith('/progresso')
					? 'progress'
					: page.url.pathname.startsWith('/perfil')
						? 'profile'
						: 'other'
	);

	let startX = 0;
	let startY = 0;
	let offX = 0;
	let offY = 0;
	let moved = false;

	function onPointerDown(e: PointerEvent): void {
		(e.currentTarget as HTMLElement).setPointerCapture(e.pointerId);
		startX = e.clientX;
		startY = e.clientY;
		offX = e.clientX - left;
		offY = e.clientY - top;
		moved = false;
	}
	function onPointerMove(e: PointerEvent): void {
		const el = e.currentTarget as HTMLElement;
		if (!el.hasPointerCapture(e.pointerId)) return;
		if (!moved && Math.hypot(e.clientX - startX, e.clientY - startY) > DRAG_THRESHOLD) {
			moved = true;
			dragging = true;
		}
		if (moved) {
			left = Math.max(MARGIN, Math.min(e.clientX - offX, window.innerWidth - SIZE - MARGIN));
			top = clampTop(e.clientY - offY);
		}
	}
	function onPointerUp(e: PointerEvent): void {
		(e.currentTarget as HTMLElement).releasePointerCapture(e.pointerId);
		if (!moved) {
			open = true; // foi um toque, nao um arrasto
		} else {
			left = snapLeft(left);
			localStorage.setItem(KEY, JSON.stringify({ left, top }));
		}
		dragging = false;
	}
</script>

{#if ready}
	<button
		type="button"
		aria-label={m.feedback_open()}
		title={m.feedback_open()}
		style="left: {left}px; top: {top}px; width: {SIZE}px; height: {SIZE}px;"
		onpointerdown={onPointerDown}
		onpointermove={onPointerMove}
		onpointerup={onPointerUp}
		class="fixed z-20 grid touch-none place-items-center rounded-2xl bg-emerald-600 text-white shadow-lg active:bg-emerald-700 {dragging
			? 'scale-105 cursor-grabbing'
			: 'transition-all duration-200 motion-reduce:transition-none'}"
	>
		<svg viewBox="0 0 24 24" class="h-6 w-6" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" /></svg>
	</button>
{/if}

{#if open}
	<FeedbackModal initialModule={currentModule} onClose={() => (open = false)} />
{/if}
