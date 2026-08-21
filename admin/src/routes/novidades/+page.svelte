<script lang="ts">
	import { api, ApiError, type AdminNews, type AdminNewsWrite } from '$lib/api';
	import { showToast } from '$lib/toast.svelte';
	import { errorMessage, shortDate } from '$lib/format';

	// Os tres idiomas sao obrigatorios de proposito: novidade publicada pela metade
	// aparece em branco para quem usa o app em ingles ou espanhol.
	const IDIOMAS = [
		{ chave: 'pt_br', rotulo: 'Portugues', titulo: 'title_pt_br', corpo: 'body_pt_br' },
		{ chave: 'en', rotulo: 'English', titulo: 'title_en', corpo: 'body_en' },
		{ chave: 'es', rotulo: 'Espanol', titulo: 'title_es', corpo: 'body_es' }
	] as const;

	function vazia(): AdminNewsWrite {
		return {
			published_on: new Date().toISOString().slice(0, 10),
			importance: 'normal',
			published: true,
			title_pt_br: '',
			body_pt_br: '',
			title_en: '',
			body_en: '',
			title_es: '',
			body_es: ''
		};
	}

	let novidades = $state<AdminNews[]>([]);
	let carregando = $state(true);
	let salvando = $state(false);

	// null = formulario fechado; 0 = criando; id = editando
	let editandoId = $state<number | null>(null);
	let rascunho = $state<AdminNewsWrite>(vazia());
	let abaIdioma = $state<'pt_br' | 'en' | 'es'>('pt_br');
	let confirmandoExclusao = $state<number | null>(null);
	let confirmandoDespublicar = $state<number | null>(null);

	async function carregar(): Promise<void> {
		try {
			novidades = await api.listNews();
		} catch (error) {
			showToast(errorMessage(error instanceof ApiError ? error.code : 'GENERIC_ERROR'));
		} finally {
			carregando = false;
		}
	}

	$effect(() => {
		void carregar();
	});

	const camposFaltando = $derived(
		IDIOMAS.filter(
			(idioma) => !rascunho[idioma.titulo].trim() || !rascunho[idioma.corpo].trim()
		).map((idioma) => idioma.rotulo)
	);

	function abrirNova(): void {
		rascunho = vazia();
		editandoId = 0;
		abaIdioma = 'pt_br';
	}

	function abrirEdicao(item: AdminNews): void {
		const { id, created_at, read_count, ...resto } = item;
		rascunho = { ...resto };
		editandoId = id;
		abaIdioma = 'pt_br';
	}

	function fechar(): void {
		editandoId = null;
	}

	async function salvar(): Promise<void> {
		if (salvando || camposFaltando.length > 0 || editandoId === null) return;
		salvando = true;
		try {
			if (editandoId === 0) {
				const criada = await api.createNews(rascunho);
				novidades = [criada, ...novidades];
				showToast(rascunho.published ? 'Novidade publicada' : 'Novidade salva como rascunho');
			} else {
				const atualizada = await api.updateNews(editandoId, rascunho);
				novidades = novidades.map((item) => (item.id === editandoId ? atualizada : item));
				showToast('Novidade atualizada');
			}
			editandoId = null;
		} catch (error) {
			showToast(errorMessage(error instanceof ApiError ? error.code : 'GENERIC_ERROR'));
		} finally {
			salvando = false;
		}
	}

	// Despublicar tira do ar para TODOS os usuarios dali em diante: e acao de impacto,
	// entao confirma antes, igual a exclusao. Publicar de novo nao confirma - repor algo
	// no ar e reversivel em um toque e o proprio estado da lista mostra o resultado.
	async function alternarPublicacao(item: AdminNews): Promise<void> {
		const novoEstado = !item.published;
		if (!novoEstado && confirmandoDespublicar !== item.id) {
			confirmandoDespublicar = item.id;
			return;
		}
		confirmandoDespublicar = null;
		const { id, created_at, read_count, ...resto } = item;
		try {
			const atualizada = await api.updateNews(id, { ...resto, published: novoEstado });
			novidades = novidades.map((linha) => (linha.id === id ? atualizada : linha));
			showToast(novoEstado ? 'Novidade publicada' : 'Novidade tirada do ar');
		} catch (error) {
			showToast(errorMessage(error instanceof ApiError ? error.code : 'GENERIC_ERROR'));
		}
	}

	async function excluir(item: AdminNews): Promise<void> {
		try {
			await api.deleteNews(item.id);
			novidades = novidades.filter((linha) => linha.id !== item.id);
			confirmandoExclusao = null;
			showToast('Novidade excluida');
		} catch (error) {
			showToast(errorMessage(error instanceof ApiError ? error.code : 'GENERIC_ERROR'));
		}
	}
