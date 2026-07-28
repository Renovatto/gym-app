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

// Desbloqueio comum (a maioria das conquistas: treino, peso, dieta). dur=0: o
// card de conquista SO fecha manual (o usuario decide quando fechar/ja viu).
export const POOL_GENERAL: CelebrationDef[] = [
	{ slug: 'explosao-classica', scene: 'gold', cls: 'm-pop r-pulse', dur: 0 },
	{ slug: 'canhoes-laterais', scene: 'paper', cls: 'm-pop', dur: 0 },
	{ slug: 'chuva-confete', scene: 'sky', cls: 'm-pop', dur: 0 },
	{ slug: 'serpentinas', scene: 'paper', cls: 'm-pop', dur: 0 },
	{ slug: 'espiral-dourada', scene: 'gold', cls: 'm-flip x-glow', dur: 0 },
	{ slug: 'chafariz-moedas', scene: 'violet', cls: 'm-pop x-glow', dur: 0 },
	{ slug: 'forja-brilhante', scene: 'gold', cls: 'x-shine x-glow', dur: 0 },
	{ slug: 'peso-pesado', scene: 'slate', cls: 'm-drop x-shake', dur: 0 },
	{ slug: 'giro-moeda', scene: 'paper', cls: 'm-flip', dur: 0 },
	{ slug: 'ascensao-trofeu', scene: 'violet', cls: 'm-rise x-raysoft', dur: 0 },
	{ slug: 'batimento', scene: 'mint', cls: 'm-beat r-beat', dur: 0 },
	{ slug: 'orbita-estrelas', scene: 'night', cls: 'm-pop', dur: 0 }
];

// Conquistas de streak (semanas seguidas): visual de fogo/celeste. dur=0: so fecha manual.
export const POOL_STREAK: CelebrationDef[] = [
	{ slug: 'chama-acesa', scene: 'fire', cls: 'm-beat', dur: 0 },
	{ slug: 'numero-brasa', scene: 'fire', cls: 'm-none', dur: 0, extra: '<div class="push-up"><div class="ce-bignum" data-n></div></div>' },
	{ slug: 'meteoro', scene: 'night', cls: 'm-late', dur: 0 },
	{ slug: 'constelacao-classica', scene: 'night', cls: 'm-none t-js', dur: 0 },
	{ slug: 'constelacao-ascendente', scene: 'slate', cls: 'm-none t-js', dur: 0 },
	{ slug: 'constelacao-pico', scene: 'violet', cls: 'm-none t-js', dur: 0 },
	{ slug: 'aurora', scene: 'night', cls: 'm-pop x-aurora', dur: 0 },
	{ slug: 'chuva-estrelas', scene: 'night', cls: 'm-pop', dur: 0 },
	{ slug: 'combo-crescente', scene: 'slate', cls: 'm-late', dur: 0, extra: '<div class="ce-combo"><span>×1</span><span>×2</span><span>×3</span></div>' },
	{ slug: 'semana-chamas', scene: 'fire', cls: 'm-late', dur: 0, extra: '<div class="ce-dots">' + ['S', 'T', 'Q', 'Q', 'S', 'S', 'D'].map((d, i) => `<b data-fx="🔥" style="animation-delay:${i * 0.08}s">${d}</b>`).join('') + '</div>' }
];

// Marco grande (conquistas de meta alta: 100/200 treinos, streak 12, -10kg...). dur=0: so fecha manual.
export const POOL_MILESTONE: CelebrationDef[] = [
	{ slug: 'grande-slam', scene: 'gold', cls: 'm-slam x-rays x-shock x-shake x-flash', dur: 0 },
	{ slug: 'fogos-artificio', scene: 'night', cls: 'm-late', dur: 0 },
	{ slug: 'podio', scene: 'violet', cls: 'm-drop', dur: 0, extra: '<div class="ce-podium"><i>2</i><i>1</i><i>3</i></div>' },
	{ slug: 'treino-marco', scene: 'gold', cls: 'm-none x-rays x-shock x-flash', dur: 0, extra: '<div class="push-up"><div class="ce-bignum ce-bignum-gold ce-bignum-mega" data-n></div></div>' },
	{ slug: 'foguete', scene: 'night', cls: 'm-late', dur: 0 }
];

// Subiu de nivel (titulo evolutivo). dur=0: so fecha manual.
export const POOL_LEVELUP: CelebrationDef[] = [
	{ slug: 'raios-solares', scene: 'gold', cls: 'm-pop x-rays', dur: 0 },
	{ slug: 'onda-choque', scene: 'slate', cls: 'm-slam x-shock x-shake', dur: 0 },
	{ slug: 'titulo-virado', scene: 'paper', cls: 'm-pop t-flipx', dur: 0 },
	{ slug: 'contador-epico', scene: 'night', cls: 'm-none x-flash', dur: 0, extra: '<div class="push-up"><div class="ce-bignum" data-n></div></div>' }
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

/** Paleta de cada cenario para desenho em CANVAS (imagem de compartilhar a medalha).
 * Espelha os cenarios em CSS do CelebrationOverlay: 'from'/'to' sao as duas pontas do
 * gradiente de fundo, 'ink' e o titulo, 'sub' a descricao e 'kick' o texto de topo e
 * os aneis em volta da medalha. Existe separado porque a versao CSS mora em variaveis
 * do componente (--sk-bg etc.) e nao da pra ler do JS - ao mudar um cenario la, mude
 * aqui tambem para a imagem continuar da mesma familia visual da animacao. */
export interface ScenePalette {
	from: string;
	to: string;
	ink: string;
	sub: string;
	kick: string;
}

export const SCENE_PALETTE: Record<string, ScenePalette> = {
	paper: { from: '#f6faf7', to: '#dde7e0', ink: '#17211c', sub: '#5a6a60', kick: '#047857' },
	gold: { from: '#fff6da', to: '#e9a92c', ink: '#3d2b05', sub: '#6d5210', kick: '#8a5800' },
	night: { from: '#1a2150', to: '#0a0e2a', ink: '#ffffff', sub: '#b9c2ea', kick: '#ffd166' },
	violet: { from: '#542a8f', to: '#22093f', ink: '#fdf4ff', sub: '#d9bcf7', kick: '#f0abfc' },
	fire: { from: '#8a2d0e', to: '#2e0a06', ink: '#fff7ed', sub: '#fdc99b', kick: '#fbbf24' },
	sky: { from: '#eaf4ff', to: '#bcd8f5', ink: '#12294f', sub: '#42618f', kick: '#1d4ed8' },
	mint: { from: '#eafcf2', to: '#bfeed5', ink: '#083b2b', sub: '#256a52', kick: '#047857' },
	sunset: { from: '#ff8b3d', to: '#b32964', ink: '#ffffff', sub: '#ffe3ea', kick: '#ffe45e' },
	slate: { from: '#2b3950', to: '#131c2b', ink: '#f2f6fb', sub: '#9fb0c6', kick: '#34d399' },
	frost: { from: '#24507e', to: '#0b1a30', ink: '#f0f7ff', sub: '#aecbe9', kick: '#fca5a5' },
	bloom: { from: '#ffe3ee', to: '#fff3c4', ink: '#2c2233', sub: '#6c5c74', kick: '#db2777' },
	spooky: { from: '#d3590f', to: '#2a0a3d', ink: '#fff7ed', sub: '#f3bd9c', kick: '#facc15' }
};

export function scenePalette(scene: string): ScenePalette {
	return SCENE_PALETTE[scene] ?? SCENE_PALETTE.gold;
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
