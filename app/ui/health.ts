// Warnings worked out from the host numbers the sidecar already reports (the "system" call).
// A full disk or exhausted memory is the usual reason an agent or the index stops saving,
// so the app says so before it happens.

export type SystemStats = {
  cpu: number;
  ram: number;
  swap: number;
  disk: number;
  disk_free: number;
};

/** Free disk space, in GB, below which saving is at risk. */
export const DISK_FREE_MIN_GB = 2;
/** Memory in use, in percent, above which the computer starts to stall. */
export const RAM_MAX_PERCENT = 92;
/** Swap in use, in percent, above which the computer is close to running out of memory. */
export const SWAP_MAX_PERCENT = 80;

/** One short line per problem, worst first. Empty when all is well or nothing has been read yet. */
export function systemWarnings(stats: SystemStats | null): string[] {
  if (!stats) return [];
  const lines: string[] = [];
  if (stats.disk_free < DISK_FREE_MIN_GB)
    lines.push(
      `Disk almost full: ${stats.disk_free.toFixed(1)} GB free. Notes and agent work may not save.`,
    );
  if (stats.ram >= RAM_MAX_PERCENT)
    lines.push(
      `Memory almost full: ${Math.round(stats.ram)}% in use. Close an agent or another app.`,
    );
  if (stats.swap >= SWAP_MAX_PERCENT)
    lines.push(
      `Swap almost full: ${Math.round(stats.swap)}% in use. The computer may freeze.`,
    );
  return lines;
}
