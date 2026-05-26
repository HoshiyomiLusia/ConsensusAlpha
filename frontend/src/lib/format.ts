export function displayValue(value: string | null | undefined): string {
  if (!value) return "无";
  const key = value.toUpperCase();
  const map: Record<string, string> = {
    BUY: "买入",
    SELL: "卖出",
    HOLD: "观望",
    MARKET: "市价",
    LIMIT: "限价",
    PAPER: "模拟",
    LIVE: "实盘",
    MOCK: "模拟源",
    WEBULL: "Webull",
    TEST: "模拟测试数据",
    PRODUCTION: "真实数据",
    HEALTHY: "正常",
    APPROVED: "已通过",
    BLOCKED: "受阻",
    FILLED: "已成交",
    ACCEPTED: "已接受",
    PENDING: "待处理",
    PENDING_CONFIRMATION: "待确认",
    CONFIRMED: "已确认",
    REJECTED: "已拒绝",
    CANCELLED: "已取消",
    FAILED: "失败",
    EXPIRED: "已过期",
    EQUITY: "美股",
    ETF: "ETF",
    LONG: "多头",
    SHORT: "空头",
    LLM: "提案模型",
    RULES: "规则扫描",
    MARKET_ANALYST: "市场分析",
    RISK_MANAGER: "风控经理",
    CONTRARIAN_CRITIC: "反方审查",
    EXECUTION_SPECIALIST: "执行专家",
    CHAIRPERSON: "会议主席"
  };
  return map[key] ?? value;
}

export function formatAuditAction(action: string): string {
  const map: Record<string, string> = {
    "settings.update": "设置更新",
    "decision.run": "一键决策",
    "conference.run": "会议运行",
    "proposal.run": "提案扫描",
    "live_preview.reject": "拒绝实盘预览",
    "order_preview.reject": "拒绝订单预览",
    "paper_order.confirm": "确认模拟订单",
    "live_order.confirm": "确认实盘订单",
    "live_order.confirm_failed": "实盘确认失败",
    "live_preview.expire": "实盘预览过期",
    "order_preview.expire": "订单预览过期"
  };
  return map[action] ?? action;
}

export function formatRole(role: string): string {
  const map: Record<string, string> = {
    market_analyst: "市场分析员",
    risk_manager: "风控经理",
    contrarian_critic: "反方审查",
    execution_specialist: "执行专家",
    chairperson: "会议主席"
  };
  return map[role] ?? role;
}

export function formatSettingKey(key: string): string {
  const map: Record<string, string> = {
    app_env: "应用环境",
    api_auth_enabled: "API 访问保护",
    has_api_auth_token: "已配置 API Token",
    broker_provider: "券商数据源",
    trading_mode: "交易模式",
    enable_live_trading: "实盘开关",
    webull_env: "数据类型",
    webull_region: "Webull 区域",
    webull_account_id: "Webull 账户",
    webull_trading_endpoint: "交易接口地址",
    webull_market_data_endpoint: "行情接口地址",
    webull_trading_endpoint_test: "模拟测试交易接口地址",
    webull_market_data_endpoint_test: "模拟测试行情接口地址",
    webull_trading_endpoint_production: "真实交易接口地址",
    webull_market_data_endpoint_production: "真实行情接口地址",
    has_webull_app_key: "已配置 App Key",
    has_webull_app_secret: "已配置 App Secret",
    llm_provider: "LLM 提供方",
    llm_model: "LLM 模型",
    llm_base_url: "LLM 接口地址",
    has_llm_api_key: "已配置 LLM Key",
    llm_agent_configs: "Agent 模型配置",
    mock_agent_action: "默认模拟动作",
    max_position_pct: "单标的最大仓位比例",
    max_single_trade_risk_pct: "单笔最大风险比例",
    max_daily_loss_pct: "最大日亏损比例",
    min_agent_confidence: "最低 Agent 置信度",
    trade_cooldown_seconds: "交易冷却秒数",
    max_order_price_deviation_pct: "最大限价偏离比例",
    live_preview_ttl_seconds: "实盘预览有效秒数",
    max_daily_live_order_count: "每日实盘订单上限",
    max_daily_live_notional: "每日实盘金额上限",
    regular_trading_hours_only: "常规交易时段限制",
    app_env_production: "生产环境",
    api_auth_configured: "访问保护",
    database_is_postgres: "生产数据库",
    broker_is_webull: "Webull 数据源",
    webull_production_env: "Webull 真实环境",
    webull_credentials: "Webull 凭据",
    live_trading_switches: "实盘开关",
    real_llm_quorum: "真实模型数量",
    risk_limits_sane: "保守风控参数",
    daily_live_limits: "每日实盘限制",
    regular_hours_only: "常规交易时段",
    holiday_calendar_uat: "交易日历 UAT",
    provider_connectivity: "券商连接"
  };
  return map[key] ?? key;
}

