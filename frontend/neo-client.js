/**
 * neo-client.js
 * =============
 * Frontend API client for Neo's FastAPI backend.
 * Drop this into your frontend (works with both React and Vanilla JS).
 * 
 * Usage:
 *   const neo = new NeoClient("http://localhost:8000");
 *   
 *   // Chat
 *   const response = await neo.chat("draw a diagram");
 *   // → { role: "ai", content: "...", tool_data: { has_tool: true, ... } }
 *   
 *   // Streaming chat
 *   await neo.chatStream("hello", (chunk) => console.log(chunk));
 *   
 *   // Search tools
 *   const results = await neo.searchTools("pdf converter");
 *   
 *   // Get embed HTML
 *   const embed = await neo.getEmbed("excalidraw");
 */

class NeoClient {
  constructor(baseURL = "http://localhost:8000") {
    this.baseURL = baseURL.replace(/\/$/, "");
    this.history = [];
  }

  // ─── Core Chat ───────────────────────────────────────────────────────────

  async chat(message, options = {}) {
    const body = {
      message,
      history: this.history,
      stream: false,
      model: options.model || null,
      temperature: options.temperature ?? 0.7
    };

    const res = await fetch(`${this.baseURL}/api/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body)
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `HTTP ${res.status}`);
    }

    const data = await res.json();

    // Update local history
    this.history.push({ role: "user", content: message });
    this.history.push({ role: "ai", content: data.content, tool_data: data.tool_data });

    // Trim history to last 20 messages to save memory
    if (this.history.length > 20) {
      this.history = this.history.slice(-20);
    }

    return data;
  }

  // ─── Streaming Chat (SSE) ────────────────────────────────────────────────

  async chatStream(message, onChunk, options = {}) {
    const body = {
      message,
      history: this.history,
      stream: true,
      model: options.model || null,
      temperature: options.temperature ?? 0.7
    };

    const res = await fetch(`${this.baseURL}/api/chat/stream`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body)
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `HTTP ${res.status}`);
    }

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop();

      for (const line of lines) {
        if (line.startsWith("data: ")) {
          try {
            const chunk = JSON.parse(line.slice(6));
            onChunk(chunk);
          } catch (e) {
            // ignore parse errors
          }
        }
      }
    }
  }

  // ─── Tool Search ─────────────────────────────────────────────────────────

  async searchTools(query, limit = 5, category = null) {
    const body = { query, limit, category };
    const res = await fetch(`${this.baseURL}/api/tools/search`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body)
    });
    return res.json();
  }

  async searchToolsGet(query, limit = 5) {
    const params = new URLSearchParams({ q: query, limit: String(limit) });
    const res = await fetch(`${this.baseURL}/api/tools/search?${params}`);
    return res.json();
  }

  // ─── Tool Embed ──────────────────────────────────────────────────────────

  async getEmbed(toolId, width = "100%", height = "480px") {
    const params = new URLSearchParams({ width, height });
    const res = await fetch(`${this.baseURL}/api/tools/${toolId}/embed?${params}`);
    return res.json();
  }

  // ─── Registry Stats ──────────────────────────────────────────────────────

  async getStats() {
    const res = await fetch(`${this.baseURL}/api/tools/stats`);
    return res.json();
  }

  // ─── Quick Actions ───────────────────────────────────────────────────────

  async getQuickActions() {
    const res = await fetch(`${this.baseURL}/api/tools/quick-actions`);
    return res.json();
  }

  // ─── Categories ──────────────────────────────────────────────────────────

  async getCategories() {
    const res = await fetch(`${this.baseURL}/api/tools/categories`);
    return res.json();
  }

  async getToolsByCategory(categoryId) {
    const res = await fetch(`${this.baseURL}/api/tools/category/${categoryId}`);
    return res.json();
  }

  // ─── Self-host Info ──────────────────────────────────────────────────────

  async getSelfhostInfo(toolId) {
    const res = await fetch(`${this.baseURL}/api/tools/${toolId}/selfhost`);
    return res.json();
  }

  // ─── Health Check ────────────────────────────────────────────────────────

  async health() {
    const res = await fetch(`${this.baseURL}/api/health`);
    return res.json();
  }

  // ─── History Management ──────────────────────────────────────────────────

  clearHistory() {
    this.history = [];
  }

  getHistory() {
    return [...this.history];
  }
}

// Expose globally for vanilla JS usage
if (typeof window !== "undefined") {
  window.NeoClient = NeoClient;
}

// ES module export
if (typeof module !== "undefined" && module.exports) {
  module.exports = { NeoClient };
}
