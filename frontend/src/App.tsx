import { useState, useCallback, useEffect, useRef } from "react";
import { Chat } from "./components/Chat";
import { AdminPanel } from "./components/AdminPanel";
import { useWebSocket } from "./hooks/useWebSocket";
import { getStatus, getMessages, joinChat, adminLogin, getMyStats } from "./api";
import type {
  ChatMessage,
  ToneConfig,
  ModelConfig,
  WSMessage,
  DiffusingMessage,
  UserSession,
  DisplayMessage,
  MyStatsResponse,
} from "./types";

function App() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [displayMessages, setDisplayMessages] = useState<DisplayMessage[]>([]);
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
  const [joinError, setJoinError] = useState("");

  // Session from backend auth
  const [session, setSession] = useState<UserSession | null>(null);
  const [myStats, setMyStats] = useState<MyStatsResponse | null>(null);

  // Live stats from WS stats_update events
  const [liveStats, setLiveStats] = useState<{
    total_messages: number;
    total_tokens: number;
    active_users: number;
  }>({ total_messages: 0, total_tokens: 0, active_users: 0 });

  // Track messages currently being diffused (real denoising in progress)
  const [diffusing, setDiffusing] = useState<Map<string, DiffusingMessage>>(
    new Map()
  );

  // Pipeline state for the local user's last sent message
  const [pipeline, setPipeline] = useState<string | null>(null);

  // Ref to avoid stale closures
  const diffusingRef = useRef(diffusing);
  diffusingRef.current = diffusing;

  // Helper: add a system message to the display
  const addSystemMessage = useCallback((text: string) => {
    const sysMsg: DisplayMessage = {
      kind: "system",
      type: "system",
      text,
      timestamp: Date.now() / 1000,
    };
    setDisplayMessages((prev) => [...prev, sysMsg]);
  }, []);

  // Handle incoming WebSocket messages
  const handleWS = useCallback(
    (msg: WSMessage) => {
      switch (msg.type) {
        case "diffusion_start": {
          const dm: DiffusingMessage = {
            msg_id: msg.msg_id,
            user: msg.user,
            original: msg.original,
            currentContent: msg.original,
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
          const chatMsg: ChatMessage = {
            user: msg.user,
            message: msg.message,
            original: msg.original,
            timestamp: msg.timestamp,
            tone_name: msg.tone_name ?? "",
            msg_id: msg.msg_id,
            diffused: msg.diffused,
            rewrite_status: msg.rewrite_status,
            token_estimate: msg.token_estimate,
          };
          setMessages((prev) => [...prev, chatMsg]);

          // Also add to display messages
          const displayMsg: DisplayMessage = { ...chatMsg, kind: "chat" };
          setDisplayMessages((prev) => [...prev, displayMsg]);

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

        case "context_reset": {
          // Admin cleared all chat history
          setMessages([]);
          setDisplayMessages([]);
          addSystemMessage("Chat history cleared by admin");
          break;
        }

        case "user_joined": {
          addSystemMessage(`${msg.username} joined the chat`);
          setLiveStats((prev) => ({ ...prev, active_users: msg.user_count }));
          break;
        }

        case "user_left": {
          addSystemMessage(`${msg.username} left the chat`);
          setLiveStats((prev) => ({ ...prev, active_users: msg.user_count }));
          break;
        }

        case "stats_update": {
          setLiveStats({
            total_messages: msg.total_messages,
            total_tokens: msg.total_tokens,
            active_users: msg.active_users,
          });
          break;
        }

        case "pong":
          break;
      }
    },
    [addSystemMessage]
  );

  const { connected } = useWebSocket(handleWS);

  // Load initial state
  useEffect(() => {
    getStatus()
      .then((s) => {
        setTone(s.tone);
        setModel(s.model);
        setLiveStats((prev) => ({
          ...prev,
          total_messages: s.message_count,
          active_users: s.connected_clients,
        }));
      })
      .catch(console.error);

    getMessages()
      .then((msgs) => {
        const chatMsgs: ChatMessage[] = msgs.map((m) => ({
          user: m.user,
          message: m.rewritten,
          original: m.original,
          timestamp: m.timestamp,
          tone_name: m.tone_name,
          token_estimate: m.token_estimate,
        }));
        setMessages(chatMsgs);
        setDisplayMessages(
          chatMsgs.map((cm) => ({ ...cm, kind: "chat" as const }))
        );
      })
      .catch(console.error);
  }, []);

  // Periodically refresh personal stats when in chat
  useEffect(() => {
    if (!enteredChat) return;
    const fetchStats = () => {
      getMyStats().then(setMyStats).catch(() => { /* ignore if endpoint not available */ });
    };
    fetchStats();
    const interval = setInterval(fetchStats, 15000);
    return () => clearInterval(interval);
  }, [enteredChat]);

  // Handle join — calls backend auth
  const handleJoin = async () => {
    const trimmed = username.trim();
    if (!trimmed) return;
    setJoinError("");
    try {
      const userSession = await joinChat(trimmed);
      setSession(userSession);
      setAdminAuthed(userSession.role === "admin");
      setEnteredChat(true);
    } catch (err) {
      // Fallback: if auth endpoint doesn't exist yet, join client-side only
      if (err instanceof Error && err.message.includes("404")) {
        setEnteredChat(true);
      } else {
        setJoinError(err instanceof Error ? err.message : "Failed to join");
      }
    }
  };

  // Username entry screen
  if (!enteredChat) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="w-full max-w-sm px-6">
          <h1 className="text-3xl font-bold text-white mb-2 text-center">
            ToneChat
          </h1>
          <p className="text-sm text-gray-500 mb-8 text-center">
            Every message reshaped by the room&apos;s vibe
          </p>

          <div className="space-y-4">
            <input
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && username.trim()) {
                  handleJoin();
                }
              }}
              placeholder="Enter your name"
              autoFocus
              className="w-full bg-gray-800 text-white rounded-lg px-4 py-3 text-sm 
                         placeholder-gray-500 border border-gray-700 
                         focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500"
            />
            <button
              onClick={handleJoin}
              disabled={!username.trim()}
              className="w-full px-4 py-3 bg-indigo-600 text-white text-sm font-medium rounded-lg
                         hover:bg-indigo-500 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
            >
              Join Chat
            </button>
            {joinError && (
              <p className="text-xs text-red-400 text-center">{joinError}</p>
            )}
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

  const handleAdminLogin = async () => {
    setAdminPassError(false);
    try {
      const updatedSession = await adminLogin(adminPassInput);
      setSession(updatedSession);
      setAdminAuthed(true);
      setShowAdmin(true);
      setAdminPassInput("");
    } catch (err) {
      // Fallback: if auth endpoint doesn't exist, try client-side check
      if (err instanceof Error && err.message.includes("404")) {
        if (adminPassInput === "h4x0r") {
          setAdminAuthed(true);
          setShowAdmin(true);
          setAdminPassInput("");
        } else {
          setAdminPassError(true);
        }
      } else {
        setAdminPassError(true);
      }
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
          {/* Live stats bar */}
          <div className="hidden sm:flex items-center gap-2 text-xs text-gray-500">
            <span className="font-mono">{liveStats.total_messages}</span>
            <span className="text-gray-700">msgs</span>
            <span className="text-gray-700">·</span>
            <span className="font-mono">{liveStats.total_tokens.toLocaleString()}</span>
            <span className="text-gray-700">tokens</span>
            <span className="text-gray-700">·</span>
            <span className="font-mono">{liveStats.active_users}</span>
            <span className="text-gray-700">online</span>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {/* User info with role badge */}
          <div className="flex items-center gap-1.5">
            <span className="text-xs text-gray-500">{username}</span>
            {session?.role === "admin" && (
              <span className="px-1.5 py-0.5 text-[10px] rounded bg-purple-600/30 text-purple-300 border border-purple-500/30">
                admin
              </span>
            )}
            {myStats && (
              <span className="text-[10px] text-gray-600 font-mono">
                ({myStats.total_messages} msgs / {myStats.total_tokens_used.toLocaleString()} tok)
              </span>
            )}
          </div>
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
            displayMessages={displayMessages}
            diffusing={diffusing}
            tone={tone}
            username={username}
            showOriginals={showOriginals}
            pipeline={pipeline}
            onPipelineChange={setPipeline}
            liveStats={liveStats}
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

              {/* Personal stats */}
              {myStats && (
                <section>
                  <h3 className="text-sm font-semibold text-gray-300 mb-2 uppercase tracking-wide">
                    Your Stats
                  </h3>
                  <div className="text-xs text-gray-500 space-y-1">
                    <div>
                      Messages: <span className="font-mono text-gray-400">{myStats.total_messages}</span>
                    </div>
                    <div>
                      Tokens used: <span className="font-mono text-gray-400">{myStats.total_tokens_used.toLocaleString()}</span>
                    </div>
                    <div>
                      Role: <span className={myStats.role === "admin" ? "text-purple-400" : "text-gray-400"}>{myStats.role}</span>
                    </div>
                  </div>
                </section>
              )}

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
