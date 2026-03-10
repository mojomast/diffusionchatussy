import { useState, useEffect } from "react";
import type { ToneConfig, ModelConfig } from "../types";
import {
  setTone,
  setModel,
  getTonePresets,
  getProviderPresets,
} from "../api";

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

  // Load presets on mount
  useEffect(() => {
    getTonePresets().then(setTonePresets).catch(console.error);
    getProviderPresets().then(setProviderPresets).catch(console.error);
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
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className={labelClass}>Max Tokens</label>
                    <input
                      type="number"
                      min={1}
                      max={4096}
                      value={maxTokens}
                      onChange={(e) => setMaxTokens(Number(e.target.value))}
                      className={inputClass}
                    />
                  </div>

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
