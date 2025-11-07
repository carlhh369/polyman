"""
新闻服务模块
"""
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from newsapi import NewsApiClient
from config import config
from utils.logger import logger
from services.llm import llm_service
import json


class NewsArticle:
    """新闻文章类"""
    
    def __init__(self, data: Dict[str, Any]):
        self.title = data.get("title", "")
        self.description = data.get("description", "")
        self.url = data.get("url", "")
        self.source = data.get("source", {}).get("name", "")
        self.published_at = data.get("publishedAt", "")
        self.sentiment = "neutral"
        self.relevance_score = 0.5
    
    def __repr__(self):
        return f"<NewsArticle: {self.title[:50]}...>"


class NewsSignal:
    """新闻信号类"""
    
    def __init__(
        self,
        market: str,
        signal: str,
        confidence: float,
        articles: List[NewsArticle]
    ):
        self.market = market
        self.signal = signal  # bullish, bearish, neutral
        self.confidence = confidence
        self.articles = articles
    
    def __repr__(self):
        return f"<NewsSignal: {self.signal} ({self.confidence:.2f}) - {len(self.articles)} articles>"


class NewsService:
    """新闻服务类"""
    
    # 情绪词典
    POSITIVE_WORDS = [
        "surge", "soar", "rally", "boom", "growth", "gain", "rise",
        "increase", "positive", "success", "win", "victory", "breakthrough"
    ]
    
    NEGATIVE_WORDS = [
        "crash", "plunge", "fall", "decline", "drop", "loss", "fail",
        "negative", "crisis", "concern", "worry", "risk", "threat"
    ]
    
    def __init__(self):
        if not config.NEWS_API_KEY:
            logger.warning("未配置 NEWS_API_KEY，新闻功能将受限")
            self.client = None
        else:
            self.client = NewsApiClient(api_key=config.NEWS_API_KEY)
        
        # 使用统一的 LLM 服务
        self.use_llm = llm_service.is_enabled()
        if self.use_llm:
            logger.info("✓ 新闻服务将使用 LLM 进行智能分析")
        else:
            logger.info("新闻服务使用规则式方法")
    
    def search_news(self, query: str, days_back: int = 7) -> List[NewsArticle]:
        """
        搜索新闻
        
        Args:
            query: 搜索关键词
            days_back: 搜索过去几天的新闻
        
        Returns:
            新闻文章列表
        """
        if not self.client:
            logger.warning("新闻客户端未初始化")
            return []
        
        try:
            from_date = (datetime.now() - timedelta(days=days_back)).strftime("%Y-%m-%d")
            
            response = self.client.get_everything(
                q=query,
                language="en",
                sort_by="relevancy",
                page_size=50,
                from_param=from_date
            )
            
            articles = [NewsArticle(article) for article in response.get("articles", [])]
            
            # 分析情绪
            for article in articles:
                article.sentiment = self._analyze_sentiment(
                    f"{article.title} {article.description}"
                )
            
            logger.info(f"搜索到 {len(articles)} 篇相关新闻: {query}")
            return articles
            
        except Exception as e:
            logger.error(f"搜索新闻失败: {e}")
            return []
    
    def get_market_signals(
        self,
        market_title: str,
        market_rules: Optional[str] = None
    ) -> NewsSignal:
        """
        获取市场新闻信号
        
        Args:
            market_title: 市场标题
            market_rules: 市场规则（可选）
        
        Returns:
            新闻信号
        """
        # 提取搜索关键词
        keywords = self._extract_keywords(market_title)
        
        # 搜索新闻
        articles = self.search_news(keywords)
        
        if not articles:
            return NewsSignal(
                market=market_title,
                signal="neutral",
                confidence=0.0,
                articles=[]
            )
        
        # 使用 LLM 或规则式方法分析
        if self.use_llm:
            return self._analyze_with_llm(market_title, market_rules, articles)
        else:
            return self._analyze_rule_based(market_title, articles)
    
    def _analyze_rule_based(
        self,
        market_title: str,
        articles: List[NewsArticle]
    ) -> NewsSignal:
        """
        基于规则的市场信号分析
        
        Args:
            market_title: 市场标题
            articles: 新闻文章列表
        
        Returns:
            新闻信号
        """
        # 分析情绪
        positive_count = sum(1 for a in articles if a.sentiment == "positive")
        negative_count = sum(1 for a in articles if a.sentiment == "negative")
        total = len(articles)
        
        positive_ratio = positive_count / total if total > 0 else 0
        negative_ratio = negative_count / total if total > 0 else 0
        
        # 确定信号
        if positive_ratio > 0.6:
            signal = "bullish"
            confidence = positive_ratio
        elif negative_ratio > 0.6:
            signal = "bearish"
            confidence = negative_ratio
        else:
            signal = "neutral"
            confidence = 0.5
        
        # 根据文章数量调整信心度
        article_bonus = min(0.2, len(articles) * 0.02)
        confidence = min(0.95, confidence + article_bonus)
        
        logger.info(
            f"市场信号 (规则式): {market_title[:50]}... -> {signal} "
            f"({confidence*100:.1f}% 信心, {len(articles)} 篇文章)"
        )
        
        return NewsSignal(
            market=market_title,
            signal=signal,
            confidence=confidence,
            articles=articles[:5]
        )
    
    def _analyze_with_llm(
        self,
        market_title: str,
        market_rules: Optional[str],
        articles: List[NewsArticle]
    ) -> NewsSignal:
        """
        使用大模型进行市场信号分析
        
        Args:
            market_title: 市场标题
            market_rules: 市场规则
            articles: 新闻文章列表
        
        Returns:
            新闻信号
        """
        try:
            # 准备新闻摘要
            news_summary = "\n".join([
                f"- {a.title} ({a.source}): {a.description[:100]}..."
                for a in articles[:10]
            ])
            
            # 构建提示词
            prompt = f"""You are a prediction market analyst. Analyze the following news articles and determine the market signal.

Market Question: {market_title}
{f"Market Rules: {market_rules}" if market_rules else ""}

Recent News Articles:
{news_summary}

Based on these news articles, provide your analysis in the following JSON format:
{{
    "signal": "bullish" or "bearish" or "neutral",
    "confidence": 0.0 to 1.0,
    "reasoning": "brief explanation"
}}

Analysis:"""
            
            response = llm_service.call(prompt, max_tokens=300)
            
            # 解析 JSON 响应
            # 尝试提取 JSON
            json_start = response.find('{')
            json_end = response.rfind('}') + 1
            if json_start >= 0 and json_end > json_start:
                json_str = response[json_start:json_end]
                result = json.loads(json_str)
                
                signal = result.get("signal", "neutral")
                confidence = float(result.get("confidence", 0.5))
                reasoning = result.get("reasoning", "")
                
                # 验证信号值
                if signal not in ["bullish", "bearish", "neutral"]:
                    signal = "neutral"
                
                # 限制信心度范围
                confidence = max(0.0, min(1.0, confidence))
                
                logger.info(
                    f"市场信号 (LLM): {market_title[:50]}... -> {signal} "
                    f"({confidence*100:.1f}% 信心, {len(articles)} 篇文章)"
                )
                logger.info(f"LLM 推理: {reasoning}")
                
                return NewsSignal(
                    market=market_title,
                    signal=signal,
                    confidence=confidence,
                    articles=articles[:5]
                )
            else:
                raise ValueError("无法从响应中提取 JSON")
                
        except Exception as e:
            logger.error(f"LLM 市场分析失败: {e}，回退到规则式方法")
            return self._analyze_rule_based(market_title, articles)
    
    def _extract_keywords(self, market_title: str) -> str:
        """
        从市场标题提取关键词（支持 LLM 或规则式）
        
        Args:
            market_title: 市场标题
        
        Returns:
            关键词字符串
        """
        if self.use_llm:
            return self._extract_keywords_with_llm(market_title)
        else:
            return self._extract_keywords_rule_based(market_title)
    
    def _extract_keywords_rule_based(self, market_title: str) -> str:
        """
        基于规则的关键词提取
        
        Args:
            market_title: 市场标题
        
        Returns:
            关键词字符串
        """
        # 移除常见词汇
        stop_words = ["will", "before", "after", "by", "in", "the", "and", "or", "?"]
        
        words = market_title.lower().split()
        keywords = [w for w in words if w not in stop_words and len(w) > 3]
        
        # 返回前 3 个关键词
        return " ".join(keywords[:3])
    
    def _extract_keywords_with_llm(self, market_title: str) -> str:
        """
        使用大模型提取关键词
        
        Args:
            market_title: 市场标题
        
        Returns:
            关键词字符串
        """
        try:
            prompt = f"""Extract the most important keywords from the following prediction market question for news search.
Return 2-4 keywords that would be most relevant for finding related news articles.
Respond with ONLY the keywords separated by spaces, no explanation.

Question: {market_title}

Keywords:"""
            
            response = llm_service.call(prompt, max_tokens=30)
            keywords = response.strip()
            
            # 验证返回值不为空
            if keywords and len(keywords.split()) >= 1:
                logger.debug(f"LLM 提取关键词: '{market_title}' -> '{keywords}'")
                return keywords
            else:
                logger.warning(f"LLM 返回了空关键词，使用规则式方法")
                return self._extract_keywords_rule_based(market_title)
                
        except Exception as e:
            logger.error(f"LLM 关键词提取失败: {e}，回退到规则式方法")
            return self._extract_keywords_rule_based(market_title)
    
    def _analyze_sentiment(self, text: str) -> str:
        """
        情绪分析（支持 LLM 或规则式）
        
        Args:
            text: 文本内容
        
        Returns:
            情绪: positive, negative, neutral
        """
        if self.use_llm:
            return self._analyze_sentiment_with_llm(text)
        else:
            return self._analyze_sentiment_rule_based(text)
    
    def _analyze_sentiment_rule_based(self, text: str) -> str:
        """
        基于规则的情绪分析
        
        Args:
            text: 文本内容
        
        Returns:
            情绪: positive, negative, neutral
        """
        text_lower = text.lower()
        
        positive_score = sum(1 for word in self.POSITIVE_WORDS if word in text_lower)
        negative_score = sum(1 for word in self.NEGATIVE_WORDS if word in text_lower)
        
        if positive_score > negative_score + 1:
            return "positive"
        elif negative_score > positive_score + 1:
            return "negative"
        else:
            return "neutral"
    
    def _analyze_sentiment_with_llm(self, text: str) -> str:
        """
        使用大模型进行情绪分析
        
        Args:
            text: 文本内容
        
        Returns:
            情绪: positive, negative, neutral
        """
        try:
            prompt = f"""Analyze the sentiment of the following news text. 
Respond with ONLY ONE WORD: "positive", "negative", or "neutral".

Text: {text[:500]}

Sentiment:"""
            
            response = llm_service.call(prompt, max_tokens=10)
            sentiment = response.strip().lower()
            
            # 验证返回值
            if sentiment in ["positive", "negative", "neutral"]:
                return sentiment
            else:
                logger.warning(f"LLM 返回了无效的情绪值: {sentiment}，使用规则式方法")
                return self._analyze_sentiment_rule_based(text)
                
        except Exception as e:
            logger.error(f"LLM 情绪分析失败: {e}，回退到规则式方法")
            return self._analyze_sentiment_rule_based(text)
    

