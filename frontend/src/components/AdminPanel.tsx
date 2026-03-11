import { useState, useEffect, useRef, useCallback } from "react";
import type { ToneConfig, ModelConfig, UserSession, ContextStats } from "../types";
import {
  setTone,
  setModel,
  getTonePresets,
  getProviderPresets,
  searchOpenRouterModels,
  getOpenRouterFavorites,
  getContextStats,
  resetContext,
  setContextSettings,
  getUsers,
  setUserRole,
  kickUser,
} from "../api";
import type { OpenRouterModel, OpenRouterFavorite } from "../api";

interface AdminPanelProps {
  tone: ToneConfig | null;
  model: ModelConfig | null;
  onToneUpdate: (t: ToneConfig) => void;
  onModelUpdate: (m: ModelConfig) => void;
  showOriginals: boolean;
  onToggleOriginals: () => void;
}

export function AdminPanel({
  tone,
  model,
  onToneUpdate,
  onModelUpdate,
  showOriginals,
  onToggleOriginals,
}: AdminPanelProps) {
  const [tonePresets, setTonePresets] = useState<Record<string, string>>({});
  const [providerPresets, setProviderPresets] = useState<
    Record<string, { base_url: string; default_model: string }>
  >({});

  // Local form state for tone
  const [toneName, setToneName] = useState("");
  const [toneDesc, setToneDesc] = useState("");
  const [toneStrength, setToneStrength] = useState(100);

  // Local form state for model
  const [provider, setProvider] = useState("");
  const [modelName, setModelName] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [baseUrl, setBaseUrl] = useState("");
  const [diffusion, setDiffusion] = useState(false);
  const [maxTokens, setMaxTokens] = useState(256);
  const [temperature, setTemperature] = useState(0.7);
  const [topP, setTopP] = useState(1.0);
  const [freqPenalty, setFreqPenalty] = useState(0.0);
  const [presPenalty, setPresPenalty] = useState(0.0);
  const [timeout, setTimeout_] = useState(30);

  const [saving, setSaving] = useState(false);
  const [expanded, setExpanded] = useState(false);

  // --- Context management state ---
  const [contextStats, setContextStats] = useState<ContextStats | null>(null);
  const [ctxMaxMessages, setCtxMaxMessages] = useState(500);
  const [ctxMaxTokens, setCtxMaxTokens] = useState(100000);
  const [confirmReset, setConfirmReset] = useState(false);
  const [ctxSaving, setCtxSaving] = useState(false);

  // --- User management state ---
  const [users, setUsers] = useState<UserSession[]>([]);
  const [usersLoading, setUsersLoading] = useState(false);

  // OpenRouter model search state
  const [modelSearchQuery, setModelSearchQuery] = useState("");
  const [modelSearchResults, setModelSearchResults] = useState<OpenRouterModel[]>([]);
  const [modelSearchTotal, setModelSearchTotal] = useState(0);
  const [modelSearching, setModelSearching] = useState(false);
  const [showModelSearch, setShowModelSearch] = useState(false);
  const [favorites, setFavorites] = useState<OpenRouterFavorite[]>([]);
  const searchTimeoutRef = useRef<ReturnType<typeof window.setTimeout> | null>(null);

  // Debounced search for OpenRouter models
  const doModelSearch = useCallback(async (query: string) => {
    setModelSearching(true);
    try {
      const res = await searchOpenRouterModels(query, 30);
      setModelSearchResults(res.models);
      setModelSearchTotal(res.total);
    } catch (err) {
      console.error("Model search failed:", err);
    } finally {
      setModelSearching(false);
    }
  }, []);

  useEffect(() => {
    if (!showModelSearch) return;
    if (searchTimeoutRef.current) clearTimeout(searchTimeoutRef.current);
    searchTimeoutRef.current = window.setTimeout(() => {
      doModelSearch(modelSearchQuery);
    }, 300);
    return () => {
      if (searchTimeoutRef.current) clearTimeout(searchTimeoutRef.current);
    };
  }, [modelSearchQuery, showModelSearch, doModelSearch]);

  // Load presets on mount
  useEffect(() => {
    getTonePresets().then(setTonePresets).catch(console.error);
    getProviderPresets().then(setProviderPresets).catch(console.error);
    getOpenRouterFavorites()
      .then((res) => setFavorites(res.favorites))
      .catch(console.error);
  }, []);

  // Load context stats and users on mount, auto-refresh every 10s
  useEffect(() => {
    const fetchAdmin = () => {
      getContextStats()
        .then((stats) => {
          setContextStats(stats);
          setCtxMaxMessages(stats.max_messages);
          setCtxMaxTokens(stats.max_tokens_per_user);
        })
        .catch(() => { /* endpoint may not exist yet */ });
      setUsersLoading(true);
      getUsers()
        .then((data) => {
          setUsers(data.users ?? []);
        })
        .catch(() => { /* ignore */ })
        .finally(() => setUsersLoading(false));
    };
    fetchAdmin();
    const interval = setInterval(fetchAdmin, 10000);
    return () => clearInterval(interval);
  }, []);

  // Sync from props
  useEffect(() => {
    if (tone) {
      setToneName(tone.tone_name);
      setToneDesc(tone.description);
      setToneStrength(tone.strength);
    }
  }, [tone]);

  useEffect(() => {
    if (model) {
      setProvider(model.provider);
      setModelName(model.model);
      setBaseUrl(model.base_url);
      setDiffusion(model.diffusion);
      setMaxTokens(model.max_tokens);
      setTemperature(model.temperature);
      setTopP(model.top_p);
      setFreqPenalty(model.frequency_penalty);
      setPresPenalty(model.presence_penalty);
      setTimeout_(model.timeout);
    }
  }, [model]);

  const handleTonePreset = (name: string) => {
    setToneName(name);
    const desc = tonePresets[name];
    if (desc) setToneDesc(desc);
  };

  const handleProviderPreset = (name: string) => {
    setProvider(name);
    const preset = providerPresets[name];
    if (preset) {
      setBaseUrl(preset.base_url);
      setModelName(preset.default_model);
    }
  };

  const saveTone = async () => {
    setSaving(true);
    try {
      const updated = await setTone(toneName, toneDesc, toneStrength);
      onToneUpdate(updated);
    } catch (err) {
      console.error("Failed to save tone:", err);
    } finally {
      setSaving(false);
    }
  };

  const saveModel = async () => {
    setSaving(true);
    try {
      const updated = await setModel({
        provider,
        model: modelName,
        api_key: apiKey || undefined,
        base_url: baseUrl || undefined,
        diffusion,
        max_tokens: maxTokens,
        temperature,
        top_p: topP,
        frequency_penalty: freqPenalty,
        presence_penalty: presPenalty,
        timeout,
      });
      onModelUpdate(updated);
      setApiKey("");
    } catch (err) {
      console.error("Failed to save model:", err);
    } finally {
      setSaving(false);
    }
  };

  // --- Context management handlers ---
  const handleResetContext = async () => {
    try {
      await resetContext();
      setConfirmReset(false);
      // Refresh stats
      getContextStats().then(setContextStats).catch(() => {});
    } catch (err) {
      console.error("Failed to reset context:", err);
    }
  };

  const handleSaveContextSettings = async () => {
    setCtxSaving(true);
    try {
      await setContextSettings({
        max_messages: ctxMaxMessages,
        max_tokens_per_user: ctxMaxTokens,
      });
      // Refresh stats
      getContextStats().then(setContextStats).catch(() => { /* ignore */ });
    } catch (err) {
      console.error("Failed to save context settings:", err);
    } finally {
      setCtxSaving(false);
    }
  };

  // --- User management handlers ---
  const handleSetRole = async (userId: string, role: "user" | "admin") => {
    try {
      await setUserRole(userId, role);
      setUsers((prev) =>
        prev.map((u) => (u.user_id === userId ? { ...u, role } : u))
      );
    } catch (err) {
      console.error("Failed to set role:", err);
    }
  };

  const handleKick = async (userId: string) => {
    try {
      await kickUser(userId);
      setUsers((prev) => prev.filter((u) => u.user_id !== userId));
    } catch (err) {
      console.error("Failed to kick user:", err);
    }
  };

  const formatRelativeTime = (ts: number) => {
    const seconds = Math.floor(Date.now() / 1000 - ts);
    if (seconds < 60) return "just now";
    if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
    if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`;
    return `${Math.floor(seconds / 86400)}d ago`;
  };

  const labelClass = "block text-xs font-medium text-gray-400 mb-1";
  const inputClass =
    "w-full bg-gray-800 text-white text-sm rounded-md px-3 py-2 border border-gray-700 focus:outline-none focus:border-indigo-500 transition-colors";
  const selectClass =
    "w-full bg-gray-800 text-white text-sm rounded-md px-3 py-2 border border-gray-700 focus:outline-none focus:border-indigo-500 transition-colors";
  const btnClass =
    "w-full px-4 py-2 text-sm font-medium rounded-lg transition-colors disabled:opacity-40";

  return (
    <div className="flex flex-col h-full overflow-y-auto">
      <div className="px-4 py-3 border-b border-gray-800 bg-gray-900/50">
        <h2 className="text-lg font-semibold text-white">Admin</h2>
      </div>

      <div className="flex-1 px-4 py-4 space-y-6 overflow-y-auto">
        {/* ---- TONE SECTION ---- */}
        <section>
          <h3 className="text-sm font-semibold text-gray-300 mb-3 uppercase tracking-wide">
            Tone Profile
          </h3>

          <div className="flex flex-wrap gap-1.5 mb-3">
            {Object.keys(tonePresets).map((name) => (
              <button
                key={name}
                onClick={() => handleTonePreset(name)}
                className={`px-2.5 py-1 text-xs rounded-md border transition-colors ${
                  toneName === name
                    ? "bg-indigo-600/30 border-indigo-500 text-indigo-300"
                    : "bg-gray-800 border-gray-700 text-gray-400 hover:border-gray-600"
                }`}
              >
                {name}
              </button>
            ))}
          </div>

          <div className="space-y-3">
            <div>
              <label className={labelClass}>Tone Name</label>
              <input
                type="text"
                value={toneName}
                onChange={(e) => setToneName(e.target.value)}
                className={inputClass}
                placeholder="e.g. friendly"
              />
            </div>

            <div>
              <label className={labelClass}>Description</label>
              <textarea
                value={toneDesc}
                onChange={(e) => setToneDesc(e.target.value)}
                rows={2}
                className={`${inputClass} resize-none`}
                placeholder="Describe the tone..."
              />
            </div>

            <div>
              <label className={labelClass}>
                Strength: {toneStrength}%
                <span className="text-gray-600 ml-1">
                  {toneStrength === 0
                    ? "(raw)"
                    : toneStrength < 50
                      ? "(light)"
                      : toneStrength < 100
                        ? "(moderate)"
                        : "(full)"}
                </span>
              </label>
              <input
                type="range"
                min={0}
                max={100}
                value={toneStrength}
                onChange={(e) => setToneStrength(Number(e.target.value))}
                className="w-full accent-indigo-500"
              />
            </div>

            <button
              onClick={saveTone}
              disabled={saving || !toneName}
              className={`${btnClass} bg-indigo-600 text-white hover:bg-indigo-500`}
            >
              {saving ? "Saving..." : "Apply Tone"}
            </button>
          </div>
        </section>

        {/* ---- MODEL SECTION ---- */}
        <section>
          <h3 className="text-sm font-semibold text-gray-300 mb-3 uppercase tracking-wide">
            Model Configuration
          </h3>

          <div className="space-y-3">
            <div>
              <label className={labelClass}>Provider</label>
              <select
                value={provider}
                onChange={(e) => handleProviderPreset(e.target.value)}
                className={selectClass}
              >
                {Object.keys(providerPresets).map((name) => (
                  <option key={name} value={name}>
                    {name}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className={labelClass}>Model</label>
              <input
                type="text"
                value={modelName}
                onChange={(e) => setModelName(e.target.value)}
                className={inputClass}
                placeholder="e.g. mercury-2"
              />
              {provider === "openrouter" && (
                <button
                  onClick={() => {
                    setShowModelSearch(!showModelSearch);
                    if (!showModelSearch && modelSearchResults.length === 0) {
                      doModelSearch("");
                    }
                  }}
                  className="mt-1.5 text-xs text-indigo-400 hover:text-indigo-300 transition-colors"
                >
                  {showModelSearch ? "Close model browser" : "Browse OpenRouter models..."}
                </button>
              )}

              {/* OpenRouter model search dropdown */}
              {showModelSearch && provider === "openrouter" && (
                <div className="mt-2 border border-gray-700 rounded-lg bg-gray-900/80 overflow-hidden">
                  <div className="p-2 border-b border-gray-800">
                    <input
                      type="text"
                      value={modelSearchQuery}
                      onChange={(e) => setModelSearchQuery(e.target.value)}
                      className="w-full bg-gray-800 text-white text-xs rounded px-2.5 py-1.5 border border-gray-700 
                                 focus:outline-none focus:border-indigo-500 transition-colors"
                      placeholder="Search models... (e.g. claude, llama, gpt)"
                      autoFocus
                    />
                  </div>
                  <div className="max-h-72 overflow-y-auto">
                    {/* Favorites section — shown when search is empty */}
                    {!modelSearchQuery && favorites.length > 0 && (
                      <>
                        <div className="px-3 py-1.5 bg-gray-800/50 border-b border-gray-800">
                          <span className="text-xs font-semibold text-amber-400/80 uppercase tracking-wide">
                            Recommended for ToneChat
                          </span>
                        </div>
                        {favorites.map((fav) => {
                          const isSelected = modelName === fav.id;
                          return (
                            <button
                              key={fav.id}
                              onClick={() => {
                                setModelName(fav.id);
                                setShowModelSearch(false);
                                setModelSearchQuery("");
                              }}
                              className={`w-full text-left px-3 py-2 text-xs border-b border-gray-800/50 
                                          hover:bg-gray-800 transition-colors ${
                                            isSelected ? "bg-indigo-900/30 border-l-2 border-l-indigo-500" : ""
                                          }`}
                            >
                              <div className="flex items-center gap-1.5">
                                <span className="text-amber-400/60">*</span>
                                <span className="font-medium text-gray-200 truncate">
                                  {fav.name}
                                </span>
                              </div>
                              <div className="text-gray-600 truncate mt-0.5 ml-4">
                                {fav.id}
                              </div>
                              <div className="text-gray-500 mt-0.5 ml-4 leading-snug">
                                {fav.why}
                              </div>
                            </button>
                          );
                        })}
                        <div className="px-3 py-1.5 bg-gray-800/50 border-b border-gray-800">
                          <span className="text-xs font-semibold text-gray-500 uppercase tracking-wide">
                            All Models
                          </span>
                          <span className="text-xs text-gray-600 ml-2">
                            {modelSearching
                              ? "loading..."
                              : `${modelSearchTotal} available`}
                          </span>
                        </div>
                      </>
                    )}
                    {/* Search status when query is active */}
                    {modelSearchQuery && (
                      <div className="px-3 py-1.5 bg-gray-800/50 border-b border-gray-800">
                        <span className="text-xs text-gray-500">
                          {modelSearching
                            ? "Searching..."
                            : `${modelSearchTotal} result${modelSearchTotal !== 1 ? "s" : ""}`}
                        </span>
                      </div>
                    )}
                    {/* Search results / all models */}
                    {modelSearchResults.map((m) => {
                      const promptCost = parseFloat(m.prompt_price) * 1_000_000;
                      const completionCost = parseFloat(m.completion_price) * 1_000_000;
                      const isSelected = modelName === m.id;
                      return (
                        <button
                          key={m.id}
                          onClick={() => {
                            setModelName(m.id);
                            setShowModelSearch(false);
                            setModelSearchQuery("");
                          }}
                          className={`w-full text-left px-3 py-2 text-xs border-b border-gray-800/50 
                                      hover:bg-gray-800 transition-colors ${
                                        isSelected ? "bg-indigo-900/30 border-l-2 border-l-indigo-500" : ""
                                      }`}
                        >
                          <div className="font-medium text-gray-200 truncate">
                            {m.name}
                          </div>
                          <div className="flex items-center gap-2 mt-0.5 text-gray-500">
                            <span className="text-gray-600 truncate">{m.id}</span>
                            <span className="text-gray-700">|</span>
                            <span>{(m.context_length / 1000).toFixed(0)}k ctx</span>
                            {promptCost > 0 && (
                              <>
                                <span className="text-gray-700">|</span>
                                <span>
                                  ${promptCost.toFixed(2)}/{completionCost.toFixed(2)} per 1M
                                </span>
                              </>
                            )}
                            {promptCost === 0 && (
                              <>
                                <span className="text-gray-700">|</span>
                                <span className="text-green-500">free</span>
                              </>
                            )}
                          </div>
                        </button>
                      );
                    })}
                    {modelSearchResults.length === 0 && !modelSearching && (
                      <div className="px-3 py-4 text-xs text-gray-600 text-center">
                        No models found
                      </div>
                    )}
                  </div>
                </div>
              )}
            </div>

            <div>
              <label className={labelClass}>API Key</label>
              <input
                type="password"
                value={apiKey}
                onChange={(e) => setApiKey(e.target.value)}
                className={inputClass}
                placeholder={
                  model?.has_api_key
                    ? "Key configured (enter to change)"
                    : "sk-..."
                }
              />
            </div>

            <div>
              <label className={labelClass}>Base URL</label>
              <input
                type="text"
                value={baseUrl}
                onChange={(e) => setBaseUrl(e.target.value)}
                className={inputClass}
                placeholder="Auto-detected from provider"
              />
            </div>

            {/* ---- MAX TOKENS ---- */}
            <div>
              <label className={labelClass}>
                Max Tokens: <span className="font-mono text-indigo-400">{maxTokens}</span>
              </label>
              <div className="flex items-center gap-2">
                <input
                  type="range"
                  min={1}
                  max={16384}
                  step={1}
                  value={maxTokens}
                  onChange={(e) => setMaxTokens(Number(e.target.value))}
                  className="flex-1 accent-indigo-500"
                />
                <input
                  type="number"
                  min={1}
                  max={50000}
                  value={maxTokens}
                  onChange={(e) => {
                    const v = Number(e.target.value);
                    if (v >= 1 && v <= 50000) setMaxTokens(v);
                  }}
                  className="w-20 bg-gray-800 text-white text-xs font-mono rounded px-2 py-1.5 border border-gray-700 focus:outline-none focus:border-indigo-500 transition-colors"
                />
              </div>
              <div className="flex justify-between mt-1">
                {[32, 128, 256, 512, 1024, 2048, 4096].map((v) => (
                  <button
                    key={v}
                    onClick={() => setMaxTokens(v)}
                    className={`text-[10px] px-1.5 py-0.5 rounded transition-colors ${
                      maxTokens === v
                        ? "bg-indigo-600/30 text-indigo-300 border border-indigo-500/50"
                        : "text-gray-600 hover:text-gray-400"
                    }`}
                  >
                    {v >= 1024 ? `${v / 1024}k` : v}
                  </button>
                ))}
              </div>
            </div>

            {/* ---- DIFFUSION TOGGLE ---- */}
            <div className="border border-purple-500/20 rounded-lg p-3 bg-purple-900/10">
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={diffusion}
                  onChange={(e) => setDiffusion(e.target.checked)}
                  className="accent-purple-500"
                />
                <span className="text-sm font-medium text-purple-300">
                  Real diffusion streaming
                </span>
              </label>
              <p className="text-xs text-gray-500 mt-1.5 ml-5">
                Stream Mercury 2's actual denoising steps to the chat.
                Watch text resolve from noise through the model's real
                diffusion process. Requires Inception provider.
              </p>
              {model && !model.diffusion_available && diffusion && (
                <p className="text-xs text-amber-400 mt-1.5 ml-5">
                  Current provider ({model.provider}) does not support
                  diffusion streaming. Switch to "inception" provider
                  for real diffusion.
                </p>
              )}
            </div>

            {/* Advanced toggle */}
            <button
              onClick={() => setExpanded(!expanded)}
              className="text-xs text-gray-500 hover:text-gray-300 transition-colors"
            >
              {expanded ? "Hide" : "Show"} advanced settings
            </button>

            {expanded && (
              <div className="space-y-3 border border-gray-800 rounded-lg p-3 bg-gray-900/30">
                <div>
                  <label className={labelClass}>Timeout (s)</label>
                  <input
                    type="number"
                    min={1}
                    max={120}
                    value={timeout}
                    onChange={(e) => setTimeout_(Number(e.target.value))}
                    className={inputClass}
                  />
                </div>

                <div>
                  <label className={labelClass}>
                    Temperature: {temperature.toFixed(2)}
                  </label>
                  <input
                    type="range"
                    min={0}
                    max={200}
                    value={temperature * 100}
                    onChange={(e) =>
                      setTemperature(Number(e.target.value) / 100)
                    }
                    className="w-full accent-indigo-500"
                  />
                </div>

                <div>
                  <label className={labelClass}>
                    Top P: {topP.toFixed(2)}
                  </label>
                  <input
                    type="range"
                    min={0}
                    max={100}
                    value={topP * 100}
                    onChange={(e) => setTopP(Number(e.target.value) / 100)}
                    className="w-full accent-indigo-500"
                  />
                </div>

                <div>
                  <label className={labelClass}>
                    Frequency Penalty: {freqPenalty.toFixed(2)}
                  </label>
                  <input
                    type="range"
                    min={-200}
                    max={200}
                    value={freqPenalty * 100}
                    onChange={(e) =>
                      setFreqPenalty(Number(e.target.value) / 100)
                    }
                    className="w-full accent-indigo-500"
                  />
                </div>

                <div>
                  <label className={labelClass}>
                    Presence Penalty: {presPenalty.toFixed(2)}
                  </label>
                  <input
                    type="range"
                    min={-200}
                    max={200}
                    value={presPenalty * 100}
                    onChange={(e) =>
                      setPresPenalty(Number(e.target.value) / 100)
                    }
                    className="w-full accent-indigo-500"
                  />
                </div>
              </div>
            )}

            <button
              onClick={saveModel}
              disabled={saving || !modelName}
              className={`${btnClass} bg-emerald-600 text-white hover:bg-emerald-500`}
            >
              {saving ? "Saving..." : "Apply Model"}
            </button>
          </div>
        </section>

        {/* ---- DISPLAY OPTIONS ---- */}
        <section>
          <h3 className="text-sm font-semibold text-gray-300 mb-3 uppercase tracking-wide">
            Display
          </h3>
          <label className="flex items-center gap-2 cursor-pointer">
            <input
              type="checkbox"
              checked={showOriginals}
              onChange={onToggleOriginals}
              className="accent-indigo-500"
            />
            <span className="text-sm text-gray-400">
              Show original messages
            </span>
          </label>
        </section>

        {/* ---- CONTEXT MANAGEMENT ---- */}
        <section>
          <h3 className="text-sm font-semibold text-gray-300 mb-3 uppercase tracking-wide">
            Context Management
          </h3>
          <div className="space-y-3">
            {/* Current stats */}
            {contextStats && (
              <div className="border border-gray-800 rounded-lg p-3 bg-gray-900/30 space-y-1">
                <div className="flex items-center justify-between text-xs">
                  <span className="text-gray-500">Messages</span>
                  <span className="font-mono text-gray-300">
                    {contextStats.message_count}
                    <span className="text-gray-600"> / {contextStats.max_messages}</span>
                  </span>
                </div>
                <div className="w-full bg-gray-800 rounded-full h-1.5">
                  <div
                    className="bg-indigo-500 h-1.5 rounded-full transition-all"
                    style={{
                      width: `${Math.min(100, (contextStats.message_count / contextStats.max_messages) * 100)}%`,
                    }}
                  />
                </div>
                <div className="flex items-center justify-between text-xs mt-2">
                  <span className="text-gray-500">Total tokens</span>
                  <span className="font-mono text-gray-300">
                    {contextStats.total_tokens.toLocaleString()}
                  </span>
                </div>
              </div>
            )}

            {/* Limits */}
            <div>
              <label className={labelClass}>
                Max Messages: <span className="font-mono">{ctxMaxMessages}</span>
              </label>
              <input
                type="range"
                min={50}
                max={2000}
                step={50}
                value={ctxMaxMessages}
                onChange={(e) => setCtxMaxMessages(Number(e.target.value))}
                className="w-full accent-indigo-500"
              />
            </div>
            <div>
              <label className={labelClass}>
                Max Tokens/User: <span className="font-mono">{ctxMaxTokens.toLocaleString()}</span>
              </label>
              <input
                type="range"
                min={10000}
                max={500000}
                step={10000}
                value={ctxMaxTokens}
                onChange={(e) => setCtxMaxTokens(Number(e.target.value))}
                className="w-full accent-indigo-500"
              />
            </div>

            <button
              onClick={handleSaveContextSettings}
              disabled={ctxSaving}
              className={`${btnClass} bg-emerald-600 text-white hover:bg-emerald-500`}
            >
              {ctxSaving ? "Saving..." : "Apply Limits"}
            </button>

            {/* Reset button */}
            {!confirmReset ? (
              <button
                onClick={() => setConfirmReset(true)}
                className={`${btnClass} bg-red-900/30 text-red-400 border border-red-500/30 hover:bg-red-900/50`}
              >
                Reset Chat History
              </button>
            ) : (
              <div className="flex gap-2">
                <button
                  onClick={handleResetContext}
                  className="flex-1 px-3 py-2 text-xs font-medium rounded-lg bg-red-600 text-white hover:bg-red-500 transition-colors"
                >
                  Confirm Reset
                </button>
                <button
                  onClick={() => setConfirmReset(false)}
                  className="flex-1 px-3 py-2 text-xs font-medium rounded-lg bg-gray-800 text-gray-400 hover:bg-gray-700 transition-colors"
                >
                  Cancel
                </button>
              </div>
            )}
          </div>
        </section>

        {/* ---- USER MANAGEMENT ---- */}
        <section>
          <h3 className="text-sm font-semibold text-gray-300 mb-3 uppercase tracking-wide">
            Users
            {usersLoading && (
              <span className="ml-2 text-gray-600 font-normal normal-case">loading...</span>
            )}
          </h3>
          <div className="space-y-2">
            {users.length === 0 && !usersLoading && (
              <p className="text-xs text-gray-600">No active users</p>
            )}
            {users.map((u) => (
              <div
                key={u.user_id}
                className="border border-gray-800 rounded-lg p-2.5 bg-gray-900/30"
              >
                <div className="flex items-center justify-between mb-1">
                  <div className="flex items-center gap-1.5">
                    <span className="text-xs font-medium text-gray-200">
                      {u.username}
                    </span>
                    <span
                      className={`px-1.5 py-0.5 text-[10px] rounded ${
                        u.role === "admin"
                          ? "bg-purple-600/30 text-purple-300 border border-purple-500/30"
                          : "bg-gray-800 text-gray-500 border border-gray-700"
                      }`}
                    >
                      {u.role}
                    </span>
                  </div>
                  <span className="text-[10px] text-gray-600">
                    {formatRelativeTime(u.last_active)}
                  </span>
                </div>

                <div className="flex items-center gap-3 text-[10px] text-gray-500 mb-2">
                  <span>
                    <span className="font-mono text-gray-400">{u.total_messages}</span> msgs
                  </span>
                  <span>
                    <span className="font-mono text-gray-400">{u.total_tokens_used.toLocaleString()}</span> tok
                  </span>
                </div>

                <div className="flex items-center gap-2">
                  <select
                    value={u.role}
                    onChange={(e) =>
                      handleSetRole(u.user_id, e.target.value as "user" | "admin")
                    }
                    className="flex-1 bg-gray-800 text-gray-300 text-[10px] rounded px-1.5 py-1 border border-gray-700 focus:outline-none focus:border-indigo-500"
                  >
                    <option value="user">user</option>
                    <option value="admin">admin</option>
                  </select>
                  <button
                    onClick={() => handleKick(u.user_id)}
                    className="px-2 py-1 text-[10px] rounded bg-red-900/30 text-red-400 border border-red-500/30 hover:bg-red-900/50 transition-colors"
                  >
                    Kick
                  </button>
                </div>
              </div>
            ))}
          </div>
        </section>

        {/* ---- STATUS ---- */}
        {model && (
          <section className="text-xs text-gray-600 space-y-1 pb-4">
            <div>
              Provider: {model.provider} | Model: {model.model}
            </div>
            <div>
              API Key: {model.has_api_key ? "configured" : "not set"} |
              Max Tokens: {model.max_tokens}
            </div>
            <div>
              Diffusion: {model.diffusion ? "ON" : "off"}
              {model.diffusion && !model.diffusion_available && " (unavailable on this provider)"}
              {model.diffusion && model.diffusion_available && " (active)"}
            </div>
            <div>
              Temp: {model.temperature} | Top P: {model.top_p} | Timeout:{" "}
              {model.timeout}s
            </div>
          </section>
        )}
      </div>
    </div>
  );
}
