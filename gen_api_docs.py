# -*- coding: utf-8 -*-
"""生成接口文档：解析 Controller + DTO 字段，产出 docs/api-user.md 与 docs/api-admin.md。"""
import os, re, io

ROOT = os.path.dirname(os.path.abspath(__file__))
SVCS = ["user-service", "risk-service", "loan-service", "cs-service"]
SCAN_DIRS = [os.path.join(ROOT, "common-api", "src", "main", "java")] + \
            [os.path.join(ROOT, "services", s, "src", "main", "java") for s in SVCS + ["common-runtime"]]

def src_dir(s): return os.path.join(ROOT, "services", s, "src", "main", "java")

# ---------- 1. 索引所有 DTO / VO / Entity 类字段 ----------
SCHEMA_RE = re.compile(r'@Schema\(([^)]*)\)', re.S)
DESC_RE = re.compile(r'description\s*=\s*"((?:[^"\\]|\\.)*)"')
EX_RE = re.compile(r'example\s*=\s*"((?:[^"\\]|\\.)*)"')
FIELD_RE = re.compile(r'private\s+([\w\.<>,\[\]\s]+?)\s+(\w+)\s*;')
CLASS_RE = re.compile(r'(?:public\s+)?(?:class|record|enum)\s+(\w+)')
NOTNULL_RE = re.compile(r'@(?:NotNull|NotBlank|NotEmpty)')

classes = {}

def java2ts(t):
    t = t.strip()
    if t in ("String", "char", "CharSequence"):
        return "string"
    if t in ("Long", "long", "Integer", "int", "BigDecimal", "Double", "double", "Float", "float", "Short", "short"):
        return "number"
    if t in ("Boolean", "boolean"):
        return "boolean"
    if t in ("LocalDateTime", "LocalDate", "LocalTime", "Date", "Instant"):
        return "string(时间)"
    m = re.match(r'(?:List|Set|Collection)<(.+)>', t)
    if m:
        return "array<" + java2ts(m.group(1)) + ">"
    if re.match(r'Map<', t):
        return "object"
    if t == "Object":
        return "object"
    return t

for rootdir in SCAN_DIRS:
    for dp, _, files in os.walk(rootdir):
        for fn in files:
            if not fn.endswith(".java"):
                continue
            p = os.path.join(dp, fn)
            try:
                src = io.open(p, encoding="utf-8", errors="replace").read()
            except Exception:
                continue
            cm = CLASS_RE.search(src)
            if not cm:
                continue
            name = cm.group(1)
            fields = []
            if "private " in src:
                # 普通 class/实体：private 字段 + @Schema 注解
                for f in FIELD_RE.finditer(src):
                    ftype, fname = f.group(1).strip(), f.group(2)
                    if fname == "serialVersionUID":
                        continue
                    seg = src[:f.start()]
                    scs = list(SCHEMA_RE.finditer(seg))
                    desc, ex = "", ""
                    if scs:
                        sc = scs[-1].group(1)
                        dm = DESC_RE.search(sc)
                        if dm: desc = dm.group(1).replace('"', "'")
                        em = EX_RE.search(sc)
                        if em: ex = em.group(1)
                    req = bool(NOTNULL_RE.search(seg[-200:]))
                    fields.append({"name": fname, "type": ftype, "desc": desc, "example": ex, "required": req})
            else:
                # record：字段是构造器组件
                rm = re.search(r'record\s+\w+\s*\(([^)]*)\)', src, re.S)
                if rm:
                    for c in rm.group(1).split(","):
                        c = c.strip()
                        if not c:
                            continue
                        mm = re.search(r'([\w\.<>\[\]]+)\s+(\w+)\s*$', c)
                        if mm:
                            fields.append({"name": mm.group(2), "type": mm.group(1),
                                           "desc": "", "example": "", "required": False})
            classes[name] = {"fields": fields}

# ---------- 2. 解析 Controller ----------
HTTP_RE = re.compile(r'@(Get|Post|Put|Delete|Patch)Mapping(?:\(([^)]*)\))?')
OP_RE = re.compile(r'@Operation\(\s*summary\s*=\s*"([^"]*)"')
AUTH_RE = re.compile(r'@PreAuthorize\("([^"]*)"\)')
REQMAP_RE = re.compile(r'@RequestMapping\([^)]*?"([^"]*)"')
TAG_RE = re.compile(r'@Tag\(\s*name\s*=\s*"([^"]*)"')
PUBLIC_RE = re.compile(r'public\s+([\w\.<>,\[\]\s]+?)\s+(\w+)\s*\(')

