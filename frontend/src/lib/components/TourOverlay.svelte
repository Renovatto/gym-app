<script lang="ts">
	import { page } from '$app/state';
	import { m } from '$lib/paraglide/messages';
	import { session } from '$lib/session.svelte';
	import {
		isTourPending,
		nextStep,
		pauseTour,
		prevStep,
		skipTour,
		startTour,
		tour
	} from '$lib/tour.svelte';
	import { TOUR_BY_ROUTE, TOURS } from '$lib/tourSteps';

	// Tempo que a tela tem para buscar os dados na API antes de tentarmos apontar
	// qualquer coisa. Sem essa espera o tour abriria em cima de uma tela vazia.
	const START_DELAY_MS = 600;
	// Alvo que nao aparece neste tempo nao existe nesta tela (card condicional,
	// como "treino ativo"): o passo e pulado em vez de travar o tour.
	const ANCHOR_TIMEOUT_MS = 1500;
	const GAP_PX = 12; // respiro entre o recorte e o balao
	const PAD_PX = 8; // folga do recorte em volta do alvo

	interface Spotlight {
		top: number;
		left: number;
		width: number;
		height: number;
	}

	const steps = $derived(TOURS[tour.id] ?? []);
	const step = $derived(steps[tour.step] ?? null);

	let spot = $state<Spotlight | null>(null);
	let balloonEl = $state<HTMLElement | null>(null);
	let nextButtonEl = $state<HTMLButtonElement | null>(null);
	let balloonTop = $state(0);
	let arrowLeft = $state(0);
	let arrowOnTop = $state(true); // seta no topo do balao = balao esta abaixo do alvo

	let targetEl: HTMLElement | null = null;
	// Nao sao $state de proposito: servem so para nao reabrir o tour na mesma visita
	// depois que a pessoa pausou, e reagir aqui criaria laco no efeito de disparo.
	let visitedPath = '';
	let alreadyTried = false;

	function reducedMotion(): boolean {
		return window.matchMedia('(prefers-reduced-motion: reduce)').matches;
	}

	function wait(ms: number): Promise<void> {
		return new Promise((resolve) => setTimeout(resolve, ms));
	}

	function findAnchor(name: string): HTMLElement | null {
		const el = document.querySelector<HTMLElement>(`[data-tour="${name}"]`);
		if (el === null) return null;
		// Sem tamanho e o mesmo que nao existir: nao da para iluminar o vazio. Acontece
		// com lista ainda sem itens (as refeicoes de quem nao lancou nada hoje), que
		// deixa o container no DOM com altura zero.
		const box = el.getBoundingClientRect();
		return box.width > 0 && box.height > 0 ? el : null;
	}

	async function waitForAnchor(name: string): Promise<HTMLElement | null> {
		const deadline = Date.now() + ANCHOR_TIMEOUT_MS;
		let el = findAnchor(name);
		while (el === null && Date.now() < deadline) {
			await wait(100);
			el = findAnchor(name);
		}
		return el;
	}

	/**
	 * Traz o alvo para a area visivel. So rola quando precisa: elemento ja inteiro
	 * na tela fica parado, e a barra de abas (fixed) nunca provoca rolagem.
	 */
	async function bringIntoView(el: HTMLElement): Promise<void> {
		const margin = 24;
		const box = el.getBoundingClientRect();
		const alreadyVisible = box.top >= margin && box.bottom <= window.innerHeight - margin;
		if (alreadyVisible || getComputedStyle(el).position === 'fixed') return;

		const tallerThanScreen = box.height > window.innerHeight - margin * 2;
		const target = Math.max(
			0,
			tallerThanScreen
				? window.scrollY + box.top - margin
				: window.scrollY + box.top - (window.innerHeight - box.height) / 2
		);
		window.scrollTo({ top: target, behavior: reducedMotion() ? 'auto' : 'smooth' });
		await settleScroll(target);
	}

	/**
	 * Espera a rolagem parar. Ha ambiente que ignora o scroll suave (Chrome com as
	 * animacoes desligadas, por exemplo), entao no fim conferimos onde paramos e, se
	 * preciso, saltamos para a posicao: o tutorial nao pode apontar para o vazio.
	 */
	async function settleScroll(target: number): Promise<void> {
		let previous = -1;
		for (let i = 0; i < 8 && Math.round(window.scrollY) !== previous; i += 1) {
			previous = Math.round(window.scrollY);
			await wait(80);
		}
		if (Math.abs(window.scrollY - target) > 4) window.scrollTo({ top: target, behavior: 'auto' });
	}

	function measureTarget(): void {
		if (targetEl === null) return;
		const box = targetEl.getBoundingClientRect();
		spot = {
			top: box.top - PAD_PX,
			left: box.left - PAD_PX,
			width: box.width + PAD_PX * 2,
			height: box.height + PAD_PX * 2
		};
	}

	// Dispara o tour da aba na primeira visita. As quatro condicoes tem que valer:
	// tutorial ligado, rota com tour, ainda sobra passo novo e nenhuma modal aberta.
	$effect(() => {
		const path = page.url.pathname;
		if (path !== visitedPath) {
			visitedPath = path;
			alreadyTried = false;
		}
		const tourId = TOUR_BY_ROUTE[path];
		if (!tourId || alreadyTried || tour.active) return;
		if (!session.profile || !isTourPending(tourId)) return;

		const timer = setTimeout(() => {
			// Uma modal ja aberta manda na tela; nao empilhamos dois overlays.
			if (document.querySelector('[aria-modal="true"]') !== null) return;
			alreadyTried = true;
			startTour(tourId);
		}, START_DELAY_MS);
		return () => clearTimeout(timer);
	});

	// Sai da aba no meio do tour: guarda o lugar em vez de deixar o balao orfao.
	$effect(() => {
		const path = page.url.pathname;
		if (tour.active && TOUR_BY_ROUTE[path] !== tour.id) pauseTour();
	});

	// A cada passo: acha o alvo, rola ate ele e mede.
	$effect(() => {
		const current = step;
		if (!tour.active || current === null) {
			spot = null;
			targetEl = null;
			return;
		}
		let cancelled = false;
		void (async () => {
			if (current.anchor === null) {
				targetEl = null;
				spot = null;
				return;
			}
			const el = await waitForAnchor(current.anchor);
			if (cancelled) return;
			if (el === null) {
				nextStep(); // alvo nao existe nesta tela: segue para o proximo
				return;
			}
			targetEl = el;
			await bringIntoView(el);
			if (cancelled) return;
			measureTarget();
		})();
		return () => {
			cancelled = true;
		};
	});

	// Onde o balao cabe: abaixo do alvo quando ha espaco, senao acima. Sem alvo,
	// no meio da tela.
	$effect(() => {
		const card = balloonEl;
		const area = spot;
		void tour.step; // texto novo muda a altura do card: remede a cada passo
		if (card === null) return;

		const cardHeight = card.offsetHeight;
		if (area === null) {
			balloonTop = Math.max(GAP_PX, (window.innerHeight - cardHeight) / 2);
			return;
		}
		const fitsBelow = area.top + area.height + GAP_PX + cardHeight <= window.innerHeight - 16;
		balloonTop = fitsBelow
			? area.top + area.height + GAP_PX
			: Math.max(GAP_PX, area.top - GAP_PX - cardHeight);
		arrowOnTop = fitsBelow;

		const cardBox = card.getBoundingClientRect();
		const targetCenter = area.left + area.width / 2;
		arrowLeft = Math.min(Math.max(targetCenter - cardBox.left, 24), cardBox.width - 24);
	});

	// Teclado: o foco vai para o botao que avanca, entao da para percorrer o tour
	// inteiro sem tocar na tela.
	$effect(() => {
		void tour.step;
		nextButtonEl?.focus({ preventScroll: true });
	});

	function onKeydown(event: KeyboardEvent): void {
		if (!tour.active) return;
		if (event.key === 'Escape') pauseTour();
	}
