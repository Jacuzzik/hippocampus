// Home page: the role pills choose which agent card shows (real cards captured from the app). Without this script the first role shows.
const roles = {
  hippo: ["hippo", "Hippoherman", "Claude · main", "<b>Runs your team.</b> Reads what you ask, splits it into jobs, hands each one to the right agent and tells you when it is done."],
  researcher: ["researcher", "Researcher", "Gemini CLI", "<b>Digs into anything.</b> Reads the web and your vault, writes short notes with sources and links them into the graph."],
  writer: ["writer", "Writer", "Codex", "<b>Turns ideas into pages.</b> Drafts notes, plans and posts from what is already in your vault, in your words."],
  editor: ["editor", "Editor", "Ollama · local", "<b>Checks before it ships.</b> Reads drafts, fixes what is wrong and asks you before anything leaves the computer."],
  librarian: ["librarian", "Librarian", "Mistral", "<b>Keeps the vault tidy.</b> Finds notes nothing links to, merges duplicates and keeps tags in order."],
  yours: ["your", "Your own", "Any engine", "<b>Hire who you need.</b> Write a role and its rules in plain words, pick an engine, give it a face."],
};

// The deck holds the six real agent cards; data-active brings one to the front (motion.css fans the rest).
const deck = document.getElementById("role-card");
const desc = document.getElementById("role-desc");
const pills = [...document.querySelectorAll("[data-role]")];
function pick(role) {
  const [face, name, engine, text] = roles[role];
  for (const b of pills) b.setAttribute("aria-pressed", String(b.dataset.role === role));
  deck.dataset.active = face;
  deck.setAttribute("aria-label", `The ${name} agent card from the app (${engine})`);
  desc.innerHTML = text; // fixed text from this file, never from the visitor
}
for (const button of pills) button.addEventListener("click", () => pick(button.dataset.role));
// Clicking a card behind the front one brings it forward too.
for (const img of deck.querySelectorAll("[data-card]"))
  img.addEventListener("click", () => {
    const role = Object.keys(roles).find((r) => roles[r][0] === img.dataset.card);
    if (role) pick(role);
  });
