/**
 * Toast global. Regra do projeto: TODA mutacao confirma com um toast agradavel -
 * o usuario nunca fica sem retorno visual de que a acao funcionou.
 */
interface ToastState {
	message: string;
	visible: boolean;
}

export const toastState = $state<ToastState>({ message: '', visible: false });

let timer: ReturnType<typeof setTimeout> | null = null;

export function showToast(message: string, durationMs = 4000): void {
	toastState.message = message;
	toastState.visible = true;
	if (timer) clearTimeout(timer);
	timer = setTimeout(() => {
		toastState.visible = false;
	}, durationMs);
}
