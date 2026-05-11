# ── 兼容引用 ──────────────────────────────────────────────────────────────────
# BankAccount 和 BankStatement 已移至 finance.models.py
# 此文件保留以确保所有 from .models_bank 的旧引用仍然有效
from apps.finance.models import BankAccount, BankStatement

__all__ = ['BankAccount', 'BankStatement']
