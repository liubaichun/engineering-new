# GREEN ERP Code Quality & Security Pattern Analysis

**Generated:** 2026-05-29  
**Scope:** 195 Python files (excluding migrations, venv, __pycache__) in /root/engineering-new/

---

## CRITICAL

### 1. `objects.get()` without try/except — Potential 500 errors
`objects.get()` raises `DoesNotExist` if no record is found. 46 calls found without exception handling. Key locations in production code:

| File | Line | Code |
|------|------|------|
| `apps/approvals/services.py` | 58 | `return User.objects.get(id=approver_id, is_active=True)` |
| `apps/approvals/services.py` | 114 | `expense_obj = ExpenseModel.objects.get(id=expense.id)` |
| `apps/approvals/services.py` | 167 | `income_obj = IncomeModel.objects.get(id=income.id)` |
| `apps/approvals/views.py` | 41 | `project = Project.objects.get(pk=flow.related_id)` |
| `apps/approvals/views.py` | 70 | `obj = ModelClass.objects.get(pk=flow.related_id)` |
| `apps/approvals/views.py` | 306 | `target_user = User.objects.get(id=target_user_id)` |
| `apps/approvals/views.py` | 363 | `delegate_user = User.objects.get(id=delegate_user_id)` |
| `apps/tasks/views.py` | 143 | `return User.objects.get(username=value)` |
| `apps/tasks/views.py` | 720 | `template = FlowTemplate.objects.get(id=template_id)` |
| `apps/tasks/flow_engine.py` | 29 | `template = FlowTemplate.objects.get(id=template, is_active=True)` |
| `apps/tasks/flow_engine.py` | 31 | `template = FlowTemplate.objects.get(id=template.get('id'), is_active=True)` |
| `apps/tasks/flow_engine.py` | 90 | `return User.objects.get(id=int(node.assignee_value))` |
| `apps/tasks/flow_engine.py` | 106 | `node_template = FlowNodeTemplate.objects.get(id=node_template_or_id)` |
| `apps/tasks/flow_engine.py` | 108 | `node_template = FlowNodeTemplate.objects.get(id=node_template_or_id.get('id'))` |
| `apps/finance/views.py` | 749 | `trigger_approval = SystemSetting.objects.get(...)` |
| `apps/finance/views.py` | 1515 | `stmt = BankStatement.objects.get(id=statement_id, ...)` |
| `apps/finance/tax_invoice_import.py` | 494 | `company = Company.objects.get(id=company_id)` |
| `apps/finance/tax_invoice_import.py` | 544 | `company = Company.objects.get(id=company_id)` |
| `apps/finance/classification_rules.py` | 34 | `return Account.objects.get(code=code, company__isnull=True)` |
| `apps/finance/bank_import_views.py` | 700 | `company = Company.objects.get(id=company_id)` |
| `apps/finance/bank_import_views.py` | 931 | `company = Company.objects.get(id=company_id)` |
| `apps/crm/views.py` | 385 | `co = Contract.objects.get(pk=contract.pk)` |
| `apps/core/tenant_resolver.py` | 52 | `return Company.objects.get(id=settings.DEFAULT_COMPANY_ID)` |
| `apps/core/serializers.py` | 73 | `user = User.objects.get(username=username)` |
| `apps/core/views.py` | 130 | `user = User.objects.get(pk=uid)` |
| `apps/core/views.py` | 377 | `company = Company.objects.get(id=company_id)` |
| `apps/core/views.py` | 431 | `company = Company.objects.get(id=company_id)` |
| `apps/core/views.py` | 680 | `user = User.objects.get(id=uid, is_active=False)` |
| `apps/core/views.py` | 1260 | `company = Company.objects.get(id=company_id)` |
| `apps/core/views.py` | 1349 | `action_obj = ModuleAction.objects.get(module=ump.module, name=action_name)` |
| `apps/core/middleware.py` | 39 | `company = Company.objects.get(id=company_id)` |
| `apps/core/middleware.py` | 52 | `company = Company.objects.get(id=first_ucp.company_id)` |
| `apps/core/middleware.py` | 75 | `company = Company.objects.get(id=settings.DEFAULT_COMPANY_ID)` |
| `apps/channels/views.py` | 98 | `user = User.objects.get(id=user_id)` |
| `apps/channels/views.py` | 312 | `target_user = User.objects.get(id=target_user_id)` |
| `apps/equipment/views.py` | 225 | `rel = EquipmentBOMRelation.objects.get(pk=bom_id, equipment_id=pk)` |
| `apps/notifications/views.py` | 61 | `rule = NotificationRouterRule.objects.get(pk=pk, company_id=company_id)` |
| `apps/notifications/views.py` | 105 | `rule = NotificationRouterRule.objects.get(pk=pk, company_id=company_id)` |
| `apps/purchasing/views.py` | 147 | `pr = PurchaseRequest.objects.get(pk=request_id.pk)` |
| `apps/purchasing/views.py` | 296 | `po = PurchaseOrder.objects.get(pk=order_id.pk)` |
| `apps/purchasing/views.py` | 398 | `pr = PurchaseReceive.objects.get(pk=receive_id.pk)` |
| `apps/material/views.py` | 241 | `node = MaterialBOMNode.objects.get(pk=node_id, bom_id=pk)` |
| `apps/material/views.py` | 251 | `node = MaterialBOMNode.objects.get(pk=node_id, bom_id=pk)` |
| `apps/material/views.py` | 296 | `item = MaterialBOMNode.objects.get(pk=item_id, bom_id=pk)` |
| `apps/material/views.py` | 306 | `item = MaterialBOMNode.objects.get(pk=item_id, bom_id=pk)` |
| `apps/notifications/management/commands/check_alerts.py` | 115 | `timeout_hours = int(SystemSetting.objects.get(key='approval_timeout_hours').value)` |
| `apps/notifications/management/commands/check_alerts.py` | 119 | `escalate_enabled = SystemSetting.objects.get(key='approval_escalate_enabled').value == 'true'` |

