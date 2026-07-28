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
