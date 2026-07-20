// Definicoes de celebracao (gamificacao): so o lado VISUAL (cenario, classes CSS,
// HTML decorativo extra). O CONTEUDO (kicker/emoji/titulo/descricao) vem de fora na
// hora do disparo - normalmente da propria conquista real (nome/descricao/icone),
// entao a celebracao sempre mostra algo verdadeiro, nunca texto generico inventado.
//
// 'slug' e a chave que o CelebrationOverlay usa para achar a funcao de efeito (fx/js)
// correspondente - a logica de particulas fica so no componente, aqui e so dado.

export interface CelebrationDef {
	slug: string;
	scene: string; // cenario (cores de fundo/texto legiveis, ver CelebrationOverlay)
	cls: string; // classes que animam medalha/aneis/titulo/camadas (espaco-separadas)
	extra?: string; // HTML decorativo extra (podio, pontinhos, presente...)
	dur: number; // ms visivel antes de avancar sozinha (0 = so fecha manual)
}

// Desbloqueio comum (a maioria das conquistas: treino, peso, dieta).
export const POOL_GENERAL: CelebrationDef[] = [
	{ slug: 'explosao-classica', scene: 'gold', cls: 'm-pop r-pulse', dur: 3600 },
	{ slug: 'canhoes-laterais', scene: 'paper', cls: 'm-pop', dur: 3600 },
	{ slug: 'chuva-confete', scene: 'sky', cls: 'm-pop', dur: 3600 },
	{ slug: 'serpentinas', scene: 'paper', cls: 'm-pop', dur: 3600 },
	{ slug: 'espiral-dourada', scene: 'gold', cls: 'm-flip x-glow', dur: 3600 },
	{ slug: 'chafariz-moedas', scene: 'violet', cls: 'm-pop x-glow', dur: 3600 },
	{ slug: 'forja-brilhante', scene: 'gold', cls: 'x-shine x-glow', dur: 3400 },
	{ slug: 'peso-pesado', scene: 'slate', cls: 'm-drop x-shake', dur: 3600 },
	{ slug: 'giro-moeda', scene: 'paper', cls: 'm-flip', dur: 3400 },
	{ slug: 'ascensao-trofeu', scene: 'violet', cls: 'm-rise x-raysoft', dur: 3600 },
	{ slug: 'batimento', scene: 'mint', cls: 'm-beat r-beat', dur: 3400 },
	{ slug: 'orbita-estrelas', scene: 'night', cls: 'm-pop', dur: 3600 }
];

// Conquistas de streak (semanas seguidas): visual de fogo/celeste.
export const POOL_STREAK: CelebrationDef[] = [
	{ slug: 'chama-acesa', scene: 'fire', cls: 'm-beat', dur: 3600 },
	{ slug: 'numero-brasa', scene: 'fire', cls: 'm-none', dur: 3400, extra: '<div class="push-up"><div class="ce-bignum" data-n></div></div>' },
	{ slug: 'meteoro', scene: 'night', cls: 'm-late', dur: 3800 },
	{ slug: 'constelacao-classica', scene: 'night', cls: 'm-none t-js', dur: 4400 },
	{ slug: 'constelacao-ascendente', scene: 'slate', cls: 'm-none t-js', dur: 4400 },
	{ slug: 'constelacao-pico', scene: 'violet', cls: 'm-none t-js', dur: 4400 },
	{ slug: 'aurora', scene: 'night', cls: 'm-pop x-aurora', dur: 3600 },
	{ slug: 'chuva-estrelas', scene: 'night', cls: 'm-pop', dur: 3600 },
	{ slug: 'combo-crescente', scene: 'slate', cls: 'm-late', dur: 3800, extra: '<div class="ce-combo"><span>×1</span><span>×2</span><span>×3</span></div>' },
	{ slug: 'semana-chamas', scene: 'fire', cls: 'm-late', dur: 4400, extra: '<div class="ce-dots">' + ['S', 'T', 'Q', 'Q', 'S', 'S', 'D'].map((d, i) => `<b data-fx="🔥" style="animation-delay:${i * 0.08}s">${d}</b>`).join('') + '</div>' }
];

// Marco grande (conquistas de meta alta: 100/200 treinos, streak 12, -10kg...).
export const POOL_MILESTONE: CelebrationDef[] = [
	{ slug: 'grande-slam', scene: 'gold', cls: 'm-slam x-rays x-shock x-shake x-flash', dur: 3800 },
	{ slug: 'fogos-artificio', scene: 'night', cls: 'm-late', dur: 4000 },
	{ slug: 'podio', scene: 'violet', cls: 'm-drop', dur: 3600, extra: '<div class="ce-podium"><i>2</i><i>1</i><i>3</i></div>' },
	{ slug: 'treino-marco', scene: 'gold', cls: 'm-none x-rays x-shock x-flash', dur: 4600, extra: '<div class="push-up"><div class="ce-bignum ce-bignum-gold ce-bignum-mega" data-n></div></div>' },
	{ slug: 'foguete', scene: 'night', cls: 'm-late', dur: 5600 }
];

// Subiu de nivel (titulo evolutivo).
export const POOL_LEVELUP: CelebrationDef[] = [
	{ slug: 'raios-solares', scene: 'gold', cls: 'm-pop x-rays', dur: 3800 },
	{ slug: 'onda-choque', scene: 'slate', cls: 'm-slam x-shock x-shake', dur: 3600 },
	{ slug: 'titulo-virado', scene: 'paper', cls: 'm-pop t-flipx', dur: 3400 },
	{ slug: 'contador-epico', scene: 'night', cls: 'm-none x-flash', dur: 3600, extra: '<div class="push-up"><div class="ce-bignum" data-n></div></div>' }
];

// Aniversario (sorteia entre as variacoes).
export const POOL_BIRTHDAY: CelebrationDef[] = [
	{ slug: 'aniversario-bolo', scene: 'violet', cls: 'm-pop', dur: 4000 },
	{ slug: 'aniversario-baloes', scene: 'sunset', cls: 'm-pop', dur: 9000 }
];

// Feriados mundiais (Natal, Ano Novo, Pascoa, Halloween).
export const POOL_HOLIDAY: CelebrationDef[] = [
	{ slug: 'natal', scene: 'frost', cls: 'm-pop', dur: 4400 },
	{ slug: 'ano-novo', scene: 'night', cls: 'm-late', dur: 4400 },
	{ slug: 'pascoa', scene: 'bloom', cls: 'm-pop', dur: 4400 },
	{ slug: 'halloween', scene: 'spooky', cls: 'm-pop', dur: 4400 }
];

export function pickRandom<T>(list: T[]): T {
	return list[(Math.random() * list.length) | 0];
}

// Espelha MILESTONE_CODES do backend (services/achievements.py): conquistas de meta
// alta que merecem a celebracao "de marco grande" em vez da celebracao padrao.
export const MILESTONE_CODES = new Set([
	'workouts_100',
	'workouts_200',
	'streak_12',
	'weigh_ins_50',
	'lost_10kg',
	'diet_days_100'
]);