</script>

<svelte:window
	onkeydown={onKeydown}
	onresize={measureTarget}
	onscroll={measureTarget}
	onorientationchange={measureTarget}
/>

{#if tour.active && step}
	<!-- Camada que segura os cliques: durante o tour a tela nao responde, e tocar
		 fora do balao pausa (o progresso fica salvo). -->
	<div
		class="fixed inset-0 z-[55]"
		role="button"
		tabindex="-1"
		aria-label={m.tour_pause()}
		onclick={pauseTour}
		onkeydown={() => {}}
	></div>

	{#if spot}
		<!-- O escuro e o recorte sao o MESMO elemento: uma sombra de 9999px em volta
			 de um retangulo furado. Sem mascara SVG, sem quatro divs. -->
		<div
			class="tour-hole"
			style="top: {spot.top}px; left: {spot.left}px; width: {spot.width}px; height: {spot.height}px;"
		></div>
	{:else}
		<div class="tour-veil"></div>
	{/if}

	<div
		bind:this={balloonEl}
		class="tour-balloon rounded-3xl bg-white p-5 shadow-xl"
		style="top: {balloonTop}px;"
		role="dialog"
		aria-modal="true"
		aria-labelledby="tour-step-title"
	>
		{#if spot}
			<span
				class="tour-arrow"
				style="left: {arrowLeft}px; {arrowOnTop ? 'top: -7px;' : 'bottom: -7px;'}"
			></span>
		{/if}

		<h2 id="tour-step-title" class="text-lg font-bold text-slate-900">{step.title()}</h2>
		<p class="mt-1 text-slate-500">{step.text()}</p>

		<!-- Mesma barra segmentada do cadastro: a pessoa ja sabe ler esse progresso. -->
		<div class="mt-4 flex gap-1.5" aria-hidden="true">
			{#each steps as _, i (i)}
				<div class="h-1.5 flex-1 rounded-full {i <= tour.step ? 'bg-emerald-600' : 'bg-slate-200'}"></div>
			{/each}
		</div>

		<div class="mt-4 flex gap-3">
			{#if tour.step > 0}
				<button
					type="button"
					class="h-14 flex-1 rounded-2xl border-2 border-slate-200 bg-white font-bold text-slate-700 active:bg-slate-100"
					onclick={prevStep}
				>
					{m.back()}
				</button>
			{/if}
			<button
				bind:this={nextButtonEl}
				type="button"
				class="h-14 flex-[2] rounded-2xl bg-emerald-600 text-lg font-bold text-white active:bg-emerald-700"
				onclick={nextStep}
			>
				{tour.step === steps.length - 1 ? m.finish() : m.next()}
			</button>
		</div>

		<button
			type="button"
			class="mt-3 w-full text-center text-sm font-semibold text-slate-400 active:text-slate-600"
			onclick={skipTour}
		>
			{m.tour_skip()}
		</button>
	</div>
{/if}

<style>
	.tour-hole,
	.tour-veil {
		position: fixed;
		z-index: 56;
		pointer-events: none;
	}

	.tour-veil {
		inset: 0;
		background: rgb(0 0 0 / 0.62);
	}

	.tour-hole {
		border-radius: 24px;
		box-shadow: 0 0 0 9999px rgb(0 0 0 / 0.62);
		outline: 2px solid var(--color-emerald-500);
		transition:
			top 0.32s ease,
			left 0.32s ease,
			width 0.32s ease,
			height 0.32s ease;
	}

	.tour-balloon {
		position: fixed;
		z-index: 57;
		left: 50%;
		width: min(100% - 2rem, 28rem);
		transform: translateX(-50%);
		animation: tourBalloonIn 0.24s ease-out both;
	}

	.tour-arrow {
		position: absolute;
		width: 14px;
		height: 14px;
		border-radius: 3px;
		background: var(--color-white);
		transform: translateX(-50%) rotate(45deg);
	}

	@keyframes tourBalloonIn {
		from {
			opacity: 0;
			transform: translateX(-50%) translateY(6px);
		}
	}

	@media (prefers-reduced-motion: reduce) {
		.tour-hole {
			transition: none;
		}
		.tour-balloon {
			animation: none;
		}
	}
</style>
