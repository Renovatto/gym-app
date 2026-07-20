<script lang="ts">
	// Motor de celebracao (gamificacao): confete/particulas em canvas proprio + animacoes
	// CSS, portado do laboratorio de celebracoes. Mostra UMA celebracao por vez, lendo a
	// fila global (celebration.svelte.ts). O CONTEUDO (kicker/emoji/titulo/descricao) vem
	// de fora - normalmente da propria conquista real - e o 'slug' do CelebrationDef so
	// escolhe o efeito visual (confete/cenario/medalha).
	import { celebrationState, dismissCelebration } from '$lib/celebration.svelte';
	import { m } from '$lib/paraglide/messages';

	let stageEl = $state<HTMLDivElement | null>(null);
	let canvasEl = $state<HTMLCanvasElement | null>(null);
	let extraEl = $state<HTMLDivElement | null>(null);
	let domfxEl = $state<HTMLDivElement | null>(null);
	let titleEl = $state<HTMLDivElement | null>(null);

	const current = $derived(celebrationState.queue[0] ?? null);
	let scene = $state('paper');
	let stageClasses = $state('');

	const reduced =
		typeof matchMedia !== 'undefined' && matchMedia('(prefers-reduced-motion: reduce)').matches;

	/* ================= motor de particulas (canvas) ================= */
	let ctx: CanvasRenderingContext2D | null = null;
	let parts: Part[] = [];
	let customs: Custom[] = [];
	let raf = 0;
	const rnd = (a: number, b: number) => a + Math.random() * (b - a);
	const pick = <T,>(arr: T[]): T => arr[(Math.random() * arr.length) | 0];
	const CONF = ['#10b981', '#f59e0b', '#3b82f6', '#ec4899', '#8b5cf6', '#ef4444', '#14b8a6', '#facc15'];
	const GOLD = ['#fde68a', '#fbbf24', '#f59e0b', '#fff7d6'];

	interface Part {
		x: number; y: number; vx: number; vy: number; g: number; drag: number;
		rot: number; vr: number; size: number; life: number; ttl: number;
		color: string; type: string; sway: number; char?: string;
	}
	interface Custom { t: number; dur: number; draw: (c: CanvasRenderingContext2D, k: number, w: number, h: number) => void; }

	function P(o: Partial<Part>): Part {
		return {
			x: 0, y: 0, vx: 0, vy: 0, g: 0.16, drag: 0.992, rot: rnd(0, 6.3), vr: rnd(-0.25, 0.25),
			size: rnd(5, 10), life: 0, ttl: rnd(60, 95), color: pick(CONF), type: 'rect', sway: 0, ...o
		};
	}
	function star5(c: CanvasRenderingContext2D, r: number): void {
		c.beginPath();
		for (let i = 0; i < 10; i++) {
			const a = (Math.PI / 5) * i - Math.PI / 2;
			const rr = i % 2 ? r * 0.45 : r;
			const x = Math.cos(a) * rr, y = Math.sin(a) * rr;
			i ? c.lineTo(x, y) : c.moveTo(x, y);
		}
		c.closePath();
	}
	function drawP(c: CanvasRenderingContext2D, p: Part): void {
		const a = Math.max(0, 1 - p.life / p.ttl);
		c.save();
		c.globalAlpha = a;
		c.translate(p.x, p.y);
		if (p.type === 'rect') { c.rotate(p.rot); c.fillStyle = p.color; c.fillRect(-p.size / 2, -p.size / 2, p.size, p.size * 0.62); }
		else if (p.type === 'circle') { c.fillStyle = p.color; c.beginPath(); c.arc(0, 0, p.size / 2, 0, 6.3); c.fill(); }
		else if (p.type === 'star') { c.rotate(p.rot); c.fillStyle = p.color; star5(c, p.size / 2 + 2); c.fill(); }
		else if (p.type === 'spark') { c.strokeStyle = p.color; c.lineWidth = 2; c.beginPath(); c.moveTo(0, 0); c.lineTo(-p.vx * 2.4, -p.vy * 2.4); c.stroke(); }
		else if (p.type === 'emoji' && p.char) { c.font = p.size + 'px system-ui'; c.textAlign = 'center'; c.textBaseline = 'middle'; c.fillText(p.char, 0, 0); }
		else if (p.type === 'coin') { const s = Math.abs(Math.cos(p.life * 0.16)) * 0.85 + 0.15; c.rotate(p.rot * 0.2); c.scale(s, 1); c.fillStyle = '#fbbf24'; c.beginPath(); c.arc(0, 0, p.size / 2 + 2, 0, 6.3); c.fill(); c.strokeStyle = '#b45309'; c.lineWidth = 2; c.stroke(); }
		else if (p.type === 'ribbon') { c.rotate(p.rot); c.fillStyle = p.color; c.fillRect(-2.5, -p.size, 5, p.size * 2.2); }
		c.restore();
	}

	function sizeCanvas(): void {
		if (!canvasEl || !stageEl) return;
		const r = stageEl.getBoundingClientRect();
		const d = Math.min(devicePixelRatio || 1, 2);
		canvasEl.width = r.width * d;
		canvasEl.height = r.height * d;
		ctx?.setTransform(d, 0, 0, d, 0, 0);
	}

	function loop(): void {
		if (!ctx || !canvasEl) return;
		const W = canvasEl.getBoundingClientRect().width, H = canvasEl.getBoundingClientRect().height;
		ctx.clearRect(0, 0, W, H);
		const born: Part[] = [];
		parts = parts.filter((p) => {
			p.life++;
			if (p.type === 'rocket') {
				p.x += p.vx; p.y += p.vy; p.vy += p.g;
				born.push(P({ x: p.x, y: p.y, vx: 0, vy: 0, g: 0, size: rnd(2, 4), ttl: 16, color: '#fde68a', type: 'circle' }));
				if (p.vy >= -0.8 || p.life > p.ttl) {
					born.push(...mkBurst(p.x, p.y, { n: 72, colors: [p.color, '#fff', '#ffd166', ...CONF], speed: [1.8, 6.4], g: 0.05, ttl: [44, 84], types: ['circle', 'spark', 'star'], size: [3, 7] }));
					return false;
				}
			} else if (p.type === 'meteor') {
				p.x += p.vx; p.y += p.vy;
				born.push(P({ x: p.x, y: p.y, vx: rnd(-0.3, 0.3), vy: rnd(-0.3, 0.3), g: 0, size: p.size * rnd(0.4, 0.8), ttl: 22, color: p.color, type: 'circle' }));
				if (p.life > p.ttl) return false;
			} else {
				p.vx *= p.drag; p.vy *= p.drag; p.vy += p.g; p.x += p.vx; p.y += p.vy; p.rot += p.vr;
				if (p.sway) p.x += Math.sin(p.life * 0.12 + p.rot) * p.sway;
				if (p.life > p.ttl) return false;
			}
			drawP(ctx!, p);
			return true;
		});
		parts.push(...born);
		customs = customs.filter((c) => { c.t++; c.draw(ctx!, Math.min(1, c.t / c.dur), W, H); return c.t < c.dur; });
		if (parts.length || customs.length) raf = requestAnimationFrame(loop);
		else { raf = 0; ctx.clearRect(0, 0, W, H); }
	}
	function spawn(list: Part[]): void { if (reduced) return; parts.push(...list); if (!raf) raf = requestAnimationFrame(loop); }
	function addCustom(c: Custom): void { if (reduced) return; customs.push(c); if (!raf) raf = requestAnimationFrame(loop); }

	function mkBurst(cx: number, cy: number, o: Partial<{ n: number; colors: string[]; speed: [number, number]; g: number; ttl: [number, number]; types: string[]; size: [number, number]; up: number; angFrom: number; angTo: number }> = {}): Part[] {
		const { n = 90, colors = CONF, speed = [3, 9], g = 0.16, ttl = [55, 95], types = ['rect', 'circle'], size = [5, 11], up = 3.2, angFrom = 0, angTo = Math.PI * 2 } = o;
		const out: Part[] = [];
		for (let i = 0; i < n; i++) {
			const a = rnd(angFrom, angTo), sp = rnd(speed[0], speed[1]);
			out.push(P({ x: cx, y: cy, vx: Math.cos(a) * sp, vy: Math.sin(a) * sp - up, g, ttl: rnd(ttl[0], ttl[1]), color: pick(colors), type: pick(types), size: rnd(size[0], size[1]) }));
		}
		return out;
	}
	function dims(): { width: number; height: number } {
		return canvasEl?.getBoundingClientRect() ?? { width: 300, height: 400 };
	}

	/* helpers de efeito (mesmo toolkit do laboratorio) */
	function fxBurst(o: Parameters<typeof mkBurst>[2] = {}): void { const { width: W, height: H } = dims(); spawn(mkBurst(W / 2, H * 0.42, o)); }
	function fxCannons(): void {
		const { width: W, height: H } = dims();
		spawn(mkBurst(6, H - 10, { n: 55, angFrom: -Math.PI * 0.52, angTo: -Math.PI * 0.2, speed: [6, 12], up: 0 }));
		spawn(mkBurst(W - 6, H - 10, { n: 55, angFrom: -Math.PI * 0.8, angTo: -Math.PI * 0.48, speed: [6, 12], up: 0 }));
	}
	function fxRain(types: string[], n: number, colors?: string[]): void {
		const { width: W } = dims();
		let c = 0;
		const iv = setInterval(() => {
			if (++c > n) { clearInterval(iv); return; }
			spawn([P({ x: rnd(0, W), y: -12, vx: rnd(-0.6, 0.6), vy: rnd(1, 2.6), g: 0.035, ttl: rnd(120, 170), type: pick(types), color: pick(colors || CONF), sway: rnd(0.4, 1.2), size: rnd(5, 10) })]);
		}, 32);
		ivs.push(iv);
	}
	function fxEmojiRain(chars: string[], n: number): void {
		const { width: W } = dims();
		let c = 0;
		const iv = setInterval(() => {
			if (++c > n) { clearInterval(iv); return; }
			spawn([P({ x: rnd(0, W), y: -16, vx: rnd(-0.4, 0.4), vy: rnd(1, 2.2), g: 0.03, ttl: rnd(110, 150), type: 'emoji', char: pick(chars), size: rnd(18, 26), sway: rnd(0.4, 1) })]);
		}, 68);
		ivs.push(iv);
	}
	function fxSnow(): void {
		const { width: W } = dims();
		let c = 0;
		const iv = setInterval(() => {
			if (++c > 80) { clearInterval(iv); return; }
			spawn([P({ x: rnd(0, W), y: -10, vx: rnd(-0.3, 0.3), vy: rnd(0.6, 1.4), g: 0.01, ttl: rnd(190, 270), type: 'circle', color: pick(['#ffffff', '#e0f2ff', '#dbeafe']), size: rnd(3, 7), sway: rnd(0.5, 1.3) })]);
		}, 48);
		ivs.push(iv);
	}
	function fxFireworks(n: number, opts?: { step?: number }): void {
		const { width: W, height: H } = dims();
		const step = opts?.step || 560;
		for (let i = 0; i < n; i++) later(() => spawn([P({ x: rnd(W * 0.16, W * 0.84), y: H + 8, vx: rnd(-0.7, 0.7), vy: rnd(-9.8, -8), g: 0.13, ttl: 70, type: 'rocket', color: pick(CONF) })]), i * step);
	}
	function fxSpiral(): void {
		const { width: W, height: H } = dims();
		for (let i = 0; i < 46; i++) {
			const a = i * 0.42, r = 8 + i * 2.6;
			later(() => spawn([P({ x: W / 2 + Math.cos(a) * r, y: H * 0.42 + Math.sin(a) * r, vx: Math.cos(a) * 1.6, vy: Math.sin(a) * 1.6 - 0.6, g: 0.02, ttl: 60, type: i % 3 ? 'circle' : 'star', color: pick(GOLD), size: rnd(4, 8) })]), i * 30);
		}
	}
	function fxFountain(type: string): void {
		const { width: W, height: H } = dims();
		let c = 0;
		const iv = setInterval(() => {
			if (++c > 34) { clearInterval(iv); return; }
			spawn([P({ x: W / 2 + rnd(-16, 16), y: H - 8, vx: rnd(-2.6, 2.6), vy: rnd(-9.5, -7), g: 0.24, ttl: rnd(60, 90), type, size: rnd(9, 14) })]);
		}, 50);
		ivs.push(iv);
	}
	function fxEmojiBurst(chars: string[]): void {
		const { width: W, height: H } = dims();
		spawn(mkBurst(W / 2, H * 0.42, { n: 26, types: ['emoji'], speed: [2.5, 7], size: [18, 30], ttl: [55, 85] }).map((p) => ((p.char = pick(chars)), p)));
	}
	function fxEmbers(): void {
		const { width: W, height: H } = dims();
		let c = 0;
		const iv = setInterval(() => {
			if (++c > 60) { clearInterval(iv); return; }
			spawn([P({ x: rnd(W * 0.2, W * 0.8), y: H - 6, vx: rnd(-0.5, 0.5), vy: rnd(-2.4, -1.2), g: -0.012, ttl: rnd(60, 100), type: 'circle', color: pick(['#fbbf24', '#f97316', '#fde68a']), size: rnd(2.5, 5), sway: rnd(0.4, 1) })]);
		}, 34);
		ivs.push(iv);
	}
	function fxDust(yRatio: number): void {
		const { width: W, height: H } = dims();
		spawn(mkBurst(W / 2, H * yRatio, { n: 26, colors: ['#d6d3d1', '#a8a29e', '#e7e5e4'], speed: [1.5, 4], g: 0.1, up: 1.4, ttl: [26, 44], types: ['circle'], size: [3, 7] }));
	}
	function fxStarsFall(): void { fxRain(['star'], 46, GOLD); }
	function fxGoldRain(): void { fxRain(['rect', 'circle', 'star'], 80, GOLD); }
	function fxMeteor(golden = false): void {
		const { width: W, height: H } = dims();
		spawn([P({ x: -16, y: H * 0.16, vx: 7.4, vy: 2.4, g: 0, ttl: Math.ceil((W + 40) / 7.4), type: 'meteor', color: golden ? '#fde68a' : '#93c5fd', size: 7 })]);
	}
	function fxConstellation(pts: [number, number][], revealFrames: number, holdFrames: number): void {
		const reveal = revealFrames || 320;
		const hold = holdFrames != null ? holdFrames : 1800;
		let frame = 0;
		addCustom({ t: 0, dur: reveal + hold, draw(c, _k, W, H) {
			frame++;
			const k = Math.min(1, frame / reveal);
			const P2 = pts.map(([px, py]) => [px * W, py * H]);
			P2.forEach(([x, y], i) => {
				const ap = Math.min(1, Math.max(0, k * 2.6 - i * 0.3));
				if (ap <= 0) return;
				c.save(); c.globalAlpha = ap; c.fillStyle = '#fff'; c.translate(x, y);
				star5(c, 5 + Math.sin(Math.min(frame, reveal) * 0.0625 + i) * 1.2);
				c.fill(); c.restore();
			});
			const lk = Math.max(0, (k - 0.42) / 0.58), seg = lk * (P2.length - 1);
			c.save(); c.strokeStyle = 'rgba(255,255,255,.6)'; c.lineWidth = 1.4; c.beginPath();
			for (let i = 0; i < Math.floor(seg); i++) { c.moveTo(P2[i][0], P2[i][1]); c.lineTo(P2[i + 1][0], P2[i + 1][1]); }
			const f = seg % 1, i0 = Math.floor(seg);
			if (i0 < P2.length - 1 && f > 0) { c.moveTo(P2[i0][0], P2[i0][1]); c.lineTo(P2[i0][0] + (P2[i0 + 1][0] - P2[i0][0]) * f, P2[i0][1] + (P2[i0 + 1][1] - P2[i0][1]) * f); }
			c.stroke(); c.restore();
		} });
	}
	const CONSTELLATION_CLASSIC: [number, number][] = [[0.2, 0.3], [0.34, 0.18], [0.5, 0.3], [0.62, 0.16], [0.78, 0.3], [0.68, 0.46]];
	const CONSTELLATION_RISING: [number, number][] = [[0.12, 0.68], [0.28, 0.55], [0.42, 0.6], [0.56, 0.4], [0.7, 0.45], [0.86, 0.22]];
	const CONSTELLATION_ARC: [number, number][] = [[0.15, 0.5], [0.28, 0.28], [0.42, 0.18], [0.58, 0.18], [0.72, 0.28], [0.85, 0.5]];

	/* dom fx */
	function domTwinkles(n: number, glyphs?: string[]): void {
		if (!domfxEl || reduced) return;
		for (let i = 0; i < n; i++) {
			const s = document.createElement('span');
			s.className = 'ce-twk';
			s.textContent = pick(glyphs || ['✦', '✧', '✨']);
			s.style.left = rnd(8, 88) + '%'; s.style.top = rnd(10, 78) + '%';
			s.style.animationDelay = rnd(0, 1.5) + 's'; s.style.fontSize = rnd(11, 20) + 'px';
			domfxEl.appendChild(s);
		}
	}
	function domPopmojis(chars: string[], n: number): void {
		if (!domfxEl || reduced) return;
		for (let i = 0; i < n; i++) {
			const s = document.createElement('span');
			s.className = 'ce-popmoji'; s.textContent = pick(chars);
			s.style.left = rnd(10, 84) + '%'; s.style.top = rnd(46, 80) + '%'; s.style.animationDelay = i * 0.17 + 's';
			domfxEl.appendChild(s);
		}
	}
	function domOrbit(): void {
		if (!domfxEl || reduced) return;
		for (let i = 0; i < 3; i++) {
			const o = document.createElement('span');
			o.className = 'ce-orbit'; o.style.animationDelay = i * 0.3 + 's'; o.innerHTML = '<span>⭐</span>';
			domfxEl.appendChild(o);
		}
	}
	function domBalloons(count: number, delayStep: number): void {
		if (!domfxEl || reduced) return;
		const cols = ['#ef4444', '#f59e0b', '#3b82f6', '#ec4899', '#10b981', '#8b5cf6', '#f472b6', '#22d3ee'];
		for (let i = 0; i < count; i++) {
			const b = document.createElement('span');
			b.className = 'ce-balloon';
			b.style.left = rnd(6, 88) + '%';
			b.style.background = `radial-gradient(circle at 35% 30%, rgb(255 255 255 / .55), transparent 40%),${cols[i % cols.length]}`;
			b.style.animationDelay = i * delayStep + 's';
			b.style.transform = `scale(${rnd(0.85, 1.2).toFixed(2)})`;
			domfxEl.appendChild(b);
		}
	}
	function domBats(n: number): void {
		if (!domfxEl || reduced) return;
		for (let i = 0; i < n; i++) {
			const b = document.createElement('span');
			b.className = 'ce-bat'; b.textContent = '🦇';
			b.style.top = rnd(8, 55) + '%'; b.style.animationDelay = i * 0.4 + 's';
			domfxEl.appendChild(b);
		}
	}

	/* pendentes (limpos a cada play) */
	let tos: ReturnType<typeof setTimeout>[] = [];
	let ivs: ReturnType<typeof setInterval>[] = [];
	function later(fn: () => void, ms: number): void { tos.push(setTimeout(fn, ms)); }
	function clearPending(): void { tos.forEach(clearTimeout); ivs.forEach(clearInterval); tos = []; ivs = []; }

	/* letras saltitantes (usado na constelacao) */
	function jsLetters(txt: string, stagger = 0.09): void {
		if (!titleEl) return;
		titleEl.innerHTML = '';
		[...txt].forEach((ch, i) => {
			const s = document.createElement('span');
			s.className = 'ce-lt';
			s.style.animationDelay = i * stagger + 's';
			s.innerHTML = ch === ' ' ? '&nbsp;' : ch;
			titleEl!.appendChild(s);
		});
	}

	/* ================= slug -> efeito ================= */
	function runEffect(slug: string, content: { title: string; number?: number }): void {
		const number_ = content.number;
		const setBignum = (n: number | undefined) => {
			const el = extraEl?.querySelector<HTMLElement>('[data-n]');
			if (el && n != null) el.textContent = String(Math.round(n));
		};
		switch (slug) {
			case 'explosao-classica': fxBurst({ n: 120 }); break;
			case 'canhoes-laterais': fxCannons(); later(fxCannons, 420); break;
			case 'chuva-confete': fxRain(['rect', 'circle'], 90); break;
			case 'serpentinas': fxBurst({ n: 60, types: ['ribbon'], speed: [4, 10], ttl: [70, 110] }); break;
			case 'espiral-dourada': fxSpiral(); break;
			case 'chafariz-moedas': fxFountain('coin'); break;
			case 'peso-pesado': later(() => fxDust(0.6), 520); break;
			case 'ascensao-trofeu': later(() => fxBurst({ n: 50 }), 950); break;
			case 'orbita-estrelas': domOrbit(); break;
			case 'chama-acesa': fxEmbers(); break;
			case 'numero-brasa': fxEmbers(); setBignum(number_); break;
			case 'meteoro': fxMeteor(); later(() => domTwinkles(8), 650); break;
			case 'constelacao-classica': fxConstellation(CONSTELLATION_CLASSIC, 320, 1800); jsLetters(content.title); break;
			case 'constelacao-ascendente': fxConstellation(CONSTELLATION_RISING, 320, 1800); jsLetters(content.title); break;
			case 'constelacao-pico': fxConstellation(CONSTELLATION_ARC, 320, 1800); jsLetters(content.title); break;
			case 'aurora': fxRain(['star'], 18, ['#a7f3d0', '#bae6fd']); break;
			case 'chuva-estrelas': fxStarsFall(); domTwinkles(8); break;
			case 'combo-crescente': later(() => fxBurst({ n: 60 }), 1500); break;
			case 'semana-chamas':
				domfxEl?.querySelectorAll<HTMLElement>('.ce-dots b')?.forEach((b, i) => later(() => b.classList.add('hit'), 600 + i * 300));
				later(() => fxBurst({ n: 70, colors: ['#fbbf24', '#f97316', '#ef4444', '#fde68a'] }), 2900);
				break;
			case 'grande-slam': fxBurst({ n: 130 }); later(fxCannons, 460); break;
			case 'fogos-artificio': fxFireworks(5); break;
			case 'podio': later(() => fxBurst({ n: 70 }), 1350); break;
			case 'treino-marco':
				fxGoldRain();
				later(() => fxFireworks(5, { step: 440 }), 320);
				later(() => fxBurst({ n: 100, colors: GOLD }), 380);
				setBignum(number_);
				break;
			case 'foguete': {
				const { width: W, height: H } = dims();
				spawn([P({ x: W / 2, y: H + 10, vx: 0, vy: -9.8, g: 0.1, ttl: 78, type: 'rocket', color: '#60a5fa' })]);
				later(() => fxFireworks(10, { step: 560 }), 900);
				later(() => domTwinkles(8), 900);
				break;
			}
			case 'raios-solares': fxBurst({ n: 70 }); break;
			case 'contador-epico': {
				const goal = Math.max(1, Math.round(number_ ?? 1));
				let v = 1;
				setBignum(v);
				const iv = setInterval(() => {
					v++;
					if (v > goal) { clearInterval(iv); fxBurst({ n: 90 }); return; }
					setBignum(v);
				}, 380);
				ivs.push(iv);
				break;
			}
			case 'aniversario-bolo': domTwinkles(10, ['✨', '🕯️']); later(() => fxBurst({ n: 80 }), 650); break;
			case 'aniversario-baloes': domBalloons(18, 0.22); fxRain(['star'], 30, ['#fff', '#ffe45e']); break;
			case 'natal':
				fxSnow();
				later(() => domTwinkles(10, ['✨', '❄️']), 400);
				later(() => fxBurst({ n: 70, colors: ['#ef4444', '#16a34a', '#fbbf24', '#fff'] }), 650);
				break;
			case 'ano-novo': fxFireworks(7); break;
			case 'pascoa':
				fxEmojiRain(['🥚', '🐣', '🌷', '🌸'], 26);
				later(() => fxBurst({ n: 50, colors: ['#fbcfe8', '#a7f3d0', '#fde68a', '#c4b5fd'] }), 400);
				break;
			case 'halloween': domBats(6); later(() => fxEmojiBurst(['🎃', '👻', '🦇', '🍬']), 340); break;
			default: break; // forja-brilhante/giro-moeda/batimento/onda-choque/titulo-virado: so CSS, sem fx
		}
	}

	/* ================= reproducao ================= */
	let advanceTimer: ReturnType<typeof setTimeout> | null = null;

	function play(item: NonNullable<typeof current>): void {
		clearPending();
		parts = []; customs = [];
		if (domfxEl) domfxEl.innerHTML = '';
		if (extraEl) extraEl.innerHTML = '';
		if (advanceTimer) clearTimeout(advanceTimer);

		scene = item.def.scene;
		stageClasses = '';
		sizeCanvas();
		ctx?.clearRect(0, 0, canvasEl?.width ?? 0, canvasEl?.height ?? 0);

		requestAnimationFrame(() => {
			if (extraEl && item.def.extra) extraEl.innerHTML = item.def.extra;
			stageClasses = 'on ' + item.def.cls;
			if (!item.def.cls.includes('t-js') && titleEl) titleEl.textContent = item.content.title;
			if (!reduced) runEffect(item.def.slug, item.content);
		});

		if (item.def.dur > 0) {
			advanceTimer = setTimeout(() => dismissCelebration(), item.def.dur);
		}
	}

	$effect(() => {
		if (current) play(current);
	});

	$effect(() => {
		sizeCanvas();
	});

	$effect(() => {
		return () => {
			clearPending();
			if (advanceTimer) clearTimeout(advanceTimer);
		};
	});

	function skip(): void {
		if (advanceTimer) clearTimeout(advanceTimer);
		dismissCelebration();
	}
