"""
简单阈值策略
"""
import json
from typing import List, Dict, Any
from strategies.base import BaseStrategy, MarketOpportunity
from services.news import NewsService
from config import config
from utils.logger import logger


class SimpleThresholdStrategy(BaseStrategy):
    """简单阈值策略"""
    
    def __init__(self):
        strategy_config = {
            "enabled": True,
            "buy_threshold": config.SIMPLE_BUY_THRESHOLD,
            "sell_threshold": config.SIMPLE_SELL_THRESHOLD,
            "min_edge": config.SIMPLE_MIN_EDGE,
            "use_news_signals": True
        }
        
        super().__init__(
            name="SimpleThresholdStrategy",
            description="基于简单价格阈值的交易策略",
            config=strategy_config
        )
        
        self.news_service = NewsService()
    
    def find_opportunities(
        self,
        markets: List[Dict[str, Any]],
        open_positions: Dict[str, Any]
    ) -> List[MarketOpportunity]:
        """查找交易机会"""
        if not self.is_active():
            return []
        
        opportunities = []
        
        logger.info(f"简单阈值策略: 检查 {len(markets)} 个市场")
        
        for market in markets:
            condition_id = market.get("conditionId")
            
            # 跳过已有持仓的市场
            if condition_id in open_positions:
                logger.debug(f"跳过 {condition_id[:10]}... - 已有持仓")
                continue
            
            # 分析市场
            market_opportunities = self.analyze_market(market)
            opportunities.extend(market_opportunities)
        
        logger.info(f"找到 {len(opportunities)} 个简单阈值策略机会")
        return opportunities
    
    def analyze_market(
        self,
        market: Dict[str, Any]
    ) -> List[MarketOpportunity]:
        """分析单个市场"""
        opportunities = []
        
        question = market.get("question", "")
        condition_id = market.get("conditionId", "")
        
        logger.debug(f"分析市场: {question[:50]}...")
        
        # 获取价格
        prices = self.extract_prices(market)
        
        # 获取结果
        try:
            outcomes = json.loads(market.get("outcomes", '["Yes", "No"]'))
        except:
            outcomes = ["Yes", "No"]
        
        # 获取新闻信号（如果启用）
        news_signal = None
        if self.config["use_news_signals"]:
            try:
                news_signal = self.news_service.get_market_signals(question)
            except Exception as e:
                logger.warning(f"获取新闻信号失败: {e}")
        
        # 分析每个结果
        for i, outcome in enumerate(outcomes):
            if i >= len(prices):
                continue
            
            price = prices[i]
            outcome_name = outcome.upper()
            
            # 买入条件：价格 <= 买入阈值
            if price <= self.config["buy_threshold"]:
                edge = self.config["buy_threshold"] - price
                
                if edge >= self.config["min_edge"]:
                    opportunity = self._create_opportunity(
                        market=market,
                        outcome=outcome_name,
                        price=price,
                        edge=edge,
                        news_signal=news_signal,
                        is_inverse=False
                    )
                    
                    if opportunity:
                        opportunities.append(opportunity)
            
            # 寻找 NO 便宜的机会（YES 昂贵）
            if outcome_name == "YES" and price >= self.config["sell_threshold"]:
                no_price = 1 - price
                edge = price - self.config["sell_threshold"]
                
                if edge >= self.config["min_edge"] and no_price <= self.config["buy_threshold"]:
                    opportunity = self._create_opportunity(
                        market=market,
                        outcome="NO",
                        price=no_price,
                        edge=edge,
                        news_signal=news_signal,
                        is_inverse=True
                    )
                    
                    if opportunity:
                        opportunities.append(opportunity)
        
        return opportunities
    
    def _create_opportunity(
        self,
        market: Dict[str, Any],
        outcome: str,
        price: float,
        edge: float,
        news_signal: Any,
        is_inverse: bool
    ) -> MarketOpportunity:
        """创建交易机会"""
        
        # 基础信心度
        confidence = 0.8
        
        # 新闻信号
        news_signals = [
            f"价格优势: {outcome} @ {price*100:.1f}%" if not is_inverse
            else f"价格优势: NO @ {price*100:.1f}% (YES 昂贵)"
        ]
        
        # 如果有新闻信号，使用混合信心评分
        if news_signal and news_signal.articles:
            # 简化的混合评分
            price_confidence = 0.5 + (edge * 4)
            news_confidence = news_signal.confidence
            
            # 检查对齐
            if news_signal.signal == "bullish" and outcome == "YES":
                # 对齐
                pass
            elif news_signal.signal == "bearish" and outcome == "NO":
                # 对齐
                pass
            elif news_signal.signal == "bullish" and outcome == "NO":
                # 相反
                news_confidence = 1 - news_confidence
            elif news_signal.signal == "bearish" and outcome == "YES":
                # 相反
                news_confidence = 1 - news_confidence
            
            # 综合信心
            confidence = (price_confidence * 0.6) + (news_confidence * 0.4)
            
            # 添加新闻信号
            news_signals.append(
                f"新闻: {news_signal.signal} ({news_signal.confidence*100:.0f}% 信心, "
                f"{len(news_signal.articles)} 篇文章)"
            )
            
            # 添加文章标题
            for article in news_signal.articles[:2]:
                news_signals.append(f"📰 {article.title[:60]}...")
        
        # 计算风险评分
        risk_score = self.calculate_risk_score(market, edge)
        
        # 期望值
        expected_value = edge * 100 * confidence
        
        # 到期时间
        hours_to_expiry = None
        if "endDate" in market:
            from utils.helpers import parse_market_end_date, hours_until_expiry
            end_date = parse_market_end_date(market["endDate"])
            if end_date:
                hours_to_expiry = hours_until_expiry(end_date)
        
        logger.info(
            f"简单策略机会: {market.get('question', '')[:50]}..."
        )
        logger.info(
            f"  {outcome} @ {price*100:.1f}% (信心: {confidence*100:.1f}%)"
        )
        
        return MarketOpportunity(
            market_id=market.get("conditionId", ""),
            question=market.get("question", ""),
            outcome=outcome,
            current_price=price,
            predicted_probability=price + edge,
            confidence=confidence,
            expected_value=expected_value,
            news_signals=news_signals,
            risk_score=risk_score,
            volume=market.get("volume", 0),
            hours_to_expiry=hours_to_expiry
        )