### 2. `.save()` without exception handling — 93 calls found
Most `.save()` calls lack try/except blocks. Key areas without wrapping:
- `apps/approvals/views.py` — 16 calls (lines 152-426)
- `apps/crm/views.py` — 13 calls (lines 64-549)
- `apps/crm/serializers.py` — 6 calls (lines 40-188)
- `apps/finance/views.py` — 22 calls (lines 217-2663)
- `apps/finance/admin.py` — 3 calls (lines 138-182)
- `apps/tasks/views.py` — 11 calls (lines 438-1238)
- `apps/channels/views.py` — 4 calls (lines 376-626)
- `apps/core/views.py` — 7 calls (lines 138-1454)
- `apps/core/serializers.py` — 1 call (line 46)
- `apps/equipment/views.py` — 4 calls (lines 78-165)

### 3. Raw SQL queries — `extra()` used
**File:** `apps/core/permissions.py`  
- Line 101: `).extra(where=["granted_bits & %d = %d" % (bit, bit)]).exists()`  
- Line 343: `).extra(where=["granted_bits & %d = %d" % (bit, bit)]).exists()`  
- Line 374: `).extra(where=["granted_bits & %d = %d" % (bit, bit)])`  
These use string formatting for SQL parameters — potential SQL injection if parameters come from user input.

---

## WARNING

### 4. `filter()` without `order_by()` — potential pagination inconsistency
Queryset results without explicit ordering can produce different page-to-page results:

