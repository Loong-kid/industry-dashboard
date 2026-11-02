/* 그래프 카드 너비 드래그 조절 (전 탭 공통).

   카드 오른쪽 가장자리를 끌면 너비가 바뀌고, 더블클릭하면 원래대로 돌아간다. 값은 탭·카드 이름별로
   이 브라우저의 localStorage에만 저장한다.

   탭마다 코드를 고치지 않도록 화면에 생기는 차트를 감시해 손잡이를 붙인다. CSS 격자는 칸 너비를 벗어날
   수 없으므로, 너비를 바꾼 카드가 있는 격자만 flex 배치로 바꾼다. 아무것도 안 건드린 격자는 그대로다. */
"use strict";

const CARD_RESIZE = (() => {
  const MIN_WIDTH = 320;      // 이보다 좁으면 범례·값이 깨진다
  const AUTO_GROW = 1.4;      // 안 건드린 카드가 빈자리를 메우며 늘어나는 한도(원래 칸 대비)
  const KEY_STEP = 24;
  const NARROW_PX = 720;      // 한 칸짜리 화면은 저장값을 적용하지 않고 원래 배치를 쓴다

  const clampWidth = (width, min, max) => Math.round(Math.max(Math.min(min, max), Math.min(width, max)));

  // 계산된 grid-column → 차지하는 칸 수. "full"은 한 줄 전체(1 / -1).
  function columnSpan(start, end, cols) {
    if (end === "-1") return "full";
    const match = /^span (\d+)$/.exec(start) || /^span (\d+)$/.exec(end);
    return match ? Math.max(1, Math.min(Number(match[1]), cols)) : 1;
  }

  const spanBasis = (span, track, gap) => track * span + gap * (span - 1);

  return {MIN_WIDTH, AUTO_GROW, KEY_STEP, NARROW_PX, clampWidth, columnSpan, spanBasis};
})();

if (typeof module !== "undefined") module.exports = CARD_RESIZE;

