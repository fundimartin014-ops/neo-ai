/**
 * neo-chat-tools.js
 * =================
 * Vanilla JS version for Neo's chat UI.
 * No React, no build step, no dependencies.
 * Just include this + NeoChatToolEmbed.css in your HTML.
 * 
 * Usage:
 *   <div id="neo-chat"></div>
 *   <script src="neo-chat-tools.js"></script>
 *   <script>
 *     const chat = new NeoChatUI("neo-chat", {
 *       theme: "dark",
 *       onSend: (msg) => console.log("User said:", msg),
 *       onToolOpen: (tool) => console.log("Opened:", tool.name)
 *     });
 *     
 *     // When your backend returns tool data:
 *     chat.addMessage({
 *       role: "ai",
 *       content: "Here's a tool for that!",
 *       tool_data: { has_tool: true, tools: [...], iframe_html: "..." }
 *     });
 *   </script>
 */

(function (global) {
  "use strict";

  const QUICK_ACTIONS = [
    { id: "excalidraw", label: "🎨 Draw", icon: "✏️", trigger: "draw" },
    { id: "json-crack", label: "📊 JSON", icon: "🔍", trigger: "json" },
    { id: "cyberchef", label: "🔒 Encode", icon: "🔐", trigger: "encode" },
    { id: "carbon", label: "💻 Code", icon: "📸", trigger: "code screenshot" },
    { id: "regexr", label: "📐 Regex", icon: "🔤", trigger: "regex" },
    { id: "squoosh", label: "🖼️ Image", icon: "🗜️", trigger: "compress image" },
    { id: "bentopdf", label: "📄 PDF", icon: "📑", trigger: "pdf" },
    { id: "vert", label: "🔄 Convert", icon: "⚙️", trigger: "convert" },
  ];

  class NeoChatUI {
    constructor(containerId, options = {}) {
      this.container = document.getElementById(containerId);
      if (!this.container) throw new Error(`Container #${containerId} not found`);

      this.options = {
        theme: options.theme || "dark",
        onSend: options.onSend || (() => {}),
        onToolOpen: options.onToolOpen || (() => {}),
        ...options
      };

      this.messages = [];
      this.expandedTool = null;
      this.isLoading = false;

      this._init();
    }

    _init() {
      this.container.className = `neo-chat-container neo-theme-${this.options.theme}`;
      this.container.innerHTML = `
        <div class="neo-messages"></div>
        <div class="neo-quick-actions"></div>
        <form class="neo-input-area">
          <input type="text" class="neo-input" placeholder="Ask Neo anything, or type a task like 'draw a diagram'…" />
          <button type="submit" class="neo-send-btn">➤</button>
        </form>
      `;

      this.messagesEl = this.container.querySelector(".neo-messages");
      this.quickActionsEl = this.container.querySelector(".neo-quick-actions");
      this.inputEl = this.container.querySelector(".neo-input");
      this.formEl = this.container.querySelector(".neo-input-area");
      this.sendBtn = this.container.querySelector(".neo-send-btn");

      this._renderQuickActions();
      this._bindEvents();
    }

    _bindEvents() {
      this.formEl.addEventListener("submit", (e) => {
        e.preventDefault();
        const text = this.inputEl.value.trim();
        if (!text || this.isLoading) return;
        this.addMessage({ role: "user", content: text });
        this.inputEl.value = "";
        this.options.onSend(text);
      });
    }

    _renderQuickActions() {
      this.quickActionsEl.innerHTML = QUICK_ACTIONS.map(a => `
        <button class="neo-quick-btn" data-trigger="${a.trigger}" data-id="${a.id}" title="${a.label}">
          <span class="neo-quick-icon">${a.icon}</span>
          <span class="neo-quick-label">${a.label}</span>
        </button>
      `).join("");

      this.quickActionsEl.querySelectorAll(".neo-quick-btn").forEach(btn => {
        btn.addEventListener("click", () => {
          const trigger = btn.dataset.trigger;
          this.inputEl.value = trigger;
          this.formEl.dispatchEvent(new Event("submit"));
        });
      });
    }

    addMessage(message) {
      this.messages.push(message);
      const el = document.createElement("div");
      el.className = `neo-message ${message.role === "user" ? "neo-user" : "neo-ai"}`;
      el.style.animation = "neoFadeIn 0.3s ease";

      const avatar = message.role === "user" ? "🧑" : "🤖";
      let contentHtml = "";

      if (message.role === "ai" && message.tool_data?.has_tool) {
        contentHtml = this._renderToolSuggestion(message.tool_data);
      }

      if (message.content) {
        contentHtml += `<div class="neo-message-text">${this._escapeHtml(message.content)}</div>`;
      }

      el.innerHTML = `
        <div class="neo-message-avatar">${avatar}</div>
        <div class="neo-message-content">${contentHtml}</div>
      `;

      // Bind tool buttons after insert
      if (message.tool_data?.has_tool) {
        setTimeout(() => this._bindToolButtons(el, message.tool_data), 0);
      }

      this.messagesEl.appendChild(el);
      this._scrollToBottom();
    }

    _renderToolSuggestion(toolData) {
      const { tools, response_text } = toolData;
      const topTool = tools[0];

      let html = `<div class="neo-tool-suggestion">`;

      if (response_text) {
        html += `<div class="neo-tool-text"><span class="neo-tool-badge">🛠️ Tool</span><p>${this._mdLite(response_text)}</p></div>`;
      }

      html += `<div class="neo-tool-actions">`;
      tools.slice(0, 3).forEach(tool => {
        const stars = tool.stars ? `⭐ ${this._formatStars(tool.stars)}` : "";
        const meta = tool.integration_type === "selfhost" ? " · Self-host" : " · Browser";
        html += `
          <button class="neo-tool-action-btn" data-tool-id="${tool.id}" data-tool-url="${tool.url}" data-tool-name="${this._escapeHtml(tool.name)}">
            <span class="neo-tool-action-name">${this._escapeHtml(tool.name)}</span>
            <span class="neo-tool-action-meta">${stars}${meta}</span>
          </button>
        `;
      });
      html += `</div>`;

      // Iframe placeholder
      html += `<div class="neo-iframe-slot" style="display:none;"></div>`;

      // Self-host hint
      if (topTool?.integration_type === "selfhost" && topTool?.github) {
        html += `
          <div class="neo-selfhost-hint">
            <span>💡</span>
            <span>Want offline access? <a href="${topTool.github}" target="_blank" rel="noopener">Self-host ${this._escapeHtml(topTool.name)}</a></span>
          </div>
        `;
      }

      html += `</div>`;
      return html;
    }

    _bindToolButtons(messageEl, toolData) {
      const buttons = messageEl.querySelectorAll(".neo-tool-action-btn");
      const slot = messageEl.querySelector(".neo-iframe-slot");

      buttons.forEach(btn => {
        btn.addEventListener("click", () => {
          const toolId = btn.dataset.toolId;
          const toolUrl = btn.dataset.toolUrl;
          const toolName = btn.dataset.toolName;

          // Toggle active state
          buttons.forEach(b => b.classList.remove("active"));

          if (this.expandedTool === toolId) {
            this.expandedTool = null;
            slot.style.display = "none";
            slot.innerHTML = "";
            return;
          }

          btn.classList.add("active");
          this.expandedTool = toolId;

          // Build iframe
          slot.innerHTML = `
            <div class="neo-iframe-wrapper" style="animation: neoSlideDown 0.25s ease;">
              <div class="neo-iframe-header">
                <span class="neo-iframe-title">${toolName}</span>
                <div class="neo-iframe-controls">
                  <button class="neo-iframe-btn neo-open-tab" title="Open in new tab">↗</button>
                  <button class="neo-iframe-btn neo-iframe-close" title="Close">✕</button>
                </div>
              </div>
              <div class="neo-iframe-container">
                <iframe src="${toolUrl}" 
                  sandbox="allow-scripts allow-same-origin allow-forms allow-downloads allow-popups"
                  loading="lazy" allow="clipboard-write; clipboard-read"
                  title="${toolName}"></iframe>
                <div class="neo-iframe-loading">
                  <span class="neo-spinner"></span>
                  <span>Loading tool…</span>
                </div>
              </div>
            </div>
          `;
          slot.style.display = "block";

          // Bind iframe controls
          const openBtn = slot.querySelector(".neo-open-tab");
          const closeBtn = slot.querySelector(".neo-iframe-close");
          const iframe = slot.querySelector("iframe");

          openBtn.addEventListener("click", () => window.open(toolUrl, "_blank", "noopener,noreferrer"));
          closeBtn.addEventListener("click", () => {
            this.expandedTool = null;
            slot.style.display = "none";
            slot.innerHTML = "";
            btn.classList.remove("active");
          });

          // Hide spinner when loaded
          iframe.addEventListener("load", () => {
            const loader = slot.querySelector(".neo-iframe-loading");
            if (loader) loader.style.display = "none";
          });

          this.options.onToolOpen({ id: toolId, name: toolName, url: toolUrl });
          this._scrollToBottom();
        });
      });
    }

    setLoading(loading) {
      this.isLoading = loading;
      this.sendBtn.disabled = loading;
      this.sendBtn.textContent = loading ? "⏳" : "➤";
      this.inputEl.disabled = loading;

      if (loading) {
        const typingEl = document.createElement("div");
        typingEl.className = "neo-message neo-ai neo-typing-msg";
        typingEl.innerHTML = `
          <div class="neo-message-avatar">🤖</div>
          <div class="neo-message-content">
            <div class="neo-typing"><span></span><span></span><span></span></div>
          </div>
        `;
        this.messagesEl.appendChild(typingEl);
        this._scrollToBottom();
      } else {
        const typing = this.messagesEl.querySelector(".neo-typing-msg");
        if (typing) typing.remove();
      }
    }

    _scrollToBottom() {
      this.messagesEl.scrollTop = this.messagesEl.scrollHeight;
    }

    _escapeHtml(text) {
      const div = document.createElement("div");
      div.textContent = text;
      return div.innerHTML;
    }

    _mdLite(text) {
      return text
        .replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>")
        .replace(/\[(.*?)\]\((.*?)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>');
    }

    _formatStars(n) {
      return n >= 1000 ? (n / 1000).toFixed(1) + "k" : n.toString();
    }
  }

  // Expose globally
  global.NeoChatUI = NeoChatUI;

})(window);
