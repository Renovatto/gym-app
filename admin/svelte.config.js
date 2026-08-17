import adapter from '@sveltejs/adapter-static';

/** @type {import('@sveltejs/kit').Config} */
export default {
	compilerOptions: {
		// Runes obrigatorias, como no app: $state/$derived/$effect, nunca stores.
		runes: true
	},
	kit: {
		// SPA estatica servida pelo nginx; o fallback faz qualquer rota cair no
		// index.html e o roteamento acontecer no navegador.
		adapter: adapter({ fallback: 'index.html' }),
		// O painel vive em /admin do mesmo dominio da API (decisao de deploy):
		// sem CORS novo e sem certificado novo.
		paths: { base: '/admin' }
	}
};