def auth_text(a):
    if not a:
        return "登录（未限角色）"
    m = re.findall(r"hasRole\('([^']+)'\)", a)
    if m:
        return "需登录（角色 " + "/".join(m) + "）"
    m = re.findall(r"hasAnyAuthority\(([^)]+)\)", a)
    if m:
        return "需权限点 " + " 或 ".join(re.findall(r"'([^']+)'", m[0]))
    m = re.findall(r"hasAuthority\('([^']+)'\)", a)
    if m:
        return "需权限点 " + "/".join(m)
    return "需权限 " + a

def parse_params(body):
    params = []
    for m in re.finditer(r'@RequestParam(?:\([^)]*\))?\s*([\w\.<>\[\]]+)\s+(\w+)', body):
        t, n = m.group(1), m.group(2)
        seg = body[:m.start()]
        ann = seg[-200:]
        has_def = "defaultValue" in ann
        has_false = re.search(r'required\s*=\s*false', ann)
        req = not has_def and not has_false
        if "MultipartFile" in t:
            params.append({"name": n, "in": "formData", "type": "file", "required": req})
        else:
            params.append({"name": n, "in": "query", "type": java2ts(t), "required": req})
    for m in re.finditer(r'@PathVariable(?:\([^)]*\))?\s*([\w\.<>\[\]]+)\s+(\w+)', body):
        params.append({"name": m.group(2), "in": "path", "type": java2ts(m.group(1)), "required": True})
    for m in re.finditer(r'@RequestBody\s*([\w\.<>\[\]]+)\s+(\w+)', body):
        params.append({"name": m.group(2), "in": "body", "type": m.group(1), "required": True})
    return params

def extract_generic(t):
    t = t.strip()
    m = re.match(r'CommonResponse<(.+)>', t)
    return m.group(1) if m else t

# 索引 Service 层方法 → Map key（用于 Map/Object 响应的字段名推断）
service_keys = {}   # (svc, method_name) -> list[str]
for svc in SVCS:
    for dp, _, files in os.walk(src_dir(svc)):
        for fn in files:
            if not (fn.endswith("Service.java") or fn.endswith("ServiceImpl.java")):
                continue
            p = os.path.join(dp, fn)
            try:
                s2 = io.open(p, encoding="utf-8", errors="replace").read()
            except Exception:
                continue
            pubs2 = list(PUBLIC_RE.finditer(s2))
            for i, pm in enumerate(pubs2):
                mname = pm.group(2)
                end = pubs2[i + 1].start() if i + 1 < len(pubs2) else len(s2)
                body = s2[pm.start():end]
                keys = set(re.findall(r'\.put\("([^"]+)"', body)) | set(re.findall(r'Map\.of\("([^"]+)"', body))
                if keys:
                    service_keys[(svc, mname)] = sorted(keys)

def lookup_map_keys(svc, called):
    best = []
    for c in called:
        k = service_keys.get((svc, c))
        if k and len(k) > len(best):
            best = k
    return best

rows = {"user": [], "admin": [], "internal": []}

def classify(fname, base, cls_auth):
    low = base.lower()
    if fname.startswith("Internal") or "/internal" in low or low.startswith("/sync") or low.startswith("/demo"):
        return "internal"
    if fname.startswith("Admin") or low.startswith("/admin"):
        return "admin"
    if cls_auth and "hasRole('USER')" not in cls_auth:
        return "admin"
    return "user"

