"""
辅助工具函数
"""
from typing import Dict, Any, Optional, Union
from datetime import datetime, timedelta


def safe_float(value: Any, default: float = 0.0) -> float:
    """
    安全地将值转换为 float
    
    Args:
        value: 要转换的值
        default: 默认值
    
    Returns:
        float 值
    """
    if value is None:
        return default
    
    try:
        return float(value)
    except (ValueError, TypeError):
        return default


def safe_int(value: Any, default: int = 0) -> int:
    """
    安全地将值转换为 int
    
    Args:
        value: 要转换的值
        default: 默认值
    
    Returns:
        int 值
    """
    if value is None:
        return default
    
    try:
        return int(float(value))
    except (ValueError, TypeError):
        return default


def calculate_kelly_size(
    edge: float,
    current_price: float,
    max_position: float,
    risk_limit: float,
    conservative_factor: float = 0.25
) -> float:
    """
    使用 Kelly Criterion 计算仓位大小
    
    Args:
        edge: 价格边际
        current_price: 当前价格
        max_position: 最大仓位
        risk_limit: 风险限额
        conservative_factor: 保守系数（默认 0.25）
    
    Returns:
        计算出的仓位大小
    """
    if current_price >= 1.0:
        return 0
    
    kelly_fraction = edge / (1 - current_price)
    raw_size = kelly_fraction * conservative_factor * max_position
    final_size = min(raw_size, risk_limit)
    
    return max(0, int(final_size))


def calculate_risk_score(
    volume: Union[float, str, int],
    hours_to_expiry: Optional[Union[float, str, int]],
    edge: Union[float, str, int]
) -> float:
    """
    计算风险评分
    
    Args:
        volume: 市场交易量
        hours_to_expiry: 到期小时数
        edge: 价格边际
    
    Returns:
        风险评分 (0-1)
    """
    # 使用安全转换函数
    volume = safe_float(volume, 0)
    edge = safe_float(edge, 0)
    hours_to_expiry = safe_float(hours_to_expiry, None) if hours_to_expiry is not None else None
    
    volume_risk = 0.3 if volume < 50000 else 0
    time_risk = 0.3 if hours_to_expiry and hours_to_expiry < 24 else 0
    edge_risk = 0.4 if edge < 0.1 else 0
    
    return volume_risk + time_risk + edge_risk


def parse_market_end_date(end_date_str: str) -> Optional[datetime]:
    """解析市场结束日期"""
    try:
        # 尝试多种日期格式
        formats = [
            "%Y-%m-%dT%H:%M:%S.%fZ",
            "%Y-%m-%dT%H:%M:%SZ",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d"
        ]
        
        for fmt in formats:
            try:
                return datetime.strptime(end_date_str, fmt)
            except ValueError:
                continue
        
        return None
    except Exception:
        return None


def hours_until_expiry(end_date: datetime) -> float:
    """计算到期剩余小时数"""
    now = datetime.utcnow()
    delta = end_date - now
    return delta.total_seconds() / 3600


def format_price(price: float) -> str:
    """格式化价格显示"""
    return f"${price:.2f}" if price >= 1 else f"{price*100:.1f}%"


def format_percentage(value: float) -> str:
    """格式化百分比显示"""
    return f"{value*100:.1f}%"


def truncate_text(text: str, max_length: int = 50) -> str:
    """截断文本"""
    if len(text) <= max_length:
        return text
    return text[:max_length-3] + "..."
