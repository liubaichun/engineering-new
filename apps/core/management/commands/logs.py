"""
CLI 日志查看工具 — 按级别/模块/关键词过滤，支持 tail 模式。

用法：
  python manage.py logs                          # 最近20条
  python manage.py logs --level WARNING          # 只看警告+
  python manage.py logs --module invoice         # 只看发票模块
  python manage.py logs --search "error"         # 关键词搜索
  python manage.py logs --tail                   # 实时追踪 (like tail -f)
  python manage.py logs --today                  # 今天的日志
  python manage.py logs --count 100              # 显示条数
  python manage.py logs --json                   # JSON原始格式
"""

import gzip
import json
import time
from datetime import date, datetime
from pathlib import Path

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = '查看/搜索结构化日志'

    def add_arguments(self, parser):
        parser.add_argument('--level', '-l', help='过滤级别 (DEBUG/INFO/WARNING/ERROR/CRITICAL)')
        parser.add_argument('--module', '-m', help='按模块名过滤')
        parser.add_argument('--search', '-s', help='关键词搜索')
        parser.add_argument('--tail', '-f', action='store_true', help='实时追踪日志')
        parser.add_argument('--today', action='store_true', help='只显示今天的日志')
        parser.add_argument('--count', '-n', type=int, default=20, help='显示条数 (默认20)')
        parser.add_argument('--json', action='store_true', help='输出原始JSON格式')
        parser.add_argument('--after', type=str, help='从指定时间后筛选 (YYYY-MM-DD HH:MM)')

    def handle(self, *args, **options):
        log_dir = self._find_log_dir()
        if not log_dir:
            self.stderr.write('❌ 未找到日志目录')
            return

        log_file = log_dir / 'django.log'
        if not log_file.exists():
            self.stderr.write(f'❌ 日志文件不存在: {log_file}')
            return

        if options['tail']:
            self._tail(log_file, options)
        else:
            self._search(log_file, options)

    def _find_log_dir(self):
        """找到日志目录"""
        from django.conf import settings

        log_dir = getattr(settings, 'LOGGING', {}).get('handlers', {}).get('file', {}).get('filename')
        if log_dir:
            return Path(log_dir).parent
        # 回退
        for p in [Path.cwd() / 'logs', Path('/root/engineering-new/logs')]:
            if p.exists():
                return p
        return None

    def _parse_line(self, line):
        """尝试解析JSON日志行"""
        line = line.strip()
        if not line:
            return None
        try:
            return json.loads(line)
        except json.JSONDecodeError:
            return None

    def _matches(self, entry, options):
        """检查日志条目是否匹配过滤条件"""
        if not entry:
            return False
        if options['level']:
            level_str = options['level'].upper()
            if entry.get('levelname', '').upper() != level_str:
                return False
        if options['module']:
            if options['module'].lower() not in entry.get('module', '').lower():
                return False
        if options['search']:
            text = json.dumps(entry, ensure_ascii=False)
            if options['search'].lower() not in text.lower():
                return False
        if options['after']:
            try:
                after_dt = datetime.strptime(options['after'], '%Y-%m-%d %H:%M')
                log_dt_str = entry.get('asctime', '')
                if log_dt_str:
                    log_dt = datetime.strptime(log_dt_str[:19], '%Y-%m-%d %H:%M:%S')
                    if log_dt < after_dt:
                        return False
            except (ValueError, IndexError):
                pass
        if options['today']:
            today_str = date.today().isoformat()
            log_dt = entry.get('asctime', '')
            if not log_dt.startswith(today_str):
                return False
        return True

    def _search(self, log_file, options):
        """搜索日志文件"""
        lines = []
        # 读取当前日志
        with open(log_file, 'r') as f:
            lines = f.readlines()
        # 读取轮转日志 (django.log.1, django.log.2.gz, ...)
        for i in range(1, 31):
            rotated = log_file.parent / f'django.log.{i}'
            if rotated.exists():
                with open(rotated, 'r') as f:
                    lines = f.readlines() + lines  # 旧的放前面
            gz_file = log_file.parent / f'django.log.{i}.gz'
            if gz_file.exists():
                try:
                    with gzip.open(gz_file, 'rt') as f:
                        lines = f.readlines() + lines
                except Exception:
                    pass

        matched = []
        for line in lines:
            entry = self._parse_line(line)
            if self._matches(entry, options):
                matched.append(entry)

        # 只显示最新的 N 条
        count = options['count']
        matched = matched[-count:] if len(matched) > count else matched

        if not matched:
            self.stdout.write('(无匹配日志条目)')
            return

        self.stdout.write(f'📋 匹配 {len(matched)} 条日志 (显示最近 {count} 条):')
        self.stdout.write('─' * 72)
        for entry in matched:
            if options['json']:
                self.stdout.write(json.dumps(entry, ensure_ascii=False))
            else:
                level = entry.get('levelname', '').ljust(8)
                ts = entry.get('asctime', '')[:19]
                mod = entry.get('module', '').ljust(15)[:15]
                msg = entry.get('message', '')
                self.stdout.write(f'{ts} | {level} | {mod} | {msg}')

    def _tail(self, log_file, options):
        """实时追踪日志"""
        self.stdout.write('🔍 实时追踪日志中 (Ctrl+C 退出)...')
        self.stdout.write('─' * 72)
        try:
            with open(log_file, 'r') as f:
                # 跳到文件末尾
                f.seek(0, 2)
                while True:
                    line = f.readline()
                    if line:
                        entry = self._parse_line(line)
                        if self._matches(entry, options):
                            ts = entry.get('asctime', '')[:19]
                            level = entry.get('levelname', '').ljust(8)
                            mod = entry.get('module', '').ljust(15)[:15]
                            msg = entry.get('message', '')
                            self.stdout.write(f'{ts} | {level} | {mod} | {msg}')
                    else:
                        time.sleep(0.5)
        except KeyboardInterrupt:
            self.stdout.write('\n👋 退出')
