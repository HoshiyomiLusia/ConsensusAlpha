import { FormEvent, useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, ChevronLeft, ChevronRight, ExternalLink, Save } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { api, SettingsUpdatePayload } from "../api/client";
import AgentModelConfigurator, {
  AgentLLMForm,
  countRealAgentConfigs,
  defaultAgentConfigs,
  hydrateAgentConfigs,
  primaryAgentConfig,
  toAgentConfigPayload,
  validateAgentConfigs
} from "../components/AgentModelConfigurator";
import { displayValue } from "../lib/format";

type SetupMode = "mock" | "webull_test" | "protected_live";

type WizardForm = {
  setup_mode: SetupMode;
  broker_provider: "mock" | "webull";
  trading_mode: "paper" | "live";
  enable_live_trading: boolean;
  webull_env: "test" | "production";
  webull_region: string;
  webull_account_id: string;
  webull_app_key: string;
  webull_app_secret: string;
  llm_agent_configs: AgentLLMForm[];
  mock_agent_action: "BUY" | "SELL" | "HOLD" | "";
  max_position_pct: string;
  max_single_trade_risk_pct: string;
  max_daily_loss_pct: string;
  min_agent_confidence: string;
  trade_cooldown_seconds: string;
};

const initialWizardForm: WizardForm = {
  setup_mode: "mock",
  broker_provider: "mock",
  trading_mode: "paper",
  enable_live_trading: false,
  webull_env: "test",
  webull_region: "us",
  webull_account_id: "",
  webull_app_key: "",
  webull_app_secret: "",
  llm_agent_configs: defaultAgentConfigs(),
  mock_agent_action: "",
  max_position_pct: "0.05",
  max_single_trade_risk_pct: "0.01",
  max_daily_loss_pct: "0.02",
  min_agent_confidence: "0.65",
  trade_cooldown_seconds: "300"
};

const steps = ["模式", "Webull", "AI", "风控", "确认"];

