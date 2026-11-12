// The tests import .ts files directly, which only Node 24 or newer can load.
// Fail early with a clear message instead of a wall of ERR_UNKNOWN_FILE_EXTENSION errors.
const major = Number(process.versions.node.split(".")[0]);
if (major < 24) {
  console.error(
    `The app tests need Node 24 or newer. This shell runs Node ${process.versions.node}.`,
  );
  console.error(
    "Switch with nvm (nvm install 24 && nvm use 24) and run npm test again.",
  );
  process.exit(1);
}