| File | Line | Code |
|------|------|------|
| `apps/finance/views.py` | 679 | `ec_qs = EmployeeCompany.objects.filter(employee_id=emp_id)` |
| `apps/finance/views.py` | 136 | `queryset = Model.objects.filter(company_id__in=company_ids)` |
| `apps/finance/views.py` | 2529 | `ar_qs = Invoice.objects.filter(type='income', status='pending')` |
| `apps/finance/views.py` | 2530 | `ap_qs = Invoice.objects.filter(type='expense', status='pending')` |
| `apps/finance/views.py` | 2574 | `qs = Invoice.objects.filter(type='income', status='pending')` |
| `apps/finance/views.py` | 2590 | `qs = Invoice.objects.filter(type='expense', status='pending')` |
| `apps/finance/reports_v2.py` | 239 | `ar_qs = Invoice.objects.filter(type='income', status='pending')` |
| `apps/finance/reports_v2.py` | 240 | `ap_qs = Invoice.objects.filter(type='expense', status='pending')` |
| `apps/finance/reports_v2.py` | 489 | `inv_qs = Invoice.objects.filter(company=company)` |
| `apps/finance/reports_v2.py` | 534 | `sr_q = SocialRecord.objects.filter(company=company)` |
| `apps/finance/classification_rules.py` | 286 | `accounts = BankAccount.objects.filter(company_id=company_id)` |
| `apps/tasks/flow_engine.py` | 246 | `instances = TaskStageInstance.objects.filter(task=self.task)` |
| `apps/finance/management/commands/check_accounting.py` | 25 | `companies = Company.objects.filter(status='active')` |

### 5. `.all()` calls in views — potential N+1 or missing filters
Many views expose unfiltered querysets:

| File | Line | Model |
|------|------|-------|
| `apps/material/views.py` | 35 | `Material.objects.all()` |
| `apps/material/views.py` | 149 | `MaterialBOM.objects.all()` |
| `apps/tasks/views.py` | 392 | `Project.objects.all()` |
| `apps/tasks/views.py` | 604 | `Task.objects.all()` |
| `apps/tasks/views.py` | 799 | `FlowTemplate.objects.all()` |
| `apps/tasks/views.py` | 835 | `FlowNodeTemplate.objects.all()` |
| `apps/tasks/views.py` | 862 | `TaskStageInstance.objects.all()` |
| `apps/tasks/views.py` | 974 | `StageActivity.objects.all()` |
| `apps/tasks/views.py` | 1000 | `FlowTransition.objects.all()` |
| `apps/tasks/views.py` | 1034 | `TaskFlowInstance.objects.all()` |
| `apps/tasks/views.py` | 1163 | `TaskComment.objects.all()` |
| `apps/tasks/views.py` | 1185 | `TaskAttachment.objects.all()` |
| `apps/tasks/views.py` | 1208 | `TaskDependency.objects.all()` |
| `apps/core/views.py` | 493 | `User.objects.all()` |
| `apps/core/views.py` | 770 | `Notification.objects.all()` |
| `apps/core/views.py` | 826 | `PermissionAuditLog.objects.all()` |
| `apps/core/views.py` | 853 | `LoginLog.objects.all()` |
| `apps/core/views.py` | 889 | `OperationAuditLog.objects.all()` |
| `apps/core/views.py` | 946 | `SystemSetting.objects.all()` |
| `apps/channels/views.py` | 1017 | `NotificationLog.objects.all()` |
| `apps/crm/views.py` | 17, 39, 78, 117, 276, 356, 392, 424, 457 | Various models |
| `apps/purchasing/views.py` | 19, 122, 170, 271, 323, 373 | Various models |
| `apps/equipment/views.py` | 33, 196 | `Equipment.objects.all()`, `EquipmentBOMRelation.objects.all()` |
| `apps/repair/views.py` | 15, 172, 181, 197 | `RepairRequest.objects.all()`, etc. |
| `apps/files/views.py` | 35, 49 | `FileCategory.objects.all()`, `CompanyFile.objects.all()` |
| `apps/finance/views.py` | 134, 201, 270, 463, 642, 1337, 2389, 2484, 2603, 2635, 2691, 2769 | Various models |

### 6. `objects.filter()` returning unlimited results (no `.first()` / no limit)
Many `filter()` calls could return many rows without `.first()` or slicing:

