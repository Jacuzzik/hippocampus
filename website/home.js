// Home page: the role pills choose which agent card shows (real cards captured from the app). Without this script the first role shows.
const roles = {
  hippo: ["hippo", "Hippoherman", "Claude · main", "<b>Runs your team.</b> Reads what you ask, splits it into jobs, hands each one to the right agent and tells you when it is done."],
  researcher: ["researcher", "Researcher", "Gemini CLI", "<b>Digs into anything.</b> Reads the web and your vault, writes short notes with sources and links them into the graph."],
  writer: ["writer", "Writer", "Codex", "<b>Turns ideas into pages.</b> Drafts notes, plans and posts from what is already in your vault, in your words."],
  editor: ["editor", "Editor", "Ollama · local", "<b>Checks before it ships.</b> Reads drafts, fixes what is wrong and asks you before anything leaves the computer."],
  librarian: ["librarian", "Librarian", "Mistral", "<b>Keeps the vault tidy.</b> Finds notes nothing links to, merges duplicates and keeps tags in order."],
  yours: ["your", "Your own", "Any engine", "<b>Hire who you need.</b> Write a role and its rules in plain words, pick an engine, give it a face."],
};

const card = document.getElementById("role-card");
const desc = document.getElementById("role-desc");
for (const button of document.querySelectorAll("[data-role]")) {
  button.addEventListener("click", () => {
    const [face, name, engine, text] = roles[button.dataset.role];
    for (const b of document.querySelectorAll("[data-role]")) b.setAttribute("aria-pressed", String(b === button));
    const img = card.querySelector("img");
    img.src = `img/app/card-${face}.webp`;
    img.alt = `The ${name} agent card from the app (${engine})`;
    desc.innerHTML = text; // fixed text from this file, never from the visitor
  });
}
