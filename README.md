# Polymarket Python Agent

Python 实现自动化参与 Polymarket 预测市场交易。

## 功能特性

- 🤖 **自动化交易** - 24/7 扫描和执行交易
- 📊 **多种策略** - 简单阈值、到期市场、LLM 到期市场、交互式、LLM 智能策略、指数跟踪
- 🧠 **AI 驱动** - 集成大语言模型进行智能市场分析
- 📰 **新闻集成** - 实时新闻分析增强决策
- 🛡️ **风险管理** - Kelly Criterion 仓位计算和多层风险控制
- 📈 **性能追踪** - 实时监控交易表现
- 🎯 **100% 完成** - 所有 TypeScript 策略已移植

## 快速开始

### 安装依赖

```bash
cd python-agent
pip install -r requirements.txt
```

### 配置环境变量

```bash
cp .env.example .env
# 编辑 .env 文件，填入你的配置
```

### 运行 Agent

```bash
# 简单阈值策略
python main.py --strategy simple

# 到期市场策略
python main.py --strategy expiring

# LLM 增强的到期市场策略（需要配置 LLM API）
python main.py --strategy llm_expiring

# LLM 智能策略（需要配置 LLM API）
python main.py --strategy llm

# 交互式策略
python main.py --strategy interactive

# 所有策略
python main.py --strategy all
```

## 项目结构

```
python-agent/
├── main.py                 # 主入口
├── config.py               # 配置管理
├── requirements.txt        # 依赖包
├── strategies/             # 交易策略
│   ├── base.py            # 基础策略类
│   ├── simple_threshold.py
│   ├── expiring_markets.py
│   ├── llm_expiring_markets.py  # LLM 增强的到期市场策略
│   ├── llm_simple_threshold.py
│   └── interactive.py
├── services/              # 核心服务
│   ├── polymarket.py      # Polymarket API
│   ├── news.py            # 新闻服务
│   ├── llm.py             # LLM 服务
│   ├── risk_manager.py    # 风险管理
│   └── executor.py        # 交易执行
└── utils/                 # 工具函数
    ├── logger.py
    └── helpers.py
```

## 配置说明

参见 `.env.example` 文件中的详细说明。

## 策略说明

详细策略文档请参考主项目的 `docs/TRADING_STRATEGIES_CN.md`。

## 许可证

MIT License
