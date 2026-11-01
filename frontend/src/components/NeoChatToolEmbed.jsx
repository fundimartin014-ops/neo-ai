/**
 * NeoChatToolEmbed.jsx
 * ====================
 * Drop-in React component for Neo's web chat UI.
 * Renders NoSignups tool suggestions, quick actions, and iframe embeds.
 * 
 * Props:
 *   - toolData: { has_tool, tools[], iframe_html, response_text } from neo_nosignups.py
 *   - onToolOpen: (tool) => void  — callback when user opens a tool
 *   - theme: "dark" | "light" (default: "dark")
 *   - maxIframeHeight: number (default: 480)
 */

import React, { useState, useEffect, useRef, useCallback } from "react";
import "./NeoChatToolEmbed.css";

// ─── Quick Action Bar (always visible above chat input) ───────────────────

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

export function NeoQuickActions({ onAction, disabled }) {
  return (
    <div className="neo-quick-actions">
      {QUICK_ACTIONS.map((action) => (
        <button
          key={action.id}
          className="neo-quick-btn"
          onClick={() => onAction(action)}
          disabled={disabled}
          title={`Open ${action.label}`}
        >
          <span className="neo-quick-icon">{action.icon}</span>
          <span className="neo-quick-label">{action.label}</span>
        </button>
      ))}
    </div>
  );
}

// ─── Tool Suggestion Card (rendered inside chat bubble) ───────────────────

export function NeoToolSuggestion({ toolData, onToolOpen, theme = "dark" }) {
  const [expandedTool, setExpandedTool] = useState(null);
  const [iframeError, setIframeError] = useState(false);
  const iframeRef = useRef(null);

  if (!toolData?.has_tool) return null;

  const { tools, iframe_html, response_text } = toolData;
  const topTool = tools[0];

  const handleOpenTool = useCallback(
    (tool) => {
      setIframeError(false);
      setExpandedTool(tool.id === expandedTool ? null : tool.id);
      if (onToolOpen) onToolOpen(tool);
    },
    [expandedTool, onToolOpen]
  );

  const handleIframeError = () => {
    setIframeError(true);
  };

  return (
    <div className={`neo-tool-suggestion neo-theme-${theme}`}>
      {/* AI response text */}
      {response_text && (
        <div className="neo-tool-text">
          <span className="neo-tool-badge">🛠️ Tool</span>
          <p dangerouslySetInnerHTML={{ __html: markdownLite(response_text) }} />
        </div>
      )}

      {/* Tool action buttons */}
      <div className="neo-tool-actions">
        {tools.slice(0, 3).map((tool) => (
          <button
            key={tool.id}
            className={`neo-tool-action-btn ${tool.id === expandedTool ? "active" : ""}`}
            onClick={() => handleOpenTool(tool)}
          >
            <span className="neo-tool-action-name">{tool.name}</span>
            <span className="neo-tool-action-meta">
              {tool.stars ? `⭐ ${formatStars(tool.stars)}` : ""}
              {tool.integration_type === "selfhost" ? " · Self-host" : " · Browser"}
            </span>
          </button>
        ))}
      </div>

      {/* Iframe embed area */}
      {expandedTool && !iframeError && (
        <div className="neo-iframe-wrapper">
          <div className="neo-iframe-header">
            <span className="neo-iframe-title">
              {tools.find((t) => t.id === expandedTool)?.name}
            </span>
            <div className="neo-iframe-controls">
              <button
                className="neo-iframe-btn"
                onClick={() =>
                  window.open(
                    tools.find((t) => t.id === expandedTool)?.url,
                    "_blank",
                    "noopener,noreferrer"
                  )
                }
                title="Open in new tab"
              >
                ↗
              </button>
              <button
                className="neo-iframe-btn neo-iframe-close"
                onClick={() => setExpandedTool(null)}
                title="Close"
              >
                ✕
              </button>
            </div>
          </div>
          <div className="neo-iframe-container">
            <iframe
              ref={iframeRef}
              src={tools.find((t) => t.id === expandedTool)?.url}
              title={tools.find((t) => t.id === expandedTool)?.name}
              sandbox="allow-scripts allow-same-origin allow-forms allow-downloads allow-popups"
              loading="lazy"
              onError={handleIframeError}
              allow="clipboard-write; clipboard-read"
            />
            <div className="neo-iframe-loading">
              <span className="neo-spinner"></span>
              <span>Loading tool…</span>
            </div>
          </div>
        </div>
      )}

      {/* Fallback if iframe fails (X-Frame-Options blocked) */}
      {iframeError && expandedTool && (
        <div className="neo-iframe-fallback">
          <p>⚠️ This tool blocks embedding.</p>
          <a
            href={tools.find((t) => t.id === expandedTool)?.url}
            target="_blank"
            rel="noopener noreferrer"
            className="neo-fallback-link"
          >
            Open {tools.find((t) => t.id === expandedTool)?.name} in new tab →
          </a>
        </div>
      )}

      {/* Self-host hint */}
      {topTool?.integration_type === "selfhost" && topTool?.github && (
        <div className="neo-selfhost-hint">
          <span>💡</span>
          <span>
            Want offline access?{" "}
            <a href={topTool.github} target="_blank" rel="noopener noreferrer">
              Self-host {topTool.name}
            </a>
          </span>
        </div>
      )}
    </div>
  );
}

