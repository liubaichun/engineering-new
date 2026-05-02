# 知识库索引

> 所有过程文件、技术沉淀、决策记录的永久存储位置。

## 目录结构

```
knowledge-base/
├── 01-requirements/          # 需求与规划
│   ├── BUSINESS_REQUIREMENTS.md      # 商业版需求报告 v2.0（主文档）
│   ├── SYSTEM_AUDIT_2026-04-29.md   # 代码审计报告
│   └── SPRINT_PLAN.md               # 迭代计划
│
├── 02-development/          # 开发过程记录
│   ├── CHANGELOG.md                  # 变更日志
│   ├── active/
│   │   ├── ISSUE_*.md               # 当前迭代问题追踪
│   │   └── SPRINT_*.md              # 当前迭代执行记录
│   └── history/                      # 历史迭代记录
│
├── 03-testing/              # 测试报告
│   ├── TEST_REPORT_*.md              # 各轮测试报告
│   └── VALIDATION_*.md               # 自动化验证结果
│
├── 04-deployment/            # 部署文档
│   ├── DEPLOY_GUIDE.md               # 部署指南
│   ├── DOCKER_DELIVERY.md             # Docker交付包说明
│   └── BACKUP_RECOVERY.md            # 备份恢复手册
│
├── 05-checklists/            # 检查清单
│   ├── PRE_DEPLOY_CHECKLIST.md       # 部署前检查
│   ├── CODE_REVIEW_CHECKLIST.md      # 代码审查清单
│   └── TEST_CHECKLIST.md             # 测试检查清单
│
├── 06-templates/            # 模板文件
│   ├── ISSUE_TEMPLATE.md              # 问题追踪模板
│   ├── SPRINT_TEMPLATE.md            # 迭代记录模板
│   └── COMMIT_TEMPLATE.md            # 提交规范模板
│
└── 07-notes/                 # 随手笔记
    ├── ARCHITECTURE_DECISIONS.md     # 架构决策记录
    ├── THIRD_PARTY_APIS.md           # 第三方API集成笔记
    └── KNOWN_ISSUES.md               # 已知问题
```

## 快速导航

### 当前迭代
- 📋 [需求报告](./01-requirements/BUSINESS_REQUIREMENTS.md)
- 🏃 [当前迭代计划](./01-requirements/SPRINT_PLAN.md)
- 🔴 [当前问题追踪](./02-development/active/)

### 核心文档
- 📖 [开发规范](../docs/STANDARDS.md)
- 🐛 [Bug修复记录](../docs/BUG_FIX_RECORD.md)
- ⚠️ [已知残留问题](./07-notes/KNOWN_ISSUES.md)

### 检查清单
- [ ] [部署前检查](../05-checklists/PRE_DEPLOY_CHECKLIST.md)
- [ ] [代码审查清单](../05-checklists/CODE_REVIEW_CHECKLIST.md)
- [ ] [测试检查清单](../05-checklists/TEST_CHECKLIST.md)

---

**维护原则**：
- 每个任务完成后立即归档，不堆积
- 决策记录即时写入 ARCHITECTURE_DECISIONS.md，不遗忘
- CHANGELOG.md 每次重要变更后更新
