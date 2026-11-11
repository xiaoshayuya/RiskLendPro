# -*- coding: utf-8 -*-
"""扫描 4 个业务服务的 Controller，生成接口总览表 docs/api-overview.md（临时，供确认范围）。"""
import os, re, io

ROOT = os.path.dirname(os.path.abspath(__file__))
SERVICES = {
    "user-service": "用户服务（8081）",
    "risk-service": "风控服务（8082）",
    "loan-service": "借贷服务（8083）",
    "cs-service":   "AI客服服务（8084）",
}
HTTP_RE = re.compile(r'@(Get|Post|Put|Delete|Patch)Mapping(?:\(([^)]*)\))?')
OP_RE = re.compile(r'@Operation\(\s*summary\s*=\s*"([^"]*)"')
AUTH_RE = re.compile(r'@PreAuthorize\("([^"]*)"\)')
PUBLIC_RE = re.compile(r'public\s+[\w<>,\.\[\]\s]+?\s+(\w+)\s*\(')
TAG_RE = re.compile(r'@Tag\(\s*name\s*=\s*"([^"]*)"')
REQ_RE = re.compile(r'@RequestMapping\([^)]*?"([^"]*)"')

def auth_text(a):
    if not a:
        return "登录（未限角色）"
    m = re.findall(r"hasRole\('([^']+)'\)", a)
    if m:
        return "登录 + 角色 " + "/".join(m)
    m = re.findall(r"hasAnyAuthority\(([^)]+)\)", a)
    if m:
        pts = re.findall(r"'([^']+)'", m[0])
        return "权限点 " + " 或 ".join(pts)
    m = re.findall(r"hasAuthority\('([^']+)'\)", a)
    if m:
        return "权限点 " + "/".join(m)
    return a

def classify(fname, base, cls_auth):
    low = base.lower()
    if fname.startswith("Internal") or "/internal" in low or low.startswith("/sync") or low.startswith("/demo"):
        return "internal"
    if fname.startswith("Admin") or low.startswith("/admin") or low.startswith("/admin/"):
        return "admin"
    if cls_auth and "hasRole('USER')" not in cls_auth:
        return "admin"
    return "user"

rows = {"user": [], "admin": [], "internal": []}

for svc, svc_desc in SERVICES.items():
    svc_dir = os.path.join(ROOT, "services", svc, "src", "main", "java")
    for dirpath, _, files in os.walk(svc_dir):
        for f in sorted(files):
            if not f.endswith("Controller.java"):
                continue
            path = os.path.join(dirpath, f)
            src = io.open(path, encoding="utf-8", errors="replace").read()
            cls_tag = TAG_RE.search(src)
            cls_tag = cls_tag.group(1) if cls_tag else f[:-5]
            cls_req = REQ_RE.search(src)
            cls_base = cls_req.group(1) if cls_req else ""
            # 类级 @PreAuthorize（出现在类声明之前的最后一个）
            cls_decl = src.find("public class")
            cls_auth = None
            for m in AUTH_RE.finditer(src[:cls_decl]):
                cls_auth = m.group(1)
            side = classify(f, cls_base, cls_auth)
            lines = src.splitlines()
            i = 0
            pend_op, pend_auth, pend_http = None, cls_auth, None
            while i < len(lines):
                ln = lines[i]
                m = HTTP_RE.search(ln)
                if m:
                    verb = m.group(1).upper()
                    params = (m.group(2) or "").strip()
                    # 路径取注解参数中所有引号字符串的第一个（兼容 {"/a","/b"} 数组与 consumes= MediaType 等属性）
                    qs = re.findall(r'"([^"]*)"', params)
                    p = qs[0] if qs else ""
                    pend_http = (verb, p)
                    pend_op = pend_op  # 保留前面近邻的 @Operation
                    i += 1
                    continue
                mo = OP_RE.search(ln)
                if mo and pend_http is None:
                    pend_op = mo.group(1)
                ma = AUTH_RE.search(ln)
                if ma and pend_http is None:
                    pend_auth = ma.group(1)
                mp = PUBLIC_RE.search(ln)
                if mp and pend_http:
                    method = mp.group(1)
                    verb, p = pend_http
                    # 方法级路径可能带 {param}
                    full = (cls_base.rstrip("/") + "/" + p.strip('"').lstrip("/")).rstrip("/") or "/"
                    rows[side].append((svc, cls_tag, method, verb, full, auth_text(pend_auth), pend_op or method))
                    pend_http, pend_op, pend_auth = None, None, cls_auth
                elif mp:
                    # 无 Mapping 的 public 方法（如私有辅助）→ 重置 pending
                    pend_op, pend_auth = None, cls_auth
                i += 1

out = io.open(os.path.join(ROOT, "docs", "api-overview.md"), "w", encoding="utf-8")
W = out.write
W("# 后端接口总览（待范围确认）\n\n")
W("> 自动扫描自 Controller 源码（路径/方法/权限注解与代码一致）。\n")
W("> 前端统一走网关 `http://localhost:8088`，**网关调用路径 = 下表「路径」列原样使用**（网关已配置 `/api/v1` 前缀与转发）。\n\n")

titles = {"user": "一、用户端接口（登录用户调用）", "admin": "二、管理员端接口（管理后台调用）",
          "internal": "三、内部 / Demo 接口（默认不交付前端，请确认是否剔除）"}
side_no = {"user": 0, "admin": 0, "internal": 0}
for side in ("user", "admin", "internal"):
    W("## " + titles[side] + "\n\n")
    last_svc = None
    for svc, tag, method, verb, full, auth, summary in rows[side]:
        if svc != last_svc:
            W("### %s — %s\n\n" % (svc, SERVICES[svc]))
            W("| # | 接口 | 方法 | 路径 | 鉴权 | 说明 |\n|---|---|---|---|---|---|\n")
            last_svc = svc
        side_no[side] += 1
        W("| %d | %s | %s | `%s` | %s | %s |\n" % (side_no[side], tag, verb, full, auth, summary or "—"))
    W("\n")

W("## 四、统计\n\n")
W("| 分类 | 接口数 |\n|---|---|\n")
for side in ("user", "admin", "internal"):
    W("| %s | %d |\n" % (titles[side].split("、")[1].split("（")[0], side_no[side]))
W("| **合计** | **%d** |\n" % sum(side_no.values()))
out.close()
print("user=%d admin=%d internal=%d" % (side_no["user"], side_no["admin"], side_no["internal"]))
