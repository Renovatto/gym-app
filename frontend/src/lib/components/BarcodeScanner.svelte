<script lang="ts">
	import { m } from '$lib/paraglide/messages';
	import Spinner from '$lib/components/Spinner.svelte';

	let { onread, onclose }: { onread: (code: string) => void; onclose: () => void } = $props();

	// Motivos de falha separados porque a acao da pessoa muda em cada um: permissao
	// ela resolve nos ajustes, conexao insegura so o endereco https resolve, e
	// aparelho sem camera nao tem solucao - so restaria digitar.
	type Falha = 'permissao' | 'insegura' | 'indisponivel';

	// A cada este intervalo uma foto do video vira uma tentativa de leitura. Mais
	// rapido que isso so gasta bateria: o codigo nao entra e sai de quadro em 150ms.
	const INTERVALO_MS = 150;
	// Se o video nao comecar a dar quadros nesse tempo, alguma coisa travou e e
	// melhor dizer isso do que deixar o spinner girando para sempre.
	const ESPERA_MAXIMA_MS = 8000;

	let video = $state<HTMLVideoElement | null>(null);
	let entradaFoto = $state<HTMLInputElement | null>(null);
	let lendoFoto = $state(false);
	let fotoFalhou = $state(false);
	let falha = $state<Falha | null>(null);
	let iniciando = $state(true);
	// Detalhe tecnico da falha (nome da excecao, estado do video). Nao e traduzido
	// de proposito: e um codigo para diagnostico, nao texto de interface - e sem ele
	// "nao consegui abrir a camera" nao diz em que passo parou.
	let detalhe = $state('');


	// Plano B: a pessoa tira UMA foto do codigo. Passa pelo mesmo decodificador da
	// camera ao vivo, so que sem stream nenhum - por isso funciona mesmo onde o
	// video inline nao toca (o caso do app instalado no iOS).
	async function lerDaFoto(arquivo: File): Promise<void> {
		lendoFoto = true;
		fotoFalhou = false;
		try {
			const imagem = await criarImagem(arquivo);
			const tela = document.createElement('canvas');
			// Limita o lado maior: foto de celular tem muito mais pixel do que a
			// leitura precisa, e o excesso so deixa a decodificacao lenta.
			const escala = Math.min(1, 1600 / Math.max(imagem.width, imagem.height));
			tela.width = Math.round(imagem.width * escala);
			tela.height = Math.round(imagem.height * escala);
			const pincel = tela.getContext('2d', { willReadFrequently: true });
			if (!pincel) throw new Error('sem canvas');
			pincel.drawImage(imagem, 0, 0, tela.width, tela.height);

			const { data } = pincel.getImageData(0, 0, tela.width, tela.height);
			const codigo = await decodificar(data, tela.width, tela.height);
			if (codigo) {
				onread(codigo);
				return;
			}
			fotoFalhou = true;
		} catch {
			fotoFalhou = true;
		} finally {
			lendoFoto = false;
		}
	}

	function criarImagem(arquivo: File): Promise<HTMLImageElement> {
		return new Promise((resolve, reject) => {
			const url = URL.createObjectURL(arquivo);
			const imagem = new Image();
			imagem.onload = () => {
				URL.revokeObjectURL(url);
				resolve(imagem);
			};
			imagem.onerror = () => {
				URL.revokeObjectURL(url);
				reject(new Error('imagem invalida'));
			};
			imagem.src = url;
		});
	}

	// Converte um quadro RGBA em codigo lido, ou null quando nao ha codigo nele.
	// E o unico lugar que fala com a biblioteca: a camera passa a faixa central do
	// video por aqui a cada 150ms, e a foto passa a imagem inteira uma vez.
	async function decodificar(rgba: Uint8ClampedArray, largura: number, altura: number): Promise<string | null> {
		const { BarcodeFormat, BinaryBitmap, DecodeHintType, HybridBinarizer, MultiFormatReader, RGBLuminanceSource } =
			await import('@zxing/library');
		const hints = new Map();
		hints.set(DecodeHintType.POSSIBLE_FORMATS, [
			BarcodeFormat.EAN_13,
			BarcodeFormat.EAN_8,
			BarcodeFormat.UPC_A,
			BarcodeFormat.UPC_E
		]);
		const leitor = new MultiFormatReader();
		leitor.setHints(hints);
		// RGBA -> luminancia (a formula padrao de brilho percebido). O leitor trabalha
		// em tons de cinza; passar o quadro colorido so daria a ele a mesma conta.
		const cinza = new Uint8ClampedArray(largura * altura);
		for (let i = 0, p = 0; i < cinza.length; i++, p += 4) {
			cinza[i] = (rgba[p] * 306 + rgba[p + 1] * 601 + rgba[p + 2] * 117) >> 10;
		}
		try {
			const fonte = new RGBLuminanceSource(cinza, largura, altura);
			return leitor.decode(new BinaryBitmap(new HybridBinarizer(fonte))).getText();
		} catch {
			return null; // nenhum codigo nesta imagem
		} finally {
			leitor.reset();
		}
	}

	$effect(() => {
		const elemento = video;
		if (!elemento) return;

		let cancelado = false;
		let stream: MediaStream | null = null;
		let timer: ReturnType<typeof setInterval> | null = null;

		function encerrar(): void {
			cancelado = true;
			if (timer) clearInterval(timer);
			stream?.getTracks().forEach((t) => t.stop());
		}

		void (async () => {
			// A camera exige contexto seguro (https ou localhost). Pelo IP da rede em
			// http o navegador nem oferece a API - e o caso mais comum de "nao abre"
			// durante o desenvolvimento, entao ele tem mensagem propria.
			if (!window.isSecureContext || !navigator.mediaDevices?.getUserMedia) {
				falha = 'insegura';
				iniciando = false;
				return;
			}

			try {
				// ideal e nao exact: se o aparelho nao tiver camera traseira, usa a que
				// tiver em vez de falhar.
				stream = await navigator.mediaDevices.getUserMedia({
					video: { facingMode: { ideal: 'environment' } }
				});
				if (cancelado) return encerrar();

				// Estas TRES coisas sao propriedade, nao atributo: o Safari do iPhone so
				// toca um video inline sem gesto se elas estiverem no objeto. Escritas
				// como atributo no HTML (o que o Svelte faz) ele ignora, a reproducao
				// nunca comeca, e o resultado e exatamente uma tela preta com a camera
				// ligada - o sintoma que isso aqui conserta.
				elemento.muted = true;
				elemento.playsInline = true;
				elemento.autoplay = true;
				elemento.srcObject = stream;

				// No app instalado (standalone) o primeiro play() pode ser recusado
				// porque os metadados do stream ainda nao chegaram. Nesse caso esperamos
				// o loadedmetadata e tentamos de novo, em vez de desistir calado - que
				// era a tela preta com a camera ligada.
				try {
					await elemento.play();
				} catch (erroPlay) {
					detalhe = `play: ${erroPlay instanceof Error ? erroPlay.name : 'falhou'}`;
					await new Promise<void>((resolve) => {
						const pronto = (): void => resolve();
						elemento.addEventListener('loadedmetadata', pronto, { once: true });
						setTimeout(pronto, 2000);
					});
					await elemento.play().catch((outro) => {
						detalhe = `play2: ${outro instanceof Error ? outro.name : 'falhou'}`;
					});
				}

				const tela = document.createElement('canvas');
				const pincel = tela.getContext('2d', { willReadFrequently: true });
				if (!pincel) {
					falha = 'indisponivel';
					iniciando = false;
					return encerrar();
				}

				const comecou = Date.now();
				let ocupado = false;

				timer = setInterval(() => {
					if (cancelado || ocupado) return;

					const largura = elemento.videoWidth;
					const altura = elemento.videoHeight;
					if (!largura || !altura) {
						if (Date.now() - comecou > ESPERA_MAXIMA_MS) {
							const faixas = stream?.getVideoTracks() ?? [];
							detalhe =
								`${detalhe ? detalhe + ' · ' : ''}sem quadros · readyState=${elemento.readyState}` +
								` · pausado=${elemento.paused} · trilha=${faixas[0]?.readyState ?? 'nenhuma'}` +
								` · standalone=${window.matchMedia('(display-mode: standalone)').matches}`;
							falha = 'indisponivel';
							iniciando = false;
							encerrar();
						}
						return;
					}
					iniciando = false;

					// Le so a faixa central do quadro, a mesma area da mira: e onde a
					// pessoa encosta o codigo, e olhar menos pixel deixa a leitura rapida
					// o bastante para rodar a cada 150ms sem esquentar o aparelho.
					const faixaAltura = Math.round(altura * 0.4);
					const topo = Math.round((altura - faixaAltura) / 2);
					tela.width = largura;
					tela.height = faixaAltura;
					pincel.drawImage(elemento, 0, topo, largura, faixaAltura, 0, 0, largura, faixaAltura);
					const { data } = pincel.getImageData(0, 0, largura, faixaAltura);

					ocupado = true;
					void decodificar(data, largura, faixaAltura)
						.then((codigo) => {
							if (cancelado || !codigo) return;
							encerrar();
							onread(codigo);
						})
						.finally(() => {
							ocupado = false;
						});
				}, INTERVALO_MS);
			} catch (erro) {
				const nome = erro instanceof DOMException ? erro.name : String(erro);
				detalhe = `${detalhe ? detalhe + ' · ' : ''}${nome}`;
				falha = nome === 'NotAllowedError' || nome === 'SecurityError' ? 'permissao' : 'indisponivel';
				iniciando = false;
				encerrar();
			}
		})();

		return encerrar;
	});
