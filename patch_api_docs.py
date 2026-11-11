# -*- coding: utf-8 -*-
"""补全接口文档中 Map/Object 响应的字段说明（人工核对代码后固化）。"""
import io, os, re

ROOT = os.path.dirname(os.path.abspath(__file__))
DYN = "`data` 为 JSON 对象（字段由后端动态组装，见代码实现）。"

def fields(keys, types=None):
    out = ["| 字段 | 类型 | 说明 |", "|---|---|---|"]
    for i, k in enumerate(keys):
        t = types[i] if types else "见联调"
        out.append("| `%s` | %s | — |" % (k, t))
    return "\n".join(out)

# 标题 -> 响应体说明文本（替换「动态组装」那一行所在段）
PATCH_USER = {
    "获取用户借款记录": "`data` 为分页对象，结构：`{ records: [借款记录], total, size, current, pages }`，其中 `records` 元素字段见上文「借款响应」字段表。",
    "获取用户贷款申请记录": "`data` 为分页对象，结构：`{ records: [申请记录], total, size, current, pages }`，其中 `records` 元素字段见上文「借款响应」字段表。",
    "U2 产品列表": "`data` 为分页对象：`{ list: [产品卡片], total, pageNum, pageSize }`，产品卡片字段如下：\n\n" + fields(
        ["productId", "productName", "institution", "categoryCode", "categoryName", "coverImage",
         "minAmount", "maxAmount", "minAnnualRate", "maxAnnualRate", "minTerm", "maxTerm",
         "termUnit", "mortgageRequired", "rateScope", "tags"]),
    "U3 产品详情": "`data` 为产品详情对象，字段如下：\n\n" + fields(
        ["productId", "productName", "institution", "categoryCode", "categoryName", "tags", "summary",
         "coverImage", "detailImages", "minAmount", "maxAmount", "minTerm", "maxTerm", "termUnit",
         "minAnnualRate", "maxAnnualRate", "rateCalcMethod", "rateScope", "repaymentMethods",
         "disbursementTime", "targetGroups", "minAge", "maxAge", "incomeRequirement", "creditRequirement",
         "occupationRequirement", "mortgageRequired", "regions", "extraConditions", "feeStatus",
         "feeDescription", "prepaymentDescription", "remark", "dataSource", "verifiedAt", "updateTime",
         "riskTip", "overview", "loanInfo", "conditions", "materials", "others", "meta",
         "inPlatformApply", "status", "everOnShelf", "version", "sortWeight"]),
    "status": "**注意**：本接口不走 `CommonResponse` 统一包裹，直接返回 JSON 对象：`{ \"service\": \"cs-service\", \"status\": \"UP\", \"llmConnected\": false }`。",
    "提交转人工工单": "`data` 对象字段：`ticketId`（工单编号，number）。",
    "上报获客行为事件，支持批量": "`data` 对象：`{ accepted: 已受理事件数, deduplicated: 去重数 }`。",
    "确认推荐曝光，按 requestId 幂等": "`data` 对象：`{ requestId, accepted, duplicate }`；`duplicate=true` 表示重复请求已幂等忽略。",
    "四场景获客推荐": "`data` 对象：`{ requestId, scene, modelVersion, abGroup, assessmentId, coldStart, fallbackUsed, riskCheckDegraded, items: [...] }`；`items` 元素为产品卡片（字段见「U2 产品列表」）并附加 `recommendationReason`、`recommendationScore`、`recallSources`、`missingProofMaterials`。",
}

PATCH_ADMIN = {
    "用户列表": "`data` 为分页对象：`{ list: [用户], total }`，`list` 元素字段如下：\n\n" + fields(
        ["id", "userId", "name", "realName", "phone", "phoneNumber", "idCard", "creditScore",
         "creditLimit", "loanCount", "totalLoan", "status", "accountStatus", "registerTime",
         "createTime", "avatar"]),
    "用户导出": "`data` 为导出结果对象（或直接返回文件流），字段见 `AdminExportHelper` 实现。",
    "操作日志": "`data` 为分页对象：`{ list: [日志], total }`，`list` 元素字段见 `AdminEntityMapper`（含 `id`、`module`、`action`、`detail`、`createTime` 等）。",
    "系统配置": "`data` 为配置项对象，字段含 `systemName`、`emailEnabled`、`logRetentionDays`、`backupRetentionDays` 等（对应 `SystemConfigUpdateRequest`）。",
    "借款记录列表": "`data` 为分页对象：`{ list: [借款记录], total }`。",
    "还款计划列表": "`data` 为分页对象：`{ list: [还款计划], total }`。",
    "计划还款记录列表": "`data` 为分页对象：`{ list: [还款记录], total }`。",
    "额度列表": "`data` 为分页对象：`{ list: [额度项], total }`，额度项字段含 `userId`、`totalLimit`、`usedLimit`、`remainingLimit` 等。",
    "信用评分列表": "`data` 为分页对象：`{ list: [评分项], total }`。",
    "获客推荐漏斗指标": "`data` 对象含 `items` 数组（每项 `{ productId, impressions, clicks, applies }`）及汇总统计字段。",
    "获取推荐场景配置": "`data` 对象：`{ weights: { ... }, candidateLimit, explorationRate, maxPerInstitution, maxPerCategory, fatigueDays, fatiguePenalty }` 等推荐参数。",
    "保存推荐场景配置": "`data` 为保存后的推荐配置对象，结构同「获取推荐场景配置」。",
}

def apply_patch(path, patch):
    src = io.open(path, encoding="utf-8").read()
    for title, newtext in patch.items():
        # 定位标题段，替换其后的 DYN 行
        m = re.search(r'(### \d+\. ' + re.escape(title) + r'\n\n)(.*?)(\n\n---\n)', src, re.S)
        if not m:
            print("  未找到段:", title)
            continue
        seg = m.group(2)
        if DYN in seg:
            seg = seg.replace(DYN, newtext)
            src = src[:m.start()] + m.group(1) + seg + m.group(3) + src[m.end():]
            print("  已补:", title)
        else:
            print("  段内无动态组装标记:", title)
    io.open(path, "w", encoding="utf-8").write(src)

apply_patch(os.path.join(ROOT, "docs", "api-user.md"), PATCH_USER)
apply_patch(os.path.join(ROOT, "docs", "api-admin.md"), PATCH_ADMIN)
print("done")