export function formatRiskCheckName(name: string): string {
  const map: Record<string, string> = {
    final_action: "最终动作",
    live_trading_enabled: "实盘交易开关",
    positive_price_quantity_notional: "价格/数量/金额为正",
    account_equity_available: "账户权益可用",
    position_limit: "仓位限制",
    single_trade_risk: "单笔交易风险",
    daily_loss_limit: "日亏损限制",
    cooldown: "交易冷却",
    buying_power_available: "可用资金",
    sell_position_available: "卖出持仓",
    limit_price_deviation: "限价偏离",
    duplicate_pending_live_preview: "重复订单预览",
    production_live_configuration: "生产实盘配置",
    regular_market_hours: "常规交易时段",
    daily_live_order_count: "每日实盘订单数",
    daily_live_notional: "每日实盘金额"
  };
  return map[name] ?? name;
}

export function formatReason(reason: string): string {
  const map: Record<string, string> = {
    "final action is HOLD": "最终动作为观望，不生成订单",
    "final action permits risk evaluation": "最终动作允许进入风控评估",
    "live trading enabled": "实盘交易已开启",
    "live trading is disabled": "实盘交易未开启",
    "paper mode does not require live trading": "模拟交易不需要开启实盘",
    "price, quantity, and notional are positive": "价格、数量和金额均为正数",
    "price, quantity, and notional must be positive": "价格、数量和金额必须为正数",
    "account equity available": "账户权益可用",
    "account equity is unavailable": "账户权益不可用",
    "buying power available": "可用资金充足",
    "buying power is insufficient": "可用资金不足",
    "sell order does not require buying power": "卖出不需要占用买入力",
    "buy order does not require existing position": "买入不需要已有持仓",
    "sell quantity is covered by current position": "卖出数量被当前持仓覆盖",
    "sell quantity exceeds current position": "卖出数量超过当前持仓",
    "limit price deviation passed": "限价相对行情快照的偏离在允许范围内",
    "limit price deviates too far from snapshot": "限价相对行情快照偏离过大",
    "limit price must be positive": "限价价格必须为正数",
    "market order does not require limit price": "市价单不需要限价检查",
    "position limit passed": "仓位限制通过",
    "position limit exceeded": "仓位限制超限",
    "single trade risk passed": "单笔交易风险通过",
    "single trade risk exceeded": "单笔交易风险超限",
    "daily loss limit passed": "日亏损限制通过",
    "daily loss limit exceeded": "日亏损限制超限",
    "cooldown passed": "交易冷却通过",
    "symbol is inside cooldown window": "该标的仍在交易冷却期",
    "no duplicate pending live preview": "不存在重复待确认订单预览",
    "duplicate pending live preview exists": "已存在相同标的和方向的待确认订单预览",
    "no duplicate pending order preview": "不存在重复待确认订单预览",
    "duplicate pending order preview exists": "已存在相同标的和方向的待确认订单预览",
    "production live configuration passed": "生产实盘配置通过",
    "production live configuration is incomplete": "生产实盘配置不完整",
    "regular market hours passed": "当前处于美股常规交易时段",
    "outside regular market hours": "当前不在美股常规交易时段",
    "regular market hours check disabled": "常规交易时段检查已关闭",
    "daily live order count passed": "每日实盘订单数未超限",
    "daily live order count exceeded": "每日实盘订单数已超限",
    "daily live notional passed": "每日实盘金额未超限",
    "daily live notional exceeded": "每日实盘金额已超限",
    "duplicate preview check skipped because no database session was provided": "未提供数据库会话，已跳过重复预览检查",
    "missing required agent opinion": "缺少必要 Agent 意见",
    "blocking concern raised": "存在阻断性疑虑",
    "confidence below threshold": "置信度低于阈值",
    "risk manager veto": "风控经理否决",
    "agents disagree": "Agent 意见不一致",
    "unanimous hold": "全体一致观望",
    "mock provider ready": "模拟数据源已就绪",
    "missing Webull app key or app secret": "缺少 Webull App Key 或 App Secret",
    "Webull provider reachable": "Webull 数据源可连接",
    approved: "已通过"
  };
  if (reason.startsWith("all required agents approved")) {
    return `所有必要 Agent 一致同意${displayValue(reason.split(" ").pop())}`;
  }
  return map[reason] ?? reason;
}
