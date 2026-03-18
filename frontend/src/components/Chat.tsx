import { useState, useRef, useEffect } from "react";
import type { ChatMessage, ToneConfig, DiffusingMessage, DisplayMessage } from "../types";
import { sendMessage } from "../api";
import { DiffusionText } from "./DiffusionText";

interface ChatProps {
  messages: ChatMessage[];
  displayMessages: DisplayMessage[];
  diffusing: Map<string, DiffusingMessage>;
  tone: ToneConfig | null;
  username: string;
  showOriginals: boolean;
  pipeline: string | null;
  onPipelineChange: (p: string | null) => void;
  liveStats: {
    total_messages: number;
    total_tokens: number;
    active_users: number;
  };
}

export function Chat({
  messages,
  displayMessages,
  diffusing,
  tone,
  username,
  showOriginals,
  pipeline,
  onPipelineChange,
  liveStats,
}: ChatProps) {
  const [input, setInput] = useState("");
  const bottomRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  // Auto-scroll
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [displayMessages, diffusing]);

  // Auto-focus the chat input on mount (after joining)
  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  // Restore focus when pipeline clears (message sent and processed)
  useEffect(() => {
    if (!pipeline) {
      inputRef.current?.focus();
    }
  }, [pipeline]);

  const handleSend = async () => {
    const text = input.trim();
    if (!text || pipeline === "sending" || pipeline === "rewriting") return;

    onPipelineChange("rewriting");
    setInput("");
    try {
      await sendMessage(username, text);
      // Pipeline will be updated by WS events (diffusion_start -> diffusing, or chat -> null)
    } catch (err) {
      console.error("Send failed:", err);
      onPipelineChange(null);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const formatTime = (ts: number) => {
    const d = new Date(ts * 1000);
    return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  };

  const isBusy = pipeline === "rewriting" || pipeline === "diffusing";

  // In-flight diffusing messages for display
  const diffusingArray = Array.from(diffusing.values());

  return (
    <div className="flex flex-col h-full">
      {/* Header bar */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-gray-800 bg-gray-900/50">
        <div className="flex items-center gap-3">
          <h2 className="text-lg font-semibold text-white">Tchaikovskussy Chat</h2>
          {tone && (
            <span className="px-2 py-0.5 text-xs rounded-full bg-indigo-600/20 text-indigo-200 border border-indigo-500/20">
              communication layer active
            </span>
          )}
        </div>
        <span className="text-xs text-gray-500">
          {messages.length} message{messages.length !== 1 ? "s" : ""}
        </span>
      </div>

      {/* Stats bar */}
      <div className="flex items-center justify-between px-4 py-1.5 border-b border-gray-800/50 bg-gray-900/30">
        <div className="flex items-center gap-3 text-xs text-gray-500">
          <span>
            <span className="font-mono text-gray-400">{liveStats.total_messages}</span> messages
          </span>
          <span className="text-gray-700">|</span>
          <span>
            ~<span className="font-mono text-gray-400">{liveStats.total_tokens.toLocaleString()}</span> tokens
          </span>
          <span className="text-gray-700">|</span>
          <span>
            <span className="font-mono text-gray-400">{liveStats.active_users}</span> user{liveStats.active_users !== 1 ? "s" : ""} online
          </span>
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-4 py-3 space-y-3">
        {displayMessages.length === 0 && diffusingArray.length === 0 && (
          <div className="flex items-center justify-center h-full text-gray-600 text-sm">
            No messages yet. Say something — BabelFish will bridge the room.
          </div>
        )}

        {/* Display messages (chat + system) */}
        {displayMessages.map((item, i) => {
          if (item.kind === "system") {
            // System message (join, leave, reset)
            return (
              <div
                key={`sys-${item.timestamp}-${i}`}
                className="flex justify-center"
              >
                <span className="px-3 py-1 text-xs text-gray-500 bg-gray-800/40 rounded-full">
                  {item.text}
                </span>
              </div>
            );
          }

          // Regular chat message
          const msg = item;
          const isMe = msg.user === username;
          return (
            <div
              key={`${msg.msg_id ?? msg.timestamp}-${i}`}
              className={`flex flex-col ${isMe ? "items-end" : "items-start"}`}
            >
              <div className="flex items-center gap-2 mb-1">
                <span className="text-xs font-medium text-gray-400">
                  {msg.user}
                </span>
                <span className="text-xs text-gray-600">
                  {formatTime(msg.timestamp)}
                </span>
                {msg.token_estimate != null && (
                  <span className="text-[10px] text-gray-600 font-mono">
                    ~{msg.token_estimate} tok
                  </span>
                )}
                {msg.tone_name && (
                  <span className="text-xs text-gray-700">
                    [{msg.tone_name}]
                  </span>
                )}
                {msg.translation_language && (
                  <span className="text-xs text-emerald-400">
                    [heard as {msg.translation_language}]
                  </span>
                )}
                {msg.source_language && msg.translation_language && msg.source_language !== msg.translation_language && (
                  <span className="text-xs text-cyan-400">
                    [spoken in {msg.source_language}]
                  </span>
                )}
                {msg.tone_applied === false && (
                  <span className="text-xs text-amber-400">
                    [tone off]
                  </span>
                )}
                {msg.diffused && (
                  <span className="text-xs text-purple-600">
                    [diffused]
                  </span>
                )}
                {msg.rewrite_status === "no_key" && (
                  <span className="text-xs text-amber-500">
                    [no api key]
                  </span>
                )}
                {msg.rewrite_status === "error" && (
                  <span className="text-xs text-red-500">
                    [rewrite failed]
                  </span>
                )}
              </div>

              <div
                className={`max-w-[75%] rounded-xl px-4 py-2 text-sm leading-relaxed ${
                  isMe
                    ? "bg-indigo-600 text-white rounded-br-sm"
                    : "bg-gray-800 text-gray-200 rounded-bl-sm"
                }`}
              >
                {msg.message}
              </div>

              {showOriginals &&
                msg.original &&
                msg.original !== msg.message && (
                  <div className="mt-1 max-w-[75%] px-3 py-1 rounded-lg bg-gray-900/50 border border-gray-800 text-xs text-gray-500 italic">
                    Original{msg.source_language ? ` (${msg.source_language})` : ""}: {msg.original}
                  </div>
                )}
            </div>
          );
        })}

        {/* In-flight diffusing messages — showing real denoising steps */}
        {diffusingArray.map((dm) => {
          const isMe = dm.user === username;
          return (
            <div
              key={dm.msg_id}
              className={`flex flex-col ${isMe ? "items-end" : "items-start"}`}
            >
              <div className="flex items-center gap-2 mb-1">
                <span className="text-xs font-medium text-gray-400">
                  {dm.user}
                </span>
                <span className="text-xs text-gray-600">
                  {formatTime(dm.timestamp)}
                </span>
                <span className="text-xs text-purple-400 animate-pulse">
                  denoising step {dm.step}
                </span>
              </div>

              <div
                className={`max-w-[75%] rounded-xl px-4 py-2 text-sm leading-relaxed border ${
                  isMe
                    ? "bg-indigo-600/80 text-white rounded-br-sm border-purple-500/30"
                    : "bg-gray-800/80 text-gray-200 rounded-bl-sm border-purple-500/30"
                }`}
              >
                <DiffusionText
                  content={dm.currentContent}
                  active={true}
                />
              </div>

              {showOriginals && (
                <div className="mt-1 max-w-[75%] px-3 py-1 rounded-lg bg-gray-900/50 border border-gray-800 text-xs text-gray-500 italic">
                  Original: {dm.original}
                </div>
              )}
            </div>
          );
        })}

        <div ref={bottomRef} />
      </div>

      {/* Pipeline status indicator */}
      {pipeline && (
        <div className="px-4 py-1.5 border-t border-gray-800/50">
          <div className="flex items-center gap-2">
            <div className="flex gap-1">
              {(["rewriting", "diffusing"] as const).map((stage) => (
                <div
                  key={stage}
                  className={`h-1 rounded-full transition-all duration-300 ${
                    stage === pipeline
                      ? "w-8 bg-purple-500 animate-pulse"
                      : stage === "rewriting" && pipeline === "diffusing"
                        ? "w-6 bg-purple-500/40"
                        : "w-6 bg-gray-800"
                  }`}
                />
              ))}
            </div>
            <span className="text-xs text-gray-500">
              {pipeline === "rewriting"
                ? "bridging languages..."
                : pipeline === "diffusing"
                  ? "processing message stream"
                  : ""}
            </span>
          </div>
        </div>
      )}

      {/* Input */}
      <div className="border-t border-gray-800 bg-gray-900/50 px-4 py-3">
        <div className="flex gap-2">
          <input
            ref={inputRef}
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
              placeholder={
                isBusy
                  ? "Passing through BabelFish..."
                  : "Type in your language..."
              }
            disabled={isBusy}
            className="flex-1 bg-gray-800 text-white rounded-lg px-4 py-2.5 text-sm 
                       placeholder-gray-500 border border-gray-700 
                       focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500
                       disabled:opacity-50 transition-colors"
          />
          <button
            onClick={handleSend}
            disabled={isBusy || !input.trim()}
            className="px-5 py-2.5 bg-indigo-600 text-white text-sm font-medium rounded-lg
                       hover:bg-indigo-500 disabled:opacity-40 disabled:cursor-not-allowed
                       transition-colors"
          >
            {isBusy ? "..." : "Send"}
          </button>
        </div>
      </div>
    </div>
  );
}
