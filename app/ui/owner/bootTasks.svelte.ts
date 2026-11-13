// Start-up work the loading screen waits for: the vault graph and each agent's terminal.
// A piece of work calls bootTask("what it is") when it starts and runs the returned function when it settles.

type Step = { name: string; done: boolean };
const steps = $state<Step[]>([]);

/** Registers a start-up task. Call the returned function once the task has finished or failed. */
export function bootTask(name = "Starting"): () => void {
  const index = steps.push({ name, done: false }) - 1;
  return () => {
    const step = steps[index];
    if (step) step.done = true;
  };
}

/** True while any start-up task is still running; `steps` lists each task by name for the loading screen. */
export const boot = {
  get busy(): boolean {
    return steps.some((s) => !s.done);
  },
  get steps(): readonly Step[] {
    return steps;
  },
  get finished(): number {
    return steps.filter((s) => s.done).length;
  },
  get total(): number {
    return steps.length;
  },
};