| File | Line | Potential Issue |
|------|------|-----------------|
| `apps/core/views.py` | 967 | `SystemSetting.objects.all()` in dict comprehension |
| `apps/core/views.py` | 1392 | `Module.objects.all()` in dict comprehension |
| `apps/core/views.py` | 1398 | `ModuleAction.objects.all()` in dict comprehension |
| `apps/finance/reports_v2.py` | 61 | `model.objects.all()` |
| `apps/finance/reports_v2.py` | 89 | `Company.objects.all()` |
| `apps/core/import_excel.py` | 165-166 | `Company.objects.all()`, `Project.objects.all()` built into dicts |
| `apps/channels/views.py` | 389 | `ChannelPlugin.objects.filter(is_deleted=False)` |
| `apps/channels/services.py` | 62, 196 | `ChannelPlugin.objects.filter(...)` |
| `apps/approvals/views.py` | 115-125 | `queryset.filter(...)` chained |

### 7. `ForeignKey` with `on_delete=models.CASCADE` that may need PROTECT
These could cause unintended cascading data loss for business-critical relations:

| File | Line | Field |
|------|------|-------|
| `apps/finance/models.py` | 853 | `SocialRecord.company` → CASCADE |
| `apps/finance/models.py` | 858 | `SocialRecord.employee` → CASCADE |
| `apps/finance/models.py` | 1012 | `BankStatement.company` → CASCADE |
| `apps/finance/models.py` | 1118 | `Budget.company` → CASCADE |
| `apps/finance/models.py` | 294 | `WageRecord.company` → CASCADE |
| `apps/core/models.py` | 75 | `UserCompanyRole.company` → CASCADE |
| `apps/core/models.py` | 432 | `ModuleAction.module` → CASCADE |
| `apps/core/models.py` | 475-478 | `UserCompanyPermission` all FK → CASCADE |
| `apps/core/models.py` | 542-544 | `UserModulePermission` all FK → CASCADE |
| `apps/channels/models.py` | 30 | `ChannelPlugin.company` → CASCADE |
| `apps/channels/models.py` | 199 | `NotificationRouterRule.company` → CASCADE |
| `apps/material/models.py` | 108 | `MaterialBOMItem.child_material` → CASCADE |
| `apps/crm/models.py` | 8, 28, 89, 159, 308, 337, 395 | Various `Company` FK → CASCADE |
| `apps/tasks/models.py` | 102 | `Task.project` → CASCADE |
| `apps/tasks/models.py` | 229 | `TaskStageInstance.task` → CASCADE |
| `apps/tasks/models.py` | 352 | `TaskComment.task` → CASCADE |
| `apps/tasks/models.py` | 454, 458 | `TaskDependency.task` / `depends_on` → CASCADE |

### 8. `except Exception` without logging
While `except Exception` is present with `as e`, many have bare `except Exception:` with no logging:

| File | Line | Code |
|------|------|------|
| `apps/approvals/views.py` | 335 | `except Exception:` |
| `apps/approvals/views.py` | 393 | `except Exception:` |
| `apps/tasks/views.py` | 442 | `except Exception:` |
| `apps/tasks/views.py` | 504 | `except Exception:` |
| `apps/repair/views.py` | 84, 99, 118, 135, 150, 165 | 6x `except Exception:` |
| `apps/finance/serializers.py` | 141, 217, 265 | 3x `except Exception:` |
| `apps/finance/bank_import_views.py` | 458, 735, 744, 789, 797, 995, 1007 | 7x `except Exception:` |
| `apps/finance/bank_adapters.py` | 110, 204, 231, 303, 327, 387, 410, 463, 485, 538, 560, 613, 635, 688, 753, 791, 832, 854, 906, 938, 946 | 21x `except Exception:` |
| `apps/finance/reports_v2.py` | 347, 357 | 2x `except Exception:` |
| `apps/crm/views.py` | 153, 187, 202 | 3x `except Exception:` |
| `apps/equipment/views.py` | 109, 127, 169 | 3x `except Exception:` |
| `apps/core/audit.py` | 69 | `except Exception:` |
| `config/schema.py` | 188 | `except Exception:` |
| `gunicorn.conf.py` | 20 | `except Exception:` |
| `apps/finance/views.py` | 20, 31 | 2x `except Exception:` |

### 9. `print()` statements in production code
Numerous `print()` calls in application code (not just scripts/tmp files):

