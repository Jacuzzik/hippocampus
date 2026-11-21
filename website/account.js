// The account page (plan 14.03) and share links (14.04). It talks only to the Hippocampus sign-in service.
// The sign-in is kept in this tab (sessionStorage) and is gone when the tab closes; no cookies.
const AUTH = "https://qrdehlqmqydphizlznhr.supabase.co";
const KEY = "sb_publishable_PCRx2rK7SQwNBAJRl_fY9w_05ttd0f3"; // public key, safe in a web page

const $ = (id) => document.getElementById(id);
const store = {
  get(k) {
    try {
      return JSON.parse(sessionStorage.getItem(k));
    } catch {
      return null;
    }
  },
  set(k, v) {
    try {
      if (v === null) sessionStorage.removeItem(k);
      else sessionStorage.setItem(k, JSON.stringify(v));
    } catch {
      /* private window: the page still works for this visit */
    }
  },
};

async function call(path, { method = "POST", body, token, prefer } = {}) {
  const headers = { apikey: KEY, "Content-Type": "application/json" };
  if (token) headers.Authorization = `Bearer ${token}`;
  if (prefer) headers.Prefer = prefer;
  const reply = await fetch(AUTH + path, {
    method,
    headers,
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const text = await reply.text();
  let data = null;
  try {
    data = text ? JSON.parse(text) : null;
  } catch {
    // Some errors (for example the delete function) answer with plain text.
    data = { message: text };
  }
  if (!reply.ok) throw new Error((data && (data.message || data.msg)) || `error ${reply.status}`);
  return data;
}

function b64url(bytes) {
  return btoa(String.fromCharCode(...new Uint8Array(bytes)))
    .replace(/\+/g, "-")
    .replace(/\//g, "_")
    .replace(/=+$/, "");
}

// --- Account page ------------------------------------------------------------------------------------
async function signIn() {
  const verifier = b64url(crypto.getRandomValues(new Uint8Array(48)));
  const challenge = b64url(await crypto.subtle.digest("SHA-256", new TextEncoder().encode(verifier)));
  store.set("hc-verifier", verifier);
  const back = location.origin + location.pathname;
  const q = new URLSearchParams({
    provider: "google",
    redirect_to: back,
    code_challenge: challenge,
    code_challenge_method: "s256",
  });
  location.assign(`${AUTH}/auth/v1/authorize?${q}`);
}

async function session() {
  const code = new URLSearchParams(location.search).get("code");
  if (code) {
    history.replaceState(null, "", location.pathname);
    const verifier = store.get("hc-verifier");
    store.set("hc-verifier", null);
    if (verifier) {
      const s = await call("/auth/v1/token?grant_type=pkce", {
        body: { auth_code: code, code_verifier: verifier },
      });
      store.set("hc-session", { token: s.access_token, user: s.user, until: Date.now() + s.expires_in * 1000 });
    }
  }
  const s = store.get("hc-session");
  if (s && s.until > Date.now() + 30000) return s;
  store.set("hc-session", null);
  return null;
}

function show(id) {
  for (const el of document.querySelectorAll("[data-view]")) el.hidden = el.id !== id;
}

async function renderAccount(s) {
  const meta = s.user.user_metadata || {};
  $("who").textContent = meta.full_name || meta.name || s.user.email;
  $("email").textContent = s.user.email;
  $("plan").textContent = (s.user.app_metadata || {}).plan === "supporter" ? "Supporter" : "Free";
  show("signed-in");
  try {
    const links = await call("/rest/v1/shares?select=id,title,expires_at&order=created_at.desc", {
      method: "GET",
      token: s.token,
    });
    const list = $("links");
    list.replaceChildren();
    for (const link of links) {
      const li = document.createElement("li");
      const a = document.createElement("a");
      a.href = `share.html#${link.id}`;
      a.textContent = link.title;
      const when = new Date(link.expires_at);
      const note = document.createElement("span");
      note.className = "muted";
      note.textContent = when < new Date() ? " · expired " : ` · until ${when.toLocaleString()} `;
      const del = document.createElement("button");
      del.className = "button quiet";
      del.textContent = "Delete";
      del.onclick = async () => {
        await call(`/rest/v1/shares?id=eq.${link.id}`, { method: "DELETE", token: s.token });
        renderAccount(s);
      };
      li.append(a, note, del);
      list.append(li);
    }
    $("no-links").hidden = links.length > 0;
    const days = await call("/rest/v1/usage_days?select=day,tokens&order=day.asc", {
      method: "GET",
      token: s.token,
    });
    const bars = $("usage");
    bars.replaceChildren();
    const top = Math.max(1, ...days.map((d) => d.tokens));
    for (const d of days.slice(-60)) {
      const bar = document.createElement("i");
      bar.style.height = `${Math.round((d.tokens / top) * 100)}%`;
      bar.title = `${d.day}: ${d.tokens.toLocaleString()} tokens`;
      bars.append(bar);
    }
    $("usage-none").hidden = days.length > 0;
    $("usage-total").textContent = days.length
      ? `${days.reduce((n, d) => n + d.tokens, 0).toLocaleString()} tokens over ${days.length} days`
      : "";
  } catch (e) {
    $("problem").textContent = `Could not load your account: ${e.message}`;
  }
}

export async function accountPage() {
  $("sign-in").onclick = () => signIn().catch((e) => ($("problem").textContent = e.message));
  $("sign-out").onclick = async () => {
    const s = store.get("hc-session");
    store.set("hc-session", null);
    if (s) await call("/auth/v1/logout", { token: s.token }).catch(() => {});
    show("signed-out");
  };
  // Delete opens a pop-up. The delete only runs when the button is held for 3 seconds.
  const dialog = $("delete-dialog");
  const hold = $("delete-hold");
  const fill = hold.querySelector(".hold-fill");
  const HOLD_MS = 3000;
  let started = 0;
  let frame = 0;
  const reset = () => {
    cancelAnimationFrame(frame);
    started = 0;
    fill.style.width = "0%";
  };
  const finish = async () => {
    reset();
    const s = store.get("hc-session");
    $("delete-problem").textContent = "";
    if (!s?.token) {
      $("delete-problem").textContent = "You are not signed in on this browser. Sign in again, then try once more.";
      return;
    }
    hold.disabled = true;
    hold.querySelector(".hold-label").textContent = "Deleting…";
    try {
      await call("/functions/v1/delete-account", { token: s.token, body: {} });
      store.set("hc-session", null);
      dialog.close();
      show("deleted");
    } catch (e) {
      hold.disabled = false;
      hold.querySelector(".hold-label").textContent = "Hold to delete";
      $("delete-problem").textContent = `Nothing was deleted: ${e.message}`;
    }
  };
  const tick = (now) => {
    const t = Math.min(1, (now - started) / HOLD_MS);
    fill.style.width = `${t * 100}%`;
    if (t >= 1) return finish();
    frame = requestAnimationFrame(tick);
  };
  const begin = (e) => {
    if (hold.disabled) return;
    e.preventDefault();
    started = performance.now();
    frame = requestAnimationFrame(tick);
  };
  hold.addEventListener("pointerdown", begin);
  ["pointerup", "pointerleave", "pointercancel"].forEach((ev) => hold.addEventListener(ev, reset));
  // Keyboard: hold Space or Enter the same way.
  hold.addEventListener("keydown", (e) => {
    if ((e.key === " " || e.key === "Enter") && !e.repeat) begin(e);
  });
  hold.addEventListener("keyup", reset);
  $("delete").onclick = () => {
    $("delete-problem").textContent = "";
    hold.disabled = false;
    hold.querySelector(".hold-label").textContent = "Hold to delete";
    reset();
    dialog.showModal();
  };
  $("keep").onclick = () => {
    reset();
    dialog.close();
  };
  try {
    const s = await session();
    if (s) await renderAccount(s);
    else show("signed-out");
  } catch (e) {
    show("signed-out");
    $("problem").textContent = `Sign-in did not finish: ${e.message}`;
  }
}

// --- Share page --------------------------------------------------------------------------------------
export function sharePage() {
  const id = location.hash.slice(1);
  if (!/^[0-9a-f-]{36}$/.test(id)) {
    $("problem").textContent = "This link is not complete. Ask for the link again.";
    $("open").hidden = true;
    return;
  }
  $("open").onsubmit = async (event) => {
    event.preventDefault();
    $("problem").textContent = "";
    try {
      const rows = await call("/rest/v1/rpc/open_share", {
        body: { p_id: id, p_password: $("password").value },
      });
      if (!rows || !rows.length) {
        $("problem").textContent = "That password is not right.";
        return;
      }
      $("open").hidden = true;
      $("title").textContent = rows[0].title;
      $("body").textContent = rows[0].body; // shown as text, never as HTML
      $("until").textContent = `This link works until ${new Date(rows[0].expires_at).toLocaleString()}.`;
      $("note").hidden = false;
    } catch (e) {
      $("problem").textContent = e.message;
    }
  };
}
