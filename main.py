"""
Polymarket Python Agent 主程序
"""
import time
import argparse
from typing import List
from config import config
from utils.logger import logger
from services.polymarket import PolymarketService
from services.risk_manager import RiskManager
from strategies.simple_threshold import SimpleThresholdStrategy
from strategies.llm_simple_threshold import LLMSimpleThresholdStrategy
from strategies.expiring_markets import ExpiringMarketsStrategy
from strategies.llm_expiring_markets import LLMExpiringMarketsStrategy
from strategies.interactive import InteractiveStrategy
from strategies.index import IndexStrategy


class PolymarketAgent:
    """Polymarket 交易代理"""
    
    def __init__(self, strategy_name: str = "simple"):
        self.polymarket = PolymarketService()
        self.risk_manager = RiskManager()
        self.strategies = []
        self.test_mode = config.TEST_MODE
        self.mock_trading = config.MOCK_TRADING
        
        # 初始化策略
        self._init_strategies(strategy_name)
        
        # 显示运行模式
        mode_str = "测试模式" if self.test_mode else "生产模式"
        trading_str = "模拟交易" if self.mock_trading else "真实交易"
        
        logger.info(f"Polymarket Agent 已初始化")
        logger.info(f"运行模式: {mode_str} | {trading_str}")
        logger.info(f"策略: {strategy_name}")
        logger.info(f"激活的策略数: {len(self.strategies)}")
        
        if self.test_mode:
            logger.warning("⚠️  当前为测试模式，不会执行真实交易")
            logger.warning("⚠️  所有操作仅在日志中输出")
    
    def _init_strategies(self, strategy_name: str):
        """初始化策略"""
        if strategy_name == "simple" or strategy_name == "all":
            self.strategies.append(SimpleThresholdStrategy())
            logger.info("✓ 简单阈值策略已加载")
        
        if strategy_name == "llm" or strategy_name == "all":
            try:
                llm_strategy = LLMSimpleThresholdStrategy()
                if llm_strategy.is_active():
                    self.strategies.append(llm_strategy)
                    logger.info("✓ LLM 智能策略已加载")
                else:
                    logger.warning("⚠️  LLM 策略未激活（需要配置 OPENROUTER_API_KEY）")
            except Exception as e:
                logger.warning(f"LLM 策略加载失败: {e}")
        
        if strategy_name == "expiring" or strategy_name == "all":
            self.strategies.append(ExpiringMarketsStrategy())
            logger.info("✓ 到期市场策略已加载")
        
        if strategy_name == "llm_expiring" or strategy_name == "all":
            try:
                llm_expiring_strategy = LLMExpiringMarketsStrategy()
                if llm_expiring_strategy.is_active():
                    self.strategies.append(llm_expiring_strategy)
                    logger.info("✓ LLM 到期市场策略已加载")
                else:
                    logger.warning("⚠️  LLM 到期市场策略未激活")
            except Exception as e:
                logger.warning(f"LLM 到期市场策略加载失败: {e}")
        
        if strategy_name == "interactive" or strategy_name == "all":
            self.strategies.append(InteractiveStrategy())
            logger.info("✓ 交互式策略已加载")
        
        if strategy_name == "index" or strategy_name == "all":
            try:
                index_strategy = IndexStrategy()
                # 初始化指数策略（异步）
                import asyncio
                try:
                    loop = asyncio.get_event_loop()
                except RuntimeError:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                loop.run_until_complete(index_strategy.initialize())
                self.strategies.append(index_strategy)
                logger.info("✓ 指数跟踪策略已加载")
            except Exception as e:
                logger.warning(f"指数策略加载失败: {e}")
        
        if not self.strategies:
            raise ValueError(f"未知的策略: {strategy_name}")
    
    def run(self):
        """运行代理"""
        logger.info("=" * 60)
        logger.info("Polymarket Agent 开始运行")
        logger.info("=" * 60)
        
        iteration = 0
        
        try:
            while True:
                iteration += 1
                logger.info(f"\n{'='*60}")
                logger.info(f"迭代 #{iteration}")
                logger.info(f"{'='*60}")
                
                # 扫描市场
                self.scan_and_trade()
                
                # 等待下一次检查
                logger.info(f"\n等待 {config.CHECK_INTERVAL} 秒后进行下一次扫描...")
                time.sleep(config.CHECK_INTERVAL)
                
        except KeyboardInterrupt:
            logger.info("\n收到中断信号，正在停止...")
        except Exception as e:
            logger.error(f"运行时错误: {e}", exc_info=True)
        finally:
            logger.info("Polymarket Agent 已停止")
    
    def scan_and_trade(self):
        """扫描市场并执行交易"""
        try:
            # 获取活跃市场
            logger.info("正在获取活跃市场...")
            markets = self.polymarket.get_active_markets(limit=10)
            
            if not markets:
                logger.warning("未找到活跃市场")
                return
            
            logger.info(f"获取到 {len(markets)} 个活跃市场")
            
            # 获取当前持仓
            open_positions = {}  # TODO: 实现获取持仓
            
            # 运行所有策略
            all_opportunities = []
            
            for strategy in self.strategies:
                if not strategy.is_active():
                    continue
                
                logger.info(f"\n运行策略: {strategy.name}")
                opportunities = strategy.find_opportunities(markets, open_positions)
                all_opportunities.extend(opportunities)
            
            # 去重（按 market_id）
            unique_opportunities = {}
            for opp in all_opportunities:
                if opp.market_id not in unique_opportunities:
                    unique_opportunities[opp.market_id] = opp
                elif opp.expected_value > unique_opportunities[opp.market_id].expected_value:
                    unique_opportunities[opp.market_id] = opp
            
            opportunities = list(unique_opportunities.values())
            
            # 按期望值排序
            opportunities.sort(key=lambda x: x.expected_value, reverse=True)
            
            logger.info(f"\n找到 {len(opportunities)} 个独特的交易机会")
            
            # 评估和执行交易
            if opportunities:
                self.evaluate_and_execute(opportunities)
            else:
                logger.info("本轮未找到交易机会")
            
        except Exception as e:
            logger.error(f"扫描和交易过程出错: {e}", exc_info=True)
    
    def evaluate_and_execute(self, opportunities: List):
        """评估和执行交易"""
        logger.info("\n" + "=" * 60)
        logger.info("评估交易机会")
        logger.info("=" * 60)
        
        executed_count = 0
        
        for i, opp in enumerate(opportunities[:10], 1):  # 只评估前 10 个
            logger.info(f"\n[{i}] {opp.question[:60]}...")
            logger.info(f"    结果: {opp.outcome} @ {opp.current_price*100:.1f}%")
            logger.info(f"    信心: {opp.confidence*100:.1f}%")
            logger.info(f"    期望值: ${opp.expected_value:.2f}")
            logger.info(f"    边际: {opp.edge*100:.1f}%")
            
            # 风险评估
            evaluation = self.risk_manager.evaluate_opportunity(opp.to_dict())
            
            logger.info(f"    最终信心: {evaluation['final_confidence']*100:.1f}%")
            logger.info(f"    风险评分: {evaluation['risk_score']*100:.1f}%")
            logger.info(f"    建议仓位: ${evaluation['position_size']:.2f}")
            logger.info(f"    理由: {evaluation['reasoning']}")
            
            if evaluation["should_trade"]:
                logger.info(f"    ✅ 决策: 执行交易")
                
                # 执行交易
                success = self.execute_trade(opp, evaluation["position_size"])
                
                if success:
                    executed_count += 1
                    self.risk_manager.record_trade()
            else:
                logger.info(f"    ❌ 决策: 不交易")
        
        logger.info(f"\n本轮执行了 {executed_count} 笔交易")
    
    def execute_trade(self, opportunity, position_size: float) -> bool:
        """
        执行交易
        
        Args:
            opportunity: 交易机会
            position_size: 仓位大小
        
        Returns:
            是否成功
        """
        logger.info(f"\n{'='*60}")
        logger.info("📝 模拟交易执行" if self.mock_trading else "💰 真实交易执行")
        logger.info(f"{'='*60}")
        logger.info(f"市场: {opportunity.question}")
        logger.info(f"结果: {opportunity.outcome}")
        logger.info(f"当前价格: {opportunity.current_price*100:.1f}%")
        logger.info(f"预测概率: {opportunity.predicted_probability*100:.1f}%")
        logger.info(f"仓位大小: ${position_size:.2f}")
        logger.info(f"信心度: {opportunity.confidence*100:.1f}%")
        logger.info(f"期望值: ${opportunity.expected_value:.2f}")
        
        if self.mock_trading:
            # 模拟交易模式
            logger.info("\n📊 交易详情（模拟）:")
            
            # 计算份额数量
            shares = position_size / opportunity.current_price
            logger.info(f"  购买份额: {shares:.2f} 份")
            logger.info(f"  单价: ${opportunity.current_price:.4f}")
            logger.info(f"  总成本: ${position_size:.2f}")
            
            # 模拟潜在收益
            if opportunity.outcome == "YES":
                potential_profit = shares * (1 - opportunity.current_price)
            else:
                potential_profit = shares * opportunity.current_price
            
            logger.info(f"  潜在利润: ${potential_profit:.2f}")
            logger.info(f"  潜在回报率: {(potential_profit/position_size)*100:.1f}%")
            
            # 显示新闻信号
            if opportunity.news_signals:
                logger.info("\n📰 支持信号:")
                for signal in opportunity.news_signals[:5]:
                    logger.info(f"  • {signal}")
            
            logger.info("\n✅ 模拟交易已记录")
            logger.info("💡 提示: 设置 MOCK_TRADING=false 以执行真实交易")
            
            return True
        else:
            # 真实交易模式
            logger.info("\n💰 准备执行真实交易...")
            
            # TODO: 实现实际的交易执行
            # 需要：
            # 1. 获取 token_id
            # 2. 计算份额数量
            # 3. 调用 CLOB API 下单
            # 4. 等待订单确认
            
            logger.error("❌ 真实交易功能尚未实现")
            logger.error("请先完成 CLOB API 集成")
            logger.info("💡 建议: 使用 MOCK_TRADING=true 进行测试")
            
            return False


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="Polymarket Python Agent")
    parser.add_argument(
        "--strategy",
        type=str,
        default="simple",
        choices=["simple", "llm", "expiring", "llm_expiring", "interactive", "index", "all"],
        help="选择交易策略"
    )
    
    args = parser.parse_args()
    
    try:
        # 验证配置
        config.validate()
        
        # 创建并运行代理
        agent = PolymarketAgent(strategy_name=args.strategy)
        agent.run()
        
    except ValueError as e:
        logger.error(f"配置错误: {e}")
    except Exception as e:
        logger.error(f"启动失败: {e}", exc_info=True)


if __name__ == "__main__":
    main()
