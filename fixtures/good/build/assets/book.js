/* techbook — book.js
   Everything here is an enhancement. The book must be fully readable with this
   file absent or JavaScript disabled, so nothing below creates content. */
(function () {
  "use strict";

  /* ── theme: auto → light → dark, remembered per reader ─────────────────── */
  var THEME_KEY = "techbook-theme";
  function readTheme() {
    try { return localStorage.getItem(THEME_KEY); } catch (e) { return null; }
  }
  function applyTheme(t) {
    if (t === "light" || t === "dark") document.documentElement.setAttribute("data-theme", t);
    else document.documentElement.removeAttribute("data-theme");
  }
  function cycleTheme() {
    var order = ["auto", "light", "dark"];
    var cur = readTheme() || "auto";
    var next = order[(order.indexOf(cur) + 1) % order.length];
    try {
      if (next === "auto") localStorage.removeItem(THEME_KEY);
      else localStorage.setItem(THEME_KEY, next);
    } catch (e) { /* private mode: theme just won't persist */ }
    applyTheme(next === "auto" ? null : next);
    labelTheme(next);
  }
  function labelTheme(t) {
    var btn = document.getElementById("theme-toggle");
    if (btn) {
      btn.textContent = t === "light" ? "Light" : t === "dark" ? "Dark" : "Auto";
      btn.setAttribute("aria-label", "Theme: " + t + ". Click to change.");
    }
  }

  /* ── copy buttons ──────────────────────────────────────────────────────── */
  function wireCopy() {
    document.querySelectorAll("button.copy").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var fig = btn.closest("figure.listing");
        var code = fig && fig.querySelector("pre code");
        if (!code) return;
        var text = code.textContent.replace(/\s+$/, "");
        var done = function () {
          btn.textContent = "Copied";
          btn.setAttribute("data-copied", "1");
          setTimeout(function () {
            btn.textContent = "Copy";
            btn.removeAttribute("data-copied");
          }, 1500);
        };
        if (navigator.clipboard && navigator.clipboard.writeText) {
          navigator.clipboard.writeText(text).then(done, function () {});
        } else {
          var ta = document.createElement("textarea");
          ta.value = text;
          ta.style.position = "fixed";
          ta.style.opacity = "0";
          document.body.appendChild(ta);
          ta.select();
          try { document.execCommand("copy"); done(); } catch (e) {}
          document.body.removeChild(ta);
        }
      });
    });
  }

  /* ── scrollspy + reading progress ──────────────────────────────────────── */
  function wireScroll() {
    var bar = document.getElementById("progress");
    var links = Array.prototype.slice.call(
      document.querySelectorAll('.toc a[href*="#"]'));
    var map = {};
    links.forEach(function (a) {
      var id = a.getAttribute("href").split("#")[1];
      if (id) map[id] = a;
    });
    var targets = Object.keys(map)
      .map(function (id) { return document.getElementById(id); })
      .filter(Boolean);

    var ticking = false;
    function update() {
      ticking = false;
      if (bar) {
        var doc = document.documentElement;
        var max = doc.scrollHeight - doc.clientHeight;
        var pct = max > 0 ? (doc.scrollTop / max) * 100 : 0;
        bar.style.width = Math.min(100, Math.max(0, pct)) + "%";
      }
      if (!targets.length) return;
      var line = window.scrollY + (window.innerHeight * 0.28);
      var active = null;
      for (var i = 0; i < targets.length; i++) {
        if (targets[i].offsetTop <= line) active = targets[i];
      }
      links.forEach(function (a) { a.removeAttribute("aria-current"); });
      if (active && map[active.id]) {
        map[active.id].setAttribute("aria-current", "location");
      }
    }
    function onScroll() {
      if (!ticking) { ticking = true; requestAnimationFrame(update); }
    }
    window.addEventListener("scroll", onScroll, { passive: true });
    window.addEventListener("resize", onScroll, { passive: true });
    update();
  }

  /* ── search ────────────────────────────────────────────────────────────── */
  function wireSearch() {
    var dlg = document.getElementById("search");
    var input = document.getElementById("search-input");
    var list = document.getElementById("search-results");
    if (!dlg || !input || !list) return;
    var index = null, loading = false;

    function load() {
      if (index || loading) return Promise.resolve();
      loading = true;
      // Inlined by the single-file build; fetched otherwise.
      if (window.__TECHBOOK_INDEX__) {
        index = window.__TECHBOOK_INDEX__;
        loading = false;
        return Promise.resolve();
      }
      return fetch("search.json")
        .then(function (r) { return r.json(); })
        .then(function (j) { index = j; loading = false; })
        .catch(function () { loading = false; });
    }

    function score(entry, terms) {
      var h = entry.heading.toLowerCase(), t = entry.text.toLowerCase(), s = 0;
      for (var i = 0; i < terms.length; i++) {
        var q = terms[i];
        if (!q) continue;
        if (h.indexOf(q) !== -1) s += 12;
        if (h.indexOf(q) === 0) s += 6;
        var n = t.split(q).length - 1;
        if (!n && h.indexOf(q) === -1) return 0;   // every term must appear
        s += Math.min(n, 6);
      }
      return s;
    }

    function excerpt(text, term) {
      var i = text.toLowerCase().indexOf(term);
      if (i < 0) return text.slice(0, 120) + "…";
      var start = Math.max(0, i - 45);
      return (start ? "…" : "") + text.slice(start, start + 130).trim() + "…";
    }

    function render(q) {
      list.innerHTML = "";
      if (!index || q.trim().length < 2) return;
      var terms = q.toLowerCase().split(/\s+/).filter(Boolean);
      var hits = index
        .map(function (e) { return { e: e, s: score(e, terms) }; })
        .filter(function (x) { return x.s > 0; })
        .sort(function (a, b) { return b.s - a.s; })
        .slice(0, 12);
      hits.forEach(function (hit) {
        var li = document.createElement("li");
        var a = document.createElement("a");
        a.href = hit.e.href;
        a.innerHTML =
          '<span class="where">' + esc(hit.e.chapter) + "</span>" +
          "<strong>" + esc(hit.e.heading) + "</strong>" +
          '<span class="ctx">' + esc(excerpt(hit.e.text, terms[0])) + "</span>";
        a.addEventListener("click", function () { dlg.close(); });
        li.appendChild(a);
        list.appendChild(li);
      });
    }

    function esc(s) {
      return String(s).replace(/[&<>"]/g, function (c) {
        return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c];
      });
    }

    function open() {
      load().then(function () {
        if (typeof dlg.showModal === "function" && !dlg.open) dlg.showModal();
        input.value = "";
        list.innerHTML = "";
        input.focus();
      });
    }

    var btn = document.getElementById("search-toggle");
    if (btn) btn.addEventListener("click", open);
    input.addEventListener("input", function () { render(input.value); });
    input.addEventListener("keydown", function (e) {
      if (e.key === "ArrowDown") {
        e.preventDefault();
        var first = list.querySelector("a");
        if (first) first.focus();
      }
    });
    dlg.addEventListener("click", function (e) { if (e.target === dlg) dlg.close(); });

    document.addEventListener("keydown", function (e) {
      var typing = /^(INPUT|TEXTAREA|SELECT)$/.test(document.activeElement.tagName);
      if ((e.key === "/" && !typing) || ((e.metaKey || e.ctrlKey) && e.key === "k")) {
        e.preventDefault();
        open();
      }
    });
  }

  /* ── keyboard chapter nav ──────────────────────────────────────────────── */
  function wireKeys() {
    document.addEventListener("keydown", function (e) {
      if (e.metaKey || e.ctrlKey || e.altKey) return;
      if (/^(INPUT|TEXTAREA|SELECT)$/.test(document.activeElement.tagName)) return;
      if (document.querySelector("dialog[open]")) return;
      var sel = e.key === "ArrowLeft" ? 'link[rel="prev"], a.prev'
              : e.key === "ArrowRight" ? 'link[rel="next"], a.next' : null;
      if (!sel) return;
      var el = document.querySelector(sel);
      if (el && el.href) window.location.href = el.href;
    });
  }

  /* ── init ──────────────────────────────────────────────────────────────── */
  function init() {
    labelTheme(readTheme() || "auto");
    var tt = document.getElementById("theme-toggle");
    if (tt) tt.addEventListener("click", cycleTheme);
    wireCopy();
    wireScroll();
    wireSearch();
    wireKeys();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
