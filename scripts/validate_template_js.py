#!/usr/bin/env python3
"""
验证 bank_statement_import.html 模板中的 JS 语法（括号/引号平衡）
Django 模板标签 {{ }} 会被 Django 渲染后才会执行 JS，
所以这里只检查 JS 代码块的括号/引号对是否平衡。
"""

import re
import sys


def validate_js_brackets(script_content):
    """检查 JS 中括号对是否平衡"""
    issues = []
    stack = []
    in_string = None
    escape_next = False

    for i, char in enumerate(script_content):
        if escape_next:
            escape_next = False
            continue

        if char == '\\':
            escape_next = True
            continue

        if in_string:
            if char == in_string:
                in_string = None
            continue

        if char in ('"', "'", '`'):
            in_string = char
            continue

        if char in '({[':
            stack.append((char, i))
        elif char in ')}]':
            if not stack:
                issues.append(f"Position {i}: unexpected closing '{char}'")
            else:
                open_char, open_pos = stack.pop()
                pairs = {'(': ')', '{': '}', '[': ']'}
                if pairs.get(open_char) != char:
                    issues.append(f"Position {i}: '{char}' doesn't match '{open_char}' at position {open_pos}")

    for char, pos in stack:
        issues.append(f"Position {pos}: unclosed '{char}'")

    return issues


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else 'templates/finance/bank_statement_import.html'

    with open(path) as f:
        html = f.read()

    # 提取所有 <script> 内容
    scripts = re.findall(r'<script>(.*?)</script>', html, re.DOTALL)

    if not scripts:
        print('No script found')
        sys.exit(1)

    main_script = scripts[0]

    # 移除 Django 模板标签
    clean = re.sub(r'\{\{[^}]+\}\}', 'XXX', main_script)

    # 检查括号平衡
    issues = validate_js_brackets(clean)

    if issues:
        print(f'JS syntax issues ({len(issues)}):')
        for issue in issues[:10]:
            print(f'  {issue}')
        sys.exit(1)
    else:
        print(f'JS syntax OK ({len(main_script)} chars)')


if __name__ == '__main__':
    main()
