# -*- coding: utf-8 -*-
"""把 index.html 里的 TAG_DB / SYN / ASSOC / QUALITY 抽出为 tags_data.json"""
import re, json

html = open(r"C:\AI\easy-ui\index.html", encoding="utf-8").read()
js = re.search(r"<script>([\s\S]*)</script>", html).group(1)

def extract_obj(name, start_idx):
    """从 name 定义处提取平衡的 {..} 或 [..] 文本（跳过字符串/注释）"""
    i = js.find(name, start_idx)
    assert i >= 0, name
    br_i = js.find("[", i)
    cb_i = js.find("{", i)
    if cb_i >= 0 and (br_i < 0 or cb_i < br_i):
        i, open_ch, close_ch = cb_i, "{", "}"
    else:
        assert br_i >= 0, name
        i, open_ch, close_ch = br_i, "[", "]"
    depth, quote, esc = 0, None, False
    for j in range(i, len(js)):
        c = js[j]
        if quote:
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == quote:
                quote = None
            continue
        if c in "\"'`":
            quote = c
        elif c == open_ch:
            depth += 1
        elif c == close_ch:
            depth -= 1
            if depth == 0:
                return js[i:j+1]
    raise ValueError(name)

def js2py(text):
    """JS 字面量 → Python: 无引号 key 加引号, true/false/null 替换"""
    t = re.sub(r'([{,]\s*)([A-Za-z_][A-Za-z0-9_]*)\s*:', r'\1"\2":', text)
    t = re.sub(r'\btrue\b', 'True', t)
    t = re.sub(r'\bfalse\b', 'False', t)
    t = re.sub(r'\bnull\b', 'None', t)
    return t

tag_db_txt = extract_obj("const TAG_DB", 0)
syn_txt = extract_obj("const SYN", 0)
assoc_txt = extract_obj("const ASSOC", 0)
qm = re.search(r'const QUALITY\s*=\s*"([^"]+)"', js)
quality = qm.group(1) if qm else "masterpiece, best quality, very aesthetic"

data = {
    "tag_db": eval(js2py(tag_db_txt), {}, {}),   # noqa: S307 (来源可信)
    "syn": eval(js2py(syn_txt), {}, {}),
    "assoc": eval(js2py(assoc_txt), {}, {}),
    "quality": quality,
}
n_tags = sum(len(g["tags"]) for g in data["tag_db"])
json.dump(data, open(r"C:\AI\easy-ui\tags_data.json", "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
print("OK  分类:", len(data["tag_db"]), "| 标签:", n_tags,
      "| 词典:", len(data["syn"]), "| 关联组:", len(data["assoc"]),
      "| 质量词:", data["quality"][:40])
