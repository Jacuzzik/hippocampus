// Start-up work the loading screen waits for: the vault graph and each agent's terminal.
// A piece of work calls bootTask() when it starts and runs the returned function when it settles.

let count = $state(0);

/** Registers a start-up task. Call the returned function once the task has finished or failed. */
export function bootTask(): () => void {
  count += 1;
  let done = false;
  return () => {
    if (done) return;
    done = true;
    count -= 1;
  };
}

/** True while any start-up task is still running. */
export const boot = {
  get busy(): boolean {
    return count > 0;
  },
};