| File | Line | Context |
|------|------|---------|
| `apps/finance/import_social_records.py` | Multiple | Debug prints in import logic |
| `apps/core/import_excel.py` | Multiple | Possible debug prints |
| (Most `print()` calls are in `tmp_*` and `scripts/` files which are outside production flow) |

---

## INFO

### 10. `null=True` fields that could cause None errors in templates
Critical `null=True` fields without safe access patterns:

| File | Line | Field |
|------|------|-------|
| `apps/crm/models.py` | 51-57 | `Client.contact_person`, `contact_phone`, `contact_email`, `address`, `remark` |
| `apps/crm/models.py` | 122-126 | `Client` (duplicate pattern) |
| `apps/crm/models.py` | 179, 183 | `Contract.client`, `Contract.supplier` |
| `apps/crm/models.py` | 195-199 | `Contract.sign_date`, `expire_date`, `attachment`, `remark` |
| `apps/crm/models.py` | 250, 253-255 | `PaymentPlan.paid_date`, `payment_method`, `payment_account`, `remark` |
| `apps/tasks/models.py` | 25-26 | `Project.start_date`, `end_date` |
| `apps/tasks/models.py` | 116-117 | `Task.due_date`, `completed_at` |
| `apps/tasks/models.py` | 241-242 | `TaskStageInstance.started_at`, `completed_at` |
| `apps/tasks/models.py` | 289-290 | `TaskFlowInstance.started_at`, `completed_at` |
| `apps/tasks/models.py` | 104 | `Task.assignee` |
| `apps/approvals/models.py` | 29, 37, 56, 95, 110, 117, 120, 125, 169, 174 | Various nullable fields |
| `apps/material/models.py` | 9, 53, 60, 64, 71, 123, 158, 162, 188, 196, 204 | Various nullable fields |
| `apps/finance/models.py` | Various | Extensive nullable fields |

### 11. Files larger than 500 lines (needing refactoring)

| File | Lines |
|------|-------|
| `apps/finance/views.py` | **2,800** |
| `apps/core/views.py` | **1,479** |
| `apps/finance/models.py` | **1,269** |
| `apps/tasks/views.py` | **1,238** |
| `apps/finance/bank_import_views.py` | **1,133** |
| `apps/channels/views.py` | **1,054** |
| `apps/finance/reports_v2.py` | **1,023** |
| `apps/finance/bank_adapters.py` | **962** |
| `apps/core/import_excel.py` | **869** |
| `apps/finance/serializers.py` | **743** |
| `apps/core/models.py` | **676** |
| `apps/finance/tax_invoice_import.py` | **587** |
| `apps/crm/views.py` | **550** |
| `apps/finance/import_views.py` | **525** |
| `apps/approvals/views.py` | **520** |
| `apps/core/serializers.py` | **518** |
| `apps/core/export_excel.py` | **514** |

### 12. Auth coverage — `@login_required` / `@permission_required` / `has_perm`
- Only 7 references to permission checks across the codebase
- `apps/core/permissions.py` has custom permission classes (line 47, 61, 69, 78)
- `apps/core/models.py` line 47: User model has `has_perm()` method
- `apps/finance/views.py` line 157: `request.user.has_perm(code)`
- Most views appear to rely on DRF's permission classes rather than decorators

### 13. `get_object_or_404` usage
Only used in `apps/channels/views.py` (16 occurrences). Other detail views in other apps use `objects.get()` directly without 404 handling.

### 14. Bare `except:` blocks — **0 found** ✅

### 15. `# TODO` / `# FIXME` — **0 found** ✅

### 16. `try:` without `except` — All try blocks appear to have matching except clauses ✅

---

## Summary

| Severity | Count | Key Findings |
|----------|-------|-------------|
| **CRITICAL** | 46+93+3 | `objects.get()` without try/except (46), `.save()` without try/except (93), raw SQL via `extra()` (3) |
| **WARNING** | 60+48+29+89+14 | Filter without order_by, `.all()` in views, unlimited filter queries, CASCADE risks, bare `except Exception` |
| **INFO** | 17+100+ | Large files needing refactoring, extensive `null=True` fields, limited auth decorator coverage |
