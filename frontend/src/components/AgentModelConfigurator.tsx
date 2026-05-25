import { ChevronDown, Copy, RotateCcw } from "lucide-react";
import { AgentLLMConfig, AgentRole, Settings } from "../api/client";

export type AgentLLMForm = AgentLLMConfig & {
  api_key: string;
};

type ProviderPreset = {
  value: string;
  label: string;
  baseUrl: string;
  model: string;
};

const providerPresets: ProviderPreset[] = [
  { value: "mock", label: "Mock 模拟", baseUrl: "", model: "" },
  { value: "openai", label: "OpenAI", baseUrl: "https://api.openai.com/v1", model: "gpt-4.1" },
  { value: "deepseek", label: "DeepSeek", baseUrl: "https://api.deepseek.com/v1", model: "deepseek-chat" },
  { value: "xai", label: "xAI", baseUrl: "https://api.x.ai/v1", model: "grok-3" },
  {
    value: "gemini",
    label: "Google Gemini 兼容接口",
    baseUrl: "https://generativelanguage.googleapis.com/v1beta/openai",
    model: "gemini-2.0-flash"
  },
  { value: "anthropic", label: "Anthropic 兼容网关", baseUrl: "", model: "claude-3-5-sonnet-latest" },
  { value: "custom", label: "自定义兼容接口", baseUrl: "", model: "" }
];

const agentRoles: Array<{ role: AgentRole; label: string; description: string }> = [
  { role: "market_analyst", label: "市场分析", description: "趋势、价格和成交量判断" },
  { role: "risk_manager", label: "风控经理", description: "仓位、止损和损失限制" },
  { role: "contrarian_critic", label: "反方审查", description: "提出反例和阻断理由" },
  { role: "execution_specialist", label: "执行专家", description: "订单类型、滑点和执行可行性" },
  { role: "chairperson", label: "会议主席", description: "汇总意见，不直接推动交易" }
];

export function defaultAgentConfigs(): AgentLLMForm[] {
  return agentRoles.map(({ role }) => ({
    role,
    provider: "mock",
    model: "",
    base_url: "",
    has_api_key: false,
    api_key: "",
    enabled: true
  }));
}

export function hydrateAgentConfigs(settings: Settings): AgentLLMForm[] {
  if (settings.llm_agent_configs?.length) {
    const byRole = new Map(settings.llm_agent_configs.map((config) => [config.role, config]));
    return agentRoles.map(({ role }) => {
      const config = byRole.get(role);
      return {
        role,
        provider: config?.provider ?? "mock",
        model: config?.model ?? "",
        base_url: config?.provider === "mock" ? "" : config?.base_url ?? "",
        has_api_key: config?.has_api_key ?? false,
        api_key: "",
        enabled: config?.enabled ?? true
      };
    });
  }

  return agentRoles.map(({ role }) => ({
    role,
    provider: settings.llm_provider || "mock",
    model: settings.llm_model || "",
    base_url: settings.llm_provider === "mock" ? "" : settings.llm_base_url || "",
    has_api_key: settings.has_llm_api_key,
    api_key: "",
    enabled: true
  }));
}

export function toAgentConfigPayload(configs: AgentLLMForm[]) {
  return configs.map(({ role, provider, model, base_url, api_key, enabled }) => ({
    role,
    provider,
    model,
    base_url,
    api_key: api_key.trim(),
    enabled
  }));
}

export function countRealAgentConfigs(configs: AgentLLMForm[]): number {
  return configs.filter((config) => config.enabled && config.provider !== "mock").length;
}

export function primaryAgentConfig(configs: AgentLLMForm[]): AgentLLMForm {
  return configs.find((config) => config.provider !== "mock") ?? configs[0] ?? defaultAgentConfigs()[0];
}

export function validateAgentConfigs(configs: AgentLLMForm[]): string {
  for (const config of configs) {
    if (!config.enabled || config.provider === "mock") continue;
    const label = roleLabel(config.role);
    if (!config.model.trim()) return `${label} 需要填写模型名称。`;
    if (!config.base_url.trim()) return `${label} 需要填写接口地址。`;
    if (!config.api_key.trim() && !config.has_api_key) return `${label} 需要填写 API Key。`;
  }
  return "";
}

export function roleLabel(role: AgentRole): string {
  return agentRoles.find((item) => item.role === role)?.label ?? role;
}

