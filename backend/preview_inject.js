// Injected into every previewed page. Keeps scroll position across live
// reloads and lets the host app pick an element ("make *this* bigger").
(function () {
  // The page is sandboxed (opaque origin, no sessionStorage), so the host app
  // remembers the scroll position and sends it back after each reload.
  var scrollTimer = null;
  window.addEventListener("scroll", function () {
    clearTimeout(scrollTimer);
    scrollTimer = setTimeout(function () {
      parent.postMessage({ source: "vox-build", type: "scroll", y: window.scrollY }, "*");
    }, 150);
  }, { passive: true });

  var picking = false;
  var selected = null;
  var box = document.createElement("div");
  box.style.cssText =
    "position:fixed;pointer-events:none;z-index:2147483647;border:2px solid #7c5cff;" +
    "background:rgba(124,92,255,.10);border-radius:6px;display:none;transition:all .06s ease-out";

  function mount() { if (!box.parentNode && document.body) document.body.appendChild(box); }
  document.addEventListener("DOMContentLoaded", mount);
  mount();

  function cssPath(el) {
    var parts = [];
    while (el && el.nodeType === 1 && el !== document.body) {
      var part = el.tagName.toLowerCase();
      if (el.id) { parts.unshift(part + "#" + el.id); break; }
      var parent = el.parentElement;
      if (parent) {
        var same = Array.prototype.filter.call(parent.children, function (c) { return c.tagName === el.tagName; });
        if (same.length > 1) part += ":nth-of-type(" + (same.indexOf(el) + 1) + ")";
      }
      parts.unshift(part);
      el = parent;
    }
    return parts.join(" > ");
  }

  function label(el) {
    var text = (el.innerText || el.getAttribute("alt") || "").trim().replace(/\s+/g, " ").slice(0, 40);
    return el.tagName.toLowerCase() + (text ? ' "' + text + '"' : "");
  }

  function show(el) {
    if (!el) { box.style.display = "none"; return; }
    var r = el.getBoundingClientRect();
    box.style.display = "block";
    box.style.left = r.left - 2 + "px";
    box.style.top = r.top - 2 + "px";
    box.style.width = r.width + 4 + "px";
    box.style.height = r.height + 4 + "px";
  }

  document.addEventListener("mouseover", function (e) { if (picking) show(e.target); }, true);
  window.addEventListener("scroll", function () { if (!picking) show(selected); }, true);

  document.addEventListener("click", function (e) {
    if (!picking) return;
    e.preventDefault();
    e.stopPropagation();
    selected = e.target;
    show(selected);
    parent.postMessage({
      source: "vox-build",
      type: "select",
      selection: { path: cssPath(selected), html: selected.outerHTML.slice(0, 4000), label: label(selected) },
    }, "*");
  }, true);

  window.addEventListener("message", function (e) {
    var d = e.data || {};
    if (d.source !== "vox-build-host") return;
    if (d.type === "scroll-to") {
      var y = +d.y || 0;
      if (document.readyState === "complete") window.scrollTo(0, y);
      else window.addEventListener("load", function () { window.scrollTo(0, y); });
    } else if (d.type === "pick") {
      picking = !!d.on;
      document.documentElement.style.cursor = picking ? "crosshair" : "";
      if (!picking) show(selected);
    } else if (d.type === "highlight") {
      try { selected = d.path ? document.querySelector(d.path) : null; } catch (_) { selected = null; }
      show(selected);
    }
  });
})();
