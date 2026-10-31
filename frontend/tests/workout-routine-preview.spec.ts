import { expect, test, type Page } from '@playwright/test';

const exercise = {
	id: 901,
	slug: 'supino-com-halteres',
	name: 'Supino com halteres',
	muscle_group: 'chest',
	muscle_region: null,
	equipment: 'dumbbell',
	kind: 'strength',
	level: 'beginner',
	media_urls: [],
	is_custom: false
};

const generationPreview = {
	routines: [
		{
			name: 'Treino A',
			items: [
				{
					slot_id: 'd0s0',
					exercise,
					target_sets: 3,
					target_reps: 10,
					target_weight_kg: null,
					target_duration_min: null,
					rest_seconds: 90
				}
			]
		},
		{
			name: 'Treino B',
			items: [
				{
					slot_id: 'd1s0',
					exercise: { ...exercise, id: 902, slug: 'crucifixo-halteres', name: 'Crucifixo com halteres' },
					target_sets: 3,
					target_reps: 12,
					target_weight_kg: null,
					target_duration_min: null,
					rest_seconds: 90
				}
			]
		}
	],
	omitted_slots: 0
};

type AppliedPlanRequest = {
	operation_key: string;
	destination?: 'append' | 'replace';
	expected_active_ids?: number[];
	routines: Array<{ name: string; items: Array<{ exercise_id: number }> }>;
	generation?: { frequency: number; level: string; equipment_mode: string };
};

async function setupRoutinePreview(
	page: Page,
	previewGate?: Promise<void>,
	loseFirstApplyResponse = false,
	initialRoutines: unknown[] = []
): Promise<{
	previewRequests: unknown[];
	applyRequests: AppliedPlanRequest[];
}> {
	const previewRequests: unknown[] = [];
	const applyRequests: AppliedPlanRequest[] = [];
	let routines: unknown[] = initialRoutines;
	await page.addInitScript(() => {
		localStorage.setItem('gymapp.access', 'workout-routine-preview-test');
		localStorage.setItem('PARAGLIDE_LOCALE', 'pt-br');
	});
	await page.route('http://127.0.0.1:18999/**', async (route) => {
		const request = route.request();
		const url = new URL(request.url());
		const path = url.pathname;
		if (path === '/me') return route.fulfill({ json: { id: 1, locale: 'pt-BR', has_profile: true, plan: 'free', is_admin: false } });
		if (path === '/me/news') return route.fulfill({ json: { items: [], unread_count: 0, pending_important: null } });
		if (path === '/me/routines' && request.method() === 'GET') return route.fulfill({ json: routines });
		if (path === '/me/routines/preview' && request.method() === 'POST') {
			previewRequests.push(request.postDataJSON());
			if (previewGate) await previewGate;
			return route.fulfill({ json: generationPreview });
		}
		if (path === '/exercises') {
			return route.fulfill({
				json: [{
					...exercise,
					id: 903,
					slug: 'voador-maquina',
					name: 'Voador máquina',
					equipment: 'machine'
				}]
			});
		}
		if (path === '/me/routines/apply' && request.method() === 'POST') {
			const payload = request.postDataJSON() as AppliedPlanRequest;
			applyRequests.push(payload);
			if (loseFirstApplyResponse && applyRequests.length === 1) {
				return route.abort();
			}
			routines = payload.routines.map((routine: { name: string; items: Array<Record<string, unknown>> }, index: number) => ({
				id: 10 + index,
				name: routine.name,
				position: index,
				archived_at: null,
				revision: `revision-${10 + index}`,
				items: routine.items.map((item, itemIndex) => ({
					...item,
					id: 100 + itemIndex,
					exercise: item.exercise_id === exercise.id ? exercise : generationPreview.routines[1].items[0].exercise,
					position: itemIndex,
					last_weight_kg: null
				}))
			}));
			return route.fulfill({ json: { routines, archived_ids: [] } });
		}
		if (path === '/me/sessions' || path === '/me/sessions/active' || path.endsWith('/periodization') || path.endsWith('/activity-days') || path.includes('/activities')) {
			return route.fulfill({ json: path.endsWith('/active') ? null : [] });
		}
		return route.fulfill({ json: [] });
	});
	return { previewRequests, applyRequests };
}

