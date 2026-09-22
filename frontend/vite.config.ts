import { paraglideVitePlugin } from '@inlang/paraglide-js';
import tailwindcss from '@tailwindcss/vite';
import adapter from '@sveltejs/adapter-static';
import { sveltekit } from '@sveltejs/kit/vite';
import { defineConfig } from 'vite';

// O backend sobe em 8765 por padrao; o start.sh usa outra porta se ela estiver
// ocupada e avisa pela mesma variavel que o cliente ja conhece.
const ALVO_API = process.env.VITE_API_PROXY ?? 'http://localhost:8765';

const PROXY_API = {
	'/api': {
		target: ALVO_API,
		changeOrigin: true,
		rewrite: (caminho: string) => caminho.replace(/^\/api/, '')
	}
};

export default defineConfig({
	plugins: [
		tailwindcss(),
		sveltekit({
			compilerOptions: {
				// Force runes mode for the project, except for libraries. Can be removed in svelte 6.
				runes: ({ filename }) => filename.split(/[/\\]/).includes('node_modules') ? undefined : true
			},

			// SPA estática: obrigatório para o empacotamento futuro com Capacitor.
			adapter: adapter({ fallback: 'index.html' })
		}),
		paraglideVitePlugin({
			project: './project.inlang',
			outdir: './src/lib/paraglide',
			strategy: ['localStorage', 'preferredLanguage', 'baseLocale']
		})
	],
	// Teste em HTTPS (camera e service worker exigem contexto seguro, que o IP da
	// rede em http nao da). Com um tunel apontando para o vite, a API passa por
	// /api no MESMO endereco: mesma origem, entao nao ha CORS envolvido.
	// Ver start-https.sh.
	server: { allowedHosts: true, proxy: PROXY_API },
	preview: { allowedHosts: true, proxy: PROXY_API }
});
