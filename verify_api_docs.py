# -*- coding: utf-8 -*-
"""接口文档自检：代码权威清单 vs 文档，交叉验证数量/路径/方法/要素/字段完整性。"""
import os, re, io, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gen_api_docs as G  # 复用其解析结果 rows / classes

ROOT = os.path.dirname(os.path.abspath(__file__))
DOCS = {"user": "docs/api-user.md", "admin": "docs/api-admin.md"}

# 文档解析：按 "### " 分块
def parse_doc(path):
    src = io.open(os.path.join(ROOT, path), encoding="utf-8").read()
    blocks = re.split(r'(?m)^### ', src)[1:]  # 每个元素以 "N. 标题\n" 开头
    items = []
    for b in blocks:
        m = re.search(r'- \*\*方法\*\*：`(\w+)`　\*\*路径\*\*：`([^`]+)`', b)
        if not m:
            continue
        verb, path = m.group(1), m.group(2)
        auth = re.search(r'- \*\*鉴权\*\*：(.+)', b)
        auth = auth.group(1).strip() if auth else ""
        has_body = "**请求体**" in b
        has_resp = "**响应体**" in b
        # 请求体字段表行数（字段名以 | ` 开头）
        body_fields = 0
        if has_body:
            seg = b.split("**请求体**", 1)[1].split("**响应体**", 1)[0]
            body_fields = len(re.findall(r'^\| `[^`]+` \|', seg, re.M))
        items.append({"verb": verb, "path": path, "auth": auth,
                      "has_body": has_body, "has_resp": has_resp, "body_fields": body_fields})
    return items

def norm(p):
    return p.strip().rstrip("/") or "/"

problems = []
checks = {"接口总数": 0, "路径方法一致": 0, "鉴权一致": 0, "要素完整": 0, "请求体字段完整": 0}

for side, doc in DOCS.items():
    code_items = G.rows[side]
    doc_items = parse_doc(doc)
    checks["接口总数"] += len(doc_items)
    # 1. 数量一致
    if len(doc_items) != len(code_items):
        problems.append(f"[{side}] 数量不一致：代码 {len(code_items)} vs 文档 {len(doc_items)}")
    # 构建代码索引 (verb, norm_path)
    code_map = {}
    for r in code_items:
        key = (r["verb"], norm(r["path"]))
        code_map[key] = r
    doc_map = {(d["verb"], norm(d["path"])): d for d in doc_items}
    # 2. 双向：代码接口都在文档，文档接口都在代码
    for key, r in code_map.items():
        if key not in doc_map:
            problems.append(f"[{side}] 代码接口缺失于文档: {key}")
        else:
            checks["路径方法一致"] += 1
    for key in doc_map:
        if key not in code_map:
            problems.append(f"[{side}] 文档多余接口: {key}")
    # 3. 鉴权一致
    for key, d in doc_map.items():
        r = code_map.get(key)
        if not r:
            continue
        if d["auth"] == r["auth"]:
            checks["鉴权一致"] += 1
        else:
            problems.append(f"[{side}] 鉴权不一致 {key}: 文档[{d['auth']}] vs 代码[{r['auth']}]")
    # 4. 要素完整 + 5. 请求体字段
    for key, r in code_map.items():
        d = doc_map.get(key)
        if not d:
            continue
        ok = d["has_resp"] and d["auth"] != ""
        if r.get("body_param"):
            ok = ok and d["has_body"]
            bt = r["body_param"]["type"]
            if bt in G.classes:
                expect = len(G.classes[bt]["fields"])
                if d["body_fields"] != expect:
                    problems.append(f"[{side}] 请求体字段数不符 {key}: 文档 {d['body_fields']} vs 代码 {expect} (DTO {bt})")
                else:
                    checks["请求体字段完整"] += 1
        if ok:
            checks["要素完整"] += 1
        else:
            problems.append(f"[{side}] 要素缺失 {key}: body={d['has_body']} resp={d['has_resp']} auth={bool(d['auth'])}")

print("=" * 60)
print("接口文档自检报告")
print("=" * 60)
for k, v in checks.items():
    print(f"  {k}: {v}")
print()
if problems:
    print(f"发现问题 {len(problems)} 项：")
    for p in problems:
        print("  ❌ " + p)
else:
    print("✅ 未发现问题，文档与代码一致。")
