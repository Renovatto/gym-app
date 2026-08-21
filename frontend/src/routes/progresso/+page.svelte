<script lang="ts">
	import {
		api,
		localDay,
		type AchievementsResult,
		type AdaptiveTdee,
		type BodyComposition,
		type BodyCompositionPanel,
		type BodyFatBand,
		type BodyCompSource,
		type TapeMeasurements,
		type DietAdherence,
		type WeekSummary,
		type WeighInInput,
		type WeightHistory,
		type WeightLog
	} from '$lib/api';
	import Stepper from '$lib/components/Stepper.svelte';
	import WeightChart from '$lib/components/WeightChart.svelte';
	import BodyMetricIcon from '$lib/components/BodyMetricIcon.svelte';
	import { onMount } from 'svelte';
	import { page } from '$app/state';
	import { bootstrap, session } from '$lib/session.svelte';
	import { showToast } from '$lib/toast.svelte';
	import { triggerAchievementCelebrations } from '$lib/celebrationTrigger';
	import SkeletonScreen from '$lib/components/SkeletonScreen.svelte';
	import { m } from '$lib/paraglide/messages';
	import { getLocale } from '$lib/paraglide/runtime';
	import { isShowingAnchor } from '$lib/tour.svelte';

	let history = $state<WeightHistory | null>(null);

	// --- Composicao corporal -------------------------------------------------
	// O texto do IMC ja avisa que ele "nao avalia a composicao corporal". Este painel
	// e o que cumpre essa promessa, usando o dado que a balanca ja grava.
	let bodyPanel = $state<BodyCompositionPanel | null>(null);
	// O painel so faz sentido com uma medicao de gordura. Este derived resolve a
	// condicao uma vez e ja entrega a porcentagem como numero, para o resto da tela
	// nao repetir a verificacao a cada uso.
	const bodyReading = $derived(
		bodyPanel && bodyPanel.fat_percentage !== null
			? { ...bodyPanel, fat_percentage: bodyPanel.fat_percentage }
			: null
	);

	// Faixas de referencia (ACE) espelhando backend/app/services/body_composition.py -
	// usadas so para montar o exemplo abaixo, sem chamar a API.
	const DEMO_BANDS_MALE: BodyFatBand[] = [
		{ key: 'essential', from_pct: 2, to_pct: 6 },
		{ key: 'athlete', from_pct: 6, to_pct: 14 },
		{ key: 'fitness', from_pct: 14, to_pct: 18 },
		{ key: 'acceptable', from_pct: 18, to_pct: 25 },
		{ key: 'high', from_pct: 25, to_pct: 40 }
	];
	const DEMO_BANDS_FEMALE: BodyFatBand[] = [
		{ key: 'essential', from_pct: 10, to_pct: 14 },
		{ key: 'athlete', from_pct: 14, to_pct: 21 },
		{ key: 'fitness', from_pct: 21, to_pct: 25 },
		{ key: 'acceptable', from_pct: 25, to_pct: 32 },
		{ key: 'high', from_pct: 32, to_pct: 45 }
	];

	// Exemplo de composicao corporal, usado so durante o passo do tutorial que
	// aponta para "Composicao corporal" - quando a conta e nova e nunca recebeu
	// uma pesagem com bioimpedancia, mostra a tela de verdade preenchida com uma
	// leitura tipica (faixa "aceitavel"), em vez de ficar vazia.
	function demoBodyPanel(): BodyCompositionPanel & { fat_percentage: number } {
		const female = session.profile?.sex === 'female';
		const weight = session.profile?.weight_kg ?? 78;
		const fat = female ? 27 : 19.5;
		const fatMass = Math.round(weight * (fat / 100) * 10) / 10;
		return {
			measured_at: new Date().toISOString(),
			weight_kg: weight,
			fat_percentage: fat,
			fat_mass_kg: fatMass,
			lean_mass_kg: Math.round((weight - fatMass) * 10) / 10,
			visceral_fat_index: female ? 6 : 8,
			water_percentage: female ? 52 : 58,
			bands: female ? DEMO_BANDS_FEMALE : DEMO_BANDS_MALE,
			band_key: 'acceptable',
			gauge_min: female ? 12 : 5,
			gauge_max: female ? 42 : 35,
			trend_days: null,
			fat_percentage_delta: null,
			lean_mass_delta_kg: null,
			target_fat_percentage: null,
			target_weight_min_kg: null,
			target_weight_max_kg: null,
			fat_source: 'scale',
			fat_percentage_scale: fat,
			fat_percentage_tape: null,
			source_preference: 'auto',
			waist_cm: null,
			neck_cm: null,
			hip_cm: null,
			arm_cm: null,
			thigh_cm: null,
			chest_cm: null,
			waist_risk: null,
			waist_risk_increased_cm: null,
			waist_risk_high_cm: null,
			waist_delta_cm: null,
			arm_delta_cm: null,
			thigh_delta_cm: null
		};
	}
	const displayBodyReading = $derived(
		bodyReading === null && isShowingAnchor('progress-body') ? demoBodyPanel() : bodyReading
	);
	// Tons da faixa de risco da cintura. Verde nao e "parabens", e "dentro da faixa":
	// a mensagem ao lado e que dá o sentido, a cor so orienta o olho.
	const WAIST_RISK_TONES: Record<string, string> = {
		ok: 'bg-emerald-50 text-emerald-800',
		increased: 'bg-amber-50 text-amber-800',
		high: 'bg-red-50 text-red-800'
	};

	function waistRiskLabel(risk: string): string {
		return (
			{ ok: m.waist_risk_ok(), increased: m.waist_risk_increased(), high: m.waist_risk_high() }[
				risk
			] ?? risk
		);
	}

	let savingSource = $state(false);

	// Fixar a fonte tambem serve para nao trocar de metodo no meio da serie: a
	// tendencia compara sempre a mesma fonte nas duas pontas.
	async function chooseSource(source: BodyCompSource): Promise<void> {
		savingSource = true;
		try {
			bodyPanel = await api.setBodyCompSource(source);
			showToast(source === 'auto' ? m.source_auto_saved() : m.source_saved());
		} finally {
			savingSource = false;
		}
	}

	let showTargetPicker = $state(false);
	let targetPct = $state(18);
	let savingTarget = $state(false);
	// Explicacao do que a calculadora e (e principalmente do que ela NAO faz): sem
	// isso e natural supor que escolher um alvo passa a mexer na meta de calorias.
	let showTargetHelp = $state(false);

	const BAND_BAR_COLORS: Record<string, string> = {
		essential: 'bg-slate-300',
		athlete: 'bg-sky-400',
		fitness: 'bg-emerald-400',
		acceptable: 'bg-blue-400',
		high: 'bg-amber-400'
	};
	// Mesma linguagem da barra de IMC da tela inicial: o marcador e uma bolinha
	// branca com anel colorido e uma carinha dentro. "Aceitavel" fica com a cara
	// neutra de proposito - e a faixa media da referencia, nao um problema.
	const BAND_EMOJI: Record<string, string> = {
		essential: '🙁',
		athlete: '🤩',
		fitness: '😃',
		acceptable: '🙂',
		high: '😕'
	};
	const BAND_RING_COLORS: Record<string, string> = {
		essential: 'border-slate-400',
		athlete: 'border-sky-400',
		fitness: 'border-emerald-400',
		acceptable: 'border-blue-400',
		high: 'border-amber-400'
	};
	const BAND_PILL_COLORS: Record<string, string> = {
		essential: 'bg-slate-100 text-slate-600',
		athlete: 'bg-sky-100 text-sky-700',
		fitness: 'bg-emerald-100 text-emerald-700',
		acceptable: 'bg-blue-100 text-blue-700',
		high: 'bg-amber-100 text-amber-700'
	};
	const BAND_TEXT_COLORS: Record<string, string> = {
		essential: 'text-slate-600',
		athlete: 'text-sky-700',
		fitness: 'text-emerald-700',
		acceptable: 'text-blue-700',
		high: 'text-amber-700'
	};

	function bandLabel(key: string): string {
		return (
			{
				essential: m.bc_band_essential(),
				athlete: m.bc_band_athlete(),
				fitness: m.bc_band_fitness(),
				acceptable: m.bc_band_acceptable(),
				high: m.bc_band_high()
			}[key] ?? key
		);
	}

	// Posicao de um valor na regua, em % da largura (recortado nos extremos dela).
	function gaugePosition(value: number, panel: BodyCompositionPanel): number {
		const span = panel.gauge_max - panel.gauge_min;
		if (span <= 0) return 0;
		return Math.max(0, Math.min(100, ((value - panel.gauge_min) / span) * 100));
	}

	// Largura de cada faixa na barra: a faixa e recortada nos limites da regua, senao
	// a gordura essencial (que fica fora) empurraria o resto para o lado.
	function bandWidth(band: { from_pct: number; to_pct: number }, panel: BodyCompositionPanel): number {
		const from = Math.max(band.from_pct, panel.gauge_min);
		const to = Math.min(band.to_pct, panel.gauge_max);
		if (to <= from) return 0;
		return ((to - from) / (panel.gauge_max - panel.gauge_min)) * 100;
	}

	// Intervalo escrito de cada faixa, para a legenda. A ultima e aberta ("25%+"):
	// nao existe teto de gordura corporal, o numero ali seria so o fim do desenho.
	function bandRange(band: BodyFatBand, panel: BodyCompositionPanel): string {
		const isLast = panel.bands[panel.bands.length - 1]?.key === band.key;
		if (isLast) return `${nf.format(band.from_pct)}%+`;
		return `${nf.format(band.from_pct)}–${nf.format(band.to_pct)}%`;
	}

	// Sinal explicito no numero: "+0,2" e "-0,2" leem melhor que "0,2" solto.
	function withSign(value: number): string {
		return value > 0 ? `+${nf.format(value)}` : nf.format(value);
	}

	// Em qual faixa cai a porcentagem escolhida no seletor (mesma regra do backend).
	function bandKeyAt(pct: number, panel: BodyCompositionPanel): string {
		for (const band of panel.bands) {
			if (pct < band.to_pct) return band.key;
		}
		return panel.bands[panel.bands.length - 1]?.key ?? 'acceptable';
	}

	// Previa do peso enquanto a pessoa arrasta o seletor. Espelha
	// services/body_composition.py (peso = magra / (1 - alvo), janela de +-1,5 ponto);
	// o valor que fica GRAVADO continua vindo do backend, no Calcular. Aqui e so para
	// a escolha ter consequencia visivel na hora, sem uma chamada por pixel arrastado.
	const targetPreview = $derived.by(() => {
		const lean = bodyReading?.lean_mass_kg;
		if (lean === null || lean === undefined) return null;
		const lightest = lean / (1 - Math.max(1, targetPct - 1.5) / 100);
		const heaviest = lean / (1 - Math.min(60, targetPct + 1.5) / 100);
		return { lightest: Math.round(lightest * 10) / 10, heaviest: Math.round(heaviest * 10) / 10 };
	});

	async function saveTarget(): Promise<void> {
		savingTarget = true;
		try {
			bodyPanel = await api.setBodyFatTarget(targetPct);
			showTargetPicker = false;
			showToast(m.bc_target_saved());
		} finally {
			savingTarget = false;
		}
	}

	async function clearTarget(): Promise<void> {
		savingTarget = true;
		try {
			bodyPanel = await api.setBodyFatTarget(null);
			showTargetPicker = false;
			showToast(m.bc_target_removed());
		} finally {
			savingTarget = false;
		}
	}
	let week = $state<WeekSummary | null>(null);
	let adaptive = $state<AdaptiveTdee | null>(null);
	let adherence = $state<DietAdherence | null>(null);
	let achievements = $state<AchievementsResult | null>(null);
	// Pontinho de "quase la": alguma conquista bloqueada com 80%+ de progresso.
	const hasCloseAchievement = $derived(
		achievements?.achievements.some((a) => !a.unlocked && a.progress_current / a.progress_goal >= 0.8) ?? false
	);
	let newWeight = $state(session.profile?.weight_kg ?? 75);
	let busy = $state(false);
	let adding = $state(false);

	// Campos opcionais da balanca de bioimpedancia. A ordem aqui e a ordem na tela.
	// O usuario le esses valores na propria balanca e digita; por isso sao inputs de
	// texto (mais rapido para valor exato) e nao steppers.
	const bodyCompositionInputs: {
		key: keyof BodyComposition;
		label: string;
		unit: string;
		icon: string;
	}[] = [
		{ key: 'fat_percentage', label: m.bc_fat_pct(), unit: '%', icon: 'fat' },
		{ key: 'fat_mass_kg', label: m.bc_fat_mass(), unit: 'kg', icon: 'fat' },
		{ key: 'visceral_fat_index', label: m.bc_visceral(), unit: '', icon: 'visceral' },
		{ key: 'muscle_percentage', label: m.bc_muscle_pct(), unit: '%', icon: 'muscle' },
		{ key: 'muscle_mass_kg', label: m.bc_muscle_mass(), unit: 'kg', icon: 'muscle' },
		{ key: 'skeletal_muscle_percentage', label: m.bc_skeletal_pct(), unit: '%', icon: 'skeletal' },
		{ key: 'skeletal_muscle_kg', label: m.bc_skeletal_mass(), unit: 'kg', icon: 'skeletal' },
		{ key: 'water_percentage', label: m.bc_water_pct(), unit: '%', icon: 'water' },
		{ key: 'water_mass_kg', label: m.bc_water_mass(), unit: 'kg', icon: 'water' },
		{ key: 'scale_bmr_kcal', label: m.bc_scale_bmr(), unit: 'kcal', icon: 'metabolism' }
	];
	// Medidas de fita metrica. Array PROPRIO, e nao no mesmo do outro: fita nao e
	// balanca, e misturar as duas sob o rotulo "dados da balanca" seria mentira.
	// Cintura, pescoco e quadril alimentam a estimativa de gordura; braco, coxa e
	// peito sao so acompanhamento (circunferencia de membro nao isola musculo).
	const tapeInputs: {
		key: keyof TapeMeasurements;
		label: string;
		hint: string;
		feedsFormula: boolean;
	}[] = [
		{ key: 'waist_cm', label: m.tape_waist(), hint: m.tape_waist_hint(), feedsFormula: true },
		{ key: 'neck_cm', label: m.tape_neck(), hint: m.tape_neck_hint(), feedsFormula: true },
		{ key: 'hip_cm', label: m.tape_hip(), hint: m.tape_hip_hint(), feedsFormula: true },
		{ key: 'arm_cm', label: m.tape_arm(), hint: m.tape_arm_hint(), feedsFormula: false },
		{ key: 'thigh_cm', label: m.tape_thigh(), hint: m.tape_thigh_hint(), feedsFormula: false },
		{ key: 'chest_cm', label: m.tape_chest(), hint: m.tape_chest_hint(), feedsFormula: false }
	];
	let tapeValues = $state<Record<string, string>>({});
	let showTapeFields = $state(false);

	// valor digitado (texto) de cada campo da balanca, indexado pela chave
	let scaleValues = $state<Record<string, string>>({});
	let showScaleFields = $state(false);
	// dia da pesagem de onde os campos foram pre-carregados (null = campos em branco)
	let prefilledFrom = $state<string | null>(null);

	/** Comeca os campos da balanca com a ultima medicao, para so mexer no que mudou.
	 *
	 * O usuario le os dez valores no visor da balanca e digita todos na mao a cada
	 * pesagem; entre uma e outra, a maioria repete ou muda na primeira decimal.
	 * O risco de pre-carregar e salvar sem querer um valor velho como se fosse de
	 * hoje - por isso a data de origem fica escrita na tela e a secao ja abre
	 * expandida: nada acontece escondido. */
	function prefillScaleValues(log: WeightLog | null): void {
		if (log === null) {
			scaleValues = {};
			prefilledFrom = null;
			return;
		}
		const filled: Record<string, string> = {};
		for (const field of bodyCompositionInputs) {
			const value = log[field.key];
			// String() de proposito, e nao nf.format(): o separador de milhar que o
			// formatador coloca (1.680) viraria 1,68 na hora de ler o numero de volta.
			if (value !== null && value !== undefined) filled[field.key] = String(value);
		}
		scaleValues = filled;

		// mesma ideia para a fita - e ali vale ainda mais: pescoco e quadril quase
		// nao mudam entre pesagens, e redigitar tudo afastaria a pessoa de medir
		const tapeFilled: Record<string, string> = {};
		for (const field of tapeInputs) {
			const value = log[field.key];
			if (value !== null && value !== undefined) tapeFilled[field.key] = String(value);
		}
		tapeValues = tapeFilled;
		if (Object.keys(tapeFilled).length > 0) showTapeFields = true;

		const anyFilled = Object.keys(filled).length > 0 || Object.keys(tapeFilled).length > 0;
		prefilledFrom = anyFilled ? log.logged_at : null;
		if (Object.keys(filled).length > 0) showScaleFields = true;
	}

	function clearScaleValues(): void {
		scaleValues = {};
		tapeValues = {};
		prefilledFrom = null;
	}

	// A semana do CALENDARIO, de segunda a domingo, cada dia sabendo se teve movimento.
	// Antes eram os ultimos 7 dias: numa segunda, a faixa comecava na terca anterior e
	// misturava a semana passada com a atual embaixo do titulo "Esta semana".
	// A inicial vem do proprio idioma (weekday: 'narrow'), entao nao ha lista de letras
	// escrita a mao para desencontrar da traducao.
	const weekDayInitial = new Intl.DateTimeFormat(getLocale(), { weekday: 'narrow' });
	const weekDays = $derived.by(() => {
		if (!week) return [];
		const active = new Set(week.active_dates);
		const today = new Date(localDay() + 'T12:00:00'); // meio-dia evita virada de fuso
		// getDay() e 0 no domingo; esta conta acha a segunda desta semana em qualquer dia
		const monday = new Date(today);
		monday.setDate(today.getDate() - ((today.getDay() + 6) % 7));
		const todayIso = localDay();
		return Array.from({ length: 7 }, (_, index) => {
			const dayDate = new Date(monday);
			dayDate.setDate(monday.getDate() + index);
			// montado a mao, e nao com toISOString(): aquele converte para UTC e pularia
			// um dia em fuso adiantado (meio-dia em UTC+13 ja e o dia anterior la)
			const iso = `${dayDate.getFullYear()}-${String(dayDate.getMonth() + 1).padStart(2, '0')}-${String(dayDate.getDate()).padStart(2, '0')}`;
			return {
				iso,
				initial: weekDayInitial.format(dayDate).toUpperCase(),
				active: active.has(iso),
				// dia que ainda nao chegou: numa segunda, seis dos sete sao futuro, e
				// pinta-los de "sem movimento" faria a semana parecer perdida no dia 1
				future: iso > todayIso
			};
		});
	});

	const dietOn = $derived(session.profile?.diet_enabled ?? false);
	const nf = new Intl.NumberFormat(getLocale());
	const df = new Intl.DateTimeFormat(getLocale(), { day: '2-digit', month: 'short' });

	async function load(): Promise<void> {
		const tzOffset = new Date().getTimezoneOffset();
		history = await api.getWeightHistory();
		if (history.current_kg !== null) newWeight = history.current_kg;
		// a ultima pesagem COM dados da balanca, nao a ultima em geral: quem registrou
		// so o peso ontem nao deve zerar os campos que ele preencheu na semana passada
		prefillScaleValues(history.latest_body_composition);
		bodyPanel = await api.getBodyComposition();
		if (bodyPanel.target_fat_percentage !== null) targetPct = bodyPanel.target_fat_percentage;
		week = await api.getWeekSummary(localDay(), tzOffset);
		achievements = await api.getAchievements(localDay(), tzOffset);
		// A conquista pode ter sido desbloqueada agora mesmo (newly_unlocked so vem
		// UMA vez, na 1a chamada apos o desbloqueio) - se essa tela for a primeira a
		// buscar, tem que celebrar aqui tambem, senao o sinal se perde pra sempre.
		triggerAchievementCelebrations(achievements);
		// TDEE adaptativo e aderencia so fazem sentido com o modulo de dieta ligado
		if (dietOn) {
			adaptive = await api.getAdaptiveTdee(localDay(), tzOffset);
			adherence = await api.getDietAdherence(localDay(), 7);
		}
	}

	// Mensagem do TDEE adaptativo: texto traduzido + tom (cor) conforme o ritmo real.
	const adaptiveMessage = $derived.by(() => {
		if (!adaptive || !adaptive.has_enough_data) return null;
		const byCode: Record<string, { text: string; tone: 'good' | 'warn' | 'info' }> = {
			ON_TRACK: { text: m.adaptive_on_track(), tone: 'good' },
			TOO_SLOW: { text: m.adaptive_too_slow(), tone: 'warn' },
			STALLED: { text: m.adaptive_stalled(), tone: 'warn' },
			// Os dois codigos abaixo bloqueiam adotar a meta (can_adopt=false), cada um
			// por uma ponta: TOO_FAST acusa a balanca (agua saindo), MEASURED_BELOW_BMR
			// acusa o diario (incompleto, gasto medido menor que o gasto em repouso).
			TOO_FAST: { text: m.adaptive_too_fast(), tone: 'warn' },
			MEASURED_BELOW_BMR: {
				text: m.adaptive_below_bmr({ bmr: nf.format(adaptive.bmr_kcal) }),
				tone: 'warn'
			},
			ESTIMATE_READY: { text: m.adaptive_estimate_ready(), tone: 'info' }
		};
		return byCode[adaptive.message_code] ?? byCode.ESTIMATE_READY;
	});

	// Por que a estimativa nao pode virar meta. Sao problemas diferentes e a acao que
	// resolve cada um tambem e: TOO_FAST pede tempo (esperar a agua sair),
	// MEASURED_BELOW_BMR pede diario completo.
	const cannotAdoptReason = $derived(
		adaptive?.message_code === 'MEASURED_BELOW_BMR'
			? m.adaptive_cannot_adopt_below_bmr()
			: m.adaptive_cannot_adopt()
	);

	// Meta atual ja bate com a sugerida -> a manutencao real ja foi adotada.
	const goalAlreadyAdopted = $derived(
		!!adaptive?.has_enough_data && adaptive.current_target_kcal === adaptive.suggested_target_kcal
	);
	let adoptingGoal = $state(false);
	let confirmingAdoptGoal = $state(false);

	// Adota a manutencao real medida: renova o periodo da dieta com ela como base,
	// substituindo a formula (mesma acao que existe em Dieta > Periodo da dieta).
	// Muda a meta calorica usada no app inteiro dai em diante, entao sempre confirma antes.
	async function adoptSuggestedGoal(): Promise<void> {
		if (!adaptive || adoptingGoal) return;
		confirmingAdoptGoal = false;
		adoptingGoal = true;
		try {
			await api.renewDietPeriod(localDay(), adaptive.estimated_maintenance_kcal ?? undefined);
			adaptive = await api.getAdaptiveTdee(localDay(), new Date().getTimezoneOffset());
			showToast(m.diet_period_renewed());
		} finally {
			adoptingGoal = false;
		}
	}

	// Monta o payload da pesagem: peso obrigatorio + campos da balanca preenchidos.
	// Campos vazios ou invalidos sao ignorados (ficam nulos no banco).
	function buildWeighIn(): WeighInInput {
		const weighIn: WeighInInput = { weight_kg: newWeight };
		for (const field of bodyCompositionInputs) {
			const raw = (scaleValues[field.key] ?? '').replace(',', '.').trim();
			if (raw === '') continue;
			const parsed = Number(raw);
			if (!Number.isNaN(parsed)) weighIn[field.key] = parsed;
		}
		for (const field of tapeInputs) {
			const raw = (tapeValues[field.key] ?? '').replace(',', '.').trim();
			if (raw === '') continue;
			const parsed = Number(raw);
			if (!Number.isNaN(parsed)) weighIn[field.key] = parsed;
		}
		return weighIn;
	}

	async function save(): Promise<void> {
		busy = true;
		try {
			await api.addWeight(buildWeighIn());
			showScaleFields = false;
			// load() repovoa os campos com a pesagem que acabou de ser salva
			await load();
			await bootstrap(); // metas dependem do peso mais recente
			adding = false;
			showToast(m.weigh_in_saved());
		} finally {
			busy = false;
		}
	}

	// Detalhes de uma pesagem (modal ao clicar no item do historico).
	let selectedLog = $state<WeightLog | null>(null);
	let confirmingDeleteWeight = $state(false);

	function openWeightDetail(log: WeightLog): void {
		selectedLog = log;
		confirmingDeleteWeight = false;
	}

	async function deleteSelectedWeight(): Promise<void> {
		if (!selectedLog) return;
		await api.deleteWeight(selectedLog.id);
		selectedLog = null;
		confirmingDeleteWeight = false;
		await load();
		await bootstrap();
		showToast(m.weigh_in_deleted());
	}

	$effect(() => {
		load();
	});

	// Vindo do atalho "Pesar" da tela inicial (/progresso?novo=1): ja abre o formulario.
	onMount(() => {
		if (page.url.searchParams.get('novo')) adding = true;
	});

	// Historico do mais recente para o mais antigo, com a variacao (peso e gordura)
	// em relacao a pesagem anterior.
	const reversedLogs = $derived.by(() => {
		if (!history) return [];
		const desc = [...history.logs].reverse();
		return desc.map((log, i) => {
			const previous = desc[i + 1]; // proxima na lista = anterior no tempo
			const delta = previous ? Math.round((log.weight_kg - previous.weight_kg) * 10) / 10 : null;
			const fatDelta =
				previous && log.fat_percentage !== null && previous.fat_percentage !== null
					? Math.round((log.fat_percentage - previous.fat_percentage) * 10) / 10
					: null;
			return { log, delta, fatDelta };
		});
	});

	// O historico cresce sem limite (uma linha por pesagem) e a tela ficava enorme.
	// Mostra as mais recentes e o resto so quando o usuario pedir - mesmo padrao do
	// historico de treino.
	const WEIGH_IN_PREVIEW = 10;
	let historyExpanded = $state(false);
	const visibleLogs = $derived(
		historyExpanded ? reversedLogs : reversedLogs.slice(0, WEIGH_IN_PREVIEW)
	);

	// Formata hora local (HH:MM) a partir do timestamp da pesagem.
	function formatClock(iso: string): string {
		return new Date(iso).toLocaleTimeString(getLocale(), { hour: '2-digit', minute: '2-digit' });
	}

	// Campos de composicao presentes na pesagem selecionada (para o modal de detalhes).
	const selectedBodyComposition = $derived.by(() => {
		if (!selectedLog) return [];
		return bodyCompositionInputs
			.map((field) => ({
				label: field.label,
				unit: field.unit,
				icon: field.icon,
				value: selectedLog![field.key]
			}))
			.filter((row) => row.value !== null && row.value !== undefined);
	});
