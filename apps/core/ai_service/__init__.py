"""
ERP AI 服务层 — 单例外观

用法:
    from apps.core.ai_service import ai

    # 文本对话
    resp = ai.chat(messages=[{"role": "user", "content": "你好"}])

    # 结构化提取
    plans = ai.extract(text=ocr_text, schema="提取付款计划JSON数组")

    # 分析推理
    result = ai.analyze(prompt="分析这个数据...")

    # 模型管理
    ai.switch_model('gpt-4o')
    ai.get_current_model()
"""

from .service import AIService

# 应用级单例（每个 worker 进程独立）
ai = AIService()

__all__ = ['ai', 'AIService']
