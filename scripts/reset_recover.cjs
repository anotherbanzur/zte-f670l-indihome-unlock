// reset_recover.cjs — setelah factory reset ZTE F670L: uji kandidat password
// pabrik yang diketahui publik sampai login web sukses.
// Usage: node reset_recover.cjs [--host 192.168.1.1]
// Hanya untuk perangkat milik sendiri. License: MIT.
const crypto = require("crypto");
const BASE = process.argv.includes("--host")
  ? `http://${process.argv[process.argv.indexOf("--host") + 1]}`
  : "http://192.168.1.1";
const UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120";
let COOKIE = "";

async function http(url, method = "GET", body = null) {
  const headers = { "User-Agent": UA, Referer: BASE + "/", "X-Requested-With": "XMLHttpRequest", ...(COOKIE ? { Cookie: COOKIE } : {}) };
  if (body !== null) headers["Content-Type"] = "application/x-www-form-urlencoded; charset=UTF-8";
  const res = await fetch(url, { method, headers, body: body ?? undefined, redirect: "manual" });
  const sc = res.headers.getSetCookie ? res.headers.getSetCookie() : [];
  for (const c of sc) { const kv = c.split(";")[0]; const [n, v] = kv.split("="); COOKIE = `${n}=${v}`; }
  return { status: res.status, text: await res.text() };
}
const sha256hex = (s) => crypto.createHash("sha256").update(s, "utf8").digest("hex");
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function tryLogin(user, pw) {
  COOKIE = "";
  let r = await http(`${BASE}/?_type=loginData&_tag=login_entry`);
  let sess; try { sess = JSON.parse(r.text).sess_token; } catch (e) { return { err: "no sess" }; }
  r = await http(`${BASE}/?_type=loginData&_tag=login_token`);
  const token = (r.text.match(/>([^<]+)</) || [])[1];
  if (!token) return { err: "no token" };
  r = await http(`${BASE}/?_type=loginData&_tag=login_entry`, "POST",
    `action=login&Password=${encodeURIComponent(sha256hex(pw + token.trim()))}&Username=${encodeURIComponent(user)}&_sessionTOKEN=${encodeURIComponent(sess)}`);
  let out; try { out = JSON.parse(r.text); } catch (e) { return { err: "nonjson" }; }
  if (out.loginErrMsg || out.lockingTime !== undefined || out.IF_ERRORID) return { fail: out };
  return { ok: out };
}

// Kandidat = kombinasi default yang terdokumentasi publik (bukan kredensial privat).
const CANDIDATES = [
  ["admin", "Telkomdso123"],
  ["admin", "Web@0063"],
  ["admin", "admin"],
  ["user", "user"],
  ["user", "Web@0763"],
  ["support", "theworldinyourhand"],
  ["telecomadmin", "admintelecom"],
];

async function main() {
  for (const [u, p] of CANDIDATES) {
    const res = await tryLogin(u, p);
    if (res.ok) {
      console.log(`*** SUKSES: ${u} / ${p}`);
      process.exit(0);
    }
    const lt = res.fail && res.fail.lockingTime;
    console.log(`gagal ${u} -> ${JSON.stringify(res.fail || res.err).slice(0, 100)}`);
    if (lt !== undefined && lt !== -1 && lt !== 0) {
      const w = (typeof lt === "number" && lt > 0 && lt < 300 ? lt : 60) + 8;
      console.log(`  lock ${lt}s — tunggu...`);
      await sleep(w * 1000);
    } else {
      await sleep(2500);
    }
  }
  console.log("semua kandidat gagal");
}
main().catch((e) => { console.error("ERR:", e); process.exit(1); });
