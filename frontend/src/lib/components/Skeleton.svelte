<script lang="ts">
	// Bloco cinza com um brilho passando por cima, para o lugar do conteudo que ainda
	// nao chegou. A forma vem toda das classes de quem usa - o componente so cuida da
	// cor e da animacao.
	let { class: klass = 'h-4 w-full' }: { class?: string } = $props();
</script>

<div class="skeleton rounded-lg bg-slate-200 {klass}" aria-hidden="true"></div>

<style>
	.skeleton {
		position: relative;
		overflow: hidden;
	}
	/* o brilho e uma faixa clara atravessando o bloco da esquerda para a direita */
	.skeleton::after {
		content: '';
		position: absolute;
		inset: 0;
		transform: translateX(-100%);
		background: linear-gradient(90deg, transparent, rgb(255 255 255 / 0.7), transparent);
		animation: shimmer 1.4s infinite;
	}
	@keyframes shimmer {
		100% {
			transform: translateX(100%);
		}
	}
	/* quem pediu menos animacao no sistema ve o cinza parado, sem o brilho */
	@media (prefers-reduced-motion: reduce) {
		.skeleton::after {
			animation: none;
		}
	}
</style>