export default function SetupWizardPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const settings = useQuery({ queryKey: ["settings"], queryFn: api.settings });
  const [form, setForm] = useState<WizardForm>(initialWizardForm);
  const [step, setStep] = useState(0);
  const [maxUnlockedStep, setMaxUnlockedStep] = useState(0);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!settings.data) return;
    setForm((current) => ({
      ...current,
      broker_provider: settings.data.broker_provider,
      trading_mode: settings.data.trading_mode,
      enable_live_trading: settings.data.enable_live_trading,
      webull_env: settings.data.webull_env,
      webull_region: settings.data.webull_region,
      llm_agent_configs: hydrateAgentConfigs(settings.data),
      mock_agent_action: settings.data.mock_agent_action,
      max_position_pct: String(settings.data.max_position_pct),
      max_single_trade_risk_pct: String(settings.data.max_single_trade_risk_pct),
      max_daily_loss_pct: String(settings.data.max_daily_loss_pct),
      min_agent_confidence: String(settings.data.min_agent_confidence),
      trade_cooldown_seconds: String(settings.data.trade_cooldown_seconds),
      setup_mode: inferMode(settings.data.broker_provider, settings.data.webull_env, settings.data.trading_mode, settings.data.enable_live_trading)
    }));
  }, [settings.data]);

  const mutation = useMutation({
    mutationFn: (payload: SettingsUpdatePayload) => api.updateSettings(payload),
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["settings"] }),
        queryClient.invalidateQueries({ queryKey: ["provider-status"] }),
        queryClient.invalidateQueries({ queryKey: ["positions"] })
      ]);
      navigate("/");
    }
  });

  const summary = useMemo(
    () => [
      ["数据源", displayValue(form.broker_provider)],
      ["数据类型", displayValue(form.webull_env)],
      ["交易模式", displayValue(form.trading_mode)],
      ["实盘开关", form.enable_live_trading ? "开启" : "关闭"],
      ["Agent 模型", summarizeAgentConfigs(form.llm_agent_configs)],
      ["最低置信度", form.min_agent_confidence],
      ["交易冷却", `${form.trade_cooldown_seconds} 秒`]
    ],
    [form]
  );

  function update<K extends keyof WizardForm>(key: K, value: WizardForm[K]) {
    setError("");
    setForm((current) => ({ ...current, [key]: value }));
  }

  function updateAgentConfigs(next: AgentLLMForm[]) {
    setError("");
    setForm((current) => ({ ...current, llm_agent_configs: next }));
  }

  function applyMode(mode: SetupMode) {
    setError("");
    setForm((current) => ({
      ...current,
      setup_mode: mode,
      broker_provider: mode === "mock" ? "mock" : "webull",
      webull_env: mode === "protected_live" ? "production" : "test",
      trading_mode: mode === "protected_live" ? "live" : "paper",
      enable_live_trading: mode === "protected_live"
    }));
  }

  function next() {
    const message = validateStep(step, form, settings.data);
    if (message) {
      setError(message);
      return;
    }
    setError("");
    const nextStep = Math.min(step + 1, steps.length - 1);
    setMaxUnlockedStep((current) => Math.max(current, nextStep));
    setStep(nextStep);
  }

  function previous() {
    setError("");
    setStep((current) => Math.max(current - 1, 0));
  }

  function submit(event: FormEvent) {
    event.preventDefault();
    for (let index = 0; index < steps.length - 1; index += 1) {
      const message = validateStep(index, form, settings.data);
      if (message) {
        setMaxUnlockedStep((current) => Math.max(current, index));
        setStep(index);
        setError(message);
        return;
      }
    }
    mutation.mutate(toPayload(form));
  }

  return (
    <div className="setup-only">
      <section className="setup-layout">
        <form className="panel setup-panel" onSubmit={submit}>
          <div className="setup-stage" key={step}>
            <div className="setup-progress-row">
              <div className="setup-progress">
                第 {step + 1} 项 / 共 {steps.length} 项
              </div>
              <div className="setup-progress-track" aria-hidden="true">
                <span style={{ width: `${((step + 1) / steps.length) * 100}%` }} />
              </div>
            </div>

            {step === 0 && (
              <div className="setup-section">
                <h3>选择初始化模式</h3>
                <p>建议先用模拟模式跑通流程，再切到 Webull 模拟测试数据。</p>
                <div className="setup-choice-grid">
                  <ModeCard
                    active={form.setup_mode === "mock"}
                    title="快速模拟"
                    subtitle="无密钥、无真实下单"
                    details="使用 mock 数据源、mock LLM、模拟交易，适合首次体验和功能测试。"
                    onClick={() => applyMode("mock")}
                  />
                  <ModeCard
                    active={form.setup_mode === "webull_test"}
                    title="Webull 模拟测试数据"
                    subtitle="用于验证 API 连接"
                    details="连接 Webull 的模拟测试数据通道，验证账户、行情和预览流程；交易仍默认模拟。"
                    onClick={() => applyMode("webull_test")}
                  />
                  <ModeCard
                    active={form.setup_mode === "protected_live"}
                    title="受保护真实数据"
                    subtitle="预览后人工确认"
                    details="读取真实账户数据，并启用受保护的实盘流程；仍必须经过订单预览确认。"
                    onClick={() => applyMode("protected_live")}
                  />
                </div>
              </div>
            )}

            {step === 1 && (
              <div className="setup-section">
                <h3>Webull 必要信息</h3>
                {form.broker_provider === "mock" ? (
                  <div className="empty-state">当前选择模拟源，不需要填写 Webull 账户或密钥。</div>
                ) : (
                <>
                  <div className="form-grid compact">
                    <label>
                      <span>数据类型</span>
                      <select value={form.webull_env} onChange={(event) => update("webull_env", event.target.value as WizardForm["webull_env"])}>
                        <option value="test">使用模拟测试数据</option>
                        <option value="production">使用真实数据</option>
                      </select>
                    </label>
                    <label>
                      <span>区域</span>
                      <input value={form.webull_region} onChange={(event) => update("webull_region", event.target.value)} />
                    </label>
                    <label>
                      <span>账户 ID</span>
                      <input value={form.webull_account_id} onChange={(event) => update("webull_account_id", event.target.value)} placeholder={settings.data?.webull_account_id || "必填"} />
                    </label>
                    <label>
                      <span>App Key</span>
                      <input value={form.webull_app_key} onChange={(event) => update("webull_app_key", event.target.value)} placeholder={settings.data?.has_webull_app_key ? "已配置，留空不修改" : "必填"} />
                    </label>
                    <label>
                      <span>App Secret</span>
                      <input type="password" value={form.webull_app_secret} onChange={(event) => update("webull_app_secret", event.target.value)} placeholder={settings.data?.has_webull_app_secret ? "已配置，留空不修改" : "必填"} />
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
                        <p><strong>账户 ID</strong> 是 Webull OpenAPI 绑定账户的标识，不是邮箱或登录名；通常在开发者后台、应用绑定账户页面，或账户列表接口返回中获取。</p>
                        <p><strong>App Key / App Secret</strong> 来自 Webull 开发者后台创建的 OpenAPI 应用。Secret 只在后端写入 `.env`，前端不会回显。</p>
                        <p><strong>区域</strong> 第一版默认使用 `us`，对应美股/ETF 场景。</p>
                      </section>
                      <section>
                        <h4>两个数据选项</h4>
                        <p>使用模拟测试数据：默认选项，适合第一次配置、检查凭证、跑会议和验证订单预览流程。</p>
                        <p>使用真实数据：读取真实账户、持仓和行情；实盘下单仍需要开启实盘模式、通过风控，并在订单页人工确认。</p>
                      </section>
                      <section>
                        <h4>建议顺序</h4>
                        <ol>
                          <li>先用快速模拟跑通会议、风控和模拟订单。</li>
                          <li>再切到 Webull 模拟测试数据验证账户和行情。</li>
                          <li>最后才考虑真实数据，并保持实盘确认流程开启。</li>
                        </ol>
                      </section>
                    </div>
                  </details>
                </>
              )}
            </div>
          )}

            {step === 2 && (
              <div className="setup-section">
                <h3>AI 与 Agent</h3>
                <p>默认全部使用 mock。切换真实模型时，每个 Agent 可以分别选择公司、模型、接口地址和 API Key。</p>
                <AgentModelConfigurator value={form.llm_agent_configs} onChange={updateAgentConfigs} />
                <div className="form-grid compact">
                  <label>
                    <span>模拟 Agent 默认动作</span>
                    <select value={form.mock_agent_action} onChange={(event) => update("mock_agent_action", event.target.value as WizardForm["mock_agent_action"])}>
                      <option value="">默认混合投票</option>
                      <option value="BUY">买入</option>
                      <option value="SELL">卖出</option>
                      <option value="HOLD">观望</option>
                    </select>
                  </label>
                </div>
              </div>
            )}

            {step === 3 && (
              <div className="setup-section">
                <h3>风控参数</h3>
                <p>这些参数是确定性风控闸门，不由 AI 决定。</p>
                <div className="form-grid compact">
                  <label>
                    <span>单标的最大仓位比例</span>
                    <small className="field-help">限制单个股票或 ETF 在账户权益中的最高占比。默认 0.05 表示最多 5%，用于避免单一标的过度集中。</small>
                    <input value={form.max_position_pct} onChange={(event) => update("max_position_pct", event.target.value)} inputMode="decimal" />
                  </label>
                  <label>
                    <span>单笔最大风险比例</span>
                    <small className="field-help">限制单次交易按止损估算的最大亏损占账户权益比例。默认 0.01 表示单笔最多承受 1% 风险。</small>
                    <input value={form.max_single_trade_risk_pct} onChange={(event) => update("max_single_trade_risk_pct", event.target.value)} inputMode="decimal" />
                  </label>
                  <label>
                    <span>最大日亏损比例</span>
                    <small className="field-help">限制当天累计亏损达到指定比例后继续交易。默认 0.02 表示日内亏损到 2% 后阻断新交易。</small>
                    <input value={form.max_daily_loss_pct} onChange={(event) => update("max_daily_loss_pct", event.target.value)} inputMode="decimal" />
                  </label>
                  <label>
                    <span>最低 Agent 置信度</span>
                    <small className="field-help">要求参与共识的 Agent 置信度达到门槛。默认 0.65 表示低于 65% 的意见不会通过交易共识。</small>
                    <input value={form.min_agent_confidence} onChange={(event) => update("min_agent_confidence", event.target.value)} inputMode="decimal" />
                  </label>
                  <label>
                    <span>同标的交易冷却秒数</span>
                    <small className="field-help">同一个标的两次交易之间必须等待的时间。默认 300 秒，用于减少连续重复下单。</small>
                    <input value={form.trade_cooldown_seconds} onChange={(event) => update("trade_cooldown_seconds", event.target.value)} inputMode="numeric" />
                  </label>
                </div>
              </div>
            )}

            {step === 4 && (
              <div className="setup-section">
                <h3>确认配置</h3>
                <p>检查无误后保存。密钥会写入 `.env`，但不会在页面回显。</p>
                <div className="review-grid">
                  {summary.map(([label, value]) => (
                    <div key={label}>
                      <span>{label}</span>
                      <strong>{value}</strong>
                    </div>
                  ))}
                </div>
                {form.setup_mode === "protected_live" && (
                  <div className="warning-box">你选择了受保护实盘。系统仍会先生成订单预览，必须人工确认后才会调用真实下单接口。</div>
                )}
              </div>
            )}
          </div>

          {error && <div className="error-box">{error}</div>}
          {mutation.error && <div className="error-box">{mutation.error.message}</div>}

          <div className="wizard-actions">
            <button type="button" className="secondary-action" onClick={previous} disabled={step === 0}>
              <ChevronLeft size={17} />
              上一项
            </button>
            {step < steps.length - 1 ? (
              <button type="button" className="primary-action step-forward" onClick={next}>
                完成并显示下一项
                <ChevronRight size={17} />
              </button>
            ) : (
              <button type="submit" className="primary-action" disabled={mutation.isPending}>
                <Save size={17} />
                {mutation.isPending ? "保存中" : "保存并完成"}
              </button>
            )}
          </div>
        </form>
      </section>
    </div>
  );
}

