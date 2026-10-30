/* ZYROX AI — accessible, dependency-free loading and state components. */
(function (root) {
  "use strict";

  const stateLabels = {
    IDLE: "Idle",
    QUEUED: "Queued",
    RUNNING: "Running",
    COMPLETED: "Completed",
    FAILED: "Failed",
    SKIPPED: "Skipped"
  };
  const stateLabelsKh = {
    IDLE: "រង់ចាំ",
    QUEUED: "កំពុងរង់ចាំជួរ",
    RUNNING: "កំពុងដំណើរការ",
    COMPLETED: "បានបញ្ចប់",
    FAILED: "បរាជ័យ",
    SKIPPED: "រំលង"
  };

  function element(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined && text !== null) node.textContent = String(text);
    return node;
  }

  function mount(host, component) {
    if (!host || !component) return null;
    host.replaceChildren(component);
    return component;
  }

  function Spinner(label = "Loading") {
    const spinner = element("span", "zyrox-spinner");
    spinner.setAttribute("aria-hidden", "true");
    spinner.dataset.label = label;
    return spinner;
  }

  function FullScreenLoader(options = {}) {
    const rootNode = element("div", "zyrox-fullscreen-loader");
    rootNode.setAttribute("role", "status");
    rootNode.setAttribute("aria-live", "polite");
    rootNode.setAttribute("aria-busy", "true");

    const brand = element("div", "zyrox-loader-brand");
    const logo = element("img", "zyrox-loader-logo");
    logo.src = options.logo || "assets/brand/zyrox-logo-icon.svg";
    logo.alt = "ZYROX AI";
    brand.append(logo, element("span", "zyrox-loader-brand-name", "ZYROX AI"));
    rootNode.append(brand, Spinner(options.status || "Preparing your workspace"));
    rootNode.append(element("h1", "zyrox-loader-title", options.title || "Preparing your workspace"));
    rootNode.append(element("p", "zyrox-loader-copy", options.status || "Connecting to live services…"));

    if (Number.isFinite(options.progress) && options.progress >= 0 && options.progress <= 100) {
      const progress = ProgressLoader({ value: options.progress, label: options.progressLabel || "Initialization progress" });
      rootNode.append(progress);
    }

    const actionHost = element("div", "zyrox-loader-actions");
    actionHost.hidden = true;
    rootNode.append(actionHost);
    rootNode._status = rootNode.querySelector(".zyrox-loader-copy");
    rootNode._actionHost = actionHost;
    return rootNode;
  }

  function PageLoader(options = {}) {
    const box = element("div", "zyrox-page-loader");
    box.setAttribute("role", "status");
    box.setAttribute("aria-live", "polite");
    box.append(Spinner(options.label || "Loading page"));
    box.append(element("span", "zyrox-state-copy", options.label || "Loading page…"));
    return box;
  }

  function SectionLoader(options = {}) {
    const box = element("div", "zyrox-section-loader");
    box.setAttribute("role", "status");
    box.setAttribute("aria-live", "polite");
    box.append(Spinner(options.label || "Loading section"));
    box.append(element("span", "zyrox-state-copy", options.label || "Loading section…"));
    return box;
  }

  function SkeletonLoader(options = {}) {
    const lines = Math.max(1, Math.min(8, Number(options.lines) || 3));
    const box = element("div", `zyrox-skeleton ${options.className || ""}`.trim());
    box.setAttribute("aria-hidden", "true");
    for (let index = 0; index < lines; index += 1) {
      const line = element("span", "zyrox-skeleton-line");
      if (index === lines - 1) line.classList.add("zyrox-skeleton-line-short");
      box.append(line);
    }
    return box;
  }

  function ChartSkeleton(options = {}) {
    const chart = element("div", "zyrox-chart-skeleton");
    chart.setAttribute("aria-hidden", "true");
    const label = options.language === "kh" ? "កំពុងផ្ទុកទិន្នន័យទៀនដែលបានផ្ទៀងផ្ទាត់" : "Loading verified candles";
    chart.append(element("span", "zyrox-chart-skeleton-label", options.label || label));
    const candles = element("div", "zyrox-chart-skeleton-candles");
    const bars = [
      [10, 56, 8, 25, -9, true], [16, 46, 12, 33, -11, false],
      [22, 51, 10, 30, -10, true], [28, 39, 13, 39, -13, true],
      [34, 43, 9, 28, -9, false], [40, 32, 14, 42, -14, true],
      [46, 36, 10, 31, -10, false], [52, 26, 14, 44, -15, true],
      [58, 31, 9, 28, -9, true], [64, 20, 13, 41, -14, false],
      [70, 25, 10, 32, -11, true], [76, 15, 14, 43, -14, true],
      [82, 20, 9, 29, -9, false], [88, 10, 13, 40, -13, true]
    ];
    bars.forEach(([x, top, body, wick, wickTop, bullish]) => {
      const candle = element("span", `zyrox-chart-candle${bullish ? " is-up" : " is-down"}`);
      candle.style.left = `${x}%`;
      candle.style.top = `${top}%`;
      candle.style.height = `${body}%`;
      candle.style.setProperty("--wick-top", `${wickTop}px`);
      candle.style.setProperty("--wick-height", `${wick}px`);
      candles.append(candle);
    });
    chart.append(candles, element("span", "zyrox-chart-scan-line"));
    chart.append(element("span", "zyrox-chart-skeleton-axis zyrox-chart-skeleton-axis-y"));
    chart.append(element("span", "zyrox-chart-skeleton-axis zyrox-chart-skeleton-axis-x"));
    return chart;
  }

  function TableSkeleton(options = {}) {
    const rows = Math.max(1, Math.min(10, Number(options.rows) || 4));
    const columns = Math.max(1, Math.min(8, Number(options.columns) || 4));
    const table = element("div", "zyrox-table-skeleton");
    table.setAttribute("aria-hidden", "true");
    for (let rowIndex = 0; rowIndex < rows; rowIndex += 1) {
      const row = element("div", `zyrox-table-skeleton-row${rowIndex === 0 ? " is-header" : ""}`);
      row.style.gridTemplateColumns = `repeat(${columns}, minmax(0, 1fr))`;
      for (let columnIndex = 0; columnIndex < columns; columnIndex += 1) {
        row.append(element("span", "zyrox-skeleton-line"));
      }
      table.append(row);
    }
    return table;
  }

  function CardSkeleton(options = {}) {
    const card = element("div", "zyrox-card-skeleton");
    card.setAttribute("aria-hidden", "true");
    card.append(element("span", "zyrox-card-skeleton-mark"));
    card.append(SkeletonLoader({ lines: options.lines || 3 }));
    return card;
  }

  function ButtonLoader(button, options = {}) {
    if (!button) return { restore() {} };
    const original = {
      children: Array.from(button.childNodes).map(node => node.cloneNode(true)),
      disabled: button.disabled,
      ariaBusy: button.getAttribute("aria-busy")
    };
    button.disabled = true;
    button.setAttribute("aria-busy", "true");
    button.classList.add("is-busy");
    button.replaceChildren(Spinner(options.label || "Working"), element("span", "", options.label || "Working…"));
    let restored = false;
    return {
      restore() {
        if (restored) return;
        restored = true;
        button.replaceChildren(...original.children);
        button.disabled = original.disabled;
        button.classList.remove("is-busy");
        if (original.ariaBusy === null) button.removeAttribute("aria-busy");
        else button.setAttribute("aria-busy", original.ariaBusy);
      }
    };
  }

  function ProgressLoader(options = {}) {
    const wrap = element("div", "zyrox-progress-loader");
    const label = options.label || "In progress";
    wrap.setAttribute("role", "status");
    wrap.setAttribute("aria-live", "polite");
    wrap.append(Spinner(label), element("span", "zyrox-state-copy", label));
    if (Number.isFinite(options.value) && options.value >= 0 && options.value <= 100) {
      wrap.setAttribute("role", "progressbar");
      wrap.setAttribute("aria-valuemin", "0");
      wrap.setAttribute("aria-valuemax", "100");
      wrap.setAttribute("aria-valuenow", String(Math.round(options.value)));
      wrap.append(element("span", "zyrox-progress-track"));
      const fill = element("span", "zyrox-progress-fill");
      fill.style.width = `${Math.round(options.value)}%`;
      wrap.querySelector(".zyrox-progress-track").append(fill);
    }
    return wrap;
  }

  function displayTime(value) {
    if (!value) return "";
    const timestamp = new Date(value);
    return Number.isNaN(timestamp.getTime()) ? "" : timestamp.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
  }

  function SignalRadar(options = {}) {
    const radar = element("span", "zyrox-signal-radar");
    radar.setAttribute("aria-hidden", "true");
    radar.append(element("span", "zyrox-radar-ring ring-outer"));
    radar.append(element("span", "zyrox-radar-ring ring-inner"));
    radar.append(element("span", "zyrox-radar-sweep"));
    radar.append(element("span", "zyrox-radar-ping"));
    const symbol = String(options.symbol || "AI").replace(/[^a-z0-9]/gi, "").slice(0, 5) || "AI";
    radar.append(element("span", "zyrox-radar-symbol", symbol));
    return radar;
  }

  function AIThinkingLoader(options = {}) {
    const panel = element("section", "zyrox-ai-thinking");
    panel.setAttribute("aria-live", "polite");
    panel.setAttribute("aria-busy", options.requestState === "RUNNING" ? "true" : "false");
    const heading = element("div", "zyrox-ai-thinking-heading");
    const titleGroup = element("div", "zyrox-ai-thinking-title-group");
    titleGroup.append(element("h3", "", options.title || "AI analysis activity"));
    titleGroup.append(element("p", "", options.task || "Live state reported by the analysis service."));
    const labels = options.language === "kh" ? stateLabelsKh : stateLabels;
    const overall = element("span", `zyrox-state-badge state-${String(options.requestState || "IDLE").toLowerCase()}`, labels[options.requestState] || labels.IDLE);
    if (options.radarSymbol) {
      const main = element("div", "zyrox-ai-thinking-main");
      main.append(SignalRadar({ symbol: options.radarSymbol }), titleGroup);
      heading.append(main, overall);
    } else {
      heading.append(titleGroup, overall);
    }
    panel.append(heading);

    const agents = Array.isArray(options.agents) ? options.agents : [];
    if (agents.length) {
      const grid = element("div", "zyrox-agent-state-grid");
      agents.forEach(agent => {
        const agentState = String(agent.execution_state || "IDLE").toUpperCase();
        const safeState = Object.prototype.hasOwnProperty.call(stateLabels, agentState) ? agentState : "IDLE";
        const card = element("article", `zyrox-agent-state state-${safeState.toLowerCase()}`);
        const row = element("div", "zyrox-agent-state-row");
        row.append(element("span", "zyrox-agent-state-name", agent.name || agent.agent_name || agent.agent_id || "Agent"));
        row.append(element("span", `zyrox-state-badge state-${safeState.toLowerCase()}`, labels[safeState]));
        card.append(row);
        const task = safeState === "RUNNING" || safeState === "QUEUED" ? agent.current_task : (agent.last_task || agent.current_task);
        if (task) card.append(element("p", "zyrox-agent-task", task));
        const time = safeState === "RUNNING" ? displayTime(agent.last_started_at) : displayTime(agent.last_completed_at);
        if (time) card.append(element("time", "zyrox-agent-time", `${safeState === "RUNNING" ? "Started" : "Updated"} ${time}`));
        if (safeState === "FAILED" && agent.last_error) card.append(element("p", "zyrox-agent-error", agent.last_error));
        grid.append(card);
      });
      panel.append(grid);
    } else {
      panel.append(element("p", "zyrox-ai-no-telemetry", options.emptyMessage || "Waiting for live agent telemetry from the server."));
    }

    if (options.notice) panel.append(element("p", "zyrox-ai-telemetry-note", options.notice));
    return panel;
  }

  function PaymentProcessingLoader(options = {}) {
    const box = element("div", "zyrox-payment-processing");
    box.setAttribute("role", "status");
    box.setAttribute("aria-live", "assertive");
    box.setAttribute("aria-busy", "true");
    box.append(Spinner("Verifying your payment"));
    box.append(element("strong", "", options.title || "Verifying your payment securely…"));
    box.append(element("p", "", options.detail || "The server will confirm the transaction before access changes."));
    return box;
  }

  function EmptyState(options = {}) {
    const box = element("div", "zyrox-empty-state");
    box.setAttribute("role", "status");
    box.append(element("span", "zyrox-empty-icon", options.icon || "◇"));
    box.append(element("strong", "", options.title || "Nothing to show yet"));
    if (options.message) box.append(element("p", "", options.message));
    return box;
  }

  function ErrorState(options = {}) {
    const box = element("div", "zyrox-error-state");
    box.setAttribute("role", "alert");
    box.append(element("strong", "", options.title || "This section could not be loaded"));
    if (options.message) box.append(element("p", "", options.message));
    if (typeof options.onRetry === "function") {
      const retry = element("button", "zyrox-retry-button", options.retryLabel || "Try again");
      retry.type = "button";
      retry.addEventListener("click", options.onRetry, { once: true });
      box.append(retry);
    }
    return box;
  }

  function beginStartup(options = {}) {
    let overlay = document.getElementById("zyrox-startup-loader");
    if (!overlay) return Promise.resolve();
    const renderedLoader = FullScreenLoader(options);
    renderedLoader.id = overlay.id;
    overlay.replaceWith(renderedLoader);
    overlay = renderedLoader;
    const timeoutMs = Math.max(1000, Number(options.timeoutMs) || 14000);
    let finished = false;
    let timeoutId;
    const dismiss = () => {
      if (finished) return;
      finished = true;
      clearTimeout(timeoutId);
      overlay.setAttribute("aria-busy", "false");
      overlay.classList.add("is-dismissed");
      window.setTimeout(() => overlay.remove(), 260);
    };
    const showTimeout = () => {
      if (finished) return;
      const status = overlay._status || overlay.querySelector(".zyrox-loader-copy");
      if (status) status.textContent = options.language === "kh"
        ? "សេវាផ្ទាល់ចំណាយពេលយូរ។ អ្នកអាចបើកផ្ទាំងជួញដូរ ហើយព្យាយាមផ្ទុកសេវាម្តងទៀត។"
        : "Live services are taking longer than expected. You can open the terminal and retry from its status controls.";
      const actions = overlay._actionHost || overlay.querySelector(".zyrox-loader-actions");
      if (actions) {
        actions.hidden = false;
        const proceed = element("button", "zyrox-retry-button", options.language === "kh" ? "បើកផ្ទាំងជួញដូរ" : "Open terminal");
        proceed.type = "button";
        proceed.addEventListener("click", dismiss, { once: true });
        actions.replaceChildren(proceed);
      }
      overlay.classList.add("has-timeout");
    };
    timeoutId = window.setTimeout(showTimeout, timeoutMs);
    const tasks = Array.isArray(options.tasks) ? options.tasks : [];
    return Promise.allSettled(tasks).then(() => {
      if (!finished) dismiss();
    });
  }

  root.ZyroxUI = Object.freeze({
    mount, Spinner, FullScreenLoader, PageLoader, SectionLoader, SkeletonLoader,
    ChartSkeleton, TableSkeleton, CardSkeleton, ButtonLoader, AIThinkingLoader,
    PaymentProcessingLoader, ProgressLoader, SignalRadar, EmptyState, ErrorState, beginStartup
  });
})(window);