</script>

<div class="fixed inset-0 z-50 flex flex-col bg-ink">
	<div
		class="flex items-center justify-between px-4 pt-[calc(env(safe-area-inset-top)+0.75rem)] pb-3"
	>
		<p class="text-sm font-bold text-white">{m.scan_title()}</p>
		<button
			type="button"
			onclick={onclose}
			aria-label={m.cancel()}
			class="grid h-9 w-9 place-items-center rounded-full text-white/70 active:bg-white/10"
		>
			<svg viewBox="0 0 24 24" class="h-5 w-5" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M6 6l12 12M18 6L6 18" /></svg>
		</button>
	</div>

	<div class="relative flex-1 overflow-hidden">
		<!-- svelte-ignore a11y_media_has_caption -->
		<video bind:this={video} class="h-full w-full object-cover"></video>

		{#if !falha}
			<!-- Janela de mira: nao recorta nada, so diz onde encostar o codigo. -->
			<div class="pointer-events-none absolute inset-0 grid place-items-center">
				<div class="h-28 w-4/5 max-w-xs rounded-2xl border-2 border-emerald-400/90 shadow-[0_0_0_9999px_rgba(15,23,42,0.55)]"></div>
			</div>
		{/if}

		{#if iniciando && !falha}
			<div class="absolute inset-0 grid place-items-center gap-3">
				<Spinner class="h-7 w-7 text-white" />
				<p class="text-xs text-white/60">{m.scan_starting()}</p>
			</div>
		{/if}

		{#if falha}
			<div class="absolute inset-0 grid place-items-center px-6">
				<div class="max-w-xs text-center">
					<p class="text-sm font-semibold text-white">
						{#if falha === 'permissao'}{m.scan_error_permission()}
						{:else if falha === 'insegura'}{m.scan_error_insecure()}
						{:else}{m.scan_error_unavailable()}{/if}
					</p>
					{#if detalhe}
						<p class="mt-2 font-mono text-[11px] break-words text-white/45">{detalhe}</p>
					{/if}
				</div>
			</div>
		{/if}
	</div>

	<div class="px-6 pt-4 pb-[calc(env(safe-area-inset-bottom)+1.25rem)] text-center">
		{#if fotoFalhou}
			<p class="mb-3 text-xs font-semibold text-amber-300">{m.scan_photo_failed()}</p>
		{:else if !falha}
			<p class="mb-3 text-xs text-white/60">{m.scan_hint()}</p>
		{/if}

		<!--
			Plano B sempre a mao: onde o video ao vivo nao toca (app instalado no iOS),
			a foto ainda funciona - ela nao depende de stream nenhum. Por isso o botao
			existe mesmo quando a camera abriu: e a saida de quem nao consegue fazer o
			codigo entrar em foco.
		-->
		<input
			bind:this={entradaFoto}
			type="file"
			accept="image/*"
			capture="environment"
			class="hidden"
			onchange={(e) => {
				const arquivo = e.currentTarget.files?.[0];
				if (arquivo) void lerDaFoto(arquivo);
				e.currentTarget.value = '';
			}}
		/>
		<button
			type="button"
			disabled={lendoFoto}
			onclick={() => entradaFoto?.click()}
			class="inline-flex h-11 items-center gap-2 rounded-2xl border-2 border-white/25 px-4 text-sm font-bold text-white active:bg-white/10 disabled:opacity-50"
		>
			{#if lendoFoto}<Spinner class="h-4 w-4" />{/if}
			{m.scan_photo_action()}
		</button>
	</div>
</div>
