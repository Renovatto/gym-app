import { api } from './api';

/*
 * Web Push do aviso de fim do descanso.
 *
 * Por que existe: com o app em segundo plano o sistema congela o JavaScript da tela
 * (o iOS quase na hora), entao o timer do descanso para e nenhum aviso sai. O push
 * inverte quem avisa: a tela diz ao servidor "o descanso acaba em N segundos", o
 * servidor envia na hora certa e o service worker mostra a notificacao mesmo com o
 * app fechado ou a tela bloqueada.
 *
 * Onde funciona: Android (Chrome, instalado ou nao) e iOS 16.4+ SOMENTE com o app
 * instalado na tela inicial. No Safari em aba comum nao ha PushManager, e todas as
 * funcoes daqui viram no-op - a tela segue com o bipe/toast de sempre.
 */

// Cache da assinatura desta abertura do app: registrar no servidor uma vez basta.
let registeredSubscription: Promise<boolean> | null = null;

export function isPushSupported(): boolean {
	return (
		typeof window !== 'undefined' &&
		'serviceWorker' in navigator &&
		'PushManager' in window &&
		'Notification' in window
	);
}

// navigator.serviceWorker.ready nunca resolve se nao houver service worker (ex.:
// dev sem registro). O limite evita deixar uma promessa pendurada para sempre.
async function readyRegistration(): Promise<ServiceWorkerRegistration | null> {
	const timeout = new Promise<null>((resolve) => setTimeout(() => resolve(null), 5000));
	return Promise.race([navigator.serviceWorker.ready, timeout]);
}

// A chave VAPID chega em base64 "de URL"; o PushManager quer os bytes crus.
function base64UrlToBytes(base64Url: string): Uint8Array<ArrayBuffer> {
	const padding = '='.repeat((4 - (base64Url.length % 4)) % 4);
	const base64 = (base64Url + padding).replace(/-/g, '+').replace(/_/g, '/');
	const binary = atob(base64);
	const bytes = new Uint8Array(new ArrayBuffer(binary.length));
	for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
	return bytes;
}

async function subscribeThisDevice(): Promise<boolean> {
	const registration = await readyRegistration();
	if (!registration) return false;
	const { public_key: publicKey } = await api.getPushPublicKey();
	if (!publicKey) return false; // servidor sem chaves VAPID: push desligado

	const subscription =
		(await registration.pushManager.getSubscription()) ??
		(await registration.pushManager.subscribe({
			// userVisibleOnly e obrigatorio: todo push precisa virar notificacao visivel
			userVisibleOnly: true,
			applicationServerKey: base64UrlToBytes(publicKey)
		}));
	const keys = subscription.toJSON().keys;
	if (!keys?.p256dh || !keys.auth) return false;
	await api.savePushSubscription({
		endpoint: subscription.endpoint,
		p256dh: keys.p256dh,
		auth: keys.auth
	});
	return true;
}

/**
 * Garante que este aparelho esta assinado e registrado no servidor. So assina com a
 * permissao ja concedida (pedir permissao e da tela, dentro de um toque do usuario).
 * Devolve false quando o push nao esta disponivel, sem nunca lancar erro.
 */
export function ensurePushSubscription(): Promise<boolean> {
	if (!isPushSupported() || Notification.permission !== 'granted') {
		return Promise.resolve(false);
	}
	registeredSubscription ??= subscribeThisDevice().catch(() => {
		registeredSubscription = null; // falhou: tenta de novo no proximo descanso
		return false;
	});
	return registeredSubscription;
}

/**
 * Agenda no servidor o aviso de fim do descanso. Devolve true se ficou agendado -
 * nesse caso quem avisa com o app em segundo plano e o push, nao a tela.
 */
export async function scheduleRestTimerPush(timer: {
	workoutSessionId: number;
	secondsRemaining: number;
	title: string;
	body: string;
}): Promise<boolean> {
	if (!(await ensurePushSubscription())) return false;
	try {
		await api.scheduleRestTimerPush({
			workout_session_id: timer.workoutSessionId,
			seconds_remaining: Math.max(1, Math.round(timer.secondsRemaining)),
			title: timer.title,
			body: timer.body
		});
		return true;
	} catch {
		return false;
	}
}

// Cancela o aviso pendente. Silencioso: se falhar, o pior caso e um aviso sobrando.
export function cancelRestTimerPush(): void {
	if (!isPushSupported() || Notification.permission !== 'granted') return;
	api.cancelRestTimerPush().catch(() => {});
}

/**
 * Notificacao local pelo service worker, para quando o push nao esta disponivel mas
 * o JavaScript ainda roda em segundo plano (Android com a aba oculta). `new
 * Notification()` nao serve: o Chrome do Android recusa quando ha service worker, e
 * o iOS nao tem esse construtor.
 */
export async function showLocalNotification(title: string, body: string, url: string): Promise<void> {
	if (!isPushSupported() || Notification.permission !== 'granted') return;
	const registration = await readyRegistration();
	await registration?.showNotification(title, {
		body,
		tag: 'gymapp-rest',
		icon: '/icon-192.png',
		data: { url },
		// vibra no Android (o iOS ignora e usa a vibracao padrao do sistema)
		vibrate: [200, 100, 200]
	} as NotificationOptions);
}

/**
 * Ao sair da conta, desfaz a assinatura deste aparelho: sem isso o proximo descanso
 * de quem saiu poderia avisar aqui. O servidor descobre sozinho (o proximo envio
 * volta 410 e a linha e apagada), entao nao precisa de login para isso.
 */
export async function unsubscribeThisDevice(): Promise<void> {
	registeredSubscription = null;
	if (!isPushSupported()) return;
	const registration = await readyRegistration();
	const subscription = await registration?.pushManager.getSubscription();
	await subscription?.unsubscribe();
}
