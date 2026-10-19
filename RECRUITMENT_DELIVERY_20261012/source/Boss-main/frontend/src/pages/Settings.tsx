import { useCallback, useEffect, useRef, useState } from "react";
import ChromeConnect from "../components/ChromeConnect";
import { api } from "../api/client";
import {
  Settings as SettingsIcon,
  Check,
  Loader2,
  Wifi,
  Shield,
  AlertCircle,
  UserPlus,
  RefreshCw,
  Trash2,
  Smartphone,
  LogIn,
  Building2,
} from "lucide-react";
import { useToast } from "../hooks/useToast";

interface Provider {
  id: string;
  name: string;
  base_url: string;
  models: { id: string; name: string; context: string }[];
}

interface CurrentSettings {
  api_key_masked: string;
  has_api_key: boolean;
  base_url: string;
  model: string;
  current_provider: string;
  boss_logged_in: boolean;
}

interface BossAccount {
  last_error: string;
  connection_type: string;
  id: number;
  name: string;
  phone: string;
  company: string;
  is_logged_in: boolean;
  is_logging_in: boolean;
  last_login_at: string | null;
  created_at: string | null;
}

export default function Settings() {
  const { pushToast } = useToast();
  const [providers, setProviders] = useState<Provider[]>([]);
  const [current, setCurrent] = useState<CurrentSettings | null>(null);
  const [loading, setLoading] = useState(true);

  // Form state
  const [selectedProvider, setSelectedProvider] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [baseUrl, setBaseUrl] = useState("");
  const [model, setModel] = useState("");
  const [customModel, setCustomModel] = useState("");

  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<{
    success: boolean;
    message: string;
  } | null>(null);

  // Boss accounts state
  const [bossAccounts, setBossAccounts] = useState<BossAccount[]>([]);
  const [loginLoading, setLoginLoading] = useState(false);
  const [loginMessage, setLoginMessage] = useState("");
  const [pendingDeleteId, setPendingDeleteId] = useState<number | null>(null);
  const pollingRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const [pollingAccountId, setPollingAccountId] = useState<number | null>(null);

  const loadBossAccounts = useCallback(async () => {
    try {
      const data = await api.get<BossAccount[]>("/api/boss-accounts");
      setBossAccounts(data);
    } catch (err) {
      console.error("Failed to load boss accounts:", err);
    }
  }, []);

  useEffect(() => {
    loadSettings();
    loadBossAccounts();
  }, [loadBossAccounts]);

  async function loadSettings() {
    try {
      const [settingsData, providersData] = await Promise.all([
        api.get<CurrentSettings>("/api/settings"),
        api.get<Provider[]>("/api/settings/providers"),
      ]);
      setCurrent(settingsData);
      setProviders(providersData);

      // Initialize form from current settings
      setSelectedProvider(settingsData.current_provider);
      setBaseUrl(settingsData.base_url);
      setModel(settingsData.model);

      // If current model is not in any provider's list, set it as custom
      const provider = providersData.find(
        (p) => p.id === settingsData.current_provider
      );
      if (
        provider &&
        provider.models.length > 0 &&
        !provider.models.find((m) => m.id === settingsData.model)
      ) {
        setCustomModel(settingsData.model);
      }
    } catch (err) {
      console.error("Failed to load settings:", err);
    } finally {
      setLoading(false);
    }
  }

  function handleProviderChange(providerId: string) {
    setSelectedProvider(providerId);
    const provider = providers.find((p) => p.id === providerId);
    if (provider) {
      if (provider.base_url) {
        setBaseUrl(provider.base_url);
      }
      if (provider.models.length > 0) {
        setModel(provider.models[0].id);
        setCustomModel("");
      }
    }
    setTestResult(null);
  }

  function handleModelChange(modelId: string) {
    setModel(modelId);
    setCustomModel("");
    setTestResult(null);
  }

  const currentProvider = providers.find((p) => p.id === selectedProvider);
  const availableModels = currentProvider?.models || [];
  const isCustom = selectedProvider === "custom";
  const finalModel = isCustom || customModel ? customModel || model : model;

  async function handleSave() {
    setSaving(true);
    setTestResult(null);
    try {
      await api.put("/api/settings", {
        api_key: apiKey || undefined,
        base_url: baseUrl,
        model: finalModel,
      });
      setSaved(true);
      setTimeout(() => setSaved(false), 3000);
      // Reload to get updated masked key
      await loadSettings();
      setApiKey("");
      pushToast({
        type: "success",
        title: "配置已保存",
        message: "新的模型配置已生效",
      });
    } catch (err) {
      pushToast({
        type: "error",
        title: "保存配置失败",
        message: (err as Error).message,
      });
    } finally {
      setSaving(false);
    }
  }

  async function handleTest() {
    setTesting(true);
    setTestResult(null);
    try {
      const result = await api.post<{
        success: boolean;
        response?: string;
        error?: string;
        model?: string;
      }>("/api/settings/test", undefined, 75_000);
      if (result.success) {
        setTestResult({
          success: true,
          message: `连接成功! 模型: ${result.model} — "${result.response}"`,
        });
      } else {
        setTestResult({
          success: false,
          message: `连接失败: ${result.error}`,
        });
      }
    } catch (err) {
      setTestResult({
        success: false,
        message: `请求错误: ${(err as Error).message}`,
      });
    } finally {
      setTesting(false);
    }
  }

  // Poll for login status when a login is in progress
  useEffect(() => {
    if (pollingAccountId === null) return;
    pollingRef.current = setInterval(async () => {
      try {
        const status = await api.get<{
          account_id: number;
          is_logged_in: boolean;
          is_logging_in: boolean;
          name: string;
          company: string;
          step: string;
          last_error: string;
        }>(`/api/boss-accounts/${pollingAccountId}/status`);

        if (status.is_logged_in) {
          setLoginMessage("登录成功! " + (status.name || "") + (status.company ? ` (${status.company})` : ""));
          setPollingAccountId(null);
          setLoginLoading(false);
          loadBossAccounts();
        } else if (!status.is_logging_in) {
          setLoginMessage(status.last_error || "尚未确认登录，请完成登录后刷新状态。");
          setPollingAccountId(null);
          setLoginLoading(false);
          loadBossAccounts();
        } else {
          const stepMap: Record<string, string> = {
            launching: "正在启动浏览器...",
            navigating: "正在打开 Boss 直聘...",
            waiting_for_login: "等待手机号登录中... 请在 Chrome 窗口中完成登录",
            login_success: "登录成功，正在保存...",
          };
          setLoginMessage(stepMap[status.step] || "处理中...");
        }
      } catch {
        // ignore polling errors
      }
    }, 2000);

    return () => {
      if (pollingRef.current) clearInterval(pollingRef.current);
    };
  }, [pollingAccountId, loadBossAccounts]);

  async function handleAddAccount() {
    setLoginLoading(true);
    setLoginMessage("正在启动 Chrome 浏览器...");
    try {
      const result = await api.post<{
        account_id: number;
        status: string;
        message: string;
      }>("/api/boss-accounts/login", { name: "" });
      setLoginMessage(result.message);
      setPollingAccountId(result.account_id);
    } catch (err) {
      setLoginMessage("启动失败: " + (err as Error).message);
      setLoginLoading(false);
    }
  }

  async function handleRelogin(accountId: number) {
    setLoginLoading(true);
    setLoginMessage("正在重新打开浏览器...");
    try {
      const result = await api.post<{
        account_id: number;
        status: string;
        message: string;
      }>(`/api/boss-accounts/${accountId}/relogin`);
      setLoginMessage(result.message);
      if (result.status !== "already_logging_in") {
        setPollingAccountId(accountId);
      }
    } catch (err) {
      setLoginMessage("启动失败: " + (err as Error).message);
      setLoginLoading(false);
    }
  }

  async function handleDeleteAccount(accountId: number) {
    try {
      await api.delete(`/api/boss-accounts/${accountId}`);
      loadBossAccounts();
      pushToast({
        type: "success",
        title: "账号已删除",
        message: `Boss 账号 ${accountId} 已从系统移除`,
      });
    } catch (err) {
      pushToast({
        type: "error",
        title: "删除账号失败",
        message: (err as Error).message,
      });
    }
  }

  if (loading) {
    return (
      <div className="flex h-64 items-center justify-center px-6">
        <Loader2 size={24} className="animate-spin text-slate-500" />
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-4xl space-y-6 px-5 py-6 lg:px-8">
      <div className="section-shell p-6 lg:p-7">
        <h1 className="flex items-center gap-2 text-3xl font-semibold text-white">
        <SettingsIcon size={24} /> 系统设置
        </h1>
        <p className="mt-3 text-sm leading-6 text-slate-400">
          统一管理大模型配置和 Boss 直聘账号登录状态。建议先完成模型连接测试，再添加招聘账号。
        </p>
      </div>

      <div className="section-shell space-y-5 p-6">
        <h2 className="text-lg font-semibold text-white">LLM 模型配置</h2>

        {/* Provider */}
        <div>
          <label className="mb-2 block text-sm font-medium text-slate-300">
            选择服务商
          </label>
          <div className="grid grid-cols-3 gap-2">
            {providers.map((p) => (
              <button
                key={p.id}
                onClick={() => handleProviderChange(p.id)}
                className={`px-3 py-2.5 rounded-lg border text-sm font-medium transition-all text-left ${
                  selectedProvider === p.id
                    ? "border-cyan-300/30 bg-cyan-300/12 text-cyan-100"
                    : "border-white/10 bg-white/4 text-slate-300 hover:bg-white/8"
                }`}
              >
                {p.name}
              </button>
            ))}
          </div>
        </div>

        {/* API Key */}
        <div>
          <label className="mb-1 block text-sm font-medium text-slate-300">
            API Key
          </label>
          {current?.has_api_key && !apiKey && (
            <div className="flex items-center gap-2 mb-2">
              <Shield size={14} className="text-emerald-300" />
              <span className="text-xs text-emerald-300">
                当前已配置: {current.api_key_masked}
              </span>
            </div>
          )}
          <input
            type="password"
            value={apiKey}
            onChange={(e) => setApiKey(e.target.value)}
            placeholder={
              current?.has_api_key ? "留空保持不变，或输入新 Key..." : "sk-..."
            }
            className="w-full rounded-2xl border border-white/10 bg-slate-950/40 px-3 py-2.5 text-sm text-white outline-none placeholder:text-slate-500"
          />
        </div>

        {/* Base URL */}
        <div>
          <label className="mb-1 block text-sm font-medium text-slate-300">
            API Base URL
          </label>
          <input
            type="text"
            value={baseUrl}
            onChange={(e) => setBaseUrl(e.target.value)}
            placeholder="https://api.example.com/v1"
            className="w-full rounded-2xl border border-white/10 bg-slate-950/40 px-3 py-2.5 text-sm text-white outline-none placeholder:text-slate-500"
          />
          {currentProvider && currentProvider.base_url && (
            <p className="mt-1 text-xs text-slate-500">
              {currentProvider.name} 默认地址: {currentProvider.base_url}
            </p>
          )}
        </div>

        {/* Model Selection */}
        <div>
          <label className="mb-1 block text-sm font-medium text-slate-300">
            模型
          </label>
          {availableModels.length > 0 ? (
            <div className="space-y-2">
              <div className="grid grid-cols-1 gap-1.5">
                {availableModels.map((m) => (
                  <button
                    key={m.id}
                    onClick={() => handleModelChange(m.id)}
                    className={`flex items-center justify-between px-3 py-2.5 rounded-lg border text-sm transition-all ${
                      model === m.id && !customModel
                        ? "border-cyan-300/30 bg-cyan-300/12 text-cyan-100"
                        : "border-white/10 bg-white/4 text-slate-300 hover:bg-white/8"
                    }`}
                  >
                    <span className="font-medium">{m.name}</span>
                    <span className="rounded bg-slate-950/40 px-2 py-0.5 text-xs text-slate-500">
                      {m.context}
                    </span>
                  </button>
                ))}
              </div>
              <div className="pt-1">
                <input
                  type="text"
                  value={customModel}
                  onChange={(e) => {
                    setCustomModel(e.target.value);
                    if (e.target.value) setModel(e.target.value);
                  }}
                  placeholder="或输入自定义模型名称..."
                  className="w-full rounded-2xl border border-dashed border-white/10 bg-slate-950/40 px-3 py-2.5 text-sm text-white outline-none placeholder:text-slate-500"
                />
              </div>
            </div>
          ) : (
            <input
              type="text"
              value={customModel || model}
              onChange={(e) => {
                setCustomModel(e.target.value);
                setModel(e.target.value);
              }}
              placeholder="输入模型名称 (如 gpt-4o, moonshot-v1-128k...)"
              className="w-full rounded-2xl border border-white/10 bg-slate-950/40 px-3 py-2.5 text-sm text-white outline-none placeholder:text-slate-500"
            />
          )}
        </div>

        {/* Test Result */}
        {testResult && (
          <div
            className={`flex items-start gap-2 p-3 rounded-lg text-sm ${
              testResult.success
                ? "border border-emerald-300/20 bg-emerald-300/10 text-emerald-200"
                : "border border-red-300/20 bg-red-300/10 text-red-200"
            }`}
          >
            {testResult.success ? (
              <Wifi size={16} className="mt-0.5 shrink-0" />
            ) : (
              <AlertCircle size={16} className="mt-0.5 shrink-0" />
            )}
            <span>{testResult.message}</span>
          </div>
        )}

        {/* Actions */}
        <div className="flex gap-3 pt-2">
          <button
            onClick={handleSave}
            disabled={saving}
            className="flex items-center gap-2 rounded-2xl bg-cyan-300 px-6 py-2.5 text-sm font-semibold text-slate-950 hover:bg-cyan-200 disabled:opacity-50"
          >
            {saving ? (
              <Loader2 size={16} className="animate-spin" />
            ) : saved ? (
              <Check size={16} />
            ) : null}
            {saved ? "已保存" : "保存配置"}
          </button>
          <button
            onClick={handleTest}
            disabled={testing}
            className="flex items-center gap-2 rounded-2xl border border-white/10 bg-white/5 px-6 py-2.5 text-sm font-medium text-slate-100 hover:bg-white/8 disabled:opacity-50"
          >
            {testing ? (
              <Loader2 size={16} className="animate-spin" />
            ) : (
              <Wifi size={16} />
            )}
            {testing ? "测试中..." : "测试连接"}
          </button>
        </div>
      </div>

      {/* Boss Zhipin Account Management */}
      <div className="section-shell space-y-5 p-6">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold flex items-center gap-2">
            <Building2 size={20} />
            Boss 直聘账号管理
          </h2>
          <button
            onClick={handleAddAccount}
            disabled={loginLoading}
            className="flex items-center gap-2 rounded-2xl bg-cyan-300 px-4 py-2.5 text-sm font-semibold text-slate-950 hover:bg-cyan-200 disabled:opacity-50"
          >
            {loginLoading ? (
              <Loader2 size={16} className="animate-spin" />
            ) : (
              <UserPlus size={16} />
            )}
            {loginLoading ? "登录中..." : "打开专用 Chrome 登录"}
          </button>
        </div>

        <p className="text-sm text-slate-400">
          已有登录的 Chrome 请使用下方的现有窗口接入。只有需要独立账号时，才使用“打开专用 Chrome 登录”。
        </p>

        <ChromeConnect onConnected={loadBossAccounts} />

        {/* Login progress message */}
        {loginMessage && (
          <div
            className={`flex items-center gap-2 p-3 rounded-lg text-sm ${
              loginMessage.includes("成功")
                ? "border border-emerald-300/20 bg-emerald-300/10 text-emerald-200"
                : loginMessage.includes("失败") || loginMessage.includes("关闭")
                ? "border border-amber-300/20 bg-amber-300/10 text-amber-200"
                : "border border-cyan-300/20 bg-cyan-300/10 text-cyan-100"
            }`}
          >
            {loginLoading && <Loader2 size={14} className="animate-spin shrink-0" />}
            {!loginLoading && loginMessage.includes("成功") && <Check size={14} className="shrink-0" />}
            {!loginLoading && !loginMessage.includes("成功") && <Smartphone size={14} className="shrink-0" />}
            <span>{loginMessage}</span>
          </div>
        )}

        {/* Account list */}
        {bossAccounts.length > 0 ? (
          <div className="space-y-2">
            {bossAccounts.map((acct) => (
              <div
                key={acct.id}
                className="flex items-center justify-between rounded-2xl border border-white/10 bg-white/4 p-3 transition-colors hover:bg-white/8"
              >
                <div className="flex items-center gap-3">
                  <div
                    className={`w-2.5 h-2.5 rounded-full shrink-0 ${
                      acct.is_logging_in
                        ? "bg-blue-400 animate-pulse"
                        : acct.is_logged_in
                        ? "bg-green-400"
                        : "bg-gray-300"
                    }`}
                  />
                  <div>
                    <div className="text-sm font-medium text-slate-100">
                      {acct.name || `账号 ${acct.id}`}
                      {acct.company && (
                        <span className="ml-2 font-normal text-slate-500">
                          {acct.company}
                        </span>
                      )}
                    </div>
                    {acct.last_error && <p className="mt-1 text-xs text-amber-200">{acct.last_error}</p>}
                    <div className="mt-0.5 text-xs text-slate-500">
                      {acct.is_logging_in ? (
                        <span className="text-blue-500">正在登录中...</span>
                      ) : acct.is_logged_in ? (
                        <span className="text-green-600">
                          已登录
                          {acct.last_login_at &&
                            ` · ${new Date(acct.last_login_at).toLocaleString("zh-CN")}`}
                        </span>
                      ) : (
                        <span className="text-slate-500">未登录</span>
                      )}
                    </div>
                  </div>
                </div>
                <div className="flex items-center gap-1.5">
                  <button
                    onClick={() => handleRelogin(acct.id)}
                    disabled={loginLoading}
                    className="rounded-lg p-2 text-slate-500 transition-colors hover:bg-white/8 hover:text-cyan-200 disabled:opacity-30"
                    title="重新登录"
                  >
                    <LogIn size={16} />
                  </button>
                  <button
                    onClick={() => setPendingDeleteId(acct.id)}
                    disabled={loginLoading}
                    className="rounded-lg p-2 text-slate-500 transition-colors hover:bg-red-300/10 hover:text-red-300 disabled:opacity-30"
                    title="删除账号"
                  >
                    <Trash2 size={16} />
                  </button>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="py-8 text-center text-sm text-slate-500">
            <Smartphone size={32} className="mx-auto mb-2 opacity-30" />
            暂无 Boss 直聘账号，请点击上方按钮添加
          </div>
        )}

        {/* Refresh button */}
        {bossAccounts.length > 0 && (
          <button
            onClick={loadBossAccounts}
            className="flex items-center gap-1 text-sm text-slate-500 transition-colors hover:text-slate-300"
          >
            <RefreshCw size={14} />
            刷新状态
          </button>
        )}
      </div>

      {/* Current Config Summary */}
      {current?.has_api_key && (
        <div className="rounded-[24px] border border-dashed border-white/10 bg-white/4 p-4">
          <h3 className="mb-2 text-sm font-medium text-slate-400">
            当前运行配置
          </h3>
          <div className="grid grid-cols-3 gap-4 text-sm">
            <div>
              <span className="text-slate-500">服务商</span>
              <p className="font-medium text-white">
                {providers.find((p) => p.id === current.current_provider)
                  ?.name || "自定义"}
              </p>
            </div>
            <div>
              <span className="text-slate-500">模型</span>
              <p className="font-medium text-white">{current.model}</p>
            </div>
            <div>
              <span className="text-slate-500">API Key</span>
              <p className="font-medium text-white">{current.api_key_masked}</p>
            </div>
          </div>
        </div>
      )}

      {pendingDeleteId !== null && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/55 p-6">
          <div className="glass-panel-strong w-full max-w-md rounded-[28px] p-6">
            <h3 className="text-lg font-semibold text-white">确认删除账号</h3>
            <p className="mt-3 text-sm leading-6 text-slate-400">
              仅移除账号绑定，保留 Chrome 窗口和登录数据。
            </p>
            <div className="mt-6 flex gap-3">
              <button
                onClick={() => setPendingDeleteId(null)}
                className="flex-1 rounded-2xl border border-white/10 bg-white/5 px-4 py-2.5 text-sm font-medium text-slate-100 hover:bg-white/8"
              >
                取消
              </button>
              <button
                onClick={async () => {
                  const targetId = pendingDeleteId;
                  setPendingDeleteId(null);
                  await handleDeleteAccount(targetId);
                }}
                className="flex-1 rounded-2xl bg-red-300 px-4 py-2.5 text-sm font-semibold text-slate-950 hover:bg-red-200"
              >
                确认删除
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
