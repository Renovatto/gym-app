import { m } from '$lib/paraglide/messages';

/**
 * Conteudo do tutorial guiado: o que cada tour explica, em ordem.
 *
 * Fica separado do motor (tour.svelte.ts) e do visual (TourOverlay.svelte) de
 * proposito - mexer no texto ou na ordem dos passos nao encosta no resto.
 *
 * Passo cujo alvo nao esta na tela e pulado, nao trava o tour: muita coisa aqui
 * e condicional (o cartao do proximo treino so existe com rotina cadastrada, os
 * suplementos so aparecem para quem cadastrou algum, e por ai vai).
 */
export interface TourStep {
	// data-tour do elemento que fica iluminado. null = balao centrado, sem recorte
	// (usado nas boas-vindas, que nao apontam nada).
	anchor: string | null;
	title: () => string;
	text: () => string;
}

export const TOURS: Record<string, TourStep[]> = {
	home: [
		{
			anchor: null,
			title: () => m.tour_home_welcome_title(),
			text: () => m.tour_home_welcome_text()
		},
		{
			anchor: 'home-calories',
			title: () => m.tour_home_calories_title(),
			text: () => m.tour_home_calories_text()
		},
		{
			anchor: 'home-water',
			title: () => m.tour_home_water_title(),
			text: () => m.tour_home_water_text()
		},
		{
			anchor: 'home-numbers',
			title: () => m.tour_home_numbers_title(),
			text: () => m.tour_home_numbers_text()
		},
		{
			anchor: 'tabbar',
			title: () => m.tour_home_tabs_title(),
			text: () => m.tour_home_tabs_text()
		},
		{
			anchor: 'feedback-fab',
			title: () => m.tour_feedback_fab_title(),
			text: () => m.tour_feedback_fab_text()
		}
	],
	workout: [
		{
			anchor: 'workout-create',
			title: () => m.tour_workout_create_title(),
			text: () => m.tour_workout_create_text()
		},
		{
			anchor: 'workout-next',
			title: () => m.tour_workout_next_title(),
			text: () => m.tour_workout_next_text()
		},
		{
			anchor: 'workout-calendar',
			title: () => m.tour_workout_calendar_title(),
			text: () => m.tour_workout_calendar_text()
		},
		{
			anchor: 'workout-catalog',
			title: () => m.tour_workout_catalog_title(),
			text: () => m.tour_workout_catalog_text()
		},
		{
			anchor: 'workout-activity',
			title: () => m.tour_workout_activity_title(),
			text: () => m.tour_workout_activity_text()
		},
		{
			anchor: 'workout-history',
			title: () => m.tour_workout_history_title(),
			text: () => m.tour_workout_history_text()
		},
		{
			anchor: 'workout-archived',
			title: () => m.tour_workout_archived_title(),
			text: () => m.tour_workout_archived_text()
		}
	],
	diet: [
		{
			anchor: 'diet-goals',
			title: () => m.tour_diet_goals_title(),
			text: () => m.tour_diet_goals_text()
		},
		{
			anchor: 'diet-meal-start',
			title: () => m.tour_diet_start_title(),
			text: () => m.tour_diet_start_text()
		},
		{
			anchor: 'diet-meals',
			title: () => m.tour_diet_meals_title(),
			text: () => m.tour_diet_meals_text()
		},
		{
			anchor: 'diet-repeat-meal',
			title: () => m.tour_diet_repeat_meal_title(),
			text: () => m.tour_diet_repeat_meal_text()
		},
		{
			anchor: 'diet-supplements',
			title: () => m.tour_diet_supplements_title(),
			text: () => m.tour_diet_supplements_text()
		},
		{
			anchor: 'diet-repeat-day',
			title: () => m.tour_diet_repeat_day_title(),
			text: () => m.tour_diet_repeat_day_text()
		},
		{
			anchor: 'diet-foods-recipes',
			title: () => m.tour_diet_foods_recipes_title(),
			text: () => m.tour_diet_foods_recipes_text()
		}
	],
	progress: [
		{
			anchor: 'progress-week',
			title: () => m.tour_progress_week_title(),
			text: () => m.tour_progress_week_text()
		},
		{
			anchor: 'progress-adaptive',
			title: () => m.tour_progress_adaptive_title(),
			text: () => m.tour_progress_adaptive_text()
		},
		{
			anchor: 'progress-weight',
			title: () => m.tour_progress_weight_title(),
			text: () => m.tour_progress_weight_text()
		},
		{
			anchor: 'progress-body',
			title: () => m.tour_progress_body_title(),
			text: () => m.tour_progress_body_text()
		},
		{
			anchor: 'progress-log',
			title: () => m.tour_progress_log_title(),
			text: () => m.tour_progress_log_text()
		}
	],
	profile: [
		{
			anchor: 'profile-achievements',
			title: () => m.tour_profile_achievements_title(),
			text: () => m.tour_profile_achievements_text()
		},
		{
			anchor: 'profile-sharing',
			title: () => m.tour_profile_sharing_title(),
			text: () => m.tour_profile_sharing_text()
		},
		{
			anchor: 'profile-guide',
			title: () => m.tour_profile_guide_title(),
			text: () => m.tour_profile_guide_text()
		},
		{
			anchor: 'profile-preferences',
			title: () => m.tour_profile_preferences_title(),
			text: () => m.tour_profile_preferences_text()
		}
	]
};

// Qual tour pertence a qual aba. Rota fora deste mapa nunca dispara tutorial -
// e por isso que as telas de foco (sessao de treino, adicionar alimento) ficam livres.
export const TOUR_BY_ROUTE: Record<string, string> = {
	'/': 'home',
	'/treino': 'workout',
	'/dieta': 'diet',
	'/progresso': 'progress',
	'/perfil': 'profile'
};
