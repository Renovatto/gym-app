// Classifica P/C/G de um item (alimento/receita/lancamento) para dar um alerta visual
// discreto - nao e diagnostico nutricional, so ajuda a "fixar" o que cada item tem.
//
// Calculo: converte cada macro pra kcal (proteina/carbo = 4 kcal/g, gordura = 9 kcal/g)
// e olha a FATIA de calorias que ele representa no item - gramas puras nao comparam
// direito entre macros porque a gordura pesa mais que o dobro por grama. Proteina
// nunca e sinalizada (mais proteina e desejavel no contexto de treino/dieta do app).
const KCAL_PER_G_PROTEIN = 4;
const KCAL_PER_G_CARB = 4;
const KCAL_PER_G_FAT = 9;

// Limiares (fatia do total de calorias do item): acima disso, chama atencao.
const FAT_SHARE_ALERT = 0.45;
const CARB_SHARE_ALERT = 0.65;

export type MacroTone = 'normal' | 'high';

export interface MacroTones {
	protein: MacroTone;
	carbs: MacroTone;
	fat: MacroTone;
}

export function macroTones(protein_g: number, carbs_g: number, fat_g: number): MacroTones {
	const proteinKcal = protein_g * KCAL_PER_G_PROTEIN;
	const carbsKcal = carbs_g * KCAL_PER_G_CARB;
	const fatKcal = fat_g * KCAL_PER_G_FAT;
	const total = proteinKcal + carbsKcal + fatKcal;
	if (total <= 0) return { protein: 'normal', carbs: 'normal', fat: 'normal' };
	return {
		protein: 'normal',
		carbs: carbsKcal / total > CARB_SHARE_ALERT ? 'high' : 'normal',
		fat: fatKcal / total > FAT_SHARE_ALERT ? 'high' : 'normal'
	};
}

// ---------------------------------------------------------------------------
// Farol do dia (consumido x meta) - diferente do macroTones acima, que olha um
// item isolado. Aqui a pergunta e "como esta o dia inteiro contra a meta".
//
// Tres estados em vez de dois: sem a faixa do meio, 1 kcal acima da meta ja
// pintava o dia de vermelho e o alerta perdia o sentido - se qualquer dia
// levemente acima e vermelho, vermelho nao quer dizer mais nada.
export type GoalStatus = 'ok' | 'near' | 'over';

// Tolerancia das calorias: 5% da meta, com piso absoluto de 80 kcal. O piso
// existe porque em meta baixa (1400 kcal) 5% seriam 70 kcal, e a faixa amarela
// ficaria estreita demais pra caber um escorregao comum.
const KCAL_TOLERANCE_RATIO = 0.05;
const KCAL_TOLERANCE_FLOOR = 80;

// Ate quantas vezes a meta o macro ainda fica amarelo; acima disso, vermelho.
// A gordura tem a faixa mais curta de proposito: a 9 kcal/g, o mesmo "um grama
// a mais" custa mais que o dobro do carboidrato em calorias.
const FAT_NEAR_LIMIT = 1.05;
const CARB_NEAR_LIMIT = 1.1;

const STATUS_SEVERITY: Record<GoalStatus, number> = { ok: 0, near: 1, over: 2 };

/** O pior entre dois farois - usado pra combinar calorias e gordura no anel. */
export function worstGoalStatus(a: GoalStatus, b: GoalStatus): GoalStatus {
	return STATUS_SEVERITY[a] >= STATUS_SEVERITY[b] ? a : b;
}

export function kcalGoalStatus(consumed: number, goal: number): GoalStatus {
	if (goal <= 0 || consumed <= goal) return 'ok';
	const tolerance = Math.max(KCAL_TOLERANCE_FLOOR, goal * KCAL_TOLERANCE_RATIO);
	return consumed <= goal + tolerance ? 'near' : 'over';
}

/** Proteina nunca chega em 'over': mais proteina e desejavel no contexto do app,
 *  entao ela para no amarelo so pra sinalizar que passou da meta. */
export function proteinGoalStatus(consumed: number, goal: number): GoalStatus {
	if (goal <= 0 || consumed <= goal) return 'ok';
	return 'near';
}

export function carbsGoalStatus(consumed: number, goal: number): GoalStatus {
	if (goal <= 0 || consumed <= goal) return 'ok';
	return consumed / goal <= CARB_NEAR_LIMIT ? 'near' : 'over';
}

export function fatGoalStatus(consumed: number, goal: number): GoalStatus {
	if (goal <= 0 || consumed <= goal) return 'ok';
	return consumed / goal <= FAT_NEAR_LIMIT ? 'near' : 'over';
}
