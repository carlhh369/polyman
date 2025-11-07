# Polymarket Python Agent 快速开始指南

## 📋 前置要求

- Python 3.8+
- pip 包管理器
- Polymarket 账户和私钥
- NewsAPI 密钥（可选，用于新闻集成）

## 🚀 快速开始

### 1. 安装依赖

```bash
cd python-agent
pip install -r requirements.txt
```

### 2. 配置环境变量

```bash
# 复制示例配置文件
cp .env.example .env

# 编辑 .env 文件
nano .env  # 或使用你喜欢的编辑器
```

**必需配置**：
```bash
POLYMARKET_PRIVATE_KEY=你的私钥
```

**可选配置**：
```bash
NEWS_API_KEY=你的NewsAPI密钥  # 增强决策
MAX_POSITION_SIZE=100          # 单笔最大仓位
MIN_CONFIDENCE_THRESHOLD=0.7   # 最小信心阈值
```

### 3. 运行 Agent

```bash
# 使用简单阈值策略
python main.py --strategy simple

# 使用到期市场策略
python main.py --strategy expiring

# 使用 LLM 智能策略
python main.py --strategy llm

# 使用所有策略
python main.py --strategy all
```

## 📊 策略说明

### 简单阈值策略（Simple Threshold）
- **适合**: 初学者、保守交易者
- **特点**: 在价格低于 30% 时买入，高于 70% 时卖出
- **风险**: 低到中等
- **频率**: 2-5 笔/天

```bash
python main.py --strategy simple
```

### 到期市场策略（Expiring Markets）
- **适合**: 风险厌恶者、追求稳定收益
- **特点**: 只交易即将到期且概率 >95% 的市场
- **风险**: 极低
- **频率**: 5-15 笔/天

```bash
python main.py --strategy expiring
```

### LLM 智能策略（LLM Simple Threshold）
- **适合**: 追求智能分析、愿意尝试 AI 辅助决策
- **特点**: 使用大语言模型分析市场，结合新闻和市场数据做出决策
- **风险**: 中等
- **频率**: 3-8 笔/天
- **要求**: 需要配置 OpenAI API 密钥或兼容的 LLM 服务

```bash
python main.py --strategy llm
```

## 🔧 配置调优

### 保守配置
```bash
MIN_CONFIDENCE_THRESHOLD=0.80
MAX_POSITION_SIZE=50
RISK_LIMIT_PER_TRADE=25
MAX_DAILY_TRADES=5
```

### 激进配置
```bash
MIN_CONFIDENCE_THRESHOLD=0.65
MAX_POSITION_SIZE=100
RISK_LIMIT_PER_TRADE=50
MAX_DAILY_TRADES=20
```

## 📈 监控运行

Agent 会输出彩色日志到控制台，同时保存到 `agent.log` 文件：

```bash
# 实时查看日志
tail -f agent.log

# 搜索交易记录
grep "执行交易" agent.log

# 查看找到的机会
grep "找到.*机会" agent.log
```

## ⚠️ 重要提示

### 当前限制

1. **交易执行未实现**: 当前版本只会扫描和评估机会，不会实际下单
2. **持仓管理未实现**: 需要手动实现 CLOB API 集成
3. **演示模式**: 适合学习和测试策略逻辑

### 实现完整交易功能需要：

1. **CLOB API 集成**
   - 实现订单签名
   - 实现订单提交
   - 实现订单状态查询

2. **钱包管理**
   - 余额查询
   - L1->L2 充值
   - Gas 费管理

3. **持仓管理**
   - 查询当前持仓
   - 计算盈亏
   - 自动赎回已解决市场

## 🛠️ 开发和扩展

### 添加自定义策略

1. 在 `strategies/` 目录创建新文件
2. 继承 `BaseStrategy` 类
3. 实现 `find_opportunities` 和 `analyze_market` 方法
4. 在 `main.py` 中注册策略

示例：
```python
from strategies.base import BaseStrategy, MarketOpportunity

class MyCustomStrategy(BaseStrategy):
    def __init__(self):
        super().__init__(
            name="MyCustomStrategy",
            description="我的自定义策略",
            config={"enabled": True}
        )
    
    def find_opportunities(self, markets, open_positions):
        # 你的逻辑
        pass
    
    def analyze_market(self, market):
        # 你的分析
        pass
```

### 调试模式

```bash
# 设置日志级别为 DEBUG
LOG_LEVEL=DEBUG python main.py --strategy simple
```

## 📚 参考资源

- **策略详细文档**: `../docs/TRADING_STRATEGIES_CN.md`
- **Polymarket API**: https://docs.polymarket.com
- **NewsAPI**: https://newsapi.org/docs

## 🆘 常见问题

### Q: 为什么找不到交易机会？
A: 检查以下几点：
- 信心阈值是否太高？降低到 0.65
- 最小边际是否太大？降低到 0.10
- 市场是否活跃？检查 Polymarket 网站

### Q: 如何实现实际交易？
A: 需要实现以下功能：
1. 在 `services/polymarket.py` 中实现 `place_order` 方法
2. 集成 CLOB API 和订单签名
3. 实现余额检查和充值逻辑

### Q: 可以同时运行多个策略吗？
A: 可以，使用 `--strategy all` 参数

### Q: 如何停止 Agent？
A: 按 `Ctrl+C` 优雅停止


**免责声明**: 这是教育和研究用途的软件。预测市场交易涉及财务风险。请自行承担风险，切勿交易超过你能承受损失的金额。
