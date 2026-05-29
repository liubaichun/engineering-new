import os
import re
from django.conf import settings
from django.http import Http404
from django.views.generic import TemplateView


def markdown_to_html(content):
    """将 Markdown 转换为基本 HTML"""
    import markdown

    md = markdown.Markdown(extensions=['tables', 'fenced_code'])
    return md.convert(content)


class DocPageView(TemplateView):
    """渲染 docs/ 目录下的 Markdown 文档"""

    template_name = 'doc_page.html'

    def get_doc_file(self, doc_name):
        """根据文档名查找文件（doc_name 支持 - 和 _ 两种分隔符）"""
        import re

        # 规范化 doc_name：压缩连续分隔符 + 统一小写
        def norm(s):
            return re.sub(r'[-_]+', '_', s).lower()

        doc_name_norm = doc_name.replace('-', '_')  # 连字符→下划线
        doc_name_hyphen = doc_name.replace('_', '-')  # 下划线→连字符

        search_patterns = [norm(doc_name), norm(doc_name_norm), norm(doc_name_hyphen)]
        search_patterns = list(dict.fromkeys(search_patterns))  # 去重

        dirs_to_search = [
            os.path.join(settings.BASE_DIR, 'docs'),
            settings.BASE_DIR,
        ]

        for d in dirs_to_search:
            if not os.path.isdir(d):
                continue
            for fname in os.listdir(d):
                f_lower = fname.lower()
                if not (f_lower.endswith('.md') or f_lower.endswith('.html')):
                    continue
                base = os.path.splitext(fname)[0].lower()
                base_norm = re.sub(r'[-_]+', '_', base)
                for pat in search_patterns:
                    if base_norm == pat:
                        return os.path.join(d, fname)
        return None

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        doc_name = kwargs.get('doc_name', '')
        doc_path = self.get_doc_file(doc_name)
        if not doc_path:
            raise Http404(f'文档不存在: {doc_name}')
        with open(doc_path, 'r', encoding='utf-8') as f:
            raw = f.read()
        # 提取标题
        title_match = re.search(r'^#\s+(.+)$', raw, re.MULTILINE)
        title = title_match.group(1) if title_match else doc_name
        ctx['doc_title'] = title
        ctx['doc_content'] = markdown_to_html(raw)
        ctx['doc_name'] = doc_name
        return ctx