for svc in SVCS:
    for dp, _, files in os.walk(src_dir(svc)):
        for fn in sorted(files):
            if not fn.endswith("Controller.java"):
                continue
            p = os.path.join(dp, fn)
            src = io.open(p, encoding="utf-8", errors="replace").read()
            tag = TAG_RE.search(src)
            tag = tag.group(1) if tag else fn[:-5]
            cls_req = REQMAP_RE.search(src)
            cls_base = cls_req.group(1).strip() if cls_req else ""
            decl = src.find("public class")
            cls_auth = None
            for m in AUTH_RE.finditer(src[:decl]):
                cls_auth = m.group(1)
            side = classify(fn, cls_base, cls_auth)
            pub = list(PUBLIC_RE.finditer(src))
            prev_end = decl if decl != -1 else 0
            for i, m in enumerate(pub):
                sig_start = m.start()
                block = src[prev_end:sig_start]  # 当前方法的注解块
                brace = src.find("{", m.end())
                prev_end = brace + 1 if brace != -1 else m.end()
                hm = list(HTTP_RE.finditer(block))
                if not hm:
                    continue
                last_http = hm[-1]
                verb = last_http.group(1).upper()
                qs = re.findall(r'"([^"]*)"', last_http.group(2) or "")
                mpath = qs[0] if qs else ""
                full = (cls_base.rstrip("/") + "/" + mpath.lstrip("/")).rstrip("/") or "/"
                om = OP_RE.search(block)
                summary = om.group(1) if om else m.group(2)
                am = AUTH_RE.search(block)
                method_auth = am.group(1) if am else cls_auth
                ret = m.group(1)
                sig = src[sig_start:brace]
                params_body = sig[sig.find("(") + 1:sig.rfind(")")]
                params = parse_params(params_body)
                body_param = next((x for x in params if x["in"] == "body"), None)
                ret_generic = extract_generic(ret)
                # 方法体里调用的方法名（service.method() 形式），用于 Map 响应字段推断
                method_end = pub[i + 1].start() if i + 1 < len(pub) else len(src)
                method_body = src[brace + 1:method_end] if brace != -1 else ""
                called = set(re.findall(r'\.(\w+)\s*\(', method_body))
                map_keys = lookup_map_keys(svc, called) if ret_generic in ("Map<String, Object>", "Map<String,Object>", "Object", "Map") else []
                rows[side].append({
                    "svc": svc, "tag": tag, "verb": verb, "path": full,
                    "auth": auth_text(method_auth), "summary": summary,
                    "params": params, "body_param": body_param, "ret": ret_generic,
                    "map_keys": map_keys,
                })

# ---------- 3. 生成 Markdown ----------
class _W:
    def __init__(self, f): self.f = f
    def __call__(self, s): self.f.write(s)
    def close(self): self.f.close()

def render_fields(cls_name):
    if cls_name not in classes:
        return ""
    out = ["| 字段 | 类型 | 必填 | 说明 | 示例 |", "|---|---|---|---|---|"]
    for f in classes[cls_name]["fields"]:
        ts = java2ts(f["type"]).replace("|", "\\|")
        out.append("| `%s` | %s | %s | %s | %s |" % (
            f["name"], ts, "是" if f["required"] else "否",
            f["desc"] or "—", f["example"] or "—"))
    return "\n".join(out)

def render_ret(ret, map_keys=None):
    t = ret.strip()
    if t in ("Void", "void", "null", ""):
        return "无 `data` 字段（仅返回 `code`/`message`）。"
    if t in ("Map<String, Object>", "Map<String,Object>", "Object", "Map"):
        if map_keys:
            rows2 = ["| 字段 | 类型 |", "|---|---|"]
            rows2 += ["| `%s` | 见联调 |" % k for k in map_keys]
            return "`data` 为 JSON 对象，字段如下（类型以实际联调为准）：\n\n" + "\n".join(rows2)
        return "`data` 为 JSON 对象（字段由后端动态组装，见代码实现）。"
    m = re.match(r'List<(.+)>', t)
    if m:
        inner = m.group(1)
        if inner in classes:
            return "`data` 为数组，元素字段如下：\n\n" + render_fields(inner)
        return "`data` 为数组，元素类型 `%s`。" % java2ts(inner)
    if t in classes:
        return "`data` 对象字段如下：\n\n" + render_fields(t)
    return "`data` 为 `%s` 类型。" % java2ts(t)

HEAD_COMMON = """## 通用说明

### 网关与路径
前端统一走网关 `http://localhost:8088`，请求路径即下文各接口「路径」列原样使用（网关已配置 `/api/v1` 前缀与转发）。

### 统一响应结构
所有接口（特别标注除外）返回统一 JSON：

```json
{ "code": 200, "message": "成功", "success": true, "data": { } }
```

| 字段 | 类型 | 说明 |
|---|---|---|
| `code` | number | 状态码，`200` 成功，其他为失败 |
| `message` | string | 提示信息 |
| `success` | boolean | 是否成功 |
| `data` | object/array/标量 | 业务数据，失败时为 `null` |

### 错误码
| code | 含义 |
|---|---|
| 200 | 成功 |
| 400 | 参数错误 / 业务校验失败 |
| 403 | 无权限访问（HTTP 403） |
| 404 | 接口不存在 |
| 409 | 数据已存在，请勿重复操作 |
| 500 | 服务器内部错误 |

### 鉴权方式
- 登录后，请求头携带 `Authorization: Bearer <JWT>`（登录接口返回 `token`）。
"""

