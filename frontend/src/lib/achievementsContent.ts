// Nome e descricao de cada conquista, nos tres idiomas lado a lado (facil de manter).
// O backend manda o code + icone + progresso; aqui traduzimos code -> texto.

import type { Locale } from '$lib/paraglide/runtime';

export interface AchievementText {
	name: string;
	description: string;
}

type ByCode = Record<string, AchievementText>;

const PT_BR: ByCode = {
	first_workout: { name: 'Primeiro treino', description: 'Voce concluiu seu primeiro treino!' },
	workouts_10: { name: '10 treinos', description: 'Dez treinos concluidos. Consistencia!' },
	workouts_25: { name: '25 treinos', description: 'Vinte e cinco treinos no historico.' },
	workouts_50: { name: '50 treinos', description: 'Cinquenta treinos. Voce e outro nivel.' },
	full_week: { name: 'Semana completa', description: '4 treinos em uma unica semana.' },
	streak_3: { name: '3 semanas seguidas', description: 'Tres semanas ativas em sequencia.' },
	streak_8: { name: '8 semanas seguidas', description: 'Oito semanas ativas. Habito formado!' },
	first_weigh_in: { name: 'Primeira pesagem', description: 'Voce comecou a acompanhar o peso.' },
	weigh_ins_10: { name: '10 pesagens', description: 'Dez registros de peso. Otimos dados!' },
	lost_1kg: { name: 'Menos 1 kg', description: 'Voce ja perdeu 1 kg desde o inicio.' },
	lost_5kg: { name: 'Menos 5 kg', description: 'Cinco quilos a menos. Que evolucao!' },
	first_diet_log: { name: 'Primeiro registro', description: 'Voce registrou sua primeira refeicao.' },
	diet_days_7: { name: '7 dias de dieta', description: 'Uma semana acompanhando a alimentacao.' }
};

const EN: ByCode = {
	first_workout: { name: 'First workout', description: 'You completed your first workout!' },
	workouts_10: { name: '10 workouts', description: 'Ten workouts done. Consistency!' },
	workouts_25: { name: '25 workouts', description: 'Twenty-five workouts logged.' },
	workouts_50: { name: '50 workouts', description: 'Fifty workouts. Next level.' },
	full_week: { name: 'Full week', description: '4 workouts in a single week.' },
	streak_3: { name: '3-week streak', description: 'Three active weeks in a row.' },
	streak_8: { name: '8-week streak', description: 'Eight active weeks. Habit formed!' },
	first_weigh_in: { name: 'First weigh-in', description: 'You started tracking your weight.' },
	weigh_ins_10: { name: '10 weigh-ins', description: 'Ten weight logs. Great data!' },
	lost_1kg: { name: 'Down 1 kg', description: "You've lost 1 kg since the start." },
	lost_5kg: { name: 'Down 5 kg', description: 'Five kilos down. Amazing progress!' },
	first_diet_log: { name: 'First log', description: 'You logged your first meal.' },
	diet_days_7: { name: '7 diet days', description: 'A week tracking your nutrition.' }
};

const ES: ByCode = {
	first_workout: { name: 'Primer entrenamiento', description: '¡Completaste tu primer entrenamiento!' },
	workouts_10: { name: '10 entrenamientos', description: 'Diez entrenamientos hechos. ¡Constancia!' },
	workouts_25: { name: '25 entrenamientos', description: 'Veinticinco entrenamientos registrados.' },
	workouts_50: { name: '50 entrenamientos', description: 'Cincuenta entrenamientos. Otro nivel.' },
	full_week: { name: 'Semana completa', description: '4 entrenamientos en una sola semana.' },
	streak_3: { name: 'Racha de 3 semanas', description: 'Tres semanas activas seguidas.' },
	streak_8: { name: 'Racha de 8 semanas', description: 'Ocho semanas activas. ¡Habito formado!' },
	first_weigh_in: { name: 'Primer pesaje', description: 'Empezaste a seguir tu peso.' },
	weigh_ins_10: { name: '10 pesajes', description: 'Diez registros de peso. ¡Buenos datos!' },
	lost_1kg: { name: 'Menos 1 kg', description: 'Ya perdiste 1 kg desde el inicio.' },
	lost_5kg: { name: 'Menos 5 kg', description: 'Cinco kilos menos. ¡Que progreso!' },
	first_diet_log: { name: 'Primer registro', description: 'Registraste tu primera comida.' },
	diet_days_7: { name: '7 dias de dieta', description: 'Una semana siguiendo tu alimentacion.' }
};

const BY_LOCALE: Record<Locale, ByCode> = { 'pt-br': PT_BR, en: EN, es: ES };

export function achievementText(locale: Locale, code: string): AchievementText {
	return (BY_LOCALE[locale] ?? PT_BR)[code] ?? { name: code, description: '' };
}
