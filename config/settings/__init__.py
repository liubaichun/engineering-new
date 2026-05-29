"""
Settings 包入口 — 环境路由。

使用方式：
  DJANGO_SETTINGS_MODULE=config.settings        → 开发环境
  DJANGO_SETTINGS_MODULE=config.settings.prod   → 生产环境
  DJANGO_SETTINGS_MODULE=config.settings.dev    → 开发环境（显式）

当省略子模块（直接引用 config.settings）时，默认加载 dev 配置。
"""
import os

# 默认使用 dev 配置
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.dev')

# 根据 DJANGO_SETTINGS_MODULE 加载对应模块
# 如果值是 config.settings（包本身），则从 dev 导入所有属性
from .dev import *  # noqa: F401, F403, E402
