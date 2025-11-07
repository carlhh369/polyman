"""
交互式策略（Agent）
多信号融合策略，结合价格、交易量和新闻情绪
"""
import json
from typing import List, Dict, Any, Optional, Set
from strategies.base import BaseStrategy, MarketOpportunity
from services.news import NewsService, NewsSignal
from config import config
from utils.logger import logger
from utils.helpers import parse_market_end_date, hours_until_expiry


class InteractiveStrategy(BaseStrategy):
    """
    交互式策略 - 复杂的多信号交易策略
    
    结合多个信号源：
    - 价格信号（40%权重）
    - 交易量信号（30%权重）
    - 新闻情绪信号（30%权重）
    """
    
    def __init__(self):
        strategy_config = {
            "enabled": True,
            "use_news_signals": config.NEWS_API_KEY != "",
            "min_confidence_threshold": config.MIN_CONFIDENCE_THRESHOLD,
            "price_edge_threshold": config.INTERACTIVE_PRICE_EDGE,
            "volume_threshold": config.INTERACTIVE_MIN_VOLUME,
            "max_position_size": config.MAX_POSITION_SIZE,
            "sentiment_weight": config.SENTIMENT_WEIGHT,
            "price_weight": config.PRICE_WEIGHT,
            "volume_weight": config.VOLUME_WEIGHT,
            "check_trending_topics": True
        }
        
        super().__init__(
            name="InteractiveStrategy",
            description="复杂的多信号交易策略，结合新闻和情绪分析",
            config=strategy_config
        )
        
        self.news_service = NewsService()
        self.trending_topics: Set[str] = set()
    
    def find_opportunities(
        self,
        markets: List[Dict[str, Any]],
        open_positions: Dict[str, Any]
    ) -> List[MarketOpportunity]:
        """查找交易机会"""
        if not self.is_active():
            return []
        
        logger.info("交互式策略: 使用多信号分析扫描市场")
        
        try:
            opportunities = []
            
            # 获取要分析的市场
            markets_to_analyze = self._get_markets_to_analyze(markets)
            
            logger.info(f"分析 {len(markets_to_analyze)} 个市场寻找交互式机会")
            
            for market in markets_to_analyze:
                condition_id = market.get("conditionId")
                
                # 跳过已有持仓
                if condition_id in open_positions:
                    continue
                
                # 分析市场
                market_opportunities = self.analyze_market(market)
                opportunities.extend(market_opportunities)
            
            # 按期望值和信心度排序
            opportunities.sort(
                key=lambda x: x.expected_value * x.confidence,
                reverse=True
            )
            
            logger.info(f"找到 {len(opportunities)} 个交互式策略机会")
            return opportunities[:10]  # 返回前 10 个机会
            
        except Exception as e:
            logger.error(f"交互式策略错误: {e}")
            return []
    
    def analyze_market(
        self,
        market: Dict[str, Any]
    ) -> List[MarketOpportunity]:
        """分析单个市场"""
        opportunities = []
        
        # 跳过低交易量市场
        volume = market.get("volume", 0)
        if volume < self.config["volume_threshold"]:
            return opportunities
        
        question = market.get("question", "")
        condition_id = market.get("conditionId", "")
        
        # 获取新闻信号（如果启用）
        news_signal = None
        if self.config["use_news_signals"]:
            try:
                news_signal = self.news_service.get_market_signals(question)
            except Exception as e:
                logger.debug(f"无法获取市场新闻: {e}")
        
        # 获取价格和结果
        prices = self.extract_prices(market)
        try:
            outcomes = json.loads(market.get("outcomes", '["Yes", "No"]'))
        except:
            outcomes = ["Yes", "No"]
        
        # 分析每个结果
        for i, outcome in enumerate(outcomes):
            if i >= len(prices):
                continue
            
            price = prices[i]
            outcome_name = outcome.upper()
            
            # 计算各种信号
            price_signal = self._calculate_price_signal(price, outcome_name)
            volume_signal = self._calculate_volume_signal(volume)
            news_signal_score = (
                self._calculate_news_signal(news_signal, outcome_name)
                if news_signal else 0.5
            )
            
            # 使用权重组合信号
            combined_score = (
                (price_signal * self.config["price_weight"]) +
                (volume_signal * self.config["volume_weight"]) +
                (news_signal_score * self.config["sentiment_weight"])
            )
            
            # 归一化评分
            total_weight = (
                self.config["price_weight"] +
                self.config["volume_weight"] +
                self.config["sentiment_weight"]
            )
            normalized_score = combined_score / total_weight
            
            # 计算边际和信心
            edge = abs(normalized_score - 0.5)
            should_buy = normalized_score > 0.5
            
            if edge >= self.config["price_edge_threshold"]:
                confidence = self._calculate_confidence(
                    edge=edge,
                    news_signal=news_signal,
                    volume=volume,
                    price_signal=price_signal
                )
                
                if confidence >= self.config["min_confidence_threshold"]:
                    target_outcome = (
                        outcome_name if should_buy
                        else ("NO" if outcome_name == "YES" else "YES")
                    )
                    target_price = price if should_buy else (1 - price)
                    
                    signals = self._build_signals(
                        market=market,
                        outcome=target_outcome,
                        price_signal=price_signal,
                        volume_signal=volume_signal,
                        news_score=news_signal_score,
                        news_signal=news_signal
                    )
                    
                    # 计算到期时间
                    hours_to_exp = None
                    if "endDate" in market:
                        end_date = parse_market_end_date(market["endDate"])
                        if end_date:
                            hours_to_exp = hours_until_expiry(end_date)
                    
                    opportunities.append(MarketOpportunity(
                        market_id=condition_id,
                        question=question,
                        outcome=target_outcome,
                        current_price=target_price,
                        predicted_probability=normalized_score,
                        confidence=confidence,
                        expected_value=edge * 100 * confidence,
                        news_signals=signals,
                        risk_score=self.calculate_risk_score(market, edge),
                        volume=volume,
                        hours_to_expiry=hours_to_exp
                    ))
                    
                    logger.info(
                        f"🎯 交互式机会: {question[:50]}..."
                    )
                    logger.info(
                        f"   {target_outcome} @ {target_price*100:.1f}% | "
                        f"信心: {confidence*100:.1f}% | 评分: {normalized_score:.3f}"
                    )
        
        return opportunities
    
    def _get_markets_to_analyze(
        self,
        all_markets: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """获取要分析的市场列表"""
        # 过滤高交易量市场
        high_volume_markets = [
            m for m in all_markets
            if m.get("volume", 0) >= self.config["volume_threshold"]
        ]
        
        # 如果启用热门话题检查，优先选择高交易量市场
        if self.config["check_trending_topics"]:
            # 按交易量排序
            high_volume_markets.sort(
                key=lambda m: m.get("volume", 0),
                reverse=True
            )
            return high_volume_markets[:50]  # 前 50 个高交易量市场
        
        return high_volume_markets
    
    def _calculate_price_signal(self, price: float, outcome: str) -> float:
        """
        计算价格信号
        寻找价格极端值，暗示机会
        """
        if outcome == "YES":
            if price < 0.2:
                return 0.8  # 非常便宜的 YES
            if price < 0.35:
                return 0.65  # 较便宜的 YES
            if price > 0.8:
                return 0.2  # 非常贵的 YES
            if price > 0.65:
                return 0.35  # 较贵的 YES
        else:  # NO
            if price < 0.2:
                return 0.8  # 非常便宜的 NO
            if price < 0.35:
                return 0.65  # 较便宜的 NO
            if price > 0.8:
                return 0.2  # 非常贵的 NO
            if price > 0.65:
                return 0.35  # 较贵的 NO
        
        return 0.5  # 中性
    
    def _calculate_volume_signal(self, volume: float) -> float:
        """
        计算交易量信号
        更高的交易量 = 更强的信号
        """
        if volume > 1000000:
            return 0.9
        if volume > 500000:
            return 0.75
        if volume > 100000:
            return 0.6
        if volume > 50000:
            return 0.5
        return 0.3  # 低交易量 = 弱信号
    
    def _calculate_news_signal(
        self,
        news_signal: Optional[NewsSignal],
        outcome: str
    ) -> float:
        """
        计算新闻情绪信号
        """
        if not news_signal or not news_signal.articles:
            return 0.5  # 中性
        
        # 使用新闻文章的情绪
        total_sentiment = 0
        article_count = 0
        
        for article in news_signal.articles:
            if article.sentiment:
                # 根据结果调整情绪
                if article.sentiment == "positive":
                    sentiment_score = 0.7
                elif article.sentiment == "negative":
                    sentiment_score = 0.3
                else:
                    sentiment_score = 0.5
                
                # 根据 YES/NO 调整
                sentiment = (
                    sentiment_score if outcome == "YES"
                    else (1 - sentiment_score)
                )
                
                total_sentiment += sentiment
                article_count += 1
        
        if article_count == 0:
            return 0.5
        
        return total_sentiment / article_count
    
    def _calculate_confidence(
        self,
        edge: float,
        news_signal: Optional[NewsSignal],
        volume: float,
        price_signal: float
    ) -> float:
        """计算综合信心度"""
        confidence = 0.5  # 基础信心
        
        # 价格边际贡献
        confidence += edge * 0.3
        
        # 交易量贡献
        if volume > 500000:
            confidence += 0.2
        elif volume > 100000:
            confidence += 0.1
        
        # 新闻信号贡献
        if news_signal and news_signal.articles:
            confidence += min(len(news_signal.articles) * 0.05, 0.2)
        
        # 价格信号贡献
        if price_signal > 0.7 or price_signal < 0.3:
            confidence += 0.1  # 强价格信号
        
        return min(confidence, 0.95)  # 上限 95%
    
    def _build_signals(
        self,
        market: Dict[str, Any],
        outcome: str,
        price_signal: float,
        volume_signal: float,
        news_score: float,
        news_signal: Optional[NewsSignal]
    ) -> List[str]:
        """构建信号列表"""
        signals = []
        
        # 添加价格信号
        signals.append(f"价格信号: {price_signal*100:.1f}%")
        
        # 添加交易量信号
        volume = market.get("volume", 0)
        signals.append(
            f"交易量: {volume/1000:.0f}k "
            f"(信号: {volume_signal*100:.0f}%)"
        )
        
        # 添加新闻信号
        if news_signal and news_signal.articles:
            signals.append(
                f"新闻情绪: {news_score*100:.0f}% "
                f"({len(news_signal.articles)} 篇文章)"
            )
            
            # 添加头条新闻
            for article in news_signal.articles[:2]:
                signals.append(f"📰 {article.title}")
        
        # 添加市场指标
        if "endDate" in market:
            end_date = parse_market_end_date(market["endDate"])
            if end_date:
                hours_to_exp = hours_until_expiry(end_date)
                if hours_to_exp < 168:  # 少于一周
                    signals.append(f"⏰ {hours_to_exp:.0f} 小时后到期")
        
        return signals
