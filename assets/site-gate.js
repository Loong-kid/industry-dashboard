/* 접속 비밀번호 입력창. 가볍게 가리는 용도라 data/ 파일 자체를 잠그지는 않는다.
   비밀번호는 scripts/set_site_password.py로 정하고, 해시만 site-gate-config.js에 저장한다. */
"use strict";

(() => {
  const config = window.SITE_GATE;
  const STORAGE_KEY = "site_gate_pass";
  const hex = bytes => [...new Uint8Array(bytes)].map(b => b.toString(16).padStart(2, "0")).join("");
  const unhex = text => Uint8Array.from(text.match(/../g), pair => parseInt(pair, 16));

  async function derive(password, salt, iterations) {
    const key = await crypto.subtle.importKey("raw", new TextEncoder().encode(password.normalize("NFC")), "PBKDF2", false, ["deriveBits"]);
    return hex(await crypto.subtle.deriveBits({name: "PBKDF2", hash: "SHA-256", salt: unhex(salt), iterations}, key, 256));
  }
  const remembered = () => { try { return localStorage.getItem(STORAGE_KEY); } catch { return null; } };
  const remember = value => { try { localStorage.setItem(STORAGE_KEY, value); } catch { /* 이번 방문만 통과 */ } };

  window.SiteGate = {derive};
  // 내 PC의 미리보기와 화면 시험은 입력창 없이 연다. 배포 주소에는 영향이 없다.
  const local = () => /^(localhost|127\.0\.0\.1|\[::1\])$/.test(location.hostname) && !config.test_local;
  // 비밀번호를 정하지 않았거나 이 기기에서 이미 통과했으면 바로 연다. 비밀번호를 바꾸면 기억도 무효가 된다.
  if (!config?.hash || local() || remembered() === config.hash) {
    window.siteGateReady = Promise.resolve();
    return;
  }

  const root = document.documentElement;
  root.classList.add("site-gate-locked");
  const robots = document.createElement("meta");
  robots.name = "robots";
  robots.content = "noindex";
  document.head.appendChild(robots);

  window.siteGateReady = new Promise(resolve => {
    const show = () => {
      const box = document.createElement("main");
      box.id = "site-gate";
      box.innerHTML = `
        <form class="site-gate-form">
          <h1>산업 KPI</h1>
          <label for="site-gate-input">비밀번호</label>
          <input id="site-gate-input" type="password" autocomplete="current-password" required autofocus>
          <button type="submit">열기</button>
          <p class="site-gate-error" role="alert" hidden></p>
        </form>`;
      document.body.appendChild(box);
      const form = box.querySelector("form"), input = box.querySelector("input"), button = box.querySelector("button"), error = box.querySelector(".site-gate-error");
      const fail = message => { error.textContent = message; error.hidden = false; };
      if (!window.crypto?.subtle) fail("이 주소에서는 비밀번호를 확인할 수 없습니다. HTTPS 주소로 열어 주세요.");
      input.focus();
      form.addEventListener("submit", async event => {
        event.preventDefault();
        if (!window.crypto?.subtle) return;
        button.disabled = true;
        error.hidden = true;
        const value = await derive(input.value, config.salt, config.iterations);
        button.disabled = false;
        if (value !== config.hash) {
          fail("비밀번호가 맞지 않습니다.");
          input.select();
          return;
        }
        remember(value);
        box.remove();
        root.classList.remove("site-gate-locked");
        robots.remove();
        resolve();
      });
    };
    if (document.body) show(); else document.addEventListener("DOMContentLoaded", show, {once: true});
  });
})();
