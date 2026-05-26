import { FormEvent, useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { AlertTriangle, ExternalLink, Rocket, Save, ShieldCheck } from "lucide-react";
import { api, getApiToken, setApiToken, SettingsUpdatePayload } from "../api/client";
import AgentModelConfigurator, {
  AgentLLMForm,
  defaultAgentConfigs,
  hydrateAgentConfigs,
  primaryAgentConfig,
  toAgentConfigPayload
} from "../components/AgentModelConfigurator";
import { HealthBadge, KillSwitchBadge, StatusBadge } from "../components/Badges";
import { displayValue, formatReason, formatSettingKey } from "../lib/format";

type FormState = {
  app_env: string;
  api_auth_enabled: boolean;
  api_auth_token: string;
  local_api_token: string;
  broker_provider: "mock" | "webull";
  trading_mode: "paper" | "live";
  enable_live_trading: boolean;
  webull_env: "test" | "production";
  webull_region: string;
  webull_account_id: string;
  webull_app_key: string;
  webull_app_secret: string;
  webull_trading_endpoint_test: string;
  webull_market_data_endpoint_test: string;
  webull_trading_endpoint_production: string;
  webull_market_data_endpoint_production: string;
  llm_provider: string;
  llm_model: string;
  llm_api_key: string;
  llm_base_url: string;
  llm_agent_configs: AgentLLMForm[];
  mock_agent_action: "BUY" | "SELL" | "HOLD" | "";
  max_position_pct: string;
  max_single_trade_risk_pct: string;
  max_daily_loss_pct: string;
  min_agent_confidence: string;
  trade_cooldown_seconds: string;
  max_order_price_deviation_pct: string;
  live_preview_ttl_seconds: string;
  max_daily_live_order_count: string;
  max_daily_live_notional: string;
  regular_trading_hours_only: boolean;
};

const initialForm: FormState = {
  app_env: "development",
  api_auth_enabled: false,
  api_auth_token: "",
  local_api_token: "",
  broker_provider: "mock",
  trading_mode: "paper",
  enable_live_trading: false,
  webull_env: "test",
  webull_region: "us",
  webull_account_id: "",
  webull_app_key: "",
  webull_app_secret: "",
  webull_trading_endpoint_test: "",
  webull_market_data_endpoint_test: "",
  webull_trading_endpoint_production: "",
  webull_market_data_endpoint_production: "",
  llm_provider: "mock",
  llm_model: "",
  llm_api_key: "",
  llm_base_url: "",
  llm_agent_configs: defaultAgentConfigs(),
  mock_agent_action: "",
  max_position_pct: "0.05",
  max_single_trade_risk_pct: "0.01",
  max_daily_loss_pct: "0.02",
  min_agent_confidence: "0.65",
  trade_cooldown_seconds: "300",
  max_order_price_deviation_pct: "0.05",
  live_preview_ttl_seconds: "300",
  max_daily_live_order_count: "5",
  max_daily_live_notional: "5000",
  regular_trading_hours_only: true
};

export default function SettingsPage() {
  const queryClient = useQueryClient();
  const settings = useQuery({ queryKey: ["settings"], queryFn: api.settings });
  const provider = useQuery({ queryKey: ["provider-status"], queryFn: api.providerStatus });
  const readiness = useQuery({ queryKey: ["production-readiness"], queryFn: api.productionReadiness });
  const [form, setForm] = useState<FormState>(initialForm);
  const [saved, setSaved] = useState(false);
  const [settingsMode, setSettingsMode] = useState<"general" | "advanced">("general");

  useEffect(() => {
    setForm((current) => ({ ...current, local_api_token: getApiToken() }));
  }, []);

  useEffect(() => {
    if (!settings.data) return;
    setForm((current) => ({
      ...current,
      app_env: settings.data.app_env,
      api_auth_enabled: settings.data.api_auth_enabled,
      broker_provider: settings.data.broker_provider,
      trading_mode: settings.data.trading_mode,
      enable_live_trading: settings.data.enable_live_trading,
      webull_env: settings.data.webull_env,
      webull_region: settings.data.webull_region,
      webull_trading_endpoint_test: settings.data.webull_trading_endpoint_test,
      webull_market_data_endpoint_test: settings.data.webull_market_data_endpoint_test,
      webull_trading_endpoint_production: settings.data.webull_trading_endpoint_production,
      webull_market_data_endpoint_production: settings.data.webull_market_data_endpoint_production,
      llm_provider: settings.data.llm_provider,
      llm_model: settings.data.llm_model,
      llm_base_url: settings.data.llm_base_url,
      llm_agent_configs: hydrateAgentConfigs(settings.data),
      mock_agent_action: settings.data.mock_agent_action,
      max_position_pct: String(settings.data.max_position_pct),
      max_single_trade_risk_pct: String(settings.data.max_single_trade_risk_pct),
      max_daily_loss_pct: String(settings.data.max_daily_loss_pct),
      min_agent_confidence: String(settings.data.min_agent_confidence),
      trade_cooldown_seconds: String(settings.data.trade_cooldown_seconds),
      max_order_price_deviation_pct: String(settings.data.max_order_price_deviation_pct),
      live_preview_ttl_seconds: String(settings.data.live_preview_ttl_seconds),
      max_daily_live_order_count: String(settings.data.max_daily_live_order_count),
      max_daily_live_notional: settings.data.max_daily_live_notional,
      regular_trading_hours_only: settings.data.regular_trading_hours_only
    }));
  }, [settings.data]);

  const mutation = useMutation({
    mutationFn: (payload: SettingsUpdatePayload) => api.updateSettings(payload),
    onSuccess: async () => {
      setSaved(true);
      setForm((current) => ({
        ...current,
        api_auth_token: "",
        webull_account_id: "",
        webull_app_key: "",
        webull_app_secret: "",
        llm_api_key: "",
        llm_agent_configs: current.llm_agent_configs.map((config) => ({ ...config, api_key: "" }))
      }));
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["settings"] }),
        queryClient.invalidateQueries({ queryKey: ["provider-status"] }),
        queryClient.invalidateQueries({ queryKey: ["production-readiness"] }),
        queryClient.invalidateQueries({ queryKey: ["positions"] })
      ]);
    }
  });

  function update<K extends keyof FormState>(key: K, value: FormState[K]) {
    setSaved(false);
    setForm((current) => ({ ...current, [key]: value }));
  }

  function updateAgentConfigs(next: AgentLLMForm[]) {
    setSaved(false);
    setForm((current) => ({ ...current, llm_agent_configs: next }));
  }

  function submit(event: FormEvent) {
    event.preventDefault();
    const primary = primaryAgentConfig(form.llm_agent_configs);
    const serverToken = form.api_auth_token.trim();
    const browserToken = serverToken || form.local_api_token.trim();
    setApiToken(browserToken);
    const payload: SettingsUpdatePayload = {
      app_env: form.app_env,
      api_auth_enabled: form.api_auth_enabled,
      broker_provider: form.broker_provider,
      trading_mode: form.trading_mode,
      enable_live_trading: form.enable_live_trading,
      webull_env: form.webull_env,
      webull_region: form.webull_region,
      webull_trading_endpoint_test: form.webull_trading_endpoint_test,
      webull_market_data_endpoint_test: form.webull_market_data_endpoint_test,
      webull_trading_endpoint_production: form.webull_trading_endpoint_production,
      webull_market_data_endpoint_production: form.webull_market_data_endpoint_production,
      llm_provider: primary.provider,
      llm_model: primary.model,
      llm_base_url: primary.base_url,
      llm_agent_configs: toAgentConfigPayload(form.llm_agent_configs),
      mock_agent_action: form.mock_agent_action,
      max_position_pct: Number(form.max_position_pct),
      max_single_trade_risk_pct: Number(form.max_single_trade_risk_pct),
      max_daily_loss_pct: Number(form.max_daily_loss_pct),
      min_agent_confidence: Number(form.min_agent_confidence),
      trade_cooldown_seconds: Number(form.trade_cooldown_seconds),
      max_order_price_deviation_pct: Number(form.max_order_price_deviation_pct),
      live_preview_ttl_seconds: Number(form.live_preview_ttl_seconds),
      max_daily_live_order_count: Number(form.max_daily_live_order_count),
      max_daily_live_notional: form.max_daily_live_notional,
      regular_trading_hours_only: form.regular_trading_hours_only
    };
    if (serverToken) payload.api_auth_token = serverToken;
    if (form.webull_account_id.trim()) payload.webull_account_id = form.webull_account_id.trim();
    if (form.webull_app_key.trim()) payload.webull_app_key = form.webull_app_key.trim();
    if (form.webull_app_secret.trim()) payload.webull_app_secret = form.webull_app_secret.trim();
    if (primary.api_key.trim()) payload.llm_api_key = primary.api_key.trim();
    mutation.mutate(payload);
  }

  return (
    <div className="page-stack">
      <section className="toolbar">
        <div>
          <h2>设置</h2>
          <p>在前端修改本地运行配置。密钥只写入后端 `.env`，不会回显。</p>
          {settings.error && <p className="danger-text">读取设置失败：{settings.error.message}</p>}
        </div>
      </section>

      <section className="setup-banner">
        <div>
          <Rocket size={22} />
          <div>
            <h3>初始化向导可随时重新运行</h3>
            <p>首次使用建议先运行；完成后也可以从这里重新进入，调整数据源、模型会议和风控参数。</p>
          </div>
        </div>
        <Link className="primary-action" to="/setup">
          重新运行初始化向导
        </Link>
      </section>

      <section className={readiness.data?.ready ? "panel readiness-panel readiness-ok" : "panel readiness-panel readiness-blocked"}>
        <div className="panel-heading">
          <div>
            <h3>真实交易上线检查</h3>
            <p>这里只显示能不能进入真实资金交易。普通模拟使用不用处理这些阻断项。</p>
          </div>
          <StatusBadge
            value={readiness.data?.ready ? "已通过" : "未通过"}
            tone={readiness.data?.ready ? "ok" : "danger"}
          />
        </div>
        <div className="readiness-summary">
          {readiness.isLoading && <span>正在检查上线条件...</span>}
          {readiness.error && <span className="danger-text">{readiness.error.message}</span>}
          {readiness.data && (
            <>
              <span>
                <ShieldCheck size={16} />
                阻断项 {readiness.data.checks.filter((check) => check.severity === "blocker" && !check.passed).length} 个
              </span>
              <span>
                <AlertTriangle size={16} />
                警告项 {readiness.data.checks.filter((check) => check.severity === "warning" && !check.passed).length} 个
              </span>
            </>
          )}
        </div>
        {readiness.data && (
          <details className="setup-help readiness-details">
            <summary>查看检查项</summary>
            <div className="readiness-list">
              {readiness.data.checks.map((check) => (
                <div className="check-row" key={check.name}>
                  <StatusBadge
                    value={check.passed ? "已通过" : check.severity === "warning" ? "警告" : "阻断"}
                    tone={check.passed ? "ok" : check.severity === "warning" ? "warn" : "danger"}
                  />
                  <div>
                    <strong>{formatSettingKey(check.name)}</strong>
                    <span>{check.summary}</span>
                  </div>
                </div>
              ))}
            </div>
          </details>
        )}
      </section>

      <section className="detail-grid">
        <div className="panel">
          <h3>数据源</h3>
          {provider.data && (
            <>
              <div className="badge-row">
                <HealthBadge healthy={provider.data.healthy} />
                <StatusBadge value={provider.data.provider.toUpperCase()} />
                <StatusBadge value={provider.data.environment.toUpperCase()} />
              </div>
              <p>{formatReason(provider.data.message)}</p>
            </>
          )}
        </div>
        <div className="panel">
          <h3>交易模式</h3>
          {settings.data && (
            <div className="badge-row">
              <StatusBadge value={settings.data.trading_mode.toUpperCase()} tone={settings.data.trading_mode === "live" ? "danger" : "ok"} />
              <KillSwitchBadge enabled={settings.data.enable_live_trading} />
            </div>
          )}
        </div>
      </section>

      <div className="settings-mode-switch" role="tablist" aria-label="设置范围">
        <button
          type="button"
          className={settingsMode === "general" ? "active" : ""}
          onClick={() => setSettingsMode("general")}
          role="tab"
          aria-selected={settingsMode === "general"}
        >
          <strong>一般设置</strong>
          <span>日常使用只看这里</span>
        </button>
        <button
          type="button"
          className={settingsMode === "advanced" ? "active" : ""}
          onClick={() => setSettingsMode("advanced")}
          role="tab"
          aria-selected={settingsMode === "advanced"}
        >
          <strong>高级设置</strong>
          <span>低频参数和排障项</span>
        </button>
      </div>

      <form className="settings-form" onSubmit={submit}>
        {settingsMode === "general" ? (
          <>
            <section className="panel">
              <h3>基础配置</h3>
              <p className="panel-note">这里控制日常运行方式。新手和模拟使用一般只需要保持默认。</p>
              <div className="form-grid compact">
                <label>
                  <span>数据源</span>
                  <select value={form.broker_provider} onChange={(event) => update("broker_provider", event.target.value as FormState["broker_provider"])}>
                    <option value="mock">模拟源</option>
                    <option value="webull">Webull</option>
                  </select>
                </label>
                <label>
                  <span>数据类型</span>
                  <select value={form.webull_env} onChange={(event) => update("webull_env", event.target.value as FormState["webull_env"])}>
                    <option value="test">使用模拟测试数据</option>
                    <option value="production">使用真实数据</option>
                  </select>
                </label>
                <label>
                  <span>交易模式</span>
                  <select value={form.trading_mode} onChange={(event) => update("trading_mode", event.target.value as FormState["trading_mode"])}>
                    <option value="paper">模拟交易</option>
                    <option value="live">实盘交易</option>
                  </select>
                </label>
                <label className="checkbox-row settings-checkbox">
                  <input type="checkbox" checked={form.enable_live_trading} onChange={(event) => update("enable_live_trading", event.target.checked)} />
                  <span>开启实盘交易总开关</span>
                </label>
              </div>
            </section>

            <section className="panel">
              <h3>安全访问</h3>
              <p className="panel-note">日常本机模拟可以保持关闭；准备部署或连接真实账户前再开启。普通使用只需要填写一个访问口令。</p>
              <div className="form-grid compact">
                <label className="checkbox-row settings-checkbox">
                  <input type="checkbox" checked={form.api_auth_enabled} onChange={(event) => update("api_auth_enabled", event.target.checked)} />
                  <span>开启控制台访问保护</span>
                </label>
                <label>
                  <span>访问口令</span>
                  <small className="field-help">保存时会同时写入后端，并保存到当前浏览器用于后续访问。已配置过时，留空表示不修改。</small>
                  <input
                    type="password"
                    value={form.api_auth_token}
                    onChange={(event) => update("api_auth_token", event.target.value)}
                    placeholder={settings.data?.has_api_auth_token ? "已配置，留空不修改" : "请输入访问口令"}
                  />
                </label>
              </div>
            </section>

            <section className="panel">
              <h3>账户连接</h3>
              <p className="panel-note">没有真实券商 API 时可以先留空，系统仍可用模拟源跑完整流程。</p>
              <div className="form-grid compact">
                <label>
                  <span>账户 ID</span>
                  <input value={form.webull_account_id} onChange={(event) => update("webull_account_id", event.target.value)} placeholder={settings.data?.webull_account_id || "留空不修改"} />
                </label>
                <label>
                  <span>App Key</span>
                  <input value={form.webull_app_key} onChange={(event) => update("webull_app_key", event.target.value)} placeholder={settings.data?.has_webull_app_key ? "已配置，留空不修改" : "未配置"} />
                </label>
                <label>
                  <span>App Secret</span>
                  <input type="password" value={form.webull_app_secret} onChange={(event) => update("webull_app_secret", event.target.value)} placeholder={settings.data?.has_webull_app_secret ? "已配置，留空不修改" : "未配置"} />
                </label>
              </div>
              <details className="setup-help">
                <summary>信息获取方式</summary>
                <div className="setup-help-content">
                  <section>
                    <h4>快速入口</h4>
                    <p>
                      申请和生成 App Key / App Secret 可以从 Webull 官方 OpenAPI 文档进入：
                      <a href="https://developer.webull.com/apis/docs/authentication/IndividualApplicationAPI/" target="_blank" rel="noreferrer">
                        个人 OpenAPI 申请流程
                        <ExternalLink size={13} />
                      </a>
                      。
                    </p>
                    <p>
                      如果是机构或团队账户，查看：
                      <a href="https://developer.webull.com/apis/docs/authentication/apply/" target="_blank" rel="noreferrer">
                        机构 OpenAPI 申请流程
                        <ExternalLink size={13} />
                      </a>
                      。
                    </p>
                  </section>
                  <section>
                    <h4>需要准备的信息</h4>
                    <p>账户 ID 是 Webull OpenAPI 绑定账户的标识，不是邮箱或登录名；通常在开发者后台、应用绑定账户页面，或账户列表接口返回中获取。</p>
                    <p>App Key / App Secret 来自 Webull 开发者后台创建的 OpenAPI 应用。Secret 只会写入后端 `.env`，页面不会回显。</p>
                  </section>
                </div>
              </details>
            </section>

            <section className="panel">
              <h3>模型会议</h3>
              <p className="panel-note">可以保持全模拟；需要真实模型时，展开对应角色填写模型和 API。</p>
              <AgentModelConfigurator value={form.llm_agent_configs} onChange={updateAgentConfigs} collapsible />
            </section>
          </>
        ) : (
          <>
            <section className="panel">
              <h3>运行环境</h3>
              <div className="form-grid compact">
                <label>
                  <span>应用环境</span>
                  <small className="field-help">production 会强制要求 API 访问口令。普通本机使用保持 development。</small>
                  <input value={form.app_env} onChange={(event) => update("app_env", event.target.value)} />
                </label>
                <label>
                  <span>区域</span>
                  <select value={form.webull_region} onChange={(event) => update("webull_region", event.target.value)}>
                    <option value="jp">日本 / jp（api.webull.co.jp）</option>
                    <option value="us">美国 / us（api.webull.com）</option>
                  </select>
                </label>
              </div>
            </section>

            <section className="panel">
              <h3>高级访问设置</h3>
              <p className="panel-note">只有后端已经配置口令、当前浏览器需要重新连接时才需要改这里。</p>
              <div className="form-grid compact">
                <label>
                  <span>当前浏览器访问口令</span>
                  <input
                    type="password"
                    value={form.local_api_token}
                    onChange={(event) => update("local_api_token", event.target.value)}
                    placeholder="只保存在本机浏览器"
                  />
                </label>
              </div>
            </section>

            <section className="panel">
              <h3>接口地址</h3>
              <p className="panel-note">除非 Webull 官方变更地址，或你要接公司代理网关，否则不要改。</p>
              <div className="form-grid compact">
                <label>
                  <span>模拟测试交易接口</span>
                  <input value={form.webull_trading_endpoint_test} onChange={(event) => update("webull_trading_endpoint_test", event.target.value)} />
                </label>
                <label>
                  <span>模拟测试行情接口</span>
                  <input value={form.webull_market_data_endpoint_test} onChange={(event) => update("webull_market_data_endpoint_test", event.target.value)} />
                </label>
                <label>
                  <span>真实交易接口</span>
                  <input value={form.webull_trading_endpoint_production} onChange={(event) => update("webull_trading_endpoint_production", event.target.value)} />
                </label>
                <label>
                  <span>真实行情接口</span>
                  <input value={form.webull_market_data_endpoint_production} onChange={(event) => update("webull_market_data_endpoint_production", event.target.value)} />
                </label>
              </div>
            </section>

            <section className="panel">
              <h3>会议测试开关</h3>
              <div className="form-grid compact">
                <label>
                  <span>默认模拟动作</span>
                  <small className="field-help">只用于 mock Agent 测试。真实模型会议一般保持默认混合投票。</small>
                  <select value={form.mock_agent_action} onChange={(event) => update("mock_agent_action", event.target.value as FormState["mock_agent_action"])}>
                    <option value="">默认混合投票</option>
                    <option value="BUY">买入</option>
                    <option value="SELL">卖出</option>
                    <option value="HOLD">观望</option>
                  </select>
                </label>
              </div>
            </section>

            <section className="panel">
              <h3>风控参数</h3>
              <p className="panel-note">这些参数会在每次会议后由后端确定性检查，AI 不能绕过。没有明确策略前建议保持默认。</p>
              <div className="form-grid compact">
                <label>
                  <span>单标的最大仓位比例</span>
                  <small className="field-help">限制单个股票或 ETF 在账户权益中的最高占比。默认 0.05 表示最多 5%。</small>
                  <input value={form.max_position_pct} onChange={(event) => update("max_position_pct", event.target.value)} inputMode="decimal" />
                </label>
                <label>
                  <span>单笔最大风险比例</span>
                  <small className="field-help">限制单次交易按止损估算的最大亏损占账户权益比例。默认 0.01 表示 1%。</small>
                  <input value={form.max_single_trade_risk_pct} onChange={(event) => update("max_single_trade_risk_pct", event.target.value)} inputMode="decimal" />
                </label>
                <label>
                  <span>最大日亏损比例</span>
                  <small className="field-help">当天累计亏损达到该比例后阻断新交易。默认 0.02 表示 2%。</small>
                  <input value={form.max_daily_loss_pct} onChange={(event) => update("max_daily_loss_pct", event.target.value)} inputMode="decimal" />
                </label>
                <label>
                  <span>最低 Agent 置信度</span>
                  <small className="field-help">参与共识的 Agent 必须达到该置信度门槛。默认 0.65 表示 65%。</small>
                  <input value={form.min_agent_confidence} onChange={(event) => update("min_agent_confidence", event.target.value)} inputMode="decimal" />
                </label>
                <label>
                  <span>交易冷却秒数</span>
                  <small className="field-help">同一个标的两次交易之间的最短等待时间。默认 300 秒。</small>
                  <input value={form.trade_cooldown_seconds} onChange={(event) => update("trade_cooldown_seconds", event.target.value)} inputMode="numeric" />
                </label>
                <label>
                  <span>最大限价偏离比例</span>
                  <small className="field-help">限价相对行情快照的最大不利偏离。默认 0.05 表示 5%。</small>
                  <input value={form.max_order_price_deviation_pct} onChange={(event) => update("max_order_price_deviation_pct", event.target.value)} inputMode="decimal" />
                </label>
                <label>
                  <span>实盘预览有效秒数</span>
                  <small className="field-help">实盘预览超过这个时间后必须重新生成，避免确认过期价格。默认 300 秒。</small>
                  <input value={form.live_preview_ttl_seconds} onChange={(event) => update("live_preview_ttl_seconds", event.target.value)} inputMode="numeric" />
                </label>
                <label>
                  <span>每日实盘订单上限</span>
                  <small className="field-help">当天真实下单次数达到上限后阻断新的实盘预览。默认 5 笔。</small>
                  <input value={form.max_daily_live_order_count} onChange={(event) => update("max_daily_live_order_count", event.target.value)} inputMode="numeric" />
                </label>
                <label>
                  <span>每日实盘金额上限</span>
                  <small className="field-help">当天真实下单累计名义金额上限。默认 5000 美元。</small>
                  <input value={form.max_daily_live_notional} onChange={(event) => update("max_daily_live_notional", event.target.value)} inputMode="decimal" />
                </label>
                <label className="checkbox-row settings-checkbox">
                  <input type="checkbox" checked={form.regular_trading_hours_only} onChange={(event) => update("regular_trading_hours_only", event.target.checked)} />
                  <span>只允许美股常规交易时段实盘下单</span>
                </label>
              </div>
            </section>
          </>
        )}

        <div className="form-actions sticky-actions">
          <button className="primary-action" type="submit" disabled={mutation.isPending}>
            <Save size={17} />
            {mutation.isPending ? "保存中" : "保存配置"}
          </button>
          {saved && <span className="success-text">配置已保存并刷新运行时设置。</span>}
          {mutation.error && <span className="danger-text">{mutation.error.message}</span>}
        </div>
      </form>

      {settingsMode === "advanced" && (
        <section className="panel">
          <h3>当前脱敏配置</h3>
          <div className="settings-grid">
            {settings.data &&
              Object.entries(settings.data).map(([key, value]) => (
                <div key={key}>
                  <span>{formatSettingKey(key)}</span>
                  <strong>{formatConfigValue(value)}</strong>
                </div>
              ))}
          </div>
        </section>
      )}
    </div>
  );
}

function formatConfigValue(value: unknown): string {
  if (typeof value === "boolean") return value ? "是" : "否";
  if (typeof value === "string") return displayValue(value);
  if (Array.isArray(value)) {
    if (value.every((item) => item && typeof item === "object" && "role" in item)) {
      const realCount = value.filter((item) => item && typeof item === "object" && "provider" in item && item.provider !== "mock").length;
      return realCount === 0 ? "全部模拟" : `${realCount} 个真实模型 / ${value.length} 个角色`;
    }
    return `${value.length} 项`;
  }
  if (value === null || value === undefined) return "无";
  return String(value);
}
