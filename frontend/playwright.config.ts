import { defineConfig } from '@playwright/test';

export default defineConfig({
	testDir: './tests',
	fullyParallel: true,
	use: {
		baseURL: 'http://127.0.0.1:5189',
		viewport: { width: 390, height: 844 },
		locale: 'pt-BR',
		trace: 'retain-on-failure'
	},
	webServer: {
		command: 'npm run dev -- --host 127.0.0.1 --port 5189 --strictPort',
		url: 'http://127.0.0.1:5189',
		env: { VITE_API_PORT: '18999' }
	}
});
