(() => {
  const flows = window.FLOWS || [];
  const navEl = document.getElementById("nav");
  const titleEl = document.getElementById("flow-title");
  const metaEl = document.getElementById("flow-meta");
  const tagsEl = document.getElementById("flow-tags");
  const stripEl = document.getElementById("filmstrip");
  const lightboxEl = document.getElementById("lightbox");
  const lightboxImage = document.getElementById("lightbox-image");
  const lightboxTitle = document.getElementById("lightbox-title");
  const lightboxIndex = document.getElementById("lightbox-index");
  const btnPrev = document.getElementById("btn-prev");
  const btnNext = document.getElementById("btn-next");
  const btnStripPrev = document.getElementById("btn-strip-prev");
  const btnStripNext = document.getElementById("btn-strip-next");
  const btnStripRestart = document.getElementById("btn-strip-restart");
  const toastEl = document.getElementById("toast");

  const state = {
    flowId: null,
    frameIndex: 0,
    lightboxOpen: false,
    toastTimer: 0,
    stickToStart: true,
  };

  function currentFlow() {
    return flows.find((flow) => flow.id === state.flowId) || flows[0];
  }

  function groupedFlows() {
    const groups = [];
    const seen = new Map();
    for (const flow of flows) {
      if (!seen.has(flow.platform)) {
        seen.set(flow.platform, []);
        groups.push({ platform: flow.platform, items: seen.get(flow.platform) });
      }
      seen.get(flow.platform).push(flow);
    }
    return groups;
  }

  function pad(n) {
    return String(n).padStart(2, "0");
  }

  function sanitizeFileName(name) {
    return String(name || "screenshot.png").replace(/[\\/:*?"<>|]/g, "-");
  }

  function hideToast() {
    toastEl.hidden = true;
    window.clearTimeout(state.toastTimer);
  }

  function showToast(message) {
    toastEl.textContent = message;
    toastEl.hidden = false;
    window.clearTimeout(state.toastTimer);
    state.toastTimer = window.setTimeout(hideToast, 1800);
  }

  function issueLine(flow) {
    return (flow.issues || []).join(" | ");
  }

  function renderNav() {
    navEl.innerHTML = groupedFlows()
      .map(
        (group) => `
        <section class="nav-group">
          <div class="nav-label">${group.platform}</div>
          ${group.items
            .map((flow) => {
              const issues = issueLine(flow);
              return `
                <button
                  class="nav-item${flow.id === state.flowId ? " is-active" : ""}"
                  type="button"
                  data-flow="${flow.id}"
                >
                  <span class="nav-item-title">${flow.title}</span>
                  ${issues ? `<span class="issue-line">${issues}</span>` : ""}
                </button>`;
            })
            .join("")}
        </section>`
      )
      .join("");
  }

  function renderFilmstrip() {
    const flow = currentFlow();
    if (!flow) return;
    titleEl.textContent = flow.title;
    metaEl.textContent = `${flow.platform}  ·  ${flow.frames.length} 帧`;
    const issues = issueLine(flow);
    tagsEl.textContent = issues;
    tagsEl.hidden = !issues;
    stripEl.innerHTML = flow.frames
      .map((frame, index) => {
        const connector =
          index < flow.frames.length - 1
            ? `<div class="connector" aria-hidden="true">
                <svg viewBox="0 0 24 24"><path d="M9 5.5L15.5 12 9 18.5"/></svg>
              </div>`
            : "";
        return `
          <article class="frame">
            <img
              class="shot"
              src="${frame.src}"
              alt="${frame.title}"
              loading="${index < 2 ? "eager" : "lazy"}"
              decoding="async"
              ${index === 0 ? 'fetchpriority="high"' : ""}
              data-index="${index}"
            />
            <div class="frame-caption">
              <div class="frame-index">${pad(index + 1)}</div>
              <div class="frame-title">${frame.title}</div>
            </div>
          </article>
          ${connector}`;
      })
      .join("");
    state.stickToStart = true;
    stripEl.scrollLeft = 0;
    bindStripOverflow();
  }

  function stripVisibleBounds() {
    const rect = stripEl.getBoundingClientRect();
    const style = getComputedStyle(stripEl);
    return {
      left: rect.left + parseFloat(style.paddingLeft),
      right: rect.right - parseFloat(style.paddingRight),
    };
  }

  function stripAtStart() {
    const first = stripEl.querySelector(".frame");
    if (!first) return true;
    return first.getBoundingClientRect().left >= stripVisibleBounds().left - 2;
  }

  function stripAtEnd() {
    const frames = stripEl.querySelectorAll(".frame");
    const last = frames[frames.length - 1];
    if (!last) return true;
    return last.getBoundingClientRect().right <= stripVisibleBounds().right + 2;
  }

  function updateStripArrows() {
    if (state.stickToStart) stripEl.scrollLeft = 0;
    const overflow = stripEl.scrollWidth > stripEl.clientWidth + 2;
    const atStart = stripAtStart();
    const atEnd = overflow && stripAtEnd();
    btnStripPrev.hidden = !overflow || atStart;
    btnStripNext.hidden = !overflow || atEnd;
    btnStripRestart.hidden = !atEnd;
  }

  function bindStripOverflow() {
    stripEl.querySelectorAll("img").forEach((img) => {
      if (!img.complete) img.addEventListener("load", updateStripArrows, { once: true });
    });
    requestAnimationFrame(updateStripArrows);
  }

  function scrollStrip(direction) {
    const frames = [...stripEl.querySelectorAll(".frame")];
    if (!frames.length) return;
    const visible = stripVisibleBounds();
    const viewWidth = visible.right - visible.left;
    const slack = 4;

    const target =
      direction > 0
        ? frames.find((frame) => frame.getBoundingClientRect().right > visible.right + slack)
        : [...frames].reverse().find((frame) => frame.getBoundingClientRect().left < visible.left - slack);
    if (!target) return;

    const box = target.getBoundingClientRect();
    const delta =
      box.width > viewWidth
        ? direction > 0
          ? box.left - visible.left
          : box.right - visible.right
        : direction > 0
          ? box.right - visible.right
          : box.left - visible.left;
    state.stickToStart = false;
    animateStripScroll(delta);
  }

  function animateStripScroll(delta, absolute) {
    if (absolute) stripEl.scrollTo({ left: delta, behavior: "smooth" });
    else stripEl.scrollBy({ left: delta, behavior: "smooth" });
  }

  function restartStrip() {
    state.stickToStart = true;
    animateStripScroll(0, true);
  }

  function selectFlow(id, updateHash = true) {
    const flow = flows.find((item) => item.id === id) || flows[0];
    if (!flow) return;
    state.flowId = flow.id;
    if (updateHash && location.hash.slice(1) !== flow.id) {
      history.replaceState(null, "", `#${flow.id}`);
    }
    hideToast();
    renderNav();
    renderFilmstrip();
  }

  function openLightbox(index) {
    const flow = currentFlow();
    if (!flow || !flow.frames[index]) return;
    state.frameIndex = index;
    state.lightboxOpen = true;
    lightboxEl.hidden = false;
    document.body.style.overflow = "hidden";
    paintLightbox();
  }

  function closeLightbox() {
    state.lightboxOpen = false;
    lightboxEl.hidden = true;
    document.body.style.overflow = "";
    hideToast();
  }

  function paintLightbox() {
    const flow = currentFlow();
    const frame = flow.frames[state.frameIndex];
    lightboxImage.src = frame.src;
    lightboxImage.alt = frame.title;
    lightboxTitle.textContent = frame.title;
    lightboxIndex.textContent = `${state.frameIndex + 1} / ${flow.frames.length}`;
    btnPrev.disabled = state.frameIndex <= 0;
    btnNext.disabled = state.frameIndex >= flow.frames.length - 1;
  }

  function stepLightbox(delta) {
    const flow = currentFlow();
    const next = state.frameIndex + delta;
    if (next < 0 || next >= flow.frames.length) return;
    state.frameIndex = next;
    paintLightbox();
  }

  async function blobToPng(blob) {
    if (blob.type === "image/png") return blob;
    const bitmap = await createImageBitmap(blob);
    const canvas = document.createElement("canvas");
    canvas.width = bitmap.width;
    canvas.height = bitmap.height;
    const ctx = canvas.getContext("2d");
    ctx.drawImage(bitmap, 0, 0);
    return await new Promise((resolve, reject) => {
      canvas.toBlob((png) => (png ? resolve(png) : reject(new Error("png"))), "image/png");
    });
  }

  async function copyCurrent() {
    const flow = currentFlow();
    const frame = flow.frames[state.frameIndex];
    try {
      const response = await fetch(frame.src);
      const blob = await blobToPng(await response.blob());
      await navigator.clipboard.write([new ClipboardItem({ "image/png": blob })]);
      showToast("已复制图片");
    } catch (error) {
      showToast("复制失败，请用本地服务打开后再试");
    }
  }

  function saveCurrent() {
    const flow = currentFlow();
    const frame = flow.frames[state.frameIndex];
    const link = document.createElement("a");
    link.href = frame.src;
    link.download = sanitizeFileName(frame.fileName);
    document.body.appendChild(link);
    link.click();
    link.remove();
  }

  navEl.addEventListener("click", (event) => {
    const button = event.target.closest("[data-flow]");
    if (!button) return;
    selectFlow(button.dataset.flow);
  });

  stripEl.addEventListener("click", (event) => {
    const image = event.target.closest(".shot");
    if (!image) return;
    openLightbox(Number(image.dataset.index));
  });

  stripEl.addEventListener(
    "wheel",
    (event) => {
      if (Math.abs(event.deltaY) <= Math.abs(event.deltaX)) return;
      event.preventDefault();
      state.stickToStart = false;
      stripEl.scrollLeft += event.deltaY;
    },
    { passive: false }
  );

  lightboxEl.addEventListener("click", (event) => {
    if (event.target.dataset.close) closeLightbox();
  });
  document.getElementById("btn-close").addEventListener("click", closeLightbox);
  btnPrev.addEventListener("click", () => stepLightbox(-1));
  btnNext.addEventListener("click", () => stepLightbox(1));
  btnStripPrev.addEventListener("click", () => scrollStrip(-1));
  btnStripNext.addEventListener("click", () => scrollStrip(1));
  btnStripRestart.addEventListener("click", restartStrip);
  stripEl.addEventListener("scroll", updateStripArrows, { passive: true });
  window.addEventListener("resize", updateStripArrows);
  document.getElementById("btn-copy").addEventListener("click", copyCurrent);
  document.getElementById("btn-save").addEventListener("click", saveCurrent);

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && state.lightboxOpen) closeLightbox();
    if (event.key === "ArrowLeft") {
      if (state.lightboxOpen) stepLightbox(-1);
      else if (!btnStripPrev.hidden) scrollStrip(-1);
    }
    if (event.key === "ArrowRight") {
      if (state.lightboxOpen) stepLightbox(1);
      else if (!btnStripRestart.hidden) restartStrip();
      else if (!btnStripNext.hidden) scrollStrip(1);
    }
  });

  window.addEventListener("hashchange", () => {
    const id = location.hash.slice(1);
    if (id && id !== state.flowId) selectFlow(id, false);
  });

  const initial = location.hash.slice(1);
  selectFlow(initial || (flows[0] && flows[0].id));
})();
