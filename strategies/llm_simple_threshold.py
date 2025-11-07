"""
基于 LLM 的简单阈值策略
使用大语言模型进行市场分析，而不是僵硬的公式规则
"""
import json
from typing import List, Dict, Any, Optional
from strategies.base import BaseStrategy, MarketOpportunity
from services.news import NewsService
from services.llm import llm_service
from config import config
from utils.logger import logger


class LLMSimpleThresholdStrategy(BaseStrategy):
    """基于 LLM 的简单阈值策略"""
    
    def __init__(self):
        strategy_config = {
            "enabled": True,
            "buy_threshold": config.SIMPLE_BUY_THRESHOLD,
            "sell_threshold": config.SIMPLE_SELL_THRESHOLD,
            "min_edge": config.SIMPLE_MIN_EDGE,
            "use_news_signals": True,
            "llm_confidence_threshold": 0.6  # LLM 推荐的最低信心度
        }
        
        super().__init__(
            name="LLMSimpleThresholdStrategy",
            description="使用大语言模型分析市场的智能策略",
            config=strategy_config
        )
        
        self.news_service = NewsService()
        
        # 使用统一的 LLM 服务
        if not llm_service.is_enabled():
            logger.warning("⚠️  LLM 服务未启用，LLM 策略将无法使用")
            self.enabled = False
        else:
            logger.info("✓ LLM 策略已启用")
    
    def find_opportunities(
        self,
        markets: List[Dict[str, Any]],
        open_positions: Dict[str, Any]
    ) -> List[MarketOpportunity]:
        """查找交易机会"""
        if not self.is_active():
            return []
        
        opportunities = []
        
        logger.info(f"LLM 策略: 检查 {len(markets)} 个市场")
        
        for market in markets:
            condition_id = market.get("conditionId")
            
            # 跳过已有持仓的市场
            if condition_id in open_positions:
                logger.debug(f"跳过 {condition_id[:10]}... - 已有持仓")
                continue
            
            # 分析市场
            try:
                market_opportunities = self.analyze_market(market)
                opportunities.extend(market_opportunities)
            except Exception as e:
                logger.error(f"LLM 分析市场失败: {e}")
                continue
        
        logger.info(f"找到 {len(opportunities)} 个 LLM 策略机会")
        return opportunities
    
    def analyze_market(
        self,
        market: Dict[str, Any]
    ) -> List[MarketOpportunity]:
        """使用 LLM 分析单个市场"""
        opportunities = []
        
        question = market.get("question", "")
        condition_id = market.get("conditionId", "")
        
        logger.debug(f"LLM 分析市场: {question[:50]}...")
        
        # 获取价格
        prices = self.extract_prices(market)
        
        # 获取结果
        try:
            outcomes = json.loads(market.get("outcomes", '["Yes", "No"]'))
        except:
            outcomes = ["Yes", "No"]
        
        # 获取新闻信号
        news_signal = None
        news_summary = "无相关新闻"
        
        if self.config["use_news_signals"]:
            try:
                news_signal = self.news_service.get_market_signals(question)
                if news_signal and news_signal.articles:
                    news_summary = f"{news_signal.signal} 信号 ({news_signal.confidence*100:.0f}% 信心), {len(news_signal.articles)} 篇文章"
                    if news_signal.articles:
                        news_summary += f"\n主要新闻: {news_signal.articles[0].title}"
            except Exception as e:
                logger.warning(f"获取新闻信号失败: {e}")
        
        # 使用 LLM 分析市场
        llm_analysis = self._analyze_with_llm(
            question=question,
            outcomes=outcomes,
            prices=prices,
            news_summary=news_summary,
            market=market
        )
        
        if not llm_analysis:
            logger.debug(f"LLM 未推荐交易: {question[:50]}...")
            return []
        
        # 根据 LLM 分析创建机会
        for recommendation in llm_analysis.get("recommendations", []):
            opportunity = self._create_opportunity_from_llm(
                market=market,
                recommendation=recommendation,
                news_signal=news_signal
            )
            
            if opportunity:
                opportunities.append(opportunity)
        
        return opportunities
    
    def _analyze_with_llm(
        self,
        question: str,
        outcomes: List[str],
        prices: List[float],
        news_summary: str,
        market: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        使用 LLM 分析市场
        
        Returns:
            LLM 分析结果，包含推荐的交易
        """
        try:
            # 构建市场信息
            market_info = []
            for i, outcome in enumerate(outcomes):
                if i < len(prices):
                    market_info.append(f"{outcome}: {prices[i]*100:.1f}%")
            
            market_info_str = ", ".join(market_info)
            
            # 获取市场元数据
            volume = market.get("volume", 0)
            end_date = market.get("endDate", "未知")
            
            # 构建提示词
            prompt = f"""You are an expert prediction market trader analyzing opportunities on Polymarket.

**Strategy Guidelines:**
- Look for mispriced markets where the current price doesn't reflect the true probability
- Buy when price is LOW (≤ {self.config['buy_threshold']*100:.0f}%) and you believe the outcome is likely
- Consider selling YES (buying NO) when YES price is HIGH (≥ {self.config['sell_threshold']*100:.0f}%) and you believe it's overpriced
- Minimum edge required: {self.config['min_edge']*100:.0f}%
- Consider news sentiment and market fundamentals

**Market Question:**
{question}

**Current Prices:**
{market_info_str}

**News Analysis:**
{news_summary}

**Market Metadata:**
- Volume: ${volume:,.0f}
- End Date: {end_date}

**Your Task:**
Analyze this market and determine if there are any trading opportunities. Consider:
1. Is the current price reasonable given the question and available information?
2. Does the news sentiment align with or contradict the current price?
3. Is there sufficient edge (price advantage) to justify a trade?
4. What are the key risks?

Respond in JSON format:
{{
    "should_trade": true/false,
    "recommendations": [
        {{
            "outcome": "YES" or "NO",
            "action": "BUY",
            "confidence": 0.0-1.0,
            "reasoning": "brief explanation",
            "predicted_probability": 0.0-1.0,
            "key_factors": ["factor1", "factor2"]
        }}
    ],
    "overall_assessment": "brief market assessment"
}}

Analysis:"""
            
            response = llm_service.call(prompt, max_tokens=800)
            
            # 解析 JSON 响应
            json_start = response.find('{')
            json_end = response.rfind('}') + 1
            
            if json_start >= 0 and json_end > json_start:
                json_str = response[json_start:json_end]
                result = json.loads(json_str)
                
                logger.info(f"LLM 分析: {question[:50]}...")
                logger.info(f"  应该交易: {result.get('should_trade', False)}")
                logger.info(f"  评估: {result.get('overall_assessment', 'N/A')[:100]}")
                
                if result.get("should_trade", False):
                    return result
                else:
                    return None
            else:
                logger.warning("无法从 LLM 响应中提取 JSON")
                return None
                
        except Exception as e:
            logger.error(f"LLM 市场分析失败: {e}")
            return None
    
    def _create_opportunity_from_llm(
        self,
        market: Dict[str, Any],
        recommendation: Dict[str, Any],
        news_signal: Any
    ) -> Optional[MarketOpportunity]:
        """根据 LLM 推荐创建交易机会"""
        
        outcome = recommendation.get("outcome", "YES")
        confidence = float(recommendation.get("confidence", 0.5))
        predicted_prob = float(recommendation.get("predicted_probability", 0.5))
        reasoning = recommendation.get("reasoning", "")
        key_factors = recommendation.get("key_factors", [])
        
        # 检查信心度阈值
        if confidence < self.config["llm_confidence_threshold"]:
            logger.debug(f"LLM 信心度过低: {confidence:.2f} < {self.config['llm_confidence_threshold']:.2f}")
            return None
        
        # 获取当前价格
        prices = self.extract_prices(market)
        try:
            outcomes = json.loads(market.get("outcomes", '["Yes", "No"]'))
        except:
            outcomes = ["Yes", "No"]
        
        # 找到对应结果的价格
        current_price = 0.5
        for i, out in enumerate(outcomes):
            if out.upper() == outcome.upper() and i < len(prices):
                current_price = prices[i]
                break
        
        # 如果是 NO，但只有 YES 价格
        if outcome.upper() == "NO" and len(outcomes) == 2 and outcomes[0].upper() == "YES":
            current_price = 1 - prices[0]
        
        # 计算边际
        edge = abs(predicted_prob - current_price)
        
        # 检查最小边际
        if edge < self.config["min_edge"]:
            logger.debug(f"边际过小: {edge:.3f} < {self.config['min_edge']:.3f}")
            return None
        
        # 构建新闻信号列表
        news_signals = [
            f"LLM 推荐: {outcome} @ {current_price*100:.1f}%",
            f"LLM 推理: {reasoning}",
        ]
        
        # 添加关键因素
        for factor in key_factors[:3]:
            news_signals.append(f"• {factor}")
        
        # 添加新闻信号
        if news_signal and news_signal.articles:
            news_signals.append(
                f"新闻: {news_signal.signal} ({news_signal.confidence*100:.0f}% 信心)"
            )
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
            f"LLM 策略机会: {market.get('question', '')[:50]}..."
        )
        logger.info(
            f"  {outcome} @ {current_price*100:.1f}% (LLM 信心: {confidence*100:.1f}%, 边际: {edge*100:.1f}%)"
        )
        
        return MarketOpportunity(
            market_id=market.get("conditionId", ""),
            question=market.get("question", ""),
            outcome=outcome,
            current_price=current_price,
            predicted_probability=predicted_prob,
            confidence=confidence,
            expected_value=expected_value,
            news_signals=news_signals,
            risk_score=risk_score,
            volume=market.get("volume", 0),
            hours_to_expiry=hours_to_expiry
        )
    

