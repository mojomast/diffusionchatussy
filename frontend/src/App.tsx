import { useState, useCallback, useEffect, useRef } from "react";
import { Chat } from "./components/Chat";
import { AdminPanel } from "./components/AdminPanel";
import { useWebSocket } from "./hooks/useWebSocket";
import { getStatus, getMessages } from "./api";
import type {
  ChatMessage,
  ToneConfig,
  ModelConfig,
  WSMessage,
  DiffusingMessage,
} from "./types";

function App() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [tone, setTone] = useState<ToneConfig | null>(null);
  const [model, setModel] = useState<ModelConfig | null>(null);
  const [username, setUsername] = useState("");
  const [enteredChat, setEnteredChat] = useState(false);
  const [showOriginals, setShowOriginals] = useState(false);
  const [showAdmin, setShowAdmin] = useState(false);
  const [adminAuthed, setAdminAuthed] = useState(false);
  const [adminPassInput, setAdminPassInput] = useState("");
  const [adminPassError, setAdminPassError] = useState(false);
  const [showSettings, setShowSettings] = useState(false);

  // Track messages currently being diffused (real denoising in progress)
  const [diffusing, setDiffusing] = useState<Map<string, DiffusingMessage>>(
    new Map()
  );

  // Pipeline state for the local user's last sent message
  const [pipeline, setPipeline] = useState<string | null>(null);

  // Ref to avoid stale closures
  const diffusingRef = useRef(diffusing);
  diffusingRef.current = diffusing;

  // Handle incoming WebSocket messages
  const handleWS = useCallback(
    (msg: WSMessage) => {
      switch (msg.type) {
        case "diffusion_start": {
          // A new message is being diffused — show it in the chat area
          const dm: DiffusingMessage = {
            msg_id: msg.msg_id,
            user: msg.user,
            original: msg.original,
            currentContent: msg.original, // Start showing original
            step: 0,
            timestamp: msg.timestamp,
            tone_name: msg.tone_name ?? "",
          };
          setDiffusing((prev) => {
            const next = new Map(prev);
            next.set(msg.msg_id, dm);
            return next;
          });
          setPipeline("diffusing");
          break;
        }

        case "diffusion_step": {
          // Update the in-flight message with the latest denoised state
          setDiffusing((prev) => {
            const existing = prev.get(msg.msg_id);
            if (!existing) return prev;
            const next = new Map(prev);
            next.set(msg.msg_id, {
              ...existing,
              currentContent: msg.content,
              step: msg.step,
            });
            return next;
          });
          break;
        }

        case "chat": {
          // Final resolved message — add to permanent list, remove from diffusing
          const chatMsg: ChatMessage = {
            user: msg.user,
            message: msg.message,
            original: msg.original,
            timestamp: msg.timestamp,
            tone_name: msg.tone_name ?? "",
            msg_id: msg.msg_id,
            diffused: msg.diffused,
            rewrite_status: msg.rewrite_status,
          };
          setMessages((prev) => [...prev, chatMsg]);

          // Remove from in-flight diffusion if it was being tracked
          if (msg.msg_id) {
            setDiffusing((prev) => {
              if (!prev.has(msg.msg_id!)) return prev;
              const next = new Map(prev);
              next.delete(msg.msg_id!);
              return next;
            });
          }
          setPipeline(null);
          break;
        }

        case "tone_change": {
          setTone({
            tone_name: msg.tone_name ?? "",
            description: msg.description ?? "",
            strength: msg.strength ?? 100,
          });
          break;
        }

        case "pong":
          break;
      }
    },
    []
  );

  const { connected } = useWebSocket(handleWS);

  // Load initial state
  useEffect(() => {
    getStatus()
      .then((s) => {
        setTone(s.tone);
        setModel(s.model);
      })
      .catch(console.error);

    getMessages()
      .then((msgs) => {
        setMessages(
          msgs.map((m) => ({
            user: m.user,
            message: m.rewritten,
            original: m.original,
            timestamp: m.timestamp,
            tone_name: m.tone_name,
          }))
        );
      })
      .catch(console.error);
  }, []);

  // Username entry screen
  if (!enteredChat) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="w-full max-w-sm px-6">
          <h1 className="text-3xl font-bold text-white mb-2 text-center">
            ToneChat
          </h1>
          <p className="text-sm text-gray-500 mb-8 text-center">
            Every message reshaped by the room's vibe
          </p>

          <div className="space-y-4">
            <input
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && username.trim()) {
                  setEnteredChat(true);
                }
              }}
              placeholder="Enter your name"
              autoFocus
              className="w-full bg-gray-800 text-white rounded-lg px-4 py-3 text-sm 
                         placeholder-gray-500 border border-gray-700 
                         focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500"
            />
            <button
              onClick={() => {
                if (username.trim()) setEnteredChat(true);
              }}
              disabled={!username.trim()}
              className="w-full px-4 py-3 bg-indigo-600 text-white text-sm font-medium rounded-lg
                         hover:bg-indigo-500 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
            >
              Join Chat
            </button>
          </div>

          <div className="mt-6 flex items-center justify-center gap-2 text-xs text-gray-600">
            <span
              className={`w-2 h-2 rounded-full ${connected ? "bg-green-500" : "bg-red-500"}`}
            />
            {connected ? "Connected" : "Connecting..."}
          </div>
        </div>
      </div>
    );
  }

  const handleAdminLogin = () => {
    if (adminPassInput === "h4x0r") {
      setAdminAuthed(true);
      setShowAdmin(true);
      setAdminPassError(false);
      setAdminPassInput("");
    } else {
      setAdminPassError(true);
    }
  };

  const toggleAdmin = () => {
    if (adminAuthed) {
      setShowAdmin(!showAdmin);
    } else {
      setShowAdmin(!showAdmin); // Show the password prompt
    }
  };

  // Main chat layout
  return (
    <div className="h-screen flex flex-col">
      {/* Top bar */}
      <header className="flex items-center justify-between px-4 py-2 border-b border-gray-800 bg-gray-900">
        <div className="flex items-center gap-3">
          <h1 className="text-sm font-bold text-white">ToneChat</h1>
          <span
            className={`w-2 h-2 rounded-full ${connected ? "bg-green-500" : "bg-red-500"}`}
          />
        </div>
        <div className="flex items-center gap-2">
          <span className="text-xs text-gray-500">{username}</span>
          <button
            onClick={() => setShowSettings(!showSettings)}
            className={`px-3 py-1 text-xs rounded-md border transition-colors ${
              showSettings && !showAdmin
                ? "bg-gray-700/50 border-gray-600 text-gray-300"
                : "bg-gray-800 border-gray-700 text-gray-400 hover:border-gray-600"
            }`}
          >
            Settings
          </button>
          <button
            onClick={toggleAdmin}
            className={`px-3 py-1 text-xs rounded-md border transition-colors ${
              showAdmin && adminAuthed
                ? "bg-indigo-600/20 border-indigo-500 text-indigo-300"
                : "bg-gray-800 border-gray-700 text-gray-400 hover:border-gray-600"
            }`}
          >
            Admin
          </button>
        </div>
      </header>

      {/* Body */}
      <div className="flex-1 flex overflow-hidden">
        {/* Chat panel */}
        <div
          className={`flex-1 flex flex-col ${(showAdmin || showSettings) ? "border-r border-gray-800" : ""}`}
        >
          <Chat
            messages={messages}
            diffusing={diffusing}
            tone={tone}
            username={username}
            showOriginals={showOriginals}
            pipeline={pipeline}
            onPipelineChange={setPipeline}
          />
        </div>

        {/* Admin sidebar — password gated */}
        {showAdmin && !adminAuthed && (
          <div className="w-80 flex-shrink-0 bg-gray-900/30 flex items-center justify-center">
            <div className="px-6 w-full">
              <h3 className="text-sm font-semibold text-gray-300 mb-4 text-center uppercase tracking-wide">
                Admin Access
              </h3>
              <input
                type="password"
                value={adminPassInput}
                onChange={(e) => {
                  setAdminPassInput(e.target.value);
                  setAdminPassError(false);
                }}
                onKeyDown={(e) => {
                  if (e.key === "Enter") handleAdminLogin();
                }}
                placeholder="Password"
                autoFocus
                className={`w-full bg-gray-800 text-white text-sm rounded-md px-3 py-2 border 
                  ${adminPassError ? "border-red-500" : "border-gray-700"} 
                  focus:outline-none focus:border-indigo-500 transition-colors`}
              />
              {adminPassError && (
                <p className="text-xs text-red-400 mt-1">Wrong password</p>
              )}
              <button
                onClick={handleAdminLogin}
                className="w-full mt-3 px-4 py-2 bg-indigo-600 text-white text-sm font-medium rounded-lg hover:bg-indigo-500 transition-colors"
              >
                Unlock
              </button>
              <button
                onClick={() => setShowAdmin(false)}
                className="w-full mt-2 px-4 py-2 text-gray-500 text-xs hover:text-gray-300 transition-colors"
              >
                Cancel
              </button>
            </div>
          </div>
        )}

        {/* Admin sidebar — authenticated */}
        {showAdmin && adminAuthed && (
          <div className="w-80 flex-shrink-0 bg-gray-900/30">
            <AdminPanel
              tone={tone}
              model={model}
              onToneUpdate={setTone}
              onModelUpdate={setModel}
              showOriginals={showOriginals}
              onToggleOriginals={() => setShowOriginals(!showOriginals)}
            />
          </div>
        )}

        {/* User settings sidebar — always available, no password */}
        {showSettings && !showAdmin && (
          <div className="w-72 flex-shrink-0 bg-gray-900/30">
            <div className="px-4 py-3 border-b border-gray-800 bg-gray-900/50">
              <h2 className="text-lg font-semibold text-white">Settings</h2>
            </div>
            <div className="px-4 py-4 space-y-4">
              <section>
                <h3 className="text-sm font-semibold text-gray-300 mb-3 uppercase tracking-wide">
                  Display
                </h3>
                <div className="space-y-2">
                  <label className="flex items-center gap-2 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={showOriginals}
                      onChange={() => setShowOriginals(!showOriginals)}
                      className="accent-indigo-500"
                    />
                    <span className="text-sm text-gray-400">
                      Show original messages
                    </span>
                  </label>
                </div>
              </section>

              {tone && (
                <section>
                  <h3 className="text-sm font-semibold text-gray-300 mb-2 uppercase tracking-wide">
                    Room Info
                  </h3>
                  <div className="text-xs text-gray-500 space-y-1">
                    <div>
                      Tone: <span className="text-indigo-400">{tone.tone_name}</span> at {tone.strength}%
                    </div>
                    <div className="text-gray-600">{tone.description}</div>
                  </div>
                </section>
              )}

              {model && (
                <section>
                  <div className="text-xs text-gray-600 space-y-1">
                    <div>Model: {model.model}</div>
                    <div>Provider: {model.provider}</div>
                    {model.diffusion && model.diffusion_available && (
                      <div className="text-purple-400">Diffusion streaming active</div>
                    )}
                  </div>
                </section>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default App;