if (typeof document !== "undefined") (() => {
  const {MIN_WIDTH, AUTO_GROW, KEY_STEP, NARROW_PX, clampWidth, columnSpan, spanBasis} = CARD_RESIZE;
  const STORE_KEY = "card_widths";
  const FREE = "card-resize-free";
  const holders = new WeakSet();
  const touched = new WeakSet();   // 이 모듈이 인라인 스타일을 넣은 요소만 되돌린다
  const watched = new Set();
  const lastWidth = new WeakMap();

  let saved = {};
  try { saved = JSON.parse(localStorage.getItem(STORE_KEY)) || {}; } catch (e) { /* 저장소 없음 */ }
  function persist() {
    try { localStorage.setItem(STORE_KEY, JSON.stringify(saved)); } catch (e) { /* 저장소 없음 */ }
  }

  // display:contents 묶음(게임 탭)을 건너뛴 실제 배치 부모와 그 자식들
  function layoutParent(el) {
    let parent = el.parentElement;
    while (parent && getComputedStyle(parent).display === "contents") parent = parent.parentElement;
    return parent;
  }
  function layoutChildren(parent) {
    return [...parent.children].flatMap(child =>
      getComputedStyle(child).display === "contents" ? layoutChildren(child) : [child]);
  }
  const isGrid = el => el.classList.contains(FREE) || getComputedStyle(el).display === "grid";

  // 격자가 지금 몇 칸·어떤 너비로 풀리는지: 같은 클래스의 빈 격자를 잠깐 만들어 잰다.
  function measureTracks(grid) {
    const probe = document.createElement("div");
    probe.className = grid.className.replace(FREE, "").trim();
    probe.style.cssText = `position:absolute;visibility:hidden;height:0;overflow:hidden;width:${grid.clientWidth}px`;
    probe.appendChild(document.createElement("div"));
    grid.parentElement.appendChild(probe);
    const style = getComputedStyle(probe);
    const tracks = style.gridTemplateColumns.split(" ").map(parseFloat).filter(Number.isFinite);
    const gap = parseFloat(style.columnGap) || 0;
    probe.remove();
    observer.takeRecords();
    const cols = tracks.length || 1;
    return {cols, gap, track: tracks.length ? tracks.reduce((a, b) => a + b, 0) / cols : grid.clientWidth};
  }

  function clearItem(item) {
    if (!touched.has(item)) return;
    touched.delete(item);
    for (const prop of ["flex", "maxWidth", "minWidth", "width"]) item.style[prop] = "";
  }

  function layout(parent) {
    if (!parent.isConnected) return;
    const items = layoutChildren(parent);
    const hasFixed = items.some(item => item.dataset.cardWidth);
    // 저장값이 있는 묶음은 좁은 화면·숨김 상태에서도 계속 지켜봐야 다시 넓어질 때 복원된다.
    if (hasFixed && !watched.has(parent)) {
      watched.add(parent);
      lastWidth.set(parent, parent.clientWidth);
      resizeWatch.observe(parent);
    } else if (!hasFixed && watched.delete(parent)) {
      resizeWatch.unobserve(parent);
    }
    const active = hasFixed && parent.clientWidth && window.innerWidth > NARROW_PX;
    if (!isGrid(parent)) {  // 격자가 아닌 묶음: 카드 너비만 지정
      for (const item of items) {
        clearItem(item);
        if (active && item.dataset.cardWidth) {
          touched.add(item);
          item.style.width = `${item.dataset.cardWidth}px`;
          item.style.maxWidth = "100%";
        }
      }
      return;
    }
    if (!active) {
      parent.classList.remove(FREE);
      items.forEach(clearItem);
      return;
    }
    const {cols, gap, track} = measureTracks(parent);
    parent.classList.add(FREE);
    for (const item of items) {
      touched.add(item);
      item.style.minWidth = "0";
      if (item.dataset.cardWidth) {
        item.style.flex = `0 0 ${item.dataset.cardWidth}px`;
        item.style.maxWidth = "100%";
        continue;
      }
      const style = getComputedStyle(item);
      const span = columnSpan(style.gridColumnStart, style.gridColumnEnd, cols);
      if (span === "full") {
        item.style.flex = "0 0 100%";
        item.style.maxWidth = "100%";
      } else {
        const basis = spanBasis(span, track, gap);
        item.style.flex = `1 1 ${basis}px`;
        item.style.maxWidth = `${Math.round(basis * AUTO_GROW)}px`;
      }
    }
  }

  // 화면 폭이 바뀌면 원래 칸 너비도 바뀐다. 숨겨졌던 탭이 나타날 때도 여기로 온다.
  const resizeWatch = new ResizeObserver(entries => {
    for (const {target} of entries) {
      if (lastWidth.get(target) === target.clientWidth) continue;
      lastWidth.set(target, target.clientWidth);
      layout(target);
    }
  });

  const routeKey = () => location.hash.replace("#/", "").split("/").slice(0, 2).join("/");

  // 저장 키: 탭 + 카드 이름 + (같은 묶음 안 동명 카드의) 순번
  function storageKey(item, parent) {
    const nameOf = el => el.querySelector(".card-name, h3, .dp-card-head b")?.textContent.trim() || "";
    const name = nameOf(item);
    if (!name) return null;
    const same = layoutChildren(parent).filter(el => nameOf(el) === name);
    return `${routeKey()}|${name}|${Math.max(0, same.indexOf(item))}`;
  }

  // 오른쪽 위 "크기 초기화": 지금 탭에서 바꾼 카드 크기를 모두 기본값으로 되돌린다.
  function resetTab() {
    const prefix = `${routeKey()}|`;
    for (const key of Object.keys(saved)) if (key.startsWith(prefix)) delete saved[key];
    persist();
    const parents = new Set();
    for (const item of document.querySelectorAll(".main .card-resizable")) {
      const parent = layoutParent(item);
      if (!item.dataset.cardWidth || !parent) continue;
      delete item.dataset.cardWidth;
      delete item.dataset.autoWidth;
      parents.add(parent);
    }
    parents.forEach(layout);
    updateResetButton();
  }
  function updateResetButton() {
    const right = document.querySelector(".topbar-right");
    if (!right) return;
    let button = document.getElementById("card-size-reset");
    if (!button) {
      button = document.createElement("button");
      button.id = "card-size-reset";
      button.type = "button";
      button.className = "card-size-reset";
      button.textContent = "크기 초기화";
      button.title = "이 탭의 그래프 크기를 기본값으로 되돌립니다";
      button.addEventListener("click", resetTab);
      right.insertBefore(button, document.getElementById("range-picker"));
    }
    const prefix = `${routeKey()}|`;
    button.hidden = !document.querySelector(".main .card-resizable");
    button.disabled = !document.querySelector(".main .card-resizable[data-card-width]")
      && !Object.keys(saved).some(key => key.startsWith(prefix));
  }

  function attachHandle(item) {
    const handle = document.createElement("div");
    handle.className = "card-resize-handle";
    handle.tabIndex = 0;
    handle.setAttribute("role", "separator");
    handle.setAttribute("aria-orientation", "vertical");
    handle.setAttribute("aria-label", "그래프 너비 조절. 좌우 화살표로 조절, Home 키로 원래대로");
    handle.title = "끌어서 너비 조절 · 더블클릭하면 원래대로";
    item.classList.add("card-resizable");
    item.appendChild(handle);

    const parentOf = () => layoutParent(item);
    const bounds = parent => {
      const auto = item.dataset.autoWidth ? Number(item.dataset.autoWidth) : item.offsetWidth;
      return [Math.min(MIN_WIDTH, auto), parent.clientWidth];
    };
    function setWidth(width, parent) {
      const [min, max] = bounds(parent);
      item.dataset.cardWidth = clampWidth(width, min, max);
      if (isGrid(parent) && parent.classList.contains(FREE)) {
        item.style.flex = `0 0 ${item.dataset.cardWidth}px`;
        item.style.maxWidth = "100%";
      } else {
        layout(parent);
      }
    }
    function remember(parent) {
      const key = storageKey(item, parent);
      if (key) { saved[key] = Number(item.dataset.cardWidth); persist(); }
      updateResetButton();
    }
    function reset() {
      const parent = parentOf();
      const key = storageKey(item, parent);
      delete item.dataset.cardWidth;
      if (key) { delete saved[key]; persist(); }
      layout(parent);
      updateResetButton();
    }

    handle.addEventListener("pointerdown", down => {
      if (down.button !== 0) return;
      down.preventDefault();
      down.stopPropagation();
      const parent = parentOf();
      const grab = item.getBoundingClientRect().right - down.clientX;
      item.dataset.autoWidth = item.dataset.autoWidth || item.offsetWidth;
      handle.setPointerCapture(down.pointerId);
      handle.classList.add("is-dragging");
      document.body.classList.add("card-resizing");
      let moved = false, frame = 0, lastX = down.clientX;
      const apply = () => {
        frame = 0;
        setWidth(lastX + grab - item.getBoundingClientRect().left, parent);
      };
      const move = event => {
        if (!moved && Math.abs(event.clientX - down.clientX) < 3) return;
        moved = true;
        lastX = event.clientX;
        if (!frame) frame = requestAnimationFrame(apply);
      };
      const up = () => {
        handle.removeEventListener("pointermove", move);
        handle.removeEventListener("pointerup", up);
        handle.removeEventListener("pointercancel", up);
        handle.classList.remove("is-dragging");
        document.body.classList.remove("card-resizing");
        if (frame) { cancelAnimationFrame(frame); apply(); }
        if (moved) remember(parent);
      };
      handle.addEventListener("pointermove", move);
      handle.addEventListener("pointerup", up);
      handle.addEventListener("pointercancel", up);
    });
    // 카드 자체의 클릭 동작(분야 열기 등)으로 번지지 않게 한다.
    handle.addEventListener("click", event => event.stopPropagation());
    handle.addEventListener("dblclick", event => { event.stopPropagation(); reset(); });
    handle.addEventListener("keydown", event => {
      const parent = parentOf();
      if (event.key === "Home") { event.preventDefault(); reset(); return; }
      if (event.key !== "ArrowLeft" && event.key !== "ArrowRight") return;
      event.preventDefault();
      item.dataset.autoWidth = item.dataset.autoWidth || item.offsetWidth;
      setWidth(item.offsetWidth + (event.key === "ArrowRight" ? KEY_STEP : -KEY_STEP), parent);
      remember(parent);
    });
  }

  function scan() {
    const main = document.querySelector(".main");
    if (!main) return;
    for (const parent of watched) {
      if (!parent.isConnected) { watched.delete(parent); resizeWatch.unobserve(parent); }
    }
    // 이 탭에 저장값이 없으면 카드마다 키를 계산하지 않는다(차트 100개가 넘는 탭이 있다).
    const route = routeKey();
    const hasSaved = Object.keys(saved).some(key => key.startsWith(`${route}|`));
    const found = new Set(main.querySelectorAll(".dp-card-wrap, .dp-stage"));
    for (const canvas of main.querySelectorAll("canvas")) {
      const holder = canvas.closest(".card, .gm-panel");
      if (holder) found.add(holder);
    }
    const dirty = new Set();
    for (const item of found) {
      if (holders.has(item)) continue;
      holders.add(item);
      attachHandle(item);
      const parent = layoutParent(item);
      if (!parent) continue;
      const key = hasSaved ? storageKey(item, parent) : null;
      if (key && saved[key]) {
        item.dataset.cardWidth = saved[key];
        dirty.add(parent);
      } else if (parent.classList.contains(FREE)) {
        dirty.add(parent);  // 이미 flex로 바뀐 격자에 새 카드가 늦게 붙은 경우
      }
    }
    dirty.forEach(layout);
    updateResetButton();
    observer.takeRecords();
  }

  let pending = 0;
  const observer = new MutationObserver(() => {
    if (!pending) pending = requestAnimationFrame(() => { pending = 0; scan(); });
  });
  function start() {
    observer.observe(document.body, {childList: true, subtree: true});
    scan();
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", start);
  else start();
})();