// ─── Full Chat Message Component (wraps text + tools) ─────────────────────

export function NeoChatMessage({ message, onToolOpen, theme = "dark" }) {
  const isUser = message.role === "user";
  const hasTool = message.tool_data?.has_tool;

  return (
    <div className={`neo-message ${isUser ? "neo-user" : "neo-ai"} neo-theme-${theme}`}>
      <div className="neo-message-avatar">{isUser ? "🧑" : "🤖"}</div>
      <div className="neo-message-content">
        {!isUser && hasTool && (
          <NeoToolSuggestion
            toolData={message.tool_data}
            onToolOpen={onToolOpen}
            theme={theme}
          />
        )}
        {message.content && (
          <div className="neo-message-text">
            {message.content}
          </div>
        )}
      </div>
    </div>
  );
}

// ─── Main Chat Container (put this in your App) ───────────────────────────

export function NeoChatContainer({
  messages,
  onSendMessage,
  onToolOpen,
  theme = "dark",
  isLoading = false,
}) {
  const [input, setInput] = useState("");
  const messagesEndRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!input.trim() || isLoading) return;
    onSendMessage(input.trim());
    setInput("");
  };

  const handleQuickAction = (action) => {
    onSendMessage(action.trigger);
  };

  return (
    <div className={`neo-chat-container neo-theme-${theme}`}>
      {/* Messages area */}
      <div className="neo-messages">
        {messages.map((msg, idx) => (
          <NeoChatMessage
            key={idx}
            message={msg}
            onToolOpen={onToolOpen}
            theme={theme}
          />
        ))}
        {isLoading && (
          <div className="neo-message neo-ai">
            <div className="neo-message-avatar">🤖</div>
            <div className="neo-message-content">
              <div className="neo-typing">
                <span></span><span></span><span></span>
              </div>
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Quick actions */}
      <NeoQuickActions onAction={handleQuickAction} disabled={isLoading} />

      {/* Input area */}
      <form className="neo-input-area" onSubmit={handleSubmit}>
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask Neo anything, or type a task like 'draw a diagram'…"
          disabled={isLoading}
          className="neo-input"
        />
        <button
          type="submit"
          disabled={isLoading || !input.trim()}
          className="neo-send-btn"
        >
          {isLoading ? "⏳" : "➤"}
        </button>
      </form>
    </div>
  );
}

// ─── Helpers ──────────────────────────────────────────────────────────────

function formatStars(n) {
  if (n >= 1000) return (n / 1000).toFixed(1) + "k";
  return n.toString();
}

function markdownLite(text) {
  // Ultra-light markdown: **bold** and [link](url)
  return text
    .replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>")
    .replace(/\[(.*?)\]\((.*?)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>');
}

// ─── Default export ───────────────────────────────────────────────────────

export default NeoChatContainer;