</script>

{#if current}
	<div
		class="ce-backdrop"
		role="button"
		tabindex="-1"
		onclick={skip}
		onkeydown={(e) => e.key === 'Escape' && skip()}
	>
		<div class="ce-stage {stageClasses}" data-scene={scene} bind:this={stageEl}>
			<div class="ce-aurora"><i></i><i></i></div>
			<div class="ce-rays"></div>
			<canvas bind:this={canvasEl}></canvas>
			<div class="ce-shock"><i></i><i></i><i></i></div>
			<div class="ce-extra" bind:this={extraEl}></div>
			<div class="ce-domfx" bind:this={domfxEl}></div>
			<div class="ce-content">
				<span class="ce-kicker">{current.content.kicker}</span>
				<div class="ce-medal-wrap">
					<span class="ce-ring"></span><span class="ce-ring2"></span>
					<div class="ce-medal"><span>{current.content.emoji}</span></div>
				</div>
				<div class="ce-title" bind:this={titleEl}>{current.content.title}</div>
				<div class="ce-desc">{current.content.desc}</div>
			</div>
			<div class="ce-flash"></div>
			<button type="button" class="ce-close" aria-label={m.close()} onclick={skip}>
				<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M6 6l12 12M18 6L6 18" /></svg>
			</button>
		</div>
	</div>
{/if}

<style>
	.ce-backdrop {
		position: fixed; inset: 0; z-index: 70; display: grid; place-items: center;
		background: rgb(0 0 0 / 0.55); padding: 20px; animation: ceFadeBg 0.25s ease-out both;
	}
	@keyframes ceFadeBg { from { opacity: 0; } }
	.ce-stage {
		position: relative; width: 100%; max-width: 340px; height: 380px; border-radius: 28px;
		overflow: hidden; box-shadow: 0 24px 60px -20px rgb(0 0 0 / 0.6);
		animation: cePopStage 0.3s cubic-bezier(0.2, 1.2, 0.4, 1) both;
		--sk-ink: #1a2420; --sk-sub: #5c6b62; --sk-kick: #059669;
		--sk-bg: linear-gradient(160deg, #eef4f0, #d9e3dc);
	}
	@keyframes cePopStage { from { transform: scale(0.9); opacity: 0; } }
	.ce-stage::before { content: ''; position: absolute; inset: 0; background: var(--sk-bg); }

	.ce-stage[data-scene='paper'] { --sk-bg: radial-gradient(120% 90% at 50% 0%, #f6faf7, #dde7e0); --sk-ink: #17211c; --sk-sub: #5a6a60; --sk-kick: #047857; }
	.ce-stage[data-scene='gold'] { --sk-bg: radial-gradient(120% 90% at 50% 10%, #fff6da, #f7ce62 55%, #e9a92c); --sk-ink: #3d2b05; --sk-sub: #6d5210; --sk-kick: #8a5800; }
	.ce-stage[data-scene='night'] { --sk-bg: radial-gradient(130% 100% at 50% 0%, #1a2150, #0a0e2a 70%); --sk-ink: #fff; --sk-sub: #b9c2ea; --sk-kick: #ffd166; }
	.ce-stage[data-scene='violet'] { --sk-bg: radial-gradient(130% 100% at 50% 0%, #542a8f, #22093f 75%); --sk-ink: #fdf4ff; --sk-sub: #d9bcf7; --sk-kick: #f0abfc; }
	.ce-stage[data-scene='fire'] { --sk-bg: radial-gradient(130% 100% at 50% 100%, #8a2d0e, #2e0a06 70%); --sk-ink: #fff7ed; --sk-sub: #fdc99b; --sk-kick: #fbbf24; }
	.ce-stage[data-scene='sky'] { --sk-bg: radial-gradient(120% 90% at 50% 0%, #eaf4ff, #bcd8f5); --sk-ink: #12294f; --sk-sub: #42618f; --sk-kick: #1d4ed8; }
	.ce-stage[data-scene='mint'] { --sk-bg: radial-gradient(120% 90% at 50% 0%, #eafcf2, #bfeed5); --sk-ink: #083b2b; --sk-sub: #256a52; --sk-kick: #047857; }
	.ce-stage[data-scene='sunset'] { --sk-bg: linear-gradient(165deg, #ff8b3d, #e5487f 70%, #b32964); --sk-ink: #fff; --sk-sub: #ffe3ea; --sk-kick: #ffe45e; }
	.ce-stage[data-scene='slate'] { --sk-bg: radial-gradient(130% 100% at 50% 0%, #2b3950, #131c2b 75%); --sk-ink: #f2f6fb; --sk-sub: #9fb0c6; --sk-kick: #34d399; }
	.ce-stage[data-scene='frost'] { --sk-bg: radial-gradient(130% 100% at 50% 0%, #24507e, #0b1a30 75%); --sk-ink: #f0f7ff; --sk-sub: #aecbe9; --sk-kick: #fca5a5; }
	.ce-stage[data-scene='bloom'] { --sk-bg: linear-gradient(160deg, #ffe3ee, #d6f3e2 55%, #fff3c4); --sk-ink: #2c2233; --sk-sub: #6c5c74; --sk-kick: #db2777; }
	.ce-stage[data-scene='spooky'] { --sk-bg: radial-gradient(130% 110% at 50% 105%, #d3590f, #2a0a3d 65%); --sk-ink: #fff7ed; --sk-sub: #f3bd9c; --sk-kick: #facc15; }

	.ce-stage canvas { position: absolute; inset: 0; width: 100%; height: 100%; z-index: 6; pointer-events: none; }
	.ce-rays, .ce-shock, .ce-flash, .ce-aurora, .ce-domfx, .ce-extra { position: absolute; inset: 0; pointer-events: none; }
	.ce-rays { z-index: 1; display: grid; place-items: center; opacity: 0; }
	.ce-rays::before { content: ''; width: 300px; height: 300px; border-radius: 50%; background: repeating-conic-gradient(from 0deg, rgb(255 255 255 / 0.22) 0 9deg, transparent 9deg 22deg); }
	.ce-stage.on.x-rays .ce-rays { opacity: 1; animation: ceRaysSpin 7s linear infinite, ceFadeIn 0.65s both; }
	.ce-stage.on.x-raysoft .ce-rays { opacity: 0.55; animation: ceRaysSpin 10s linear infinite, ceFadeIn 1s both; }
	@keyframes ceRaysSpin { to { transform: rotate(360deg); } }

	.ce-shock { z-index: 2; display: grid; place-items: center; }
	.ce-shock i { position: absolute; width: 90px; height: 90px; border-radius: 50%; border: 3px solid var(--sk-ink); opacity: 0; }
	.ce-stage.on.x-shock .ce-shock i { animation: ceShockGo 1.15s cubic-bezier(0.2, 0.7, 0.3, 1) both; }
	.ce-stage.on.x-shock .ce-shock i:nth-child(2) { animation-delay: 0.18s; }
	.ce-stage.on.x-shock .ce-shock i:nth-child(3) { animation-delay: 0.36s; }
	@keyframes ceShockGo { 0% { transform: scale(0.4); opacity: 0.8; } 100% { transform: scale(4.2); opacity: 0; } }

	.ce-flash { z-index: 7; background: #fff; opacity: 0; }
	.ce-stage.on.x-flash .ce-flash { animation: ceFlashGo 0.6s ease-out both; }
	@keyframes ceFlashGo { 0% { opacity: 0.85; } 100% { opacity: 0; } }

	.ce-aurora { z-index: 1; opacity: 0; overflow: hidden; }
	.ce-aurora i { position: absolute; width: 150%; height: 60%; left: -25%; border-radius: 50%; filter: blur(26px); opacity: 0.5; }
	.ce-aurora i:first-child { top: -12%; background: linear-gradient(90deg, #34d399, #60a5fa, #a78bfa); }
	.ce-aurora i:last-child { top: 6%; background: linear-gradient(90deg, #f472b6, #34d399); opacity: 0.32; }
	.ce-stage.on.x-aurora .ce-aurora { opacity: 1; animation: ceFadeIn 1.3s both; }
	.ce-stage.on.x-aurora .ce-aurora i:first-child { animation: ceAur 6.5s ease-in-out infinite alternate; }
	.ce-stage.on.x-aurora .ce-aurora i:last-child { animation: ceAur 8s ease-in-out infinite alternate-reverse; }
	@keyframes ceAur { from { transform: translateX(-7%) rotate(-4deg); } to { transform: translateX(7%) rotate(4deg); } }
	@keyframes ceFadeIn { from { opacity: 0; } }

	.ce-stage.on.x-shake { animation: cePopStage 0.3s cubic-bezier(0.2, 1.2, 0.4, 1) both, ceShake 0.6s ease-out 0.4s; }
	@keyframes ceShake { 0%, 100% { transform: translate(0); } 20% { transform: translate(-5px, 3px); } 40% { transform: translate(5px, -3px); } 60% { transform: translate(-4px, -2px); } 80% { transform: translate(3px, 2px); } }

	.ce-extra { z-index: 4; display: grid; place-items: center; }
	.ce-domfx { z-index: 6; overflow: hidden; }
	:global(.push-up) { transform: translateY(-92px); }

	.ce-content { position: absolute; inset: 0; z-index: 5; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 9px; padding: 24px; text-align: center; }
	.ce-kicker { font-size: 12px; font-weight: 800; letter-spacing: 0.12em; text-transform: uppercase; color: var(--sk-kick); opacity: 0; animation: ceRiseUp 0.6s ease-out 0.07s both; }
	.ce-medal-wrap { position: relative; opacity: 0; animation: cePopSoft 0.65s ease-out both; }
	.ce-medal { width: 108px; height: 108px; border-radius: 50%; display: grid; place-items: center; font-size: 54px; background: radial-gradient(circle at 50% 32%, #fff6dd, #ffe08a 55%, #eeb32a); box-shadow: 0 12px 32px -6px rgb(190 130 20 / 0.55); }
	.ce-ring, .ce-ring2 { position: absolute; inset: -10px; border-radius: 50%; border: 3px solid var(--sk-kick); opacity: 0; }
	.ce-title { font-size: 19px; font-weight: 850; letter-spacing: -0.02em; color: var(--sk-ink); opacity: 0; max-width: 100%; animation: ceRiseUp 0.65s ease-out 0.2s both; }
	.ce-desc { font-size: 13px; color: var(--sk-sub); max-width: 25ch; opacity: 0; animation: ceRiseUp 0.65s ease-out 0.32s both; }
	@keyframes ceRiseUp { from { transform: translateY(14px); opacity: 0; } to { transform: translateY(0); opacity: 1; } }
	@keyframes cePopSoft { from { transform: scale(0.6); opacity: 0; } to { transform: scale(1); opacity: 1; } }

	.ce-stage.on.m-pop .ce-medal-wrap { animation: cePopSpring 0.85s cubic-bezier(0.18, 1.6, 0.4, 1) both; }
	@keyframes cePopSpring { 0% { transform: scale(0.15); opacity: 0; } 62% { transform: scale(1.16); opacity: 1; } 82% { transform: scale(0.94); } 100% { transform: scale(1); opacity: 1; } }
	.ce-stage.on.m-drop .ce-medal-wrap { animation: ceDropIn 0.88s both; }
	@keyframes ceDropIn { 0% { transform: translateY(-220px); opacity: 0; } 45% { opacity: 1; } 58% { transform: translateY(0) scale(1, 1); } 70% { transform: translateY(0) scale(1.18, 0.78); } 84% { transform: translateY(-10px) scale(0.95, 1.06); } 100% { transform: translateY(0) scale(1); opacity: 1; } }
	.ce-stage.on.m-flip .ce-medal-wrap { animation: ceFlipY 1.05s cubic-bezier(0.2, 0.9, 0.3, 1) both; }
	@keyframes ceFlipY { 0% { transform: rotateY(560deg) scale(0.35); opacity: 0; } 100% { transform: rotateY(0) scale(1); opacity: 1; } }
	.ce-stage.on.m-slam .ce-medal-wrap { animation: ceSlamIn 0.55s cubic-bezier(0.5, 0, 0.4, 1) both; }
	@keyframes ceSlamIn { 0% { transform: scale(3); opacity: 0; } 55% { transform: scale(0.92); opacity: 1; } 100% { transform: scale(1); opacity: 1; } }
	.ce-stage.on.m-rise .ce-medal-wrap { animation: ceRiseBig 1.05s cubic-bezier(0.2, 1.1, 0.35, 1) both; }
	@keyframes ceRiseBig { 0% { transform: translateY(180px) scale(0.7); opacity: 0; } 100% { transform: translateY(0) scale(1); opacity: 1; } }
	.ce-stage.on.m-beat .ce-medal-wrap { animation: cePopSoft 0.5s both, ceBeat 1.9s ease-in-out 0.45s; }
	@keyframes ceBeat { 0%, 28%, 56%, 100% { transform: scale(1); } 12%, 40%, 68% { transform: scale(1.17); } }
	.ce-stage.on.m-none .ce-medal-wrap { display: none; }
	.ce-stage.on.m-late .ce-medal-wrap { animation: cePopSpring 0.8s cubic-bezier(0.18, 1.6, 0.4, 1) 1.2s both; }

	.ce-stage.on.r-pulse .ce-ring { animation: ceRingGo 1.3s ease-out 0.3s 2; }
	.ce-stage.on.r-pulse .ce-ring2 { animation: ceRingGo 1.3s ease-out 0.7s 2; }
	.ce-stage.on.r-beat .ce-ring { animation: ceRingGo 1.05s ease-out 0.55s 3; }
	@keyframes ceRingGo { 0% { transform: scale(0.75); opacity: 0.9; } 100% { transform: scale(1.65); opacity: 0; } }

	.ce-medal::after { content: ''; position: absolute; inset: 0; border-radius: 50%; background: linear-gradient(115deg, transparent 32%, rgb(255 255 255 / 0.9) 50%, transparent 68%); background-size: 280% 280%; background-position: 130% 0; opacity: 0; }
	.ce-stage.on.x-shine .ce-medal::after { opacity: 1; animation: ceShineGo 1.4s ease-in-out 0.3s 2; }
	@keyframes ceShineGo { from { background-position: 130% 0; } to { background-position: -130% 0; } }
	.ce-stage.on.x-glow .ce-medal { animation: ceGlowGo 1.8s ease-in-out 0.4s 2; }
	@keyframes ceGlowGo { 0%, 100% { box-shadow: 0 12px 32px -6px rgb(190 130 20 / 0.55); } 50% { box-shadow: 0 0 46px 6px rgb(255 214 100 / 0.95); } }

	.ce-stage.on.t-flipx .ce-title { animation: ceFlipX 0.8s cubic-bezier(0.2, 1.2, 0.4, 1) 0.25s both; }
	@keyframes ceFlipX { 0% { transform: rotateX(92deg); opacity: 0; } 100% { transform: rotateX(0); opacity: 1; } }
	.ce-stage.on.t-js .ce-title { animation: none; opacity: 1; }
	:global(.ce-lt) { display: inline-block; animation: ceLtPop 0.55s cubic-bezier(0.2, 1.6, 0.4, 1) both; }
	@keyframes ceLtPop { 0% { transform: translateY(110%) scale(0.6); opacity: 0; } 100% { transform: translateY(0) scale(1); opacity: 1; } }

	/* pecas de cena injetadas via innerHTML (fora do template Svelte -> precisam :global) */
	:global(.ce-bignum) { font-size: 82px; font-weight: 900; letter-spacing: -0.04em; color: var(--sk-ink); text-shadow: 0 6px 30px rgb(0 0 0 / 0.35); animation: ceBigPop 0.65s cubic-bezier(0.18, 1.5, 0.4, 1) both; }
	:global(.ce-bignum-gold) { background: linear-gradient(180deg, #fff3c4, #f4b62b); -webkit-background-clip: text; background-clip: text; color: transparent; filter: drop-shadow(0 8px 22px rgb(190 130 20 / 0.6)); }
	:global(.ce-bignum-mega) { font-size: 98px; }
	@keyframes ceBigPop { 0% { transform: scale(0.2); opacity: 0; } 65% { transform: scale(1.18); opacity: 1; } 100% { transform: scale(1); } }

	:global(.ce-combo) { position: absolute; left: 0; right: 0; top: 0; height: 82px; display: flex; align-items: center; justify-content: center; }
	:global(.ce-combo span) { position: absolute; font-size: 28px; font-weight: 900; color: var(--sk-kick); opacity: 0; text-shadow: 0 3px 10px rgb(0 0 0 / 0.3); animation: ceComboPop 0.6s cubic-bezier(0.2, 1.5, 0.4, 1) both; }
	:global(.ce-combo span:nth-child(1)) { animation-delay: 0.08s; transform: translate(-58px, -28px) rotate(-10deg); }
	:global(.ce-combo span:nth-child(2)) { animation-delay: 0.5s; transform: translate(54px, -14px) rotate(8deg); font-size: 34px; }
	:global(.ce-combo span:nth-child(3)) { animation-delay: 0.95s; transform: translate(-26px, 4px) rotate(-6deg); font-size: 40px; }
	@keyframes ceComboPop { 0% { opacity: 0; scale: 0.2; } 60% { opacity: 1; scale: 1.25; } 100% { opacity: 1; scale: 1; } }

	:global(.ce-dots) { position: absolute; bottom: 7%; left: 0; right: 0; display: flex; justify-content: center; gap: 7px; }
	:global(.ce-dots b) { width: 26px; height: 26px; border-radius: 8px; display: grid; place-items: center; font-size: 10px; font-weight: 800; color: var(--sk-sub); background: rgb(255 255 255 / 0.18); border: 1px solid rgb(255 255 255 / 0.25); animation: ceDotGo 0.4s ease-out both; }
	:global(.ce-dots b.hit) { color: #fff; background: linear-gradient(180deg, #fbbf24, #ea580c); border-color: transparent; }
	@keyframes ceDotGo { from { transform: translateY(10px); opacity: 0; } to { opacity: 1; } }

	:global(.ce-podium) { position: absolute; bottom: 4%; left: 0; right: 0; display: flex; justify-content: center; align-items: flex-end; gap: 7px; }
	:global(.ce-podium i) { width: 52px; border-radius: 10px 10px 0 0; background: linear-gradient(180deg, rgb(255 255 255 / 0.5), rgb(255 255 255 / 0.18)); transform-origin: bottom; animation: cePodGrow 0.72s cubic-bezier(0.2, 1.2, 0.4, 1) both; display: grid; place-items: center; font-weight: 900; color: var(--sk-ink); font-size: 12px; }
	:global(.ce-podium i:nth-child(1)) { height: 38px; animation-delay: 0.13s; }
	:global(.ce-podium i:nth-child(2)) { height: 58px; animation-delay: 0.36s; }
	:global(.ce-podium i:nth-child(3)) { height: 29px; animation-delay: 0.58s; }
	@keyframes cePodGrow { from { transform: scaleY(0); } to { transform: scaleY(1); } }

	:global(.ce-twk) { position: absolute; font-size: 15px; opacity: 0; animation: ceTwkGo 1.9s ease-in-out both; }
	@keyframes ceTwkGo { 0%, 100% { opacity: 0; transform: scale(0.3); } 40% { opacity: 1; transform: scale(1.15) rotate(18deg); } 70% { opacity: 0.6; transform: scale(0.85); } }
	:global(.ce-popmoji) { position: absolute; font-size: 24px; opacity: 0; animation: cePmGo 2s ease-out both; }
	@keyframes cePmGo { 0% { opacity: 0; transform: translateY(16px) scale(0.4); } 18% { opacity: 1; transform: translateY(0) scale(1.15); } 100% { opacity: 0; transform: translateY(-100px) scale(1); } }
	:global(.ce-bat) { position: absolute; font-size: 20px; top: 12%; left: -30px; animation: ceBatFly 3.4s ease-in-out both; }
	@keyframes ceBatFly { 0% { transform: translate(0, 0) scale(0.8); opacity: 0; } 10% { opacity: 1; } 50% { transform: translate(130px, -14px) scale(1); } 100% { transform: translate(290px, 10px) scale(0.9); opacity: 0; } }
	:global(.ce-balloon) { position: absolute; bottom: -70px; width: 34px; height: 46px; border-radius: 50% 50% 48% 48%; animation: ceBalUp 8.5s ease-in both; }
	@keyframes ceBalUp { 0% { transform: translateY(0) rotate(-3deg); } 50% { transform: translateY(-46vh) rotate(4deg); } 100% { transform: translateY(-400px) rotate(-3deg); } }
	:global(.ce-orbit) { position: absolute; top: 50%; left: 50%; width: 0; height: 0; animation: ceOrbGo 3.1s linear both; }
	:global(.ce-orbit span) { position: absolute; left: 60px; top: -9px; font-size: 18px; }
	@keyframes ceOrbGo { from { transform: rotate(0); opacity: 1; } 90% { opacity: 1; } to { transform: rotate(680deg); opacity: 0; } }

	.ce-close {
		position: absolute; top: 10px; right: 10px; z-index: 9; width: 32px; height: 32px;
		border-radius: 50%; border: none; cursor: pointer; display: grid; place-items: center;
		color: var(--sk-ink); background: rgb(255 255 255 / 0.25);
	}
	.ce-close svg { width: 16px; height: 16px; }

	@media (prefers-reduced-motion: reduce) {
		.ce-stage, .ce-stage * { animation: none !important; }
		.ce-kicker, .ce-medal-wrap, .ce-title, .ce-desc { opacity: 1 !important; }
		.ce-rays, .ce-aurora, .ce-domfx { display: none; }
	}
</style>