</script>

<article class="card">
	<div class="card-head" style="flex-wrap:wrap;gap:10px">
		<div>
			<p class="eyebrow">Novidades</p>
			<h2 class="card-title">O que os usuarios veem no app</h2>
		</div>
		<div class="card-head-tools">
			<button class="btn btn-sm btn-accent" onclick={abrirNova}>Nova novidade</button>
		</div>
	</div>

	<p class="card-note">
		Escreva uma novidade quando a resposta a "isso muda o que o app diz para a pessoa fazer?"
		for sim. As marcadas como <b>importante</b> abrem uma modal uma unica vez; as normais so
		aparecem no sino.
	</p>

	{#if editandoId !== null}
		<div class="editor">
			<div class="editor-row">
				<label class="field">
					<span class="field-label">Data</span>
					<input type="date" bind:value={rascunho.published_on} />
				</label>
				<label class="field">
					<span class="field-label">Importancia</span>
					<select bind:value={rascunho.importance}>
						<option value="normal">Normal (so o sino)</option>
						<option value="important">Importante (abre modal)</option>
					</select>
				</label>
				<label class="check">
					<input type="checkbox" bind:checked={rascunho.published} />
					Publicada
				</label>
			</div>

			<div class="segmented">
				{#each IDIOMAS as idioma (idioma.chave)}
					<button
						class="seg-btn"
						aria-pressed={abaIdioma === idioma.chave}
						onclick={() => (abaIdioma = idioma.chave)}
					>
						{idioma.rotulo}
						{#if !rascunho[idioma.titulo].trim() || !rascunho[idioma.corpo].trim()}
							<span class="seg-dot" title="Faltando">•</span>
						{/if}
					</button>
				{/each}
			</div>

			{#each IDIOMAS as idioma (idioma.chave)}
				{#if abaIdioma === idioma.chave}
					<input
						class="text-input"
						placeholder="Titulo em {idioma.rotulo}"
						maxlength="120"
						bind:value={rascunho[idioma.titulo]}
					/>
					<textarea
						class="text-input"
						rows="5"
						placeholder="Texto em {idioma.rotulo}"
						maxlength="4000"
						bind:value={rascunho[idioma.corpo]}
					></textarea>
				{/if}
			{/each}

			<!-- Previa: voce vai escrever isso as 23h e nao vai querer descobrir o erro
			     depois de publicado. -->
			<div class="preview">
				<p class="preview-label">Como aparece no app</p>
				<p class="preview-date">
					{shortDate(rascunho.published_on)}
					{#if rascunho.importance === 'important'}<span class="preview-tag">Importante</span>{/if}
				</p>
				<p class="preview-title">{rascunho[IDIOMAS[0].titulo] || 'Titulo da novidade'}</p>
				<p class="preview-body">{rascunho[IDIOMAS[0].corpo] || 'Texto da novidade.'}</p>
			</div>

			<div class="actions">
				{#if camposFaltando.length > 0}
					<p class="missing">Faltando: {camposFaltando.join(', ')}</p>
				{/if}
				<button class="btn btn-sm btn-ghost" onclick={fechar}>Cancelar</button>
				<button
					class="btn btn-sm btn-accent"
					disabled={salvando || camposFaltando.length > 0}
					onclick={salvar}
				>
					{editandoId === 0 ? 'Criar' : 'Salvar'}
				</button>
			</div>
		</div>
	{/if}

	<div class="card-body">
		{#if carregando}
			<p class="empty">Carregando...</p>
		{:else if novidades.length === 0}
			<p class="empty">Nenhuma novidade ainda.</p>
		{:else}
			<ul>
				{#each novidades as item (item.id)}
					<li class="news-row">
						<div class="news-main">
							<p class="news-meta mono">
								{shortDate(item.published_on)}
								<span class="chip">{item.importance === 'important' ? 'Importante' : 'Normal'}</span>
								<span class="chip">{item.published ? 'No ar' : 'Fora do ar'}</span>
								<span class="chip">{item.read_count} leram</span>
							</p>
							<p class="news-title">{item.title_pt_br}</p>
							<p class="news-body">{item.body_pt_br}</p>
						</div>
						<div class="actions">
							<button class="btn btn-sm btn-ghost" onclick={() => abrirEdicao(item)}>Editar</button>
							<button class="btn btn-sm" onclick={() => alternarPublicacao(item)}>
								{item.published ? 'Tirar do ar' : 'Publicar'}
							</button>
							<button class="btn btn-sm btn-danger" onclick={() => (confirmandoExclusao = item.id)}>
								Excluir
							</button>
						</div>

						{#if confirmandoDespublicar === item.id}
							<div class="confirm">
								<p>Tirar do ar? Os usuarios deixam de ver esta novidade.</p>
								<div class="actions">
									<button class="btn btn-sm btn-ghost" onclick={() => (confirmandoDespublicar = null)}>
										Cancelar
									</button>
									<button class="btn btn-sm" onclick={() => alternarPublicacao(item)}>Confirmar</button>
								</div>
							</div>
						{/if}

						{#if confirmandoExclusao === item.id}
							<div class="confirm">
								<p>Excluir para sempre? Some tambem o registro de quem ja leu.</p>
								<div class="actions">
									<button class="btn btn-sm btn-ghost" onclick={() => (confirmandoExclusao = null)}>
										Cancelar
									</button>
									<button class="btn btn-sm btn-danger" onclick={() => excluir(item)}>Confirmar</button>
								</div>
							</div>
						{/if}
					</li>
				{/each}
			</ul>
		{/if}
	</div>
</article>

<style>
	.editor {
		display: flex;
		flex-direction: column;
		gap: 10px;
		padding: 14px 18px;
		border-bottom: 1px solid var(--hairline);
	}
	.editor-row {
		display: flex;
		flex-wrap: wrap;
		gap: 8px;
		align-items: center;
	}
	.field-label {
		font-size: 11.5px;
		color: var(--ink-3);
	}
	.check {
		display: inline-flex;
		align-items: center;
		gap: 7px;
		font-size: 13px;
		color: var(--ink-2);
	}
	.seg-btn {
		display: inline-flex;
		align-items: center;
		gap: 5px;
	}
	.seg-dot {
		color: var(--warning);
		font-size: 16px;
		line-height: 1;
	}
	.text-input {
		width: 100%;
		padding: 9px 11px;
		border-radius: var(--radius-sm);
		border: 1px solid var(--hairline-2);
		background: var(--surface);
		color: var(--ink);
		font-size: 13.5px;
		resize: vertical;
	}
	.text-input:focus {
		outline: none;
		border-color: var(--accent);
		box-shadow: 0 0 0 3px var(--accent-glow);
	}
	.preview {
		border: 1px dashed var(--hairline-2);
		border-radius: var(--radius-md);
		padding: 12px 14px;
	}
	.preview-label {
		font-size: 10.5px;
		letter-spacing: 0.08em;
		text-transform: uppercase;
		color: var(--ink-3);
		margin-bottom: 6px;
	}
	.preview-date {
		font-size: 11.5px;
		color: var(--ink-3);
		text-transform: uppercase;
	}
	.preview-tag {
		margin-left: 6px;
		color: var(--accent);
		font-weight: 700;
	}
	.preview-title {
		font-weight: 700;
		margin-top: 2px;
	}
	.preview-body {
		font-size: 13px;
		color: var(--ink-2);
		white-space: pre-line;
		margin-top: 3px;
	}
	.missing {
		flex: 1 1 200px;
		font-size: 12.5px;
		color: var(--warning);
	}
	.news-row {
		display: flex;
		flex-wrap: wrap;
		gap: 10px;
		align-items: flex-start;
		padding: 14px 18px;
		border-bottom: 1px solid var(--hairline);
	}
	.news-main {
		flex: 1 1 320px;
		min-width: 0;
	}
	.news-meta {
		display: flex;
		flex-wrap: wrap;
		gap: 6px;
		align-items: center;
		font-size: 11.5px;
		color: var(--ink-3);
	}
	.news-title {
		font-weight: 700;
		margin-top: 4px;
	}
	.news-body {
		font-size: 13px;
		color: var(--ink-2);
		margin-top: 2px;
		display: -webkit-box;
		-webkit-line-clamp: 2;
		line-clamp: 2;
		-webkit-box-orient: vertical;
		overflow: hidden;
	}
	.confirm {
		flex: 1 1 100%;
	}
</style>