function ModeCard({
  active,
  title,
  subtitle,
  details,
  onClick
}: {
  active: boolean;
  title: string;
  subtitle: string;
  details: string;
  onClick: () => void;
}) {
  return (
    <button type="button" className={`setup-choice ${active ? "active" : ""}`} onClick={onClick}>
      <div>
        <strong>{title}</strong>
        <span>{subtitle}</span>
      </div>
      <p>{details}</p>
      {active && <CheckCircle2 size={18} />}
    </button>
  );
}

function inferMode(
  provider: "mock" | "webull",
  webullEnv: "test" | "production",
  tradingMode: "paper" | "live",
  liveEnabled: boolean
): SetupMode {
  if (provider === "mock") return "mock";
  if (webullEnv === "production" || tradingMode === "live" || liveEnabled) return "protected_live";
  return "webull_test";
}

function validateStep(step: number, form: WizardForm, settings?: Awaited<ReturnType<typeof api.settings>>) {
  if (step === 1 && form.broker_provider === "webull") {
    if (!form.webull_account_id.trim() && !settings?.webull_account_id) return "Webull 模式需要账户 ID。";
    if (!form.webull_app_key.trim() && !settings?.has_webull_app_key) return "Webull 模式需要 App Key。";
    if (!form.webull_app_secret.trim() && !settings?.has_webull_app_secret) return "Webull 模式需要 App Secret。";
  }
  if (step === 2) {
    const message = validateAgentConfigs(form.llm_agent_configs);
    if (message) return message;
  }
  if (step === 3) {
    const numericFields = [
      ["单标的最大仓位比例", form.max_position_pct],
      ["单笔最大风险比例", form.max_single_trade_risk_pct],
      ["最大日亏损比例", form.max_daily_loss_pct],
      ["最低 Agent 置信度", form.min_agent_confidence],
      ["交易冷却秒数", form.trade_cooldown_seconds]
    ];
    for (const [label, value] of numericFields) {
      if (!Number.isFinite(Number(value)) || Number(value) < 0) return `${label} 必须是非负数字。`;
    }
    if (Number(form.min_agent_confidence) > 1) return "最低 Agent 置信度不能大于 1。";
  }
  return "";
}

