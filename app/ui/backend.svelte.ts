// Which run of the backend this window is talking to. The backend gives a new id each time it
// starts; when the id changes, the backend restarted and every agent's program stopped with it.

const state = $state<{ boot: string | null; restarts: number }>({
  boot: null,
  restarts: 0,
});

export const backend = {
  /** How many times the backend has restarted since this window opened. Terminals watch this number. */
  get restarts(): number {
    return state.restarts;
  },
  /** Called with the id from any backend answer that carries one. */
  seen(boot: string | undefined): void {
    if (!boot) return;
    if (state.boot !== null && state.boot !== boot) state.restarts += 1;
    state.boot = boot;
  },
};