</script>

<h1 class="mb-4 text-2xl font-bold">{m.tab_progress()}</h1>

{#if achievements}
	<a
		href="/conquistas"
		class="mb-4 flex items-center justify-between rounded-3xl bg-white p-4 shadow-sm active:bg-slate-50"
	>
		<div class="flex items-center gap-3">
			<span class="relative text-3xl">
				🔥
				{#if hasCloseAchievement}
					<span class="absolute -top-0.5 -right-0.5 h-2.5 w-2.5 rounded-full bg-emerald-500 ring-2 ring-white"></span>
				{/if}
			</span>
			<div>
				<p class="text-lg font-black text-slate-900">
					{achievements.weekly_streak}
					<span class="text-sm font-semibold text-slate-500">{m.weeks_streak()}</span>
				</p>
				<p class="text-xs text-slate-500">{hasCloseAchievement ? m.almost_there_label() + ' · ' : ''}{m.see_achievements()}</p>
			</div>
		</div>
		<svg viewBox="0 0 24 24" class="h-5 w-5 text-slate-300" fill="none" stroke="currentColor" stroke-width="2"><path d="M9 6l6 6-6 6" stroke-linecap="round" stroke-linejoin="round" /></svg>
	</a>
{/if}

{#if week}
	<section class="mb-4 rounded-3xl bg-white p-5 shadow-sm" data-tour="progress-week">
		<p class="mb-3 text-sm font-bold text-slate-400 uppercase">{m.this_week()}</p>

		<!-- Dias em movimento como numero principal: para quem nao e atleta, constancia
			 e o que prevê resultado, e funciona igual para musculacao, corrida e ioga.
			 Saiu daqui o "volume total" (repeticoes x peso), que dava zero para exercicio
			 de peso corporal e zero para cardio - uma semana de abdominal e corrida
			 aparecia como "0 kg". -->
		<div class="mb-3">
			<p class="text-4xl leading-none font-black tracking-tight text-slate-900">
				{week.active_days}<span class="text-lg font-bold text-slate-400">/7</span>
			</p>
			<p class="mt-1 text-xs font-bold text-slate-500">{m.active_days_label()}</p>
			<div class="mt-2 flex gap-1.5">
				{#each weekDays as weekDay (weekDay.iso)}
					<span
						class="grid h-8 flex-1 place-items-center rounded-lg text-[11px] font-black {weekDay.active
							? 'bg-emerald-500 text-white'
							: weekDay.future
								? 'border border-dashed border-slate-200 text-slate-300'
								: 'bg-slate-100 text-slate-400'}"
						title={weekDay.iso}
					>
						{weekDay.initial}
					</span>
				{/each}
			</div>
		</div>

		<div class="grid grid-cols-2 gap-3">
			<div class="rounded-2xl bg-slate-50 p-3">
				<p class="text-2xl font-black text-slate-900">{week.workouts}</p>
				<p class="text-xs font-semibold text-slate-500">{m.workouts_label()}</p>
				<!-- series como linha secundaria: interessa em treino de forca, mas nao a
					 ponto de ocupar um bloco inteiro -->
				{#if week.total_sets > 0}
					<p class="mt-0.5 text-[11px] font-semibold text-slate-400">
						{week.total_sets}
						{m.sets_label()}
					</p>
				{/if}
			</div>
			<div class="rounded-2xl bg-slate-50 p-3">
				<p class="text-2xl font-black text-slate-900">{week.activities}</p>
				<p class="text-xs font-semibold text-slate-500">{m.activities_label()}</p>
				{#if week.activities_kcal > 0}
					<p class="mt-0.5 text-[11px] font-semibold text-slate-400">
						{nf.format(week.activities_kcal)} kcal
					</p>
				{/if}
			</div>
			{#if dietOn}
				<div class="rounded-2xl bg-slate-50 p-3">
					<p class="text-2xl font-black text-slate-900">
						{week.days_logged_diet > 0 ? nf.format(week.avg_kcal) : '—'}
						{#if week.days_logged_diet > 0}<span class="text-sm font-medium text-slate-400"> kcal</span>{/if}
					</p>
					<p class="text-xs font-semibold text-slate-500">{m.avg_calories()}</p>
				</div>
			{/if}
			<div class="rounded-2xl bg-slate-50 p-3">
				<p class="text-2xl font-black text-slate-900">
					{week.days_with_water > 0 ? nf.format(week.avg_water_ml / 1000) : '—'}
					{#if week.days_with_water > 0}<span class="text-sm font-medium text-slate-400"> L</span>{/if}
				</p>
				<p class="text-xs font-semibold text-slate-500">{m.avg_water()}</p>
			</div>
		</div>
	</section>
{/if}

{#if dietOn && adherence && adherence.has_goal}
	<section class="mb-4 rounded-3xl bg-white p-5 shadow-sm">
		<p class="mb-3 text-sm font-bold text-slate-400 uppercase">{m.adherence_title()}</p>
		{#if adherence.logged_days === 0}
			<p class="text-sm text-slate-500">{m.adherence_no_data()}</p>
		{:else}
			<div class="grid grid-cols-2 gap-3">
				<div class="rounded-2xl bg-slate-50 p-3">
					<p class="text-2xl font-black text-slate-900">
						{adherence.kcal_pct}<span class="text-sm font-medium text-slate-400"> %</span>
					</p>
					<p class="text-xs font-semibold text-slate-500">{m.adherence_calories()}</p>
				</div>
				<div class="rounded-2xl bg-slate-50 p-3">
					<p class="text-2xl font-black text-slate-900">
						{adherence.protein_pct}<span class="text-sm font-medium text-slate-400"> %</span>
					</p>
					<p class="text-xs font-semibold text-slate-500">{m.protein()}</p>
				</div>
			</div>
			<p class="mt-2 text-xs text-slate-400">
				{m.adherence_days_logged({ logged: adherence.logged_days, window: adherence.window })}
			</p>
		{/if}
	</section>
{/if}

{#if dietOn && adaptive}
	<section class="mb-4 rounded-3xl bg-white p-5 shadow-sm" data-tour="progress-adaptive">
		<p class="mb-1 text-sm font-bold text-slate-400 uppercase">{m.adaptive_title()}</p>
		{#if !adaptive.has_enough_data}
			<p class="text-sm text-slate-500">{m.adaptive_need_data()}</p>
			<!-- Mostra o alvo de cada exigencia (atual/minimo): sem isso a pessoa nao
			     descobre qual das tres esta faltando. Verde = ja atingida. -->
			<p class="mt-2 flex flex-wrap gap-x-2 gap-y-1 text-xs text-slate-400">
				<span class="font-semibold">{m.adaptive_progress_label()}:</span>
				{#each [ { have: adaptive.days_logged, need: adaptive.min_days_logged, label: m.adaptive_days_logged() }, { have: adaptive.weigh_ins, need: adaptive.min_weigh_ins, label: m.adaptive_weigh_ins() }, { have: adaptive.span_days, need: adaptive.min_span_days, label: m.adaptive_days_span() } ] as req}
					<span class={req.have >= req.need ? 'font-semibold text-emerald-600' : ''}>
						{req.have}/{req.need} {req.label}
					</span>
				{/each}
			</p>
		{:else}
			<!-- manutencao real estimada vs estimativa da formula -->
			<div class="grid grid-cols-2 gap-3">
				<div class="rounded-2xl bg-slate-50 p-3">
					<p class="text-2xl font-black text-slate-900">
						{nf.format(adaptive.estimated_maintenance_kcal ?? 0)}<span class="text-sm font-medium text-slate-400"> kcal</span>
					</p>
					<p class="text-xs font-semibold text-slate-500">{m.adaptive_real_maintenance()}</p>
				</div>
				<div class="rounded-2xl bg-slate-50 p-3">
					<p class="text-2xl font-black text-slate-900">
						{adaptive.weekly_change_kg > 0 ? '+' : ''}{nf.format(adaptive.weekly_change_kg)}<span class="text-sm font-medium text-slate-400"> kg</span>
					</p>
					<p class="text-xs font-semibold text-slate-500">{m.adaptive_weekly_change()}</p>
				</div>
			</div>

			<!-- comparacao de metas: atual (formula) vs sugerida (dados reais) -->
			<div class="mt-3 flex items-center justify-between rounded-2xl border-2 border-slate-100 px-4 py-3">
				<div>
					<p class="text-xs font-semibold text-slate-400">{m.adaptive_current_target()}</p>
					<p class="text-lg font-bold text-slate-500">{nf.format(adaptive.current_target_kcal)}</p>
				</div>
				<svg viewBox="0 0 24 24" class="h-5 w-5 text-slate-300" fill="none" stroke="currentColor" stroke-width="2"><path d="M5 12h14M13 6l6 6-6 6" stroke-linecap="round" stroke-linejoin="round" /></svg>
				<div class="text-right">
					<p class="text-xs font-semibold text-emerald-600">{m.adaptive_suggested_target()}</p>
					<p class="text-lg font-black text-emerald-700">{nf.format(adaptive.suggested_target_kcal ?? 0)}</p>
				</div>
			</div>

			{#if adaptiveMessage}
				<div
					class="mt-3 rounded-2xl px-4 py-3 text-sm font-semibold
						{adaptiveMessage.tone === 'good'
						? 'bg-emerald-50 text-emerald-800'
						: adaptiveMessage.tone === 'warn'
							? 'bg-amber-50 text-amber-800'
							: 'bg-sky-50 text-sky-800'}"
				>
					{adaptiveMessage.text}
				</div>
			{/if}

			{#if goalAlreadyAdopted}
				<p class="mt-3 flex items-center gap-1.5 text-xs font-semibold text-emerald-600">
					<svg viewBox="0 0 24 24" class="h-4 w-4 shrink-0" fill="none" stroke="currentColor" stroke-width="2"><path d="M5 13l4 4L19 7" stroke-linecap="round" stroke-linejoin="round" /></svg>
					{m.adaptive_already_adopted()}
				</p>
			{:else if !adaptive.can_adopt}
				<!-- a manutencao medida continua visivel acima, mas nao pode virar meta -->
				<p class="mt-3 text-xs font-semibold text-amber-700">{cannotAdoptReason}</p>
			{:else if confirmingAdoptGoal}
				<div class="mt-3 flex items-center gap-2 rounded-2xl bg-emerald-50 p-2">
					<span class="min-w-0 flex-1 pl-2 text-xs font-semibold text-emerald-800">{m.adaptive_adopt_confirm()}</span>
					<button
						type="button"
						disabled={adoptingGoal}
						onclick={adoptSuggestedGoal}
						class="h-11 shrink-0 rounded-xl bg-emerald-600 px-4 text-sm font-bold text-white active:bg-emerald-700 disabled:opacity-50"
					>
						{m.confirm()}
					</button>
					<button
						type="button"
						onclick={() => (confirmingAdoptGoal = false)}
						class="h-11 shrink-0 rounded-xl px-3 text-sm font-semibold text-slate-500 active:bg-slate-100"
					>
						{m.cancel()}
					</button>
				</div>
			{:else}
				<button
					type="button"
					onclick={() => (confirmingAdoptGoal = true)}
					class="mt-3 h-12 w-full rounded-2xl bg-emerald-600 text-sm font-bold text-white active:bg-emerald-700"
				>
					{m.adaptive_adopt_button()}
				</button>
			{/if}

			<p class="mt-2 text-xs text-slate-400">{m.adaptive_footnote()}</p>
		{/if}
	</section>
{/if}

{#if history}
	<section class="rounded-3xl bg-white p-6 shadow-sm" data-tour="progress-weight">
		<div class="flex items-end justify-between">
			<div>
				<p class="text-sm font-semibold text-slate-500">{m.current_weight()}</p>
				<p class="mt-1 text-4xl font-black tracking-tight">
					{history.current_kg !== null ? nf.format(history.current_kg) : '—'}
					<span class="text-lg font-semibold text-slate-400">kg</span>
				</p>
			</div>
			{#if history.delta_kg !== null && history.delta_kg !== 0}
				{@const down = history.delta_kg < 0}
				<div
					class="rounded-full px-3 py-1 text-sm font-bold {down
						? 'bg-emerald-50 text-emerald-700'
						: 'bg-amber-50 text-amber-700'}"
				>
					{down ? '▼' : '▲'}
					{nf.format(Math.abs(history.delta_kg))} kg
				</div>
			{/if}
		</div>

		{#if history.logs.length >= 2}
			<div class="mt-4">
				<WeightChart logs={history.logs} />
			</div>
		{:else}
			<p class="mt-4 text-sm text-slate-400">{m.weight_need_more()}</p>
		{/if}
	</section>

	<!-- Composicao corporal: a gordura vira protagonista com regua de referencia, a
		 massa magra ganha tendencia (onde a bioimpedancia acerta) e visceral/agua
		 viram apoio. Antes eram quatro numeros soltos sem nenhuma regua - a tela nao
		 respondia a unica pergunta que a pessoa tem ao abrir ("isso e bom ou ruim?"). -->
	{#if displayBodyReading}
		{@const panel = displayBodyReading}
		<section class="mt-3 rounded-3xl bg-white p-5 shadow-sm" data-tour="progress-body">
			<p class="mb-3 text-sm font-bold text-slate-400 uppercase">{m.body_composition()}</p>

			<div class="mb-3 flex items-end justify-between gap-3">
				<div class="min-w-0">
					<p class="text-4xl leading-none font-black tracking-tight text-slate-900">
						{nf.format(panel.fat_percentage)}<span class="text-lg font-bold text-slate-400">%</span>
					</p>
					<p class="mt-1 text-xs font-bold text-slate-500">
						{m.bc_fat_pct()}
						{#if panel.fat_source}
							· {panel.fat_source === 'tape' ? m.source_tape() : m.source_scale()}
						{/if}
					</p>
				</div>
				{#if panel.band_key}
					<span class="shrink-0 rounded-full px-3 py-1 text-xs font-black {BAND_PILL_COLORS[panel.band_key]}">
						{bandLabel(panel.band_key)}
					</span>
				{/if}
			</div>

			<!-- regua de referencia: cada faixa recortada nos limites do desenho -->
			<div class="flex h-2.5 overflow-hidden rounded-full">
				{#each panel.bands as band (band.key)}
					{@const width = bandWidth(band, panel)}
					{#if width > 0}
						<span class="h-full {BAND_BAR_COLORS[band.key]}" style="width: {width}%"></span>
					{/if}
				{/each}
			</div>
			<div class="relative -mt-2.5 h-7">
				<span
					class="absolute top-0 grid h-7 w-7 -translate-x-1/2 place-items-center rounded-full border-2 bg-white text-sm shadow-sm {BAND_RING_COLORS[
						panel.band_key ?? 'acceptable'
					]}"
					style="left: {gaugePosition(panel.fat_percentage, panel)}%"
				>
					{BAND_EMOJI[panel.band_key ?? 'acceptable']}
				</span>
			</div>
			<!-- Legenda com quebra de linha, e nao rotulos presos a largura de cada
				 faixa: "Em forma" ocupa 13% da barra e sairia cortado. Aqui cada nome
				 aparece inteiro, com o intervalo a que se refere. -->
			<div class="mt-3 flex flex-wrap gap-x-3 gap-y-1.5">
				{#each panel.bands as band (band.key)}
					{@const isCurrent = band.key === panel.band_key}
					<span class="flex items-center gap-1.5 text-[11px] {isCurrent ? 'font-black text-slate-900' : 'font-semibold text-slate-400'}">
						<span class="h-2 w-2 shrink-0 rounded-full {BAND_BAR_COLORS[band.key]}"></span>
						{bandLabel(band.key)}
						<span class="font-semibold {isCurrent ? 'text-slate-500' : 'text-slate-300'}">
							{bandRange(band, panel)}
						</span>
					</span>
				{/each}
			</div>

			<!-- As DUAS estimativas lado a lado quando existem. Ambas erram (a balanca
				 mais que a fita), entao eleger uma como "a verdade" seria desonesto - o
				 que vale acompanhar e a tendencia de cada uma. -->
			{#if panel.fat_percentage_scale !== null && panel.fat_percentage_tape !== null}
				<div class="mt-4 rounded-2xl bg-slate-50 p-3">
					<div class="flex flex-wrap items-center gap-2">
						{#each [{ key: 'scale' as const, label: m.source_scale(), value: panel.fat_percentage_scale }, { key: 'tape' as const, label: m.source_tape(), value: panel.fat_percentage_tape }] as option (option.key)}
							<button
								type="button"
								disabled={savingSource}
								onclick={() => chooseSource(option.key)}
								class="flex items-baseline gap-1.5 rounded-full px-3 py-1.5 text-xs font-semibold disabled:opacity-50 {panel.fat_source ===
								option.key
									? 'bg-emerald-600 text-white'
									: 'bg-white text-slate-500 ring-1 ring-slate-200'}"
							>
								{option.label}
								<span class="text-sm font-black">{nf.format(option.value ?? 0)}%</span>
							</button>
						{/each}
						{#if panel.source_preference !== 'auto'}
							<button
								type="button"
								disabled={savingSource}
								onclick={() => chooseSource('auto')}
								class="rounded-full px-2.5 py-1.5 text-xs font-semibold text-slate-400 disabled:opacity-50"
							>
								{m.source_auto()}
							</button>
						{/if}
					</div>
					<p class="mt-2 text-[11px] leading-relaxed text-slate-500">{m.source_explain()}</p>
				</div>
			{/if}

			<div class="my-4 h-px bg-slate-100"></div>

			<!-- massa magra: o numero que se protege ao emagrecer -->
			{#if panel.lean_mass_kg !== null}
				<p class="text-2xl leading-none font-black text-slate-900">
					{nf.format(panel.lean_mass_kg)}<span class="text-sm font-medium text-slate-400"> kg</span>
				</p>
				<p class="mt-0.5 text-xs font-bold text-slate-500">{m.bc_lean_mass()}</p>
				<p class="mt-1 text-[11px] leading-relaxed text-slate-400">{m.bc_lean_hint()}</p>
			{/if}

			<!-- Tendencia: as duas variacoes juntas e o periodo dito UMA vez no titulo.
				 Antes o "+0,2 kg em 19 dias" ficava solto na massa magra e a variacao da
				 gordura aparecia la embaixo com o mesmo rotulo do numero grande do topo
				 ("Gordura (%)"), o que fazia parecer dois valores concorrentes. -->
			{#if panel.trend_days === null || (panel.fat_percentage_delta === null && panel.lean_mass_delta_kg === null)}
				<!-- Sem comparacao possivel ainda. Antes o bloco simplesmente sumia, e um
					 bloco que some sem dizer nada parece defeito - a pessoa procura e nao
					 acha. Melhor ele explicar por que ainda esta vazio. -->
				<p class="mt-4 text-[10px] font-black tracking-wide text-slate-400 uppercase">
					{m.bc_trend_title()}
				</p>
				<p class="mt-1 text-xs leading-relaxed text-slate-400">{m.bc_trend_empty()}</p>
			{:else}
				<p class="mt-4 text-[10px] font-black tracking-wide text-slate-400 uppercase">
					{m.bc_trend_since({ days: panel.trend_days })}
				</p>
				<div class="mt-1.5 flex flex-wrap gap-2">
					{#if panel.fat_percentage_delta !== null}
						<span
							class="flex items-baseline gap-1.5 rounded-full px-3 py-1.5 text-xs font-semibold {panel.fat_percentage_delta <=
							0
								? 'bg-emerald-50 text-emerald-700'
								: 'bg-amber-50 text-amber-700'}"
						>
							{m.bc_fat_pct()}
							<span class="text-sm font-black">
								{withSign(panel.fat_percentage_delta)}
								{m.bc_points_suffix()}
							</span>
						</span>
					{/if}
					{#if panel.waist_delta_cm !== null && panel.waist_delta_cm !== 0}
						<span
							class="flex items-baseline gap-1.5 rounded-full px-3 py-1.5 text-xs font-semibold {panel.waist_delta_cm <=
							0
								? 'bg-emerald-50 text-emerald-700'
								: 'bg-amber-50 text-amber-700'}"
						>
							{m.tape_waist()}
							<span class="text-sm font-black">{withSign(panel.waist_delta_cm)} cm</span>
						</span>
					{/if}
					{#if panel.lean_mass_delta_kg !== null}
						<span
							class="flex items-baseline gap-1.5 rounded-full px-3 py-1.5 text-xs font-semibold {panel.lean_mass_delta_kg >=
							0
								? 'bg-emerald-50 text-emerald-700'
								: 'bg-amber-50 text-amber-700'}"
						>
							{m.bc_lean_mass()}
							<span class="text-sm font-black">{withSign(panel.lean_mass_delta_kg)} kg</span>
						</span>
					{/if}
				</div>
			{/if}

			<!-- Cintura tem destaque proprio: e a unica medida da lista com significado
				 clinico SOZINHA. Preve gordura visceral e risco cardiometabolico
				 independentemente do IMC, porque captura DISTRIBUICAO de gordura - que
				 peso e IMC nao capturam. Nao depende de formula nenhuma. -->
			{#if panel.waist_cm !== null}
				<div class="mt-4 rounded-2xl p-3 {WAIST_RISK_TONES[panel.waist_risk ?? 'ok']}">
					<div class="flex items-baseline justify-between gap-3">
						<span class="text-xs font-bold">{m.tape_waist()}</span>
						<span class="text-lg font-black">
							{nf.format(panel.waist_cm)}<span class="text-xs font-semibold"> cm</span>
						</span>
					</div>
					{#if panel.waist_risk && panel.waist_risk_increased_cm !== null && panel.waist_risk_high_cm !== null}
						<p class="mt-0.5 text-[11px] leading-relaxed font-semibold">
							{waistRiskLabel(panel.waist_risk)}
							<span class="opacity-70">
								· {m.waist_cutoffs({
									increased: nf.format(panel.waist_risk_increased_cm),
									high: nf.format(panel.waist_risk_high_cm)
								})}
							</span>
						</p>
					{/if}
				</div>
			{/if}

			<!-- Braco, coxa e peito: SO tendencia, nunca estimativa. Circunferencia de
				 membro nao isola musculo (pega gordura, liquido e osso junto) - o valor
				 delas e ver o braco subindo enquanto a cintura desce. -->
			{#if panel.arm_cm !== null || panel.thigh_cm !== null || panel.chest_cm !== null}
				<p class="mt-4 text-[10px] font-black tracking-wide text-slate-400 uppercase">
					{m.tape_measurements()}
				</p>
				<div class="mt-1.5 flex flex-wrap gap-2">
					{#each [{ label: m.tape_arm(), value: panel.arm_cm, delta: panel.arm_delta_cm }, { label: m.tape_thigh(), value: panel.thigh_cm, delta: panel.thigh_delta_cm }, { label: m.tape_chest(), value: panel.chest_cm, delta: null }] as measure (measure.label)}
						{#if measure.value !== null}
							<span class="flex items-baseline gap-1.5 rounded-full bg-slate-100 px-3 py-1.5 text-xs font-semibold text-slate-500">
								{measure.label}
								<span class="text-sm font-black text-slate-900">{nf.format(measure.value)} cm</span>
								{#if measure.delta !== null && measure.delta !== 0}
									<span class="text-[11px] font-black {measure.delta > 0 ? 'text-emerald-600' : 'text-slate-400'}">
										{withSign(measure.delta)}
									</span>
								{/if}
							</span>
						{/if}
					{/each}
				</div>
			{/if}

			<!-- Pilula por metrica, com o rotulo colado no numero. Antes eram linhas com
				 rotulo numa ponta e numero na outra: quanto mais larga a tela, mais longe
				 um do outro, e o olho precisava atravessar o vazio para ligar os dois. -->
			{#if panel.visceral_fat_index !== null || panel.water_percentage !== null}
				<p class="mt-4 text-[10px] font-black tracking-wide text-slate-400 uppercase">
					{m.bc_also_measured()}
				</p>
				<div class="mt-1.5 flex flex-wrap gap-2">
					{#if panel.visceral_fat_index !== null}
						<span class="flex items-baseline gap-1.5 rounded-full bg-slate-100 px-3 py-1.5 text-xs font-semibold text-slate-500">
							{m.bc_visceral()}
							<span class="text-sm font-black text-slate-900">{nf.format(panel.visceral_fat_index)}</span>
						</span>
					{/if}
					{#if panel.water_percentage !== null}
						<span class="flex items-baseline gap-1.5 rounded-full bg-slate-100 px-3 py-1.5 text-xs font-semibold text-slate-500">
							{m.bc_water_pct()}
							<span class="text-sm font-black text-slate-900">{nf.format(panel.water_percentage)}%</span>
						</span>
					{/if}
				</div>
			{/if}

			{#if panel.measured_at}
				<p class="mt-4 text-xs text-slate-400">
					{m.bc_measured_on()}
					{df.format(new Date(panel.measured_at))}
				</p>
			{/if}
		</section>

		<!-- Alvo: faixa derivada de um alvo que a PESSOA escolhe, com a premissa a
			 vista. Nunca um "peso ideal" unico decidido pelo app. -->
		{#if panel.lean_mass_kg !== null}
			<section class="mt-3 rounded-3xl bg-white p-5 shadow-sm">
				<!-- O nome "calculadora" e o "?" moram no cabecalho e valem para os tres
					 estados: e onde a pessoa procura quando quer saber o que isso faz. -->
				<div class="mb-3 flex items-center justify-between gap-2">
					<p class="text-sm font-bold text-slate-400 uppercase">{m.bc_calculator_title()}</p>
					<button
						type="button"
						aria-label={m.bc_help_open()}
						title={m.bc_help_open()}
						onclick={() => (showTargetHelp = true)}
						class="grid h-7 w-7 shrink-0 place-items-center rounded-full bg-slate-100 text-sm font-black text-slate-500 active:bg-slate-200"
					>
						?
					</button>
				</div>

				{#if panel.target_weight_min_kg !== null && panel.target_weight_max_kg !== null && !showTargetPicker}
					<p class="text-xs font-bold text-slate-500">
						{m.bc_target_result_title({ pct: nf.format(panel.target_fat_percentage ?? 0) })}
					</p>
					<p class="mt-1 text-3xl font-black tracking-tight text-emerald-700">
						{nf.format(panel.target_weight_min_kg)} – {nf.format(panel.target_weight_max_kg)}
						<span class="text-base font-medium text-slate-400">kg</span>
					</p>
					<p class="mt-2 text-xs leading-relaxed text-slate-500">
						{m.bc_target_premise({ lean: nf.format(panel.lean_mass_kg) })}
					</p>

					<!-- onde a faixa cai em relacao ao peso de hoje -->
					{#if panel.weight_kg !== null}
						{@const trackMin = Math.min(panel.target_weight_min_kg, panel.weight_kg) - 2}
						{@const trackMax = Math.max(panel.target_weight_max_kg, panel.weight_kg) + 2}
						{@const span = trackMax - trackMin}
						<div class="relative mt-4 h-9">
							<div class="absolute top-3 right-0 left-0 h-1.5 rounded-full bg-slate-100"></div>
							<div
								class="absolute top-3 h-1.5 rounded-full bg-emerald-200"
								style="left: {((panel.target_weight_min_kg - trackMin) / span) * 100}%; width: {((panel.target_weight_max_kg - panel.target_weight_min_kg) / span) * 100}%"
							></div>
							<span
								class="absolute top-1.5 h-4 w-4 -translate-x-1/2 rounded-full border-[3px] border-slate-900 bg-white"
								style="left: {((panel.weight_kg - trackMin) / span) * 100}%"
							></span>
							<span
								class="absolute top-6 -translate-x-1/2 text-[9px] font-black text-slate-400"
								style="left: {((panel.weight_kg - trackMin) / span) * 100}%"
							>
								{m.bc_today_label()} · {nf.format(panel.weight_kg)}
							</span>
						</div>
					{/if}

					<div class="mt-3 flex gap-2">
						<button
							type="button"
							onclick={() => (showTargetPicker = true)}
							class="h-10 flex-1 rounded-xl border-2 border-slate-200 text-sm font-bold text-slate-600 active:bg-slate-50"
						>
							{m.edit()}
						</button>
						<button
							type="button"
							disabled={savingTarget}
							onclick={clearTarget}
							class="h-10 shrink-0 rounded-xl px-3 text-sm font-semibold text-slate-400 active:bg-slate-100 disabled:opacity-50"
						>
							{m.bc_target_clear()}
						</button>
					</div>
				{:else if showTargetPicker}
					{@const targetBand = bandKeyAt(targetPct, panel)}
					<p class="text-sm font-bold text-slate-700">{m.bc_target_choose()}</p>

					<!-- A regua e o proprio grafico de cima: arrastar sobre as cores responde
						 "qual e o ideal?" sem precisar decorar numero nenhum. -->
					<div class="mt-3 flex items-center gap-3">
						<span class="grid h-10 w-10 shrink-0 place-items-center rounded-full border-2 bg-white text-lg {BAND_RING_COLORS[targetBand]}">
							{BAND_EMOJI[targetBand]}
						</span>
						<div class="min-w-0">
							<p class="text-2xl leading-none font-black text-slate-900">{nf.format(targetPct)}%</p>
							<p class="mt-0.5 text-xs font-bold {BAND_TEXT_COLORS[targetBand]}">
								{bandLabel(targetBand)}
							</p>
						</div>
					</div>

					<div class="relative mt-3 h-8">
						<div class="pointer-events-none absolute top-1/2 right-0 left-0 flex h-2.5 -translate-y-1/2 overflow-hidden rounded-full">
							{#each panel.bands as band (band.key)}
								{@const width = bandWidth(band, panel)}
								{#if width > 0}
									<span class="h-full {BAND_BAR_COLORS[band.key]}" style="width: {width}%"></span>
								{/if}
							{/each}
						</div>
						<!-- onde a pessoa esta hoje, para o alvo nascer com referencia -->
						<div
							class="pointer-events-none absolute top-1/2 h-5 w-0.5 -translate-x-1/2 -translate-y-1/2 rounded-full bg-slate-900/50"
							style="left: {gaugePosition(panel.fat_percentage, panel)}%"
						></div>
						<input
							type="range"
							min={panel.gauge_min}
							max={panel.gauge_max}
							step="0.5"
							bind:value={targetPct}
							aria-label={m.bc_target_choose()}
							class="fat-slider absolute inset-0 w-full"
						/>
					</div>
					<div class="flex justify-between text-[10px] font-bold text-slate-400">
						<span>{nf.format(panel.gauge_min)}%</span>
						<span>{m.bc_today_label()} · {nf.format(panel.fat_percentage)}%</span>
						<span>{nf.format(panel.gauge_max)}%</span>
					</div>

					{#if targetPreview}
						<div class="mt-3 rounded-2xl bg-emerald-50 p-3 text-center">
							<p class="text-xl font-black text-emerald-800">
								{nf.format(targetPreview.lightest)} – {nf.format(targetPreview.heaviest)}
								<span class="text-sm font-medium text-emerald-700/70">kg</span>
							</p>
						</div>
					{/if}

					<p class="mt-3 text-xs leading-relaxed text-slate-500">
						{m.bc_target_premise({ lean: nf.format(panel.lean_mass_kg) })}
					</p>
					<p class="mt-1.5 text-xs leading-relaxed text-slate-400">{m.bc_range_note()}</p>
					<div class="mt-3 flex gap-2">
						<button
							type="button"
							disabled={savingTarget}
							onclick={saveTarget}
							class="h-11 flex-1 rounded-xl bg-emerald-600 text-sm font-bold text-white active:bg-emerald-700 disabled:opacity-50"
						>
							{m.bc_target_save()}
						</button>
						<button
							type="button"
							onclick={() => (showTargetPicker = false)}
							class="h-11 shrink-0 rounded-xl px-3 text-sm font-semibold text-slate-500 active:bg-slate-100"
						>
							{m.cancel()}
						</button>
					</div>
				{:else}
					<button
						type="button"
						onclick={() => (showTargetPicker = true)}
						class="flex w-full items-center justify-center gap-2 rounded-2xl border-2 border-dashed border-slate-300 py-3 text-sm font-bold text-slate-700 active:bg-slate-50"
					>
						<svg viewBox="0 0 24 24" class="h-4.5 w-4.5 text-slate-500" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9" /><circle cx="12" cy="12" r="5" /><circle cx="12" cy="12" r="1" /></svg>
						{m.bc_target_open()}
					</button>
				{/if}
			</section>
		{/if}

		<!-- Modal do "?": curta, direta, e com o "nao muda nada" em destaque -->
		{#if showTargetHelp}
			<div
				class="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
				role="button"
				tabindex="-1"
				onclick={() => (showTargetHelp = false)}
				onkeydown={(e) => e.key === 'Escape' && (showTargetHelp = false)}
			>
				<div
					class="max-h-[90dvh] w-full max-w-md overflow-y-auto rounded-3xl bg-white p-6"
					role="dialog"
					tabindex="-1"
					onclick={(e) => e.stopPropagation()}
					onkeydown={() => {}}
				>
					<h2 class="text-lg font-bold text-slate-900">{m.bc_help_title()}</h2>
					<p class="mt-2 text-sm leading-relaxed text-slate-600">{m.bc_help_what()}</p>

					<div class="mt-4 rounded-2xl border-2 border-amber-200 bg-amber-50 p-3.5">
						<p class="text-xs font-black tracking-wide text-amber-700 uppercase">
							{m.bc_help_not_title()}
						</p>
						<p class="mt-1.5 text-sm leading-relaxed text-amber-900">{m.bc_help_not()}</p>
					</div>

					<p class="mt-4 text-xs font-black tracking-wide text-slate-400 uppercase">
						{m.bc_help_how_title()}
					</p>
					<p class="mt-1 text-sm leading-relaxed text-slate-600">{m.bc_help_how()}</p>

					<p class="mt-4 text-xs font-black tracking-wide text-slate-400 uppercase">
						{m.bc_help_range_title()}
					</p>
					<p class="mt-1 text-sm leading-relaxed text-slate-600">{m.bc_help_range()}</p>

					<button
						type="button"
						onclick={() => (showTargetHelp = false)}
						class="mt-6 h-12 w-full rounded-2xl bg-emerald-600 font-bold text-white active:bg-emerald-700"
					>
						{m.bc_help_got_it()}
					</button>
				</div>
			</div>
		{/if}
	{/if}

	<button
		type="button"
		data-tour="progress-log"
		onclick={() => (adding = true)}
		class="mt-3 h-14 w-full rounded-2xl bg-emerald-600 text-lg font-bold text-white active:bg-emerald-700"
	>
		{m.register_weight()}
	</button>

	{#if reversedLogs.length > 0}
		<section class="mt-3 overflow-hidden rounded-3xl bg-white shadow-sm">
			<!-- cabecalho de colunas -->
			<div class="flex items-center gap-3 border-b border-slate-100 px-5 py-2.5">
				<span class="w-20 shrink-0 text-xs font-bold tracking-wide text-slate-400 uppercase">{m.col_date()}</span>
				<span class="flex-1 text-xs font-bold tracking-wide text-slate-400 uppercase">{m.col_weight()}</span>
				<span class="w-16 text-right text-xs font-bold tracking-wide text-slate-400 uppercase">{m.col_fat()}</span>
				<span class="w-4 shrink-0"></span>
			</div>

			{#each visibleLogs as { log, delta, fatDelta } (log.id)}
				<button
					type="button"
					onclick={() => openWeightDetail(log)}
					class="flex w-full items-center gap-3 border-l-4 border-t border-slate-100 px-5 py-3 text-left active:bg-slate-50
						{delta === null || delta === 0
						? 'border-l-transparent'
						: delta < 0
							? 'border-l-emerald-400'
							: 'border-l-amber-400'}"
				>
					<!-- data + hora -->
					<div class="w-20 shrink-0">
						<p class="text-sm font-bold text-slate-700">{df.format(new Date(log.logged_at))}</p>
						<p class="text-xs text-slate-400">{formatClock(log.logged_at)}</p>
					</div>

					<!-- peso + variacao -->
					<div class="flex-1">
						<p class="font-bold text-slate-900">
							{nf.format(log.weight_kg)}<span class="ml-0.5 text-xs font-medium text-slate-400">kg</span>
						</p>
						{#if delta !== null && delta !== 0}
							<p class="text-xs font-semibold {delta < 0 ? 'text-emerald-600' : 'text-amber-600'}">
								{delta < 0 ? '▼' : '▲'} {nf.format(Math.abs(delta))}
							</p>
						{/if}
					</div>

					<!-- gordura % + variacao (quando ha dado da balanca) -->
					<div class="w-16 text-right">
						{#if log.fat_percentage !== null}
							<p class="font-bold text-slate-900">
								{nf.format(log.fat_percentage)}<span class="ml-0.5 text-xs font-medium text-slate-400">%</span>
							</p>
							{#if fatDelta !== null && fatDelta !== 0}
								<p class="text-xs font-semibold {fatDelta < 0 ? 'text-emerald-600' : 'text-amber-600'}">
									{fatDelta < 0 ? '▼' : '▲'} {nf.format(Math.abs(fatDelta))}
								</p>
							{/if}
						{:else}
							<span class="text-slate-300">—</span>
						{/if}
					</div>

					<svg viewBox="0 0 24 24" class="h-4 w-4 shrink-0 text-slate-300" fill="none" stroke="currentColor" stroke-width="2"><path d="M9 6l6 6-6 6" stroke-linecap="round" stroke-linejoin="round" /></svg>
				</button>
			{/each}
			{#if reversedLogs.length > WEIGH_IN_PREVIEW}
				<button
					type="button"
					onclick={() => (historyExpanded = !historyExpanded)}
					class="w-full border-t border-slate-100 py-3 text-sm font-bold text-emerald-700 active:bg-slate-50"
				>
					{historyExpanded
						? m.show_less()
						: m.show_more_count({ count: reversedLogs.length - WEIGH_IN_PREVIEW })}
				</button>
			{/if}
		</section>
	{/if}
{:else}
	<!-- grafico de peso + os cartoes de composicao corporal que vem logo abaixo -->
	<SkeletonScreen chart cards={2} cardLines={2} />
{/if}

<!-- Modal de registro de pesagem -->
{#if adding}
	<div
		class="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
		role="button"
		tabindex="-1"
		onclick={() => (adding = false)}
		onkeydown={(e) => e.key === 'Escape' && (adding = false)}
	>
		<div
			class="max-h-[90dvh] w-full max-w-md overflow-y-auto rounded-3xl bg-white p-6"
			role="dialog"
			tabindex="-1"
			onclick={(e) => e.stopPropagation()}
			onkeydown={() => {}}
		>
			<p class="mb-3 font-semibold text-slate-600">{m.new_weight()}</p>
			<Stepper bind:value={newWeight} min={30} max={300} step={0.1} decimals={1} unit="kg" />

			<!-- Dados opcionais da balanca de bioimpedancia (BIA) -->
			<button
				type="button"
				onclick={() => (showScaleFields = !showScaleFields)}
				class="mt-4 flex w-full items-center justify-between text-sm font-semibold text-emerald-700"
			>
				<span>{m.scale_data()}</span>
				<svg viewBox="0 0 24 24" class="h-5 w-5 transition-transform {showScaleFields ? 'rotate-180' : ''}" fill="none" stroke="currentColor" stroke-width="2">
					<path d="M6 9l6 6 6-6" stroke-linecap="round" stroke-linejoin="round" />
				</svg>
			</button>

			{#if showScaleFields}
				{#if prefilledFrom}
					<!-- de onde vieram os numeros que ja estao nos campos: sem isso, a
						 pessoa poderia salvar um valor antigo achando que era de hoje -->
					<div class="mt-2 mb-3 flex items-center gap-2 rounded-2xl bg-amber-50 p-2.5">
						<svg viewBox="0 0 24 24" class="h-4 w-4 shrink-0 text-amber-600" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9" /><path d="M12 8v4l2.5 2.5" /></svg>
						<p class="min-w-0 flex-1 text-xs font-semibold text-amber-800">
							{m.bc_prefilled_hint({ date: df.format(new Date(prefilledFrom)) })}
						</p>
						<button
							type="button"
							onclick={clearScaleValues}
							class="shrink-0 rounded-lg px-2 py-1 text-xs font-bold text-amber-700 active:bg-amber-100"
						>
							{m.bc_prefill_clear()}
						</button>
					</div>
				{:else}
					<p class="mt-1 mb-3 text-xs text-slate-400">{m.scale_data_hint()}</p>
				{/if}
				<div class="grid grid-cols-2 gap-3">
					{#each bodyCompositionInputs as field (field.key)}
						<label class="block">
							<span class="mb-1 flex items-center gap-1 text-xs font-semibold text-slate-500">
								<BodyMetricIcon kind={field.icon} class="h-3.5 w-3.5 shrink-0 text-slate-400" />
								{field.label}
							</span>
							<div class="flex items-center gap-1 rounded-2xl border-2 border-slate-200 bg-white px-3">
								<input
									inputmode="decimal"
									value={scaleValues[field.key] ?? ''}
									oninput={(e) =>
										(scaleValues[field.key] = e.currentTarget.value.replace(/[^0-9.,]/g, ''))}
									placeholder="—"
									class="h-11 w-full min-w-0 bg-transparent text-base outline-none"
								/>
								{#if field.unit}<span class="shrink-0 text-xs text-slate-400">{field.unit}</span>{/if}
							</div>
						</label>
					{/each}
				</div>
			{/if}

			<!-- Medidas de fita metrica: secao propria, porque nao vem da balanca.
				 Serve tambem para quem NAO tem balanca - com cintura e pescoco o app
				 ja estima a gordura, e antes essas pessoas nao viam painel nenhum. -->
			<button
				type="button"
				onclick={() => (showTapeFields = !showTapeFields)}
				class="mt-4 flex w-full items-center justify-between text-sm font-semibold text-emerald-700"
			>
				<span>{m.tape_data()}</span>
				<svg viewBox="0 0 24 24" class="h-5 w-5 transition-transform {showTapeFields ? 'rotate-180' : ''}" fill="none" stroke="currentColor" stroke-width="2">
					<path d="M6 9l6 6 6-6" stroke-linecap="round" stroke-linejoin="round" />
				</svg>
			</button>

			{#if showTapeFields}
				<p class="mt-1 mb-3 text-xs text-slate-400">{m.tape_data_hint()}</p>
				<div class="grid grid-cols-2 gap-3">
					{#each tapeInputs as field (field.key)}
						<label class="block">
							<span class="mb-1 flex items-center gap-1 text-xs font-semibold text-slate-500">
								<BodyMetricIcon kind="tape" class="h-3.5 w-3.5 shrink-0 text-slate-400" />
								{field.label}
								<!-- marca os tres que alimentam a estimativa de gordura: sem
									 isso ninguem adivinha por que o pescoco esta sendo pedido -->
								{#if field.feedsFormula}
									<span class="text-emerald-600" title={m.tape_feeds_formula()}>•</span>
								{/if}
							</span>
							<div class="flex items-center gap-1 rounded-2xl border-2 border-slate-200 bg-white px-3">
								<input
									inputmode="decimal"
									value={tapeValues[field.key] ?? ''}
									oninput={(e) =>
										(tapeValues[field.key] = e.currentTarget.value.replace(/[^0-9.,]/g, ''))}
									placeholder={field.hint}
									class="h-11 w-full min-w-0 bg-transparent text-base outline-none"
								/>
								<span class="shrink-0 text-xs text-slate-400">cm</span>
							</div>
						</label>
					{/each}
				</div>
				<p class="mt-2 text-[11px] leading-relaxed text-slate-400">{m.tape_formula_note()}</p>
			{/if}

			<div class="mt-5 flex gap-3">
				<button
					type="button"
					onclick={() => (adding = false)}
					class="h-14 flex-1 rounded-2xl border-2 border-slate-200 font-bold text-slate-700 active:bg-slate-100"
				>
					{m.cancel()}
				</button>
				<button
					type="button"
					disabled={busy}
					onclick={save}
					class="h-14 flex-[2] rounded-2xl bg-emerald-600 text-lg font-bold text-white active:bg-emerald-700 disabled:opacity-50"
				>
					{m.save()}
				</button>
			</div>
		</div>
	</div>
{/if}

<!-- Modal de detalhes de uma pesagem -->
{#if selectedLog}
	<div
		class="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
		role="button"
		tabindex="-1"
		onclick={() => (selectedLog = null)}
		onkeydown={(e) => e.key === 'Escape' && (selectedLog = null)}
	>
		<div
			class="max-h-[90dvh] w-full max-w-md overflow-y-auto rounded-3xl bg-white p-6"
			role="dialog"
			tabindex="-1"
			onclick={(e) => e.stopPropagation()}
			onkeydown={() => {}}
		>
			<div class="flex items-start justify-between">
				<div>
					<p class="text-3xl font-black text-slate-900">{nf.format(selectedLog.weight_kg)} kg</p>
					<p class="text-sm text-slate-500">
						{df.format(new Date(selectedLog.logged_at))} ·
						{new Date(selectedLog.logged_at).toLocaleTimeString(getLocale(), {
							hour: '2-digit',
							minute: '2-digit'
						})}
					</p>
				</div>
				<button
					type="button"
					aria-label={m.close()}
					onclick={() => (selectedLog = null)}
					class="grid h-10 w-10 shrink-0 place-items-center rounded-full bg-slate-100 text-slate-500 active:bg-slate-200"
				>
					<svg viewBox="0 0 24 24" class="h-5 w-5" fill="none" stroke="currentColor" stroke-width="2"><path d="M6 6l12 12M18 6L6 18" stroke-linecap="round" /></svg>
				</button>
			</div>

			{#if selectedBodyComposition.length > 0}
				<div class="mt-4 grid grid-cols-2 gap-3">
					{#each selectedBodyComposition as row (row.label)}
						<div class="flex items-center gap-3 rounded-2xl bg-slate-50 p-3">
							<span class="grid h-9 w-9 shrink-0 place-items-center rounded-xl bg-white text-slate-500">
								<BodyMetricIcon kind={row.icon} />
							</span>
							<div class="min-w-0">
								<p class="text-lg leading-tight font-bold text-slate-900">
									{nf.format(row.value ?? 0)}{row.unit ? ` ${row.unit}` : ''}
								</p>
								<p class="truncate text-xs font-semibold text-slate-500">{row.label}</p>
							</div>
						</div>
					{/each}
				</div>
			{:else}
				<p class="mt-4 text-sm text-slate-400">{m.no_body_composition()}</p>
			{/if}

			<!-- Exclusao sempre com confirmacao -->
			{#if confirmingDeleteWeight}
				<p class="mt-5 rounded-xl bg-red-50 px-4 py-3 text-sm font-medium text-red-700">
					{m.delete_weigh_in_confirm()}
				</p>
				<div class="mt-2 flex gap-2">
					<button
						type="button"
						onclick={() => (confirmingDeleteWeight = false)}
						class="h-12 flex-1 rounded-2xl border-2 border-slate-200 font-semibold text-slate-700 active:bg-slate-100"
					>
						{m.cancel()}
					</button>
					<button
						type="button"
						onclick={deleteSelectedWeight}
						class="h-12 flex-1 rounded-2xl bg-red-600 font-semibold text-white active:bg-red-700"
					>
						{m.delete_confirm_button()}
					</button>
				</div>
			{:else}
				<button
					type="button"
					onclick={() => (confirmingDeleteWeight = true)}
					class="mt-5 h-12 w-full rounded-2xl border-2 border-red-200 font-semibold text-red-600 active:bg-red-50"
				>
					{m.delete_weigh_in()}
				</button>
			{/if}
		</div>
	</div>
{/if}

<style>
	/* Seletor do alvo de gordura: o trilho e a propria regua colorida desenhada
	   atras, entao o input fica transparente e so o pegador aparece. */
	.fat-slider {
		appearance: none;
		-webkit-appearance: none;
		background: transparent;
		height: 100%;
		margin: 0;
		cursor: pointer;
	}
	.fat-slider::-webkit-slider-runnable-track {
		background: transparent;
		height: 100%;
	}
	.fat-slider::-moz-range-track {
		background: transparent;
		height: 100%;
	}
	/* pegador grande o bastante para o dedo (24px) e com contraste sobre qualquer
	   cor da regua */
	.fat-slider::-webkit-slider-thumb {
		appearance: none;
		-webkit-appearance: none;
		height: 24px;
		width: 24px;
		border-radius: 999px;
		background: #fff;
		border: 3px solid #0f172a;
		box-shadow: 0 1px 4px rgb(15 23 42 / 0.35);
	}
	.fat-slider::-moz-range-thumb {
		height: 24px;
		width: 24px;
		border-radius: 999px;
		background: #fff;
		border: 3px solid #0f172a;
		box-shadow: 0 1px 4px rgb(15 23 42 / 0.35);
	}
	.fat-slider:focus-visible::-webkit-slider-thumb {
		outline: 2px solid #059669;
		outline-offset: 2px;
	}
	.fat-slider:focus-visible::-moz-range-thumb {
		outline: 2px solid #059669;
		outline-offset: 2px;
	}
</style>
