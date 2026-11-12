// Tests for ui/health.ts. Node 24 strips the types when it imports the .ts file.
import assert from "node:assert/strict";
import { test } from "node:test";
import { DISK_FREE_MIN_GB, RAM_MAX_PERCENT, SWAP_MAX_PERCENT, systemWarnings } from "../ui/health.ts";

const fine = { cpu: 5, ram: 60, swap: 5, disk: 30, disk_free: 200 };

test("no warning before the first read or while all is well", () => {
  assert.deepEqual(systemWarnings(null), []);
  assert.deepEqual(systemWarnings(fine), []);
});

test("each limit warns at its edge and not just below it", () => {
  assert.equal(systemWarnings({ ...fine, disk_free: DISK_FREE_MIN_GB }).length, 0);
  assert.match(systemWarnings({ ...fine, disk_free: DISK_FREE_MIN_GB - 0.1 })[0], /^Disk almost full: 1\.9 GB free/);
  assert.equal(systemWarnings({ ...fine, ram: RAM_MAX_PERCENT - 0.1 }).length, 0);
  assert.match(systemWarnings({ ...fine, ram: RAM_MAX_PERCENT })[0], /^Memory almost full: 92%/);
  assert.equal(systemWarnings({ ...fine, swap: SWAP_MAX_PERCENT - 0.1 }).length, 0);
  assert.match(systemWarnings({ ...fine, swap: SWAP_MAX_PERCENT })[0], /^Swap almost full: 80%/);
});

test("several problems are listed, disk first", () => {
  const lines = systemWarnings({ cpu: 99, ram: 97, swap: 91, disk: 99, disk_free: 0.4 });
  assert.equal(lines.length, 3);
  assert.match(lines[0], /^Disk/);
  assert.match(lines[1], /^Memory/);
  assert.match(lines[2], /^Swap/);
});