export default function AgentModelConfigurator({
  value,
  onChange,
  collapsible = false
}: {
  value: AgentLLMForm[];
  onChange: (next: AgentLLMForm[]) => void;
  collapsible?: boolean;
}) {
  function updateRole(role: AgentRole, patch: Partial<AgentLLMForm>) {
    onChange(value.map((config) => (config.role === role ? { ...config, ...patch } : config)));
  }

  function updateProvider(role: AgentRole, provider: string) {
    const preset = providerPresets.find((item) => item.value === provider);
    updateRole(role, {
      provider,
      model: preset?.model ?? "",
      base_url: preset?.baseUrl ?? "",
      api_key: provider === "mock" ? "" : value.find((config) => config.role === role)?.api_key ?? ""
    });
  }

  function applyFirstRealToAll() {
    const template = value.find((config) => config.provider !== "mock") ?? value[0];
    if (!template) return;
    onChange(
      value.map((config) => ({
        ...config,
        provider: template.provider,
        model: template.model,
        base_url: template.base_url,
        api_key: template.api_key,
        has_api_key: config.role === template.role ? template.has_api_key : config.has_api_key
      }))
    );
  }

  return (
    <div className="agent-configurator">
      <div className="agent-config-toolbar">
        <div>
          <h4>会议 Agent 模型矩阵</h4>
          <p>每个角色可以使用不同公司、不同模型和不同 API Key。</p>
        </div>
        <div className="agent-config-actions">
          <button type="button" className="secondary-action" onClick={() => onChange(defaultAgentConfigs())}>
            <RotateCcw size={16} />
            全部模拟
          </button>
          <button type="button" className="secondary-action" onClick={applyFirstRealToAll}>
            <Copy size={16} />
            套用第一项
          </button>
        </div>
      </div>

      <div className="agent-config-list">
        {value.map((config) => {
          const role = agentRoles.find((item) => item.role === config.role);
          const isMock = config.provider === "mock";
          const providerLabel = providerPresets.find((preset) => preset.value === config.provider)?.label ?? config.provider;
          const keyLabel = isMock ? "无需 Key" : config.api_key ? "Key 待保存" : config.has_api_key ? "Key 已配置" : "缺少 Key";
          const statusLabel = config.enabled ? "已启用" : "已停用";

          if (collapsible) {
            return (
              <details className="agent-config-card agent-config-details" key={config.role}>
                <summary className="agent-config-summary">
                  <div className="agent-config-heading">
                    <div>
                      <strong>{role?.label ?? config.role}</strong>
                      <span>{role?.description}</span>
                    </div>
                  </div>
                  <div className="agent-summary-meta">
                    <span className="agent-pill">{providerLabel}</span>
                    <span className="agent-pill">{config.model || "未设置模型"}</span>
                    <span className={`agent-pill ${!isMock && !config.api_key && !config.has_api_key ? "agent-pill-danger" : ""}`}>{keyLabel}</span>
                    <span className="agent-pill">{statusLabel}</span>
                    <ChevronDown className="agent-config-chevron" size={17} />
                  </div>
                </summary>

                <div className="agent-config-details-body">
                  <label className="agent-enabled">
                    <input
                      type="checkbox"
                      checked={config.enabled}
                      onChange={(event) => updateRole(config.role, { enabled: event.target.checked })}
                    />
                    启用此 Agent
                  </label>
                  {renderAgentForm(config, isMock, updateProvider, updateRole)}
                </div>
              </details>
            );
          }

          return (
            <article className="agent-config-card" key={config.role}>
              <div className="agent-config-heading">
                <div>
                  <strong>{role?.label ?? config.role}</strong>
                  <span>{role?.description}</span>
                </div>
                <label className="agent-enabled">
                  <input
                    type="checkbox"
                    checked={config.enabled}
                    onChange={(event) => updateRole(config.role, { enabled: event.target.checked })}
                  />
                  启用
                </label>
              </div>

              {renderAgentForm(config, isMock, updateProvider, updateRole)}
            </article>
          );
        })}
      </div>

      <details className="setup-help">
        <summary>多模型会议说明</summary>
        <div className="setup-help-content">
          <section>
            <h4>推荐配置方式</h4>
            <p>可以让市场分析、风控、反方审查、执行专家和会议主席分别使用不同公司的模型，从而降低单一模型偏差。</p>
            <p>当前后端按 OpenAI-compatible `/chat/completions` 协议调用；不兼容该协议的厂商可以通过兼容网关或代理地址接入。</p>
          </section>
          <section>
            <h4>安全处理</h4>
            <p>每个角色的 API Key 都只写入后端 `.env`，页面只显示是否已配置。输入框留空表示不修改已有 Key。</p>
          </section>
        </div>
      </details>
    </div>
  );
}

function renderAgentForm(
  config: AgentLLMForm,
  isMock: boolean,
  updateProvider: (role: AgentRole, provider: string) => void,
  updateRole: (role: AgentRole, patch: Partial<AgentLLMForm>) => void
) {
  return (
    <div className="agent-config-form">
      <label>
        <span>模型公司</span>
        <select value={config.provider} onChange={(event) => updateProvider(config.role, event.target.value)}>
          {providerPresets.map((preset) => (
            <option key={preset.value} value={preset.value}>
              {preset.label}
            </option>
          ))}
        </select>
      </label>
      <label>
        <span>模型名称</span>
        <input
          value={config.model}
          disabled={isMock || !config.enabled}
          onChange={(event) => updateRole(config.role, { model: event.target.value })}
          placeholder={isMock ? "mock 可留空" : "例如 gpt-4.1 / deepseek-chat"}
        />
      </label>
      <label>
        <span>接口地址</span>
        <input
          value={config.base_url}
          disabled={isMock || !config.enabled}
          onChange={(event) => updateRole(config.role, { base_url: event.target.value })}
          placeholder={isMock ? "mock 可留空" : "OpenAI-compatible base URL"}
        />
      </label>
      <label>
        <span>API Key</span>
        <input
          type="password"
          value={config.api_key}
          disabled={isMock || !config.enabled}
          onChange={(event) => updateRole(config.role, { api_key: event.target.value })}
          placeholder={config.has_api_key ? "已配置，留空不修改" : isMock ? "mock 可留空" : "必填"}
        />
      </label>
    </div>
  );
}