function contrastRatio(foreground: string, background: string): number {
	const luminance = (color: string) => {
		const channels = color.match(/[\d.]+/g)?.slice(0, 3).map(Number) ?? [];
		const linear = channels.map((channel) => {
			const value = channel / 255;
			return value <= 0.04045 ? value / 12.92 : ((value + 0.055) / 1.055) ** 2.4;
		});
		return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2];
	};
	const values = [luminance(foreground), luminance(background)].sort((a, b) => b - a);
	return (values[0] + 0.05) / (values[1] + 0.05);
}

test('shows an editable preview and applies only after explicit confirmation', async ({ page }) => {
	const requests = await setupRoutinePreview(page);
	await page.goto('/treino');
	await expect(page.getByText('Monte seu primeiro treino')).toBeVisible();
	await page.getByRole('button', { name: 'Intermediário' }).click();
	await page.getByRole('button', { name: 'Misto' }).click();
	await page.getByRole('button', { name: '2×' }).click();
	await expect(page.getByText('Revise seu novo ciclo')).toBeVisible();
	expect(requests.previewRequests).toHaveLength(1);
	expect(requests.previewRequests[0]).toMatchObject({ frequency: 2, level: 'intermediate', equipment_mode: 'mixed' });
	expect(requests.applyRequests).toHaveLength(0);

	const names = page.getByLabel('Nome do treino');
	await names.nth(0).fill('Superior A');
	const targetInputs = page.locator('input[inputmode="decimal"]');
	await targetInputs.nth(1).fill('11');
	await targetInputs.nth(1).press('Tab');
	await page.getByRole('button', { name: 'Confirmar ciclo' }).click();
	await expect.poll(() => requests.applyRequests.length).toBe(1);
	expect(requests.applyRequests[0]).toMatchObject({
		destination: 'replace',
		routines: [
			{ name: 'Superior A', items: [{ exercise_id: 901, slot_id: 'd0s0', target_sets: 3, target_reps: 11 }] },
			{ name: 'Treino B', items: [{ exercise_id: 902, slot_id: 'd1s0', target_sets: 3, target_reps: 12 }] }
		],
		generation: { frequency: 2, level: 'intermediate', equipment_mode: 'mixed' },
		expected_active_ids: []
	});
});

test('locks generation preferences and keeps preview open when replacing an exercise', async ({ page }) => {
	let releasePreview!: () => void;
	const previewGate = new Promise<void>((resolve) => {
		releasePreview = resolve;
	});
	const requests = await setupRoutinePreview(page, previewGate);
	await page.goto('/treino');
	await page.getByRole('button', { name: 'Intermediário' }).click();
	await page.getByRole('button', { name: 'Misto' }).click();
	await page.getByRole('button', { name: '2×' }).click();
	await expect(page.getByRole('button', { name: 'Iniciante' })).toBeDisabled();
	await expect(page.getByRole('button', { name: 'Máquinas' })).toBeDisabled();
	expect(requests.previewRequests[0]).toMatchObject({ level: 'intermediate', equipment_mode: 'mixed' });

	releasePreview();
	await expect(page.getByText('Revise seu novo ciclo')).toBeVisible();
	await page.getByRole('button', { name: 'Trocar' }).first().click();
	await expect(page.getByText('Voador máquina')).toBeVisible();
	await page.goBack();
	await expect(page.getByRole('textbox', { name: 'Buscar exercício…' })).toBeHidden();
	await expect(page.getByText('Revise seu novo ciclo')).toBeVisible();
	await page.getByRole('button', { name: 'Trocar' }).first().click();
	await expect(page.getByText('Voador máquina')).toBeVisible();
	await page.getByRole('button', { name: '+' }).last().click();
	await expect(page.getByText('Revise seu novo ciclo')).toBeVisible();
	await page.getByRole('button', { name: 'Confirmar ciclo' }).click();
	await expect.poll(() => requests.applyRequests.length).toBe(1);
	expect(requests.applyRequests[0]).toMatchObject({
		generation: { frequency: 2, level: 'intermediate', equipment_mode: 'mixed' }
	});
	expect(requests.applyRequests[0].routines[0].items[0].exercise_id).toBe(903);
});

