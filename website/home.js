// Home page: the role pills choose which agent card shows. Without this script the first role shows.
const roles = {
  hippo: ["01", "Hippo", "Claude Code · main", "<b>Runs your team.</b> Reads what you ask, splits it into jobs, hands each one to the right agent and tells you when it is done."],
  researcher: ["03", "Researcher", "Gemini CLI", "<b>Digs into anything.</b> Reads the web and your vault, writes short notes with sources and links them into the graph."],
  writer: ["04", "Writer", "Codex", "<b>Turns ideas into pages.</b> Drafts notes, plans and posts from what is already in your vault, in your words."],
  editor: ["05", "Editor", "Ollama · local", "<b>Checks before it ships.</b> Reads drafts, fixes what is wrong and asks you before anything leaves the computer."],
  librarian: ["02", "Librarian", "LM Studio · local", "<b>Keeps the vault tidy.</b> Finds notes nothing links to, merges duplicates and keeps tags in order."],
  yours: ["06", "Your own", "Any engine", "<b>Hire who you need.</b> Write a role and its rules in plain words, pick an engine, give it a face."],
};

const card = document.getElementById("role-card");
const desc = document.getElementById("role-desc");
for (const button of document.querySelectorAll("[data-role]")) {
  button.addEventListener("click", () => {
    const [face, name, engine, text] = roles[button.dataset.role];
    for (const b of document.querySelectorAll("[data-role]")) b.setAttribute("aria-pressed", String(b === button));
    card.querySelector("img").src = `img/card-face-${face}.svg`;
    card.querySelector("b").textContent = name;
    card.querySelector("small").textContent = engine;
    desc.innerHTML = text; // fixed text from this file, never from the visitor
  });
}