HEAD_USER_EXTRA = """- 本端接口均需登录，角色为 `USER`（注册、登录本身无需携带 token）。

### 分页结构
- 部分列表接口返回 `{ "list": [ ... ], "total": N }`；
- 部分返回 `{ "records": [ ... ], "total": N, "size": N, "current": N, "pages": N }`；
- 产品列表返回 `{ "list": [ ... ], "total": N, "pageNum": N, "pageSize": N }`。
- 具体以各接口「响应体」说明为准。
"""

HEAD_ADMIN_EXTRA = """- 各接口所需权限点见「鉴权」列，由后台为管理员角色分配对应权限点。

### 权限点总表
| 权限点 | 说明 |
|---|---|
| `sys:user` / `sys:user:write` | 用户管理：查看 / 新增、编辑、改状态 |
| `sys:admin` / `sys:admin:write` | 管理员管理：查看 / 新增、编辑、删除 |
| `sys:config` / `sys:config:write` | 系统配置：查看 / 修改、备份恢复 |
| `sys:product` / `sys:product:write` | 产品目录：查看 / 新增、编辑、上下架、删除 |
| `audit:read` | 操作日志查看 |
| `risk:approve` / `risk:approve:write` | 风控审批：查看 / 审批、导出 |
| `risk:monitor` / `risk:monitor:write` | B 卡贷后监控：查看 / 重算、生成快照 |
| `risk:fraud:write` | 反欺诈告警处理 |
| `loan:approve` / `loan:approve:write` | 贷款审批：查看 / 审批、导出 |
| `collection:action` / `collection:action:write` / `collection:case` | 还款催收：查看 / 发送提醒、报表 / 逾期管理 |
| `credit:adjust` / `credit:adjust:write` | 信用额度：查看 / 调整额度 |
| `cs:ticket` / `cs:ticket:write` | 客服工单：查看 / 接管、回复、关闭 |
| `ROLE_SYS_ADMIN` | 超级管理员角色（部分看板接口可用此角色替代） |

### 分页结构
- 多数列表接口返回 `{ "list": [ ... ], "total": N }`；
- 部分返回 `{ "records": [ ... ], "total": N, "size": N, "current": N, "pages": N }`。
- 具体以各接口「响应体」说明为准。
"""

def write_doc(side, path, title):
    W = _W(io.open(path, "w", encoding="utf-8"))
    W("# RiskLendPro 后端接口文档 — %s\n\n" % title)
    W(HEAD_COMMON)
    W(HEAD_USER_EXTRA if side == "user" else HEAD_ADMIN_EXTRA)
    W("\n")
    last_svc = None
    idx = 0
    for r in rows[side]:
        if r["svc"] != last_svc:
            W("\n## %s\n\n" % r["svc"])
            last_svc = r["svc"]
        idx += 1
        W("### %d. %s\n\n" % (idx, r["summary"]))
        W("- **方法**：`%s`　**路径**：`%s`\n" % (r["verb"], r["path"]))
        W("- **鉴权**：%s\n" % r["auth"])
        W("- **所属模块**：%s\n\n" % r["tag"])
        if r["params"]:
            W("**请求参数**\n\n| 参数 | 位置 | 类型 | 必填 |\n|---|---|---|---|\n")
            for pp in r["params"]:
                W("| `%s` | %s | %s | %s |\n" % (pp["name"], pp["in"], pp["type"], "是" if pp["required"] else "否"))
            W("\n")
        if r["body_param"]:
            bt = r["body_param"]["type"]
            W("**请求体**（`application/json`，类型 `%s`）\n\n" % bt)
            if bt in classes:
                W(render_fields(bt) + "\n\n")
            else:
                W("（字段结构见 `%s` 类定义）\n\n" % bt)
        W("**响应体**\n\n" + render_ret(r["ret"], r.get("map_keys")) + "\n\n---\n\n")
    W.close()

if __name__ == "__main__":
    os.makedirs(os.path.join(ROOT, "docs"), exist_ok=True)
    write_doc("user", os.path.join(ROOT, "docs", "api-user.md"), "用户端")
    write_doc("admin", os.path.join(ROOT, "docs", "api-admin.md"), "管理员端")
    print("user=%d admin=%d internal=%d classes=%d" % (len(rows["user"]), len(rows["admin"]), len(rows["internal"]), len(classes)))