for (const destination of ['Adicionar aos atuais', 'Substituir os atuais']) {
	test(`keeps the review modal open for an existing cycle when choosing ${destination}`, async ({ page }) => {
		const requests = await setupRoutinePreview(page, undefined, false, [{
			id: 5,
			name: 'Ciclo atual',
			position: 0,
			archived_at: null,
			revision: 'revision-existing',
			items: []
		}]);
		await page.goto('/treino');
		await page.getByRole('button', { name: 'Novo treino' }).click();
		await page.getByRole('button', { name: 'Começar rápido' }).click();
		await page.getByRole('button', { name: '2× dias/semana' }).click();
		await expect(page.getByText('Revise seu novo ciclo')).toBeVisible();
		await page.getByRole('button', { name: 'Trocar' }).first().click();
		await expect(page.getByRole('textbox', { name: 'Buscar exercício…' })).toBeVisible();
		await page.goBack();
		await expect(page.getByRole('textbox', { name: 'Buscar exercício…' })).toBeHidden();
		await expect(page.getByText('Revise seu novo ciclo')).toBeVisible();

		await page.getByRole('button', { name: destination }).click();
		await page.getByRole('button', { name: 'Confirmar ciclo' }).click();
		await expect.poll(() => requests.applyRequests.length).toBe(1);
		expect(requests.applyRequests[0].destination).toBe(
			destination === 'Adicionar aos atuais' ? 'append' : 'replace'
		);
		expect(requests.applyRequests[0].expected_active_ids).toEqual(
			destination === 'Adicionar aos atuais' ? [] : [5]
		);
	});
}

test('retries the same template operation after a lost response and unlocks navigation on success', async ({ page }) => {
	const requests = await setupRoutinePreview(page, undefined, true);
	await page.goto('/treino');
	await page.getByRole('button', { name: '2×' }).click();
	await expect(page.getByText('Revise seu novo ciclo')).toBeVisible();
	await page.getByRole('button', { name: 'Confirmar ciclo' }).click();
	await expect(page.getByRole('button', { name: 'Verificar resultado' })).toBeVisible();
	expect(requests.applyRequests).toHaveLength(1);

	await page.getByRole('button', { name: 'Verificar resultado' }).click();
	await expect(page.getByText('Revise seu novo ciclo')).toBeHidden();
	expect(requests.applyRequests).toHaveLength(2);
	expect(requests.applyRequests[1].operation_key).toBe(requests.applyRequests[0].operation_key);
	await page.getByRole('link', { name: 'Catálogo' }).click();
	await expect(page).toHaveURL(/\/treino\/catalogo/);
});

for (const theme of ['light', 'dark'] as const) {
	test(`workout action buttons keep readable contrast in ${theme} theme`, async ({ page }) => {
		await setupRoutinePreview(page);
		await page.goto('/treino');
		await page.getByRole('button', { name: '2×' }).click();
		await expect(page.getByText('Revise seu novo ciclo')).toBeVisible();
		await page.evaluate((selectedTheme) => {
			document.documentElement.classList.toggle('dark', selectedTheme === 'dark');
		}, theme);
		const renderedColors = await page.locator('.workout-action:not(:disabled)').evaluateAll((elements) =>
			elements.map((element) => {
				const styles = getComputedStyle(element);
				return { foreground: styles.color, background: styles.backgroundColor };
			})
		);
		expect(renderedColors.length).toBeGreaterThan(0);
		for (const colors of renderedColors) {
			expect(contrastRatio(colors.foreground, colors.background)).toBeGreaterThanOrEqual(4.5);
		}
	});
}
