/**
 * ZYROX AI — Schema Studio & Database Platform
 * Information architecture & visualization inspired by SchemaDesign.com
 * Supports:
 * - Interactive ERD Canvas (Pan, Zoom, Drag, Bezier Cardinality Connectors, Minimap)
 * - AI Schema Assistant with Bilingual Khmer/EN Architectural Reasoning
 * - PostgreSQL SQL Studio with Safe Read-Only Execution & Results Grid
 * - Migration Center (Diff calculation, destructive warnings, DDL export, versioned history)
 * - Database Explorer & Live Introspection
 * - Environment Manager (Local, Staging, Render Production)
 */

(function () {
  'use strict';

  // --- Studio State ---
  const state = {
    activeTab: 'designer', // 'overview', 'designer', 'ai-assistant', 'sql-studio', 'migrations', 'explorer', 'environments', 'audit'
    schema: null,
    layout: null,
    selectedTable: null,
    zoom: 1.0,
    panX: 40,
    panY: 40,
    isPanning: false,
    dragNode: null,
    dragOffset: { x: 0, y: 0 },
    activeDomain: 'ALL',
    searchQuery: '',
    unsavedChanges: false,
    sqlResults: null,
    migrationDiff: null,
    isKhmer: false
  };

  const DOMAINS = [
    'ALL',
    'Market Data',
    'AI & Intelligence',
    'Trading & Signals',
    'Auth & SaaS',
    'Notifications',
    'System & Audit'
  ];

  // --- Initialization ---
  window.initSchemaStudio = async function () {
    const container = document.getElementById('schema-studio-root');
    if (!container) return;

    // Check language from main app if available
    state.isKhmer = document.documentElement.lang === 'km' || (window.currentLang === 'km');

    renderStudioShell(container);
    setupEventListeners();
    await loadSchemaData();
  };

  // --- Render Studio Shell ---
  function renderStudioShell(root) {
    root.innerHTML = `
      <div class="studio-wrapper">
        <!-- Studio Header Navigation Bar -->
        <header class="studio-topbar">
          <div class="studio-brand">
            <span class="studio-logo-icon">💠</span>
            <div class="studio-title-block">
              <span class="studio-title">ZYROX <span class="highlight-cyan">SCHEMA STUDIO</span></span>
              <span class="studio-subtitle">PostgreSQL Architecture & AI Database Intelligence</span>
            </div>
            <div id="studio-env-badge" class="studio-env-pill">
              <span class="env-dot"></span>
              <span id="studio-env-name">PROD: POSTGRESQL 16</span>
            </div>
          </div>

          <!-- Studio Nav Tabs -->
          <nav class="studio-nav">
            <button class="s-nav-btn active" data-tab="designer" title="Visual Entity-Relationship Diagram">
              📐 <span class="nav-text">Schema Designer</span>
            </button>
            <button class="s-nav-btn" data-tab="ai-assistant" title="AI-powered Schema Architect">
              🤖 <span class="nav-text">AI Architect</span>
            </button>
            <button class="s-nav-btn" data-tab="sql-studio" title="PostgreSQL SQL Workspace">
              ⚡ <span class="nav-text">SQL Studio</span>
            </button>
            <button class="s-nav-btn" data-tab="migrations" title="Migration Center & DDL">
              🔄 <span class="nav-text">Migrations</span>
            </button>
            <button class="s-nav-btn" data-tab="explorer" title="Database Explorer">
              🗄️ <span class="nav-text">DB Explorer</span>
            </button>
            <button class="s-nav-btn" data-tab="environments" title="Environment Manager">
              🌐 <span class="nav-text">Environments</span>
            </button>
          </nav>

          <!-- Action Controls -->
          <div class="studio-topbar-actions">
            <button id="btn-save-layout" class="btn-s-action" title="Save visual node layout">
              💾 <span class="action-text">Save Canvas</span>
            </button>
            <button id="btn-export-ddl" class="btn-s-action btn-gold" title="Export complete PostgreSQL DDL">
              📄 <span class="action-text">Export DDL</span>
            </button>
            <button id="btn-return-cockpit" class="btn-s-action btn-dark" title="Return to Market Cockpit">
              ✕ <span class="action-text">Exit Studio</span>
            </button>
          </div>
        </header>

        <!-- Main Workspace Body -->
        <div class="studio-main">
          <!-- Left Domain & Table Sidebar -->
          <aside class="studio-sidebar" id="studio-sidebar">
            <div class="sidebar-search-box">
              <span class="search-icon">🔍</span>
              <input type="text" id="studio-table-search" placeholder="Search tables, columns..." autocomplete="off"/>
            </div>

            <div class="domain-filter-tray" id="domain-filters">
              ${DOMAINS.map(d => `<button class="domain-pill ${d === 'ALL' ? 'active' : ''}" data-domain="${d}">${d}</button>`).join('')}
            </div>

            <div class="sidebar-table-list" id="sidebar-table-list">
              <div class="loading-spinner-small">Loading database tables...</div>
            </div>

            <!-- Schema Stats Footer -->
            <div class="sidebar-footer" id="sidebar-schema-stats">
              <span>Tables: <b id="stat-tables-count">0</b></span>
              <span>Columns: <b id="stat-cols-count">0</b></span>
              <span>Relations: <b id="stat-rels-count">0</b></span>
            </div>
          </aside>

          <!-- Center Workspace Views -->
          <main class="studio-viewport" id="studio-viewport">
            <!-- 1. Schema Designer View -->
            <section id="view-designer" class="studio-tab-view active">
              <!-- Canvas Toolbar -->
              <div class="canvas-floating-toolbar">
                <button class="c-tool-btn" id="tool-zoom-in" title="Zoom In">➕</button>
                <button class="c-tool-btn" id="tool-zoom-out" title="Zoom Out">➖</button>
                <button class="c-tool-btn" id="tool-zoom-reset" title="Fit to Screen">🎯</button>
                <button class="c-tool-btn" id="tool-auto-layout" title="Auto-Arrange Layout">✨ Auto-Layout</button>
                <span class="toolbar-sep"></span>
                <span class="zoom-level-indicator" id="zoom-indicator">100%</span>
              </div>

              <!-- Interactive Infinite Canvas Container -->
              <div class="canvas-viewport" id="canvas-viewport">
                <svg id="erd-svg-canvas" class="erd-canvas">
                  <defs>
                    <marker id="arrow" viewBox="0 0 10 10" refX="6" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
                      <path d="M 0 1 L 10 5 L 0 9 z" fill="var(--cyan-neon)"/>
                    </marker>
                    <pattern id="grid-dots" width="24" height="24" patternUnits="userSpaceOnUse">
                      <circle cx="2" cy="2" r="1.2" fill="rgba(255,255,255,0.06)"/>
                    </pattern>
                  </defs>
                  <rect width="100%" height="100%" fill="url(#grid-dots)" />
                  <g id="erd-transform-group">
                    <g id="erd-connections-layer"></g>
                    <g id="erd-nodes-layer"></g>
                  </g>
                </svg>

                <!-- Minimap Overlay -->
                <div class="canvas-minimap" id="canvas-minimap">
                  <canvas id="minimap-canvas" width="140" height="90"></canvas>
                  <div class="minimap-viewport-rect" id="minimap-rect"></div>
                </div>
              </div>

              <!-- Right Properties Inspector Panel -->
              <aside class="table-properties-inspector" id="table-inspector">
                <div class="inspector-header">
                  <h4 id="insp-table-name">Select a Table</h4>
                  <button id="btn-close-inspector" class="btn-icon">✕</button>
                </div>
                <div class="inspector-body" id="inspector-body">
                  <div class="inspector-empty-state">
                    Click any table node on the canvas to inspect columns, constraints, foreign keys, and indexes.
                  </div>
                </div>
              </aside>
            </section>

            <!-- 2. AI Schema Assistant View -->
            <section id="view-ai-assistant" class="studio-tab-view">
              <div class="ai-assistant-container">
                <div class="ai-input-card">
                  <div class="ai-card-title">
                    <span>🤖 ZYROX AI Database Architect</span>
                    <span class="badge-pill badge-cyan">Natural Language to PostgreSQL</span>
                  </div>
                  <p class="ai-card-desc">
                    Describe your required data models, business logic, or schema improvements in <b>English</b> or <b>Natural Khmer (ភាសាខ្មែរ)</b>.
                    The AI will analyze existing tables, normalize structures (3NF), suggest indexes, detect breaking changes, and generate validated PostgreSQL DDL.
                  </p>
                  <div class="ai-prompt-box">
                    <textarea id="ai-schema-prompt" rows="4" placeholder="e.g. Create a multi-currency crypto wallet system with ledger balances, frozen account status, and transaction audits (ឬ បង្កើតតារាងកាបូបលុយរូបិយប័ណ្ណឌីជីថល...)..."></textarea>
                    <div class="ai-prompt-actions">
                      <select id="ai-schema-provider" class="select-styled">
                        <option value="auto">Auto (Groq / Gemini / OpenRouter)</option>
                        <option value="groq">Groq (Llama-3.3 70B & GPT-OSS 120B)</option>
                        <option value="gemini">Google Gemini 2.0 Flash</option>
                      </select>
                      <button id="btn-generate-ai-schema" class="btn-s-action btn-gold">
                        ✨ Generate Schema Proposal
                      </button>
                    </div>
                  </div>
                </div>

                <div id="ai-proposal-results" class="ai-results-area" style="display:none;">
                  <div class="ai-reasoning-grid">
                    <div class="reasoning-card card-en">
                      <h5>🏛️ Architectural Rationale (English)</h5>
                      <div id="ai-res-en" class="reasoning-content"></div>
                    </div>
                    <div class="reasoning-card card-kh">
                      <h5>🇰🇭 ការពន្យល់ស្ថាបត្យកម្មទិន្នន័យ (ភាសាខ្មែរ)</h5>
                      <div id="ai-res-kh" class="reasoning-content khmer-font"></div>
                    </div>
                  </div>

                  <div class="ai-details-tabs">
                    <div class="ai-notice-box" id="ai-normalization-tips"></div>
                    <div class="ai-notice-box warning" id="ai-breaking-warnings"></div>
                  </div>

                  <div class="ai-ddl-card">
                    <div class="ddl-card-header">
                      <h5>Generated PostgreSQL DDL</h5>
                      <div class="ddl-header-buttons">
                        <button id="btn-copy-ai-ddl" class="btn-s-small">📋 Copy SQL</button>
                        <button id="btn-apply-ai-to-canvas" class="btn-s-small btn-gold">📐 Add to Canvas</button>
                      </div>
                    </div>
                    <pre><code id="ai-ddl-code" class="sql-code-block"></code></pre>
                  </div>
                </div>
              </div>
            </section>

            <!-- 3. SQL Studio View -->
            <section id="view-sql-studio" class="studio-tab-view">
              <div class="sql-studio-container">
                <div class="sql-editor-card">
                  <div class="sql-toolbar">
                    <div class="sql-toolbar-left">
                      <button id="btn-run-sql" class="btn-s-action btn-gold">▶ Run Query</button>
                      <button id="btn-explain-sql" class="btn-s-action">🔍 EXPLAIN Plan</button>
                      <label class="sql-toggle-label">
                        <input type="checkbox" id="sql-readonly-toggle" checked />
                        <span>🔒 Read-Only Safety Guard</span>
                      </label>
                    </div>
                    <div class="sql-toolbar-right">
                      <select id="sql-snippets-select" class="select-styled">
                        <option value="">-- Choose Sample Query --</option>
                        <option value="SELECT id, email, role, created_at FROM users LIMIT 10;">List Recent Users</option>
                        <option value="SELECT symbol, entry_price, stop_loss, ai_score, timestamp_utc FROM consensus_reports ORDER BY timestamp_utc DESC LIMIT 10;">Recent Consensus Signals</option>
                        <option value="SELECT name, domain, row_count FROM (SELECT 'users' as name, 'Auth & SaaS' as domain, COUNT(*) as row_count FROM users) sub;">Sample Record Count</option>
                      </select>
                    </div>
                  </div>
                  <textarea id="sql-query-input" rows="7" class="sql-textarea" placeholder="SELECT * FROM users WHERE role = 'ADMIN' LIMIT 50;"></textarea>
                  <div class="sql-meta-bar">
                    <span id="sql-status-text">Ready to execute. Read-only mode prevents destructive mutations.</span>
                    <span id="sql-duration-text"></span>
                  </div>
                </div>

                <div class="sql-results-card">
                  <div class="results-header">
                    <h5>Query Results</h5>
                    <div class="results-actions">
                      <button id="btn-export-csv" class="btn-s-small" style="display:none;">📥 Export CSV</button>
                      <button id="btn-export-json" class="btn-s-small" style="display:none;">📥 Export JSON</button>
                    </div>
                  </div>
                  <div class="results-table-wrapper" id="sql-results-table-wrapper">
                    <div class="results-empty-state">No query executed yet. Press <b>Run Query</b> above.</div>
                  </div>
                </div>
              </div>
            </section>

            <!-- 4. Migration Center View -->
            <section id="view-migrations" class="studio-tab-view">
              <div class="migrations-container">
                <div class="migration-diff-card">
                  <div class="diff-header">
                    <div>
                      <h4>Schema Diff & Versioned DDL Generator</h4>
                      <p>Compares visual diagram changes against live database schema.</p>
                    </div>
                    <button id="btn-calc-diff" class="btn-s-action btn-gold">🔄 Calculate Live Diff</button>
                  </div>
                  <div id="migration-diff-content" class="diff-body">
                    <div class="results-empty-state">Click <b>Calculate Live Diff</b> to inspect differences between the visual canvas and database.</div>
                  </div>
                </div>

                <!-- Migration History Log -->
                <div class="migration-history-card">
                  <h4>Migration Audit History</h4>
                  <div class="history-table-wrapper" id="migration-history-table">
                    <div class="loading-spinner-small">Loading migration history...</div>
                  </div>
                </div>
              </div>
            </section>

            <!-- 5. Database Explorer View -->
            <section id="view-explorer" class="studio-tab-view">
              <div class="explorer-container">
                <div class="explorer-card">
                  <div class="explorer-header">
                    <h4>PostgreSQL Introspected Schema Catalog</h4>
                    <button id="btn-refresh-explorer" class="btn-s-action">🔄 Refresh Metadata</button>
                  </div>
                  <div class="explorer-grid" id="explorer-grid">
                    <div class="loading-spinner-small">Introspecting database objects...</div>
                  </div>
                </div>
              </div>
            </section>

            <!-- 6. Environments View -->
            <section id="view-environments" class="studio-tab-view">
              <div class="environments-container">
                <div class="env-header">
                  <h4>Environment Management</h4>
                  <p>Isolate local SQLite prototyping from Render PostgreSQL production.</p>
                </div>
                <div class="env-cards-grid" id="env-cards-grid">
                  <div class="loading-spinner-small">Inspecting environment configuration...</div>
                </div>
              </div>
            </section>
          </main>
        </div>
      </div>
    `;
  }

  // --- Load Data ---
  async function loadSchemaData() {
    try {
      const [introspectRes, layoutRes, envRes] = await Promise.all([
        fetch('/api/v1/schema/introspect').then(r => r.json()),
        fetch('/api/v1/schema/layout').then(r => r.json()),
        fetch('/api/v1/schema/environments').then(r => r.json())
      ]);

      state.schema = introspectRes;
      state.layout = layoutRes;

      updateEnvBadge(envRes);
      renderSidebarTables(introspectRes.tables || []);
      renderCanvas();
      renderExplorerGrid(introspectRes);
      renderEnvironmentsGrid(envRes);
      loadMigrationHistory();
    } catch (err) {
      console.error('Failed to load schema data:', err);
    }
  }

  function updateEnvBadge(envData) {
    const badge = document.getElementById('studio-env-name');
    if (!badge) return;
    const isProd = envData.is_production;
    const dialect = (envData.dialect || 'postgresql').toUpperCase();
    badge.innerText = `${isProd ? 'RENDER PROD' : 'LOCAL'}: ${dialect}`;
  }

  // --- Sidebar Render ---
  function renderSidebarTables(tables) {
    const list = document.getElementById('sidebar-table-list');
    const statTables = document.getElementById('stat-tables-count');
    const statCols = document.getElementById('stat-cols-count');
    const statRels = document.getElementById('stat-rels-count');

    if (!list) return;

    if (statTables) statTables.innerText = tables.length;
    if (statCols) statCols.innerText = state.schema ? state.schema.column_count : 0;
    if (statRels) statRels.innerText = state.schema ? state.schema.relationship_count : 0;

    const filtered = tables.filter(t => {
      const matchesDomain = state.activeDomain === 'ALL' || t.domain === state.activeDomain;
      const matchesSearch = !state.searchQuery || t.name.toLowerCase().includes(state.searchQuery.toLowerCase());
      return matchesDomain && matchesSearch;
    });

    if (!filtered.length) {
      list.innerHTML = `<div class="sidebar-empty">No tables found matching filter.</div>`;
      return;
    }

    list.innerHTML = filtered.map(t => `
      <div class="sidebar-table-item ${state.selectedTable === t.name ? 'selected' : ''}" data-table="${t.name}">
        <span class="tbl-item-icon">🗂️</span>
        <div class="tbl-item-info">
          <span class="tbl-item-name">${escapeHtml(t.name)}</span>
          <span class="tbl-item-meta">${t.columns.length} cols · ${t.row_count || 0} rows</span>
        </div>
        <span class="tbl-domain-badge">${escapeHtml(t.domain || 'Core')}</span>
      </div>
    `).join('');

    list.querySelectorAll('.sidebar-table-item').forEach(el => {
      el.addEventListener('click', () => {
        const tName = el.getAttribute('data-table');
        selectTable(tName, true);
      });
    });
  }

  // --- Canvas Rendering (SVG + Nodes) ---
  function renderCanvas() {
    const nodesLayer = document.getElementById('erd-nodes-layer');
    const connsLayer = document.getElementById('erd-connections-layer');
    if (!nodesLayer || !connsLayer || !state.schema) return;

    nodesLayer.innerHTML = '';
    connsLayer.innerHTML = '';

    const tables = state.schema.tables || [];
    const layoutNodes = (state.layout && state.layout.nodes) || {};

    // 1. Render Table Nodes
    tables.forEach(t => {
      const pos = layoutNodes[t.name] || { x: 80, y: 80, width: 300 };
      const isSelected = state.selectedTable === t.name;

      const nodeGroup = document.createElementNS('http://www.w3.org/2000/svg', 'g');
      nodeGroup.setAttribute('class', `erd-table-node ${isSelected ? 'selected' : ''}`);
      nodeGroup.setAttribute('id', `node-${t.name}`);
      nodeGroup.setAttribute('transform', `translate(${pos.x}, ${pos.y})`);

      const colHeight = 26;
      const headerHeight = 44;
      const totalHeight = headerHeight + (t.columns.length * colHeight) + 12;

      // Card Background
      nodeGroup.innerHTML = `
        <rect class="erd-node-bg" width="300" height="${totalHeight}" rx="8" ry="8" />
        <rect class="erd-node-header-bg" width="300" height="${headerHeight}" rx="8" ry="8" />
        <rect class="erd-node-header-line" y="${headerHeight}" width="300" height="1" fill="rgba(255,255,255,0.08)" />
        <text class="erd-node-title" x="14" y="27">${escapeHtml(t.name)}</text>
        <text class="erd-node-domain" x="286" y="27" text-anchor="end">${escapeHtml(t.domain || '')}</text>
        <g class="erd-node-columns" transform="translate(0, ${headerHeight + 6})">
          ${t.columns.map((c, i) => {
            const y = i * colHeight + 16;
            const pkIcon = c.is_primary_key ? '🔑' : (c.is_foreign_key ? '🔗' : '•');
            const typeStr = (c.type || '').replace(/\(.*\)/, '');
            return `
              <g class="erd-col-row" transform="translate(0, ${i * colHeight})">
                <text class="col-icon" x="12" y="16">${pkIcon}</text>
                <text class="col-name ${c.is_primary_key ? 'is-pk' : ''}" x="30" y="16">${escapeHtml(c.name)}</text>
                <text class="col-type" x="286" y="16" text-anchor="end">${escapeHtml(typeStr)}</text>
              </g>
            `;
          }).join('')}
        </g>
      `;

      // Drag Listener
      nodeGroup.addEventListener('mousedown', (e) => {
        e.stopPropagation();
        state.dragNode = t.name;
        state.dragOffset = {
          x: (e.clientX / state.zoom) - pos.x,
          y: (e.clientY / state.zoom) - pos.y
        };
        selectTable(t.name, false);
      });

      nodesLayer.appendChild(nodeGroup);
    });

    // 2. Render Relationships (Cubic Bezier Splines)
    const rels = state.schema.relationships || [];
    rels.forEach(rel => {
      const srcPos = layoutNodes[rel.source_table];
      const tgtPos = layoutNodes[rel.target_table];
      if (!srcPos || !tgtPos) return;

      const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
      const d = calculateBezierConnector(srcPos, tgtPos);
      path.setAttribute('d', d);
      path.setAttribute('class', 'erd-rel-line');
      path.setAttribute('marker-end', 'url(#arrow)');
      connsLayer.appendChild(path);
    });

    updateTransformGroup();
    drawMinimap();
  }

  function calculateBezierConnector(src, tgt) {
    const x1 = src.x + 300;
    const y1 = src.y + 60;
    const x2 = tgt.x;
    const y2 = tgt.y + 60;

    const dx = Math.abs(x2 - x1) * 0.5;
    return `M ${x1} ${y1} C ${x1 + dx} ${y1}, ${x2 - dx} ${y2}, ${x2} ${y2}`;
  }

  function updateTransformGroup() {
    const group = document.getElementById('erd-transform-group');
    if (!group) return;
    group.setAttribute('transform', `translate(${state.panX}, ${state.panY}) scale(${state.zoom})`);
    const zoomInd = document.getElementById('zoom-indicator');
    if (zoomInd) zoomInd.innerText = `${Math.round(state.zoom * 100)}%`;
  }

  // --- Minimap ---
  function drawMinimap() {
    const canvas = document.getElementById('minimap-canvas');
    if (!canvas || !state.schema) return;
    const ctx = canvas.getContext('2d');
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    ctx.fillStyle = 'rgba(255,255,255,0.03)';
    ctx.fillRect(0, 0, canvas.width, canvas.height);

    const layoutNodes = (state.layout && state.layout.nodes) || {};
    const scale = 0.04;

    ctx.fillStyle = 'rgba(6, 182, 212, 0.4)';
    Object.values(layoutNodes).forEach(pos => {
      ctx.fillRect(pos.x * scale + 10, pos.y * scale + 10, 300 * scale, 200 * scale);
    });
  }

  // --- Select Table & Show Inspector ---
  function selectTable(tableName, panTo) {
    state.selectedTable = tableName;
    const table = state.schema ? state.schema.tables.find(t => t.name === tableName) : null;
    const inspector = document.getElementById('table-inspector');
    const inspTitle = document.getElementById('insp-table-name');
    const inspBody = document.getElementById('inspector-body');

    if (!table || !inspector) return;

    if (inspTitle) inspTitle.innerText = table.name;
    inspector.classList.add('open');

    if (inspBody) {
      inspBody.innerHTML = `
        <div class="insp-section">
          <div class="insp-meta-row">
            <span>Domain:</span> <b>${escapeHtml(table.domain || 'General')}</b>
          </div>
          <div class="insp-meta-row">
            <span>Estimated Rows:</span> <b>${(table.row_count || 0).toLocaleString()}</b>
          </div>
        </div>

        <div class="insp-section">
          <h5>Columns (${table.columns.length})</h5>
          <div class="insp-col-list">
            ${table.columns.map(c => `
              <div class="insp-col-card">
                <div class="insp-col-head">
                  <span class="col-name ${c.is_primary_key ? 'gold' : ''}">
                    ${c.is_primary_key ? '🔑 ' : (c.is_foreign_key ? '🔗 ' : '')}${escapeHtml(c.name)}
                  </span>
                  <span class="col-badge">${escapeHtml(c.type)}</span>
                </div>
                <div class="insp-col-props">
                  <span>${c.nullable ? 'NULL' : 'NOT NULL'}</span>
                  ${c.default ? `<span>DEF: <code>${escapeHtml(c.default)}</code></span>` : ''}
                  ${c.is_unique ? `<span class="badge-unique">UNIQUE</span>` : ''}
                </div>
                ${c.foreign_key_target ? `
                  <div class="insp-fk-note">➜ References: <b>${escapeHtml(c.foreign_key_target.target_table)}.${escapeHtml(c.foreign_key_target.target_column)}</b></div>
                ` : ''}
              </div>
            `).join('')}
          </div>
        </div>

        ${table.indexes && table.indexes.length ? `
          <div class="insp-section">
            <h5>Indexes (${table.indexes.length})</h5>
            <ul class="insp-idx-list">
              ${table.indexes.map(idx => `
                <li><code>${escapeHtml(idx.name)}</code> (${idx.column_names.join(', ')})${idx.unique ? ' [UNIQUE]' : ''}</li>
              `).join('')}
            </ul>
          </div>
        ` : ''}
      `;
    }

    // Highlight node on canvas
    document.querySelectorAll('.erd-table-node').forEach(el => {
      el.classList.toggle('selected', el.getAttribute('id') === `node-${tableName}`);
    });

    // Optionally center canvas on table
    if (panTo && state.layout && state.layout.nodes && state.layout.nodes[tableName]) {
      const pos = state.layout.nodes[tableName];
      const viewport = document.getElementById('canvas-viewport');
      if (viewport) {
        state.panX = (viewport.clientWidth / 2) - (pos.x * state.zoom);
        state.panY = (viewport.clientHeight / 2) - (pos.y * state.zoom);
        updateTransformGroup();
      }
    }
  }

  // --- Event Listeners ---
  function setupEventListeners() {
    // 1. Navigation Tab Switching
    document.querySelectorAll('.s-nav-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        const tab = btn.getAttribute('data-tab');
        switchTab(tab);
      });
    });

    // 2. Domain Filter Pills
    const domainTray = document.getElementById('domain-filters');
    if (domainTray) {
      domainTray.addEventListener('click', (e) => {
        const btn = e.target.closest('.domain-pill');
        if (!btn) return;
        domainTray.querySelectorAll('.domain-pill').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        state.activeDomain = btn.getAttribute('data-domain');
        if (state.schema) renderSidebarTables(state.schema.tables);
      });
    }

    // 3. Search Bar
    const searchInput = document.getElementById('studio-table-search');
    if (searchInput) {
      searchInput.addEventListener('input', (e) => {
        state.searchQuery = e.target.value.trim();
        if (state.schema) renderSidebarTables(state.schema.tables);
      });
    }

    // 4. Canvas Panning and Dragging
    const viewport = document.getElementById('canvas-viewport');
    if (viewport) {
      viewport.addEventListener('mousedown', (e) => {
        if (e.target.closest('.erd-table-node') || e.target.closest('.canvas-floating-toolbar') || e.target.closest('.table-properties-inspector')) return;
        state.isPanning = true;
        state.panStart = { x: e.clientX - state.panX, y: e.clientY - state.panY };
      });

      window.addEventListener('mousemove', (e) => {
        if (state.isPanning) {
          state.panX = e.clientX - state.panStart.x;
          state.panY = e.clientY - state.panStart.y;
          updateTransformGroup();
        } else if (state.dragNode) {
          const newX = (e.clientX / state.zoom) - state.dragOffset.x;
          const newY = (e.clientY / state.zoom) - state.dragOffset.y;
          if (state.layout && state.layout.nodes) {
            state.layout.nodes[state.dragNode] = { ...state.layout.nodes[state.dragNode], x: newX, y: newY };
          }
          const nodeEl = document.getElementById(`node-${state.dragNode}`);
          if (nodeEl) nodeEl.setAttribute('transform', `translate(${newX}, ${newY})`);
          reconnectLines();
          state.unsavedChanges = true;
        }
      });

      window.addEventListener('mouseup', () => {
        state.isPanning = false;
        state.dragNode = null;
      });

      viewport.addEventListener('wheel', (e) => {
        e.preventDefault();
        const delta = e.deltaY > 0 ? -0.1 : 0.1;
        state.zoom = Math.min(2.5, Math.max(0.3, state.zoom + delta));
        updateTransformGroup();
      }, { passive: false });
    }

    // 5. Canvas Toolbar Buttons
    const zoomIn = document.getElementById('tool-zoom-in');
    const zoomOut = document.getElementById('tool-zoom-out');
    const zoomReset = document.getElementById('tool-zoom-reset');
    const autoLayout = document.getElementById('tool-auto-layout');

    if (zoomIn) zoomIn.addEventListener('click', () => { state.zoom = Math.min(2.5, state.zoom + 0.15); updateTransformGroup(); });
    if (zoomOut) zoomOut.addEventListener('click', () => { state.zoom = Math.max(0.3, state.zoom - 0.15); updateTransformGroup(); });
    if (zoomReset) zoomReset.addEventListener('click', () => { state.zoom = 1.0; state.panX = 40; state.panY = 40; updateTransformGroup(); });
    if (autoLayout) autoLayout.addEventListener('click', runAutoLayout);

    // 6. Top Actions
    const btnSaveLayout = document.getElementById('btn-save-layout');
    const btnExportDdl = document.getElementById('btn-export-ddl');
    const btnExit = document.getElementById('btn-return-cockpit');

    if (btnSaveLayout) btnSaveLayout.addEventListener('click', saveLayoutToServer);
    if (btnExportDdl) btnExportDdl.addEventListener('click', exportFullDdl);
    if (btnExit) btnExit.addEventListener('click', closeStudioAndReturnToTrading);

    // 7. Inspector Close
    const btnCloseInsp = document.getElementById('btn-close-inspector');
    if (btnCloseInsp) btnCloseInsp.addEventListener('click', () => {
      document.getElementById('table-inspector').classList.remove('open');
      state.selectedTable = null;
      document.querySelectorAll('.erd-table-node').forEach(n => n.classList.remove('selected'));
    });

    // 8. AI Schema Assistant
    const btnGenAI = document.getElementById('btn-generate-ai-schema');
    if (btnGenAI) btnGenAI.addEventListener('click', runAISchemaGeneration);

    const btnCopyAiDdl = document.getElementById('btn-copy-ai-ddl');
    if (btnCopyAiDdl) btnCopyAiDdl.addEventListener('click', () => {
      const code = document.getElementById('ai-ddl-code').innerText;
      navigator.clipboard.writeText(code);
      btnCopyAiDdl.innerText = '✓ Copied!';
      setTimeout(() => { btnCopyAiDdl.innerText = '📋 Copy SQL'; }, 2000);
    });

    // 9. SQL Studio
    const btnRunSql = document.getElementById('btn-run-sql');
    const btnExplainSql = document.getElementById('btn-explain-sql');
    const sqlSnippetSelect = document.getElementById('sql-snippets-select');

    if (btnRunSql) btnRunSql.addEventListener('click', () => executeStudioSQL(false));
    if (btnExplainSql) btnExplainSql.addEventListener('click', () => executeStudioSQL(true));
    if (sqlSnippetSelect) sqlSnippetSelect.addEventListener('change', (e) => {
      if (e.target.value) document.getElementById('sql-query-input').value = e.target.value;
    });

    // 10. Migration Center
    const btnCalcDiff = document.getElementById('btn-calc-diff');
    if (btnCalcDiff) btnCalcDiff.addEventListener('click', calculateMigrationDiff);
  }

  function switchTab(tabName) {
    state.activeTab = tabName;
    document.querySelectorAll('.s-nav-btn').forEach(btn => {
      btn.classList.toggle('active', btn.getAttribute('data-tab') === tabName);
    });
    document.querySelectorAll('.studio-tab-view').forEach(view => {
      view.classList.toggle('active', view.getAttribute('id') === `view-${tabName}`);
    });
  }

  function reconnectLines() {
    const connsLayer = document.getElementById('erd-connections-layer');
    if (!connsLayer || !state.schema) return;
    connsLayer.innerHTML = '';
    const layoutNodes = (state.layout && state.layout.nodes) || {};

    (state.schema.relationships || []).forEach(rel => {
      const srcPos = layoutNodes[rel.source_table];
      const tgtPos = layoutNodes[rel.target_table];
      if (!srcPos || !tgtPos) return;

      const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
      path.setAttribute('d', calculateBezierConnector(srcPos, tgtPos));
      path.setAttribute('class', 'erd-rel-line');
      path.setAttribute('marker-end', 'url(#arrow)');
      connsLayer.appendChild(path);
    });
  }

  function runAutoLayout() {
    if (!state.schema) return;
    let col = 0, row = 0;
    const maxCols = 4;
    state.schema.tables.forEach(t => {
      if (!state.layout.nodes[t.name]) state.layout.nodes[t.name] = {};
      state.layout.nodes[t.name].x = 60 + (col % maxCols) * 380;
      state.layout.nodes[t.name].y = 60 + row * 340;
      col++;
      if (col % maxCols === 0) row++;
    });
    renderCanvas();
    state.unsavedChanges = true;
  }

  async function saveLayoutToServer() {
    const btn = document.getElementById('btn-save-layout');
    if (btn) btn.innerText = '💾 Saving...';
    try {
      await fetch('/api/v1/schema/layout', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          viewport: { zoom: state.zoom, pan_x: state.panX, pan_y: state.panY },
          nodes: state.layout ? state.layout.nodes : {}
        })
      });
      state.unsavedChanges = false;
      if (btn) btn.innerText = '✓ Saved!';
      setTimeout(() => { if (btn) btn.innerText = '💾 Save Canvas'; }, 2000);
    } catch (err) {
      if (btn) btn.innerText = '⚠️ Save Failed';
    }
  }

  async function exportFullDdl() {
    try {
      const r = await fetch('/api/v1/schema/ddl').then(res => res.json());
      const blob = new Blob([r.ddl], { type: 'text/sql' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `zyrox_schema_${new Date().toISOString().slice(0, 10)}.sql`;
      a.click();
    } catch (err) {
      alert('Failed to export DDL');
    }
  }

  function closeStudioAndReturnToTrading() {
    const root = document.getElementById('schema-studio-root');
    const tradingApp = document.getElementById('app-container');
    if (root) root.style.display = 'none';
    if (tradingApp) tradingApp.style.display = 'flex';
  }

  // --- AI Schema Generation ---
  async function runAISchemaGeneration() {
    const promptInput = document.getElementById('ai-schema-prompt');
    const providerSelect = document.getElementById('ai-schema-provider');
    const btn = document.getElementById('btn-generate-ai-schema');
    const resultsArea = document.getElementById('ai-proposal-results');

    const promptText = promptInput.value.trim();
    if (!promptText) {
      alert('Please enter a description for the proposed schema.');
      return;
    }

    btn.disabled = true;
    btn.innerText = '⏳ AI Architect Analyzing...';

    try {
      const res = await fetch('/api/v1/schema/ai/propose', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          prompt: promptText,
          provider: providerSelect ? providerSelect.value : 'auto'
        })
      }).then(r => r.json());

      const prop = res.proposal || {};
      document.getElementById('ai-res-en').innerText = prop.reasoning_en || 'No reasoning supplied.';
      document.getElementById('ai-res-kh').innerText = prop.reasoning_kh || 'គ្មានការពន្យល់។';

      const normBox = document.getElementById('ai-normalization-tips');
      if (normBox && prop.normalization_tips) {
        normBox.innerHTML = `<b>Normalization (3NF) Guidance:</b><ul>${prop.normalization_tips.map(t => `<li>${escapeHtml(t)}</li>`).join('')}</ul>`;
      }

      const warnBox = document.getElementById('ai-breaking-warnings');
      if (warnBox && prop.breaking_change_warnings) {
        warnBox.innerHTML = `<b>Migration Hazards & Index Advice:</b><ul>${prop.breaking_change_warnings.map(w => `<li>${escapeHtml(w)}</li>`).join('')}</ul>`;
      }

      document.getElementById('ai-ddl-code').innerText = prop.proposed_ddl || '-- No DDL generated';
      resultsArea.style.display = 'block';

    } catch (err) {
      alert('AI Generation error: ' + err.message);
    } finally {
      btn.disabled = false;
      btn.innerText = '✨ Generate Schema Proposal';
    }
  }

  // --- SQL Studio Execution ---
  async function executeStudioSQL(explain) {
    const query = document.getElementById('sql-query-input').value.trim();
    const readOnly = document.getElementById('sql-readonly-toggle').checked;
    const statusText = document.getElementById('sql-status-text');
    const durationText = document.getElementById('sql-duration-text');
    const tableWrapper = document.getElementById('sql-results-table-wrapper');

    if (!query) return;

    statusText.innerText = 'Executing query...';
    durationText.innerText = '';

    try {
      const res = await fetch('/api/v1/schema/sql/query', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          query: query,
          read_only: readOnly,
          explain_plan: explain,
          max_rows: 200
        })
      }).then(r => r.json());

      durationText.innerText = `[${res.execution_time_ms || 0}ms]`;

      if (res.status === 'FORBIDDEN') {
        statusText.innerHTML = `<span style="color:var(--accent-red)">⚠️ ${escapeHtml(res.error)}</span>`;
        tableWrapper.innerHTML = `<div class="sql-error-box">${escapeHtml(res.suggestion || res.error)}</div>`;
        return;
      }

      if (res.status === 'ERROR') {
        statusText.innerHTML = `<span style="color:var(--accent-red)">❌ Execution Error</span>`;
        tableWrapper.innerHTML = `<div class="sql-error-box">${escapeHtml(res.error)}</div>`;
        return;
      }

      statusText.innerText = `Query succeeded. Returned ${res.row_count || 0} rows.`;

      // Render table
      const cols = res.columns || [];
      const rows = res.rows || [];

      if (!rows.length) {
        tableWrapper.innerHTML = `<div class="results-empty-state">Query returned 0 rows.</div>`;
        return;
      }

      tableWrapper.innerHTML = `
        <table class="studio-data-table">
          <thead>
            <tr>${cols.map(c => `<th>${escapeHtml(c)}</th>`).join('')}</tr>
          </thead>
          <tbody>
            ${rows.map(r => `
              <tr>${r.map(val => `<td>${escapeHtml(val === null ? 'NULL' : val)}</td>`).join('')}</tr>
            `).join('')}
          </tbody>
        </table>
      `;

    } catch (err) {
      statusText.innerText = 'Network error running query.';
    }
  }

  // --- Migration Diff ---
  async function calculateMigrationDiff() {
    const diffContainer = document.getElementById('migration-diff-content');
    if (!diffContainer || !state.schema) return;

    diffContainer.innerHTML = '<div class="loading-spinner-small">Calculating schema diff against live database...</div>';

    try {
      const res = await fetch('/api/v1/schema/migrations/diff', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ target_schema: state.schema })
      }).then(r => r.json());

      const diff = res.diff || {};

      diffContainer.innerHTML = `
        <div class="diff-summary-bar">
          <span class="badge-pill ${diff.has_changes ? 'badge-cyan' : 'badge-gold'}">
            ${diff.has_changes ? 'CHANGES DETECTED' : 'LIVE DB IS IN SYNC'}
          </span>
          ${diff.is_destructive ? '<span class="badge-pill badge-red">⚠️ DESTRUCTIVE OPERATIONS DETECTED</span>' : ''}
        </div>

        ${diff.destructive_warnings && diff.destructive_warnings.length ? `
          <div class="destructive-warning-box">
            <b>Safety Notice:</b>
            <ul>${diff.destructive_warnings.map(w => `<li>${escapeHtml(w)}</li>`).join('')}</ul>
          </div>
        ` : ''}

        <div class="diff-code-section">
          <h5>Forward Upgrade DDL:</h5>
          <pre><code class="sql-code-block">${escapeHtml(diff.upgrade_sql)}</code></pre>
        </div>

        <div class="diff-actions">
          <button id="btn-apply-migration-action" class="btn-s-action btn-gold" ${!diff.has_changes ? 'disabled' : ''}>
            🚀 Apply Migration
          </button>
        </div>
      `;

      const applyBtn = document.getElementById('btn-apply-migration-action');
      if (applyBtn) {
        applyBtn.addEventListener('click', async () => {
          if (!confirm('Apply this migration to the active database?')) return;
          const applyRes = await fetch('/api/v1/schema/migrations/apply', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              migration_name: `manual_schema_sync_${Date.now()}`,
              upgrade_sql: diff.upgrade_sql,
              downgrade_sql: diff.downgrade_sql,
              confirm_production_risk: true
            })
          }).then(r => r.json());

          alert(applyRes.status === 'SUCCESS' ? 'Migration applied successfully!' : 'Migration failed: ' + applyRes.error);
          loadMigrationHistory();
        });
      }

    } catch (err) {
      diffContainer.innerHTML = `<div class="sql-error-box">Failed to calculate diff: ${escapeHtml(err.message)}</div>`;
    }
  }

  async function loadMigrationHistory() {
    const tableDiv = document.getElementById('migration-history-table');
    if (!tableDiv) return;

    try {
      const res = await fetch('/api/v1/schema/migrations/history').then(r => r.json());
      const history = res.history || [];

      if (!history.length) {
        tableDiv.innerHTML = '<div class="results-empty-state">No recorded migrations in schema_migrations table yet.</div>';
        return;
      }

      tableDiv.innerHTML = `
        <table class="studio-data-table">
          <thead>
            <tr>
              <th>ID</th>
              <th>Migration Name</th>
              <th>Environment</th>
              <th>Applied At</th>
              <th>Duration</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            ${history.map(h => `
              <tr>
                <td><code>${escapeHtml(h.id)}</code></td>
                <td><b>${escapeHtml(h.migration_name)}</b></td>
                <td>${escapeHtml(h.environment)}</td>
                <td>${escapeHtml(h.applied_at)}</td>
                <td>${h.duration_ms}ms</td>
                <td><span class="badge-pill ${h.status === 'SUCCESS' ? 'badge-green' : 'badge-red'}">${h.status}</span></td>
              </tr>
            `).join('')}
          </tbody>
        </table>
      `;
    } catch (err) {
      tableDiv.innerHTML = '<div class="results-empty-state">History table initialized.</div>';
    }
  }

  // --- Explorer Grid ---
  function renderExplorerGrid(schema) {
    const grid = document.getElementById('explorer-grid');
    if (!grid || !schema) return;

    grid.innerHTML = (schema.tables || []).map(t => `
      <div class="explorer-card-item">
        <div class="exp-card-header">
          <span class="exp-tbl-name">📊 ${escapeHtml(t.name)}</span>
          <span class="exp-tbl-domain">${escapeHtml(t.domain)}</span>
        </div>
        <div class="exp-card-meta">
          <span>${t.columns.length} Columns</span>
          <span>${(t.row_count || 0).toLocaleString()} Rows</span>
        </div>
        <div class="exp-card-cols">
          ${t.columns.slice(0, 6).map(c => `
            <div class="exp-col-chip ${c.is_primary_key ? 'pk' : ''}">
              ${c.is_primary_key ? '🔑 ' : ''}${escapeHtml(c.name)}: <i>${escapeHtml(c.type.split('(')[0])}</i>
            </div>
          `).join('')}
          ${t.columns.length > 6 ? `<div class="exp-col-chip more">+${t.columns.length - 6} more</div>` : ''}
        </div>
      </div>
    `).join('');
  }

  // --- Environments Grid ---
  function renderEnvironmentsGrid(envData) {
    const grid = document.getElementById('env-cards-grid');
    if (!grid || !envData) return;

    grid.innerHTML = (envData.environments || []).map(e => `
      <div class="env-card ${e.is_active ? 'active-env' : ''}">
        <div class="env-card-top">
          <h4>${escapeHtml(e.name)}</h4>
          <span class="env-status-badge ${e.status === 'CONNECTED' ? 'green' : 'gold'}">${e.status}</span>
        </div>
        <div class="env-card-type">${escapeHtml(e.type)}</div>
        <div class="env-card-details">
          <span>Mode: <b>${e.read_only ? 'Read-Only Protected' : 'Full DDL Permitted'}</b></span>
          <span>Current Active: <b>${e.is_active ? 'YES' : 'NO'}</b></span>
        </div>
      </div>
    `).join('');
  }

  function escapeHtml(str) {
    return String(str || '').replace(/[&<>"']/g, m => ({
      '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;'
    }[m]));
  }

})();