function toPayload(form: WizardForm): SettingsUpdatePayload {
  const primary = primaryAgentConfig(form.llm_agent_configs);
  const payload: SettingsUpdatePayload = {
    broker_provider: form.broker_provider,
    trading_mode: form.trading_mode,
    enable_live_trading: form.enable_live_trading,
    webull_env: form.webull_env,
    webull_region: form.webull_region,
    llm_provider: primary.provider,
    llm_model: primary.model,
    llm_base_url: primary.base_url,
    llm_agent_configs: toAgentConfigPayload(form.llm_agent_configs),
    mock_agent_action: form.mock_agent_action,
    max_position_pct: Number(form.max_position_pct),
    max_single_trade_risk_pct: Number(form.max_single_trade_risk_pct),
    max_daily_loss_pct: Number(form.max_daily_loss_pct),
    min_agent_confidence: Number(form.min_agent_confidence),
    trade_cooldown_seconds: Number(form.trade_cooldown_seconds)
  };
  if (form.webull_account_id.trim()) payload.webull_account_id = form.webull_account_id.trim();
  if (form.webull_app_key.trim()) payload.webull_app_key = form.webull_app_key.trim();
  if (form.webull_app_secret.trim()) payload.webull_app_secret = form.webull_app_secret.trim();
  if (primary.api_key.trim()) payload.llm_api_key = primary.api_key.trim();
  return payload;
}

function summarizeAgentConfigs(configs: AgentLLMForm[]): string {
  const realCount = countRealAgentConfigs(configs);
  if (realCount === 0) return "全部模拟";
  return `${realCount} 个真实模型 / ${configs.length} 个角色`;
}
