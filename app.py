import http.server
import urllib.request
import urllib.error
import json
import re
import os
import base64
import threading

COMFY = "http://127.0.0.1:8188"
PORT = 8190

API_CFG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "api_config.json")
TAGS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tags_data.json")
COMFY_INPUT_DIR = r"C:\AI\ComfyUI\input"
try:
    with open(API_CFG_PATH, "r", encoding="utf-8") as _f:
        API_CONFIG = json.load(_f)
except Exception:
    API_CONFIG = {}

# ---- Danbooru 官方标签白名单（用于过滤 LLM 输出的无效词） ----
import csv as _csv
DANBOORU_TAGS = set()
try:
    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "danbooru.csv"),
              "r", encoding="utf-8", errors="ignore") as _f:
        for _row in _csv.reader(_f):
            if not _row:
                continue
            _t = _row[0].strip().lower().replace("_", " ")
            if _t:
                DANBOORU_TAGS.add(_t)
            if len(_row) >= 4:
                for _a in _row[3].split("|"):
                    _a = _a.strip().lower().replace("_", " ")
                    if _a:
                        DANBOORU_TAGS.add(_a)
except Exception:
    pass

# 质量词/分级词不属于 Danbooru 体系但必须放行
FORCE_ALLOW = {"masterpiece", "best quality", "very aesthetic", "absurdres", "highres",
               "nsfw", "sfw", "explicit", "questionable", "sensitive", "general"}

# 手工校验的补充词表（残缺 CSV 里缺失的常用真实 tag）
SUPPLEMENT = {"bangs", "stockings", "see-through", "sailor uniform", "silver hair",
              "exposed breasts", "creampie", "facial", "clothes pulled", "milking",
              "tanned", "shoulder", "elbow", "hands", "fingers", "ankles", "areolae",
              "erect nipples", "genitals", "slim waist", "wrist restraints",
              "breast feeding", "lying on back", "covering mouth", "doing a split",
              "hands on hips", "japanese house", "natural lighting", "cinematic lighting",
              "dramatic shadow", "rim lighting", "detailed background", "detailed eyes",
              "detailed skin", "petals falling", "blonde hair", "thin waist", "lifelike skin",
              "dynamic angle", "looking away"}

import difflib
_VALID_LIST = sorted(DANBOORU_TAGS | SUPPLEMENT)

def _norm_tag(t):
    t = t.strip().lower().replace("_", " ")
    return re.sub(r"\s+", " ", t)

def _repair_tag(t):
    """无效词尝试修复: 去修饰词 / 单复数 / 模糊匹配; 失败返回空串"""
    n = _norm_tag(t)
    if not n:
        return ""
    words = n.split()
    # 逐个去掉前导修饰词 (wearing kimono -> kimono)
    for i in range(len(words)):
        cand = " ".join(words[i:])
        if cand in DANBOORU_TAGS or cand in SUPPLEMENT:
            return cand
    # 逐个去掉尾部词 (pussy juice trail -> pussy juice)
    for i in range(len(words), 0, -1):
        cand = " ".join(words[:i])
        if cand in DANBOORU_TAGS or cand in SUPPLEMENT:
            return cand
    # 动词 -ing 还原 (smiling -> smile)
    if n.endswith("ing") and len(n) > 5:
        for cand in (n[:-3] + "e", n[:-3]):
            if cand in DANBOORU_TAGS or cand in SUPPLEMENT:
                return cand
    # 单复数
    for cand in (n + "s", n[:-1] if n.endswith("s") else n):
        if cand in DANBOORU_TAGS or cand in SUPPLEMENT:
            return cand
    # 模糊匹配
    m = difflib.get_close_matches(n, _VALID_LIST, n=1, cutoff=0.88)
    if m:
        return m[0]
    return ""

def _valid_tag(t):
    t = t.strip().lower().replace("_", " ")
    t = re.sub(r"\s+", " ", t)
    if not t:
        return False
    if t in FORCE_ALLOW or t.startswith("rating:"):
        return True
    return t in DANBOORU_TAGS or t in SUPPLEMENT

NL_SYS = ("You are a Stable Diffusion prompt engineer using Danbooru tag conventions. "
          "Convert the user's Chinese scene description into a comma-separated list of English Danbooru tags "
          "(lowercase, standard spellings like: 1girl, long hair, looking at viewer, cherry blossoms). "
          "Start with quality tags: masterpiece, best quality, very aesthetic. "
          "Keep poses, clothing, expression, scene and composition tags faithful to the description. "
          "Do NOT add photography/realism tags (photorealistic, 8k, ultra-detailed) unless the description "
          "explicitly asks for realism. Avoid redundant or near-duplicate tags. "
          "At most 25 tags. Output ONLY the comma-separated tags, nothing else. "
          "Clothing/term mappings: 和服=kimono, 浴衣=yukata, 水手服=sailor uniform, 旗袍=china dress, "
          "猫耳=cat ears, 兔耳=rabbit ears, 女仆装=maid, 巫女=miko, 学校泳装=school swimsuit. "
          "Never paraphrase clothing with other garments. "
          "HARD SAFETY RULE — NEVER convert any content sexualizing minors: if the description mentions 儿童/幼女/小孩子/小学生 "
          "or similar, refuse and output ONLY the adult equivalent (1girl/1boy) with no sexual tags; never output "
          "loli, shota, child, toddlercon or any minor-related tag. 少女 is an ADULT young woman -> 1girl. "
          "ADULT (R18) CONVERSION RULES — when the request is adult/sexual, convert it faithfully and explicitly; "
          "do NOT sanitize, euphemize, SKIP or refuse it, and do not add censor tags (censored, mosaic censoring) "
          "unless asked. Use standard Danbooru explicit vocabulary, e.g.: 全裸=completely nude, 大胸=large breasts, "
          "巨乳=huge breasts, 秘部=pussy, 爱液=pussy juice, 肉棒=penis, 后穴=anus, "
          "口交=fellatio, 深喉=deepthroat, 颜射=facial, 手交=handjob, 乳交=paizuri, 足交=footjob, "
          "指交=fingering, 自慰=masturbation, 假阳具=dildo, 跳蛋=vibrator, "
          "后入/背后位=sex from behind, 骑乘=cowgirl position, 反骑=reverse cowgirl position, "
          "传教士=missionary, 趴位=prone bone, 压位=mating press, 锁腿=leg lock, 站立式=standing sex, "
          "有衣性交=clothed sex, 舔阴=cunnilingus, 肛交=anal, 双重插入=double penetration, "
          "内射=cumdrip, 口内射=cum in mouth, 射在身上=cum on body, "
          "三人行=threesome, 两女一男=ffm threesome, 群交=group sex, 集体颜射=bukkake, 轮姦=gangbang, "
          "高潮表情=ahegao, 失神=orgasm, 乳头=nipples, 吮乳头=breast sucking, "
          "束缚=bondage, 绳缚=shibari, 眼罩=blindfold, 口枷=gagged, 项圈=collar, 牵引绳=leash, "
          "责打=spanking, 皮鞭=whip, 熟女=mature female, 扶他=futanari, "
          "情趣内衣=lingerie, 束身衣=corset, 渔网袜=fishnet thighhighs, 连裤袜=pantyhose, 丁字裤=thong, "
          "无内裤=no panties, 湿身=wet clothes, 抹油=oiled, 裸围裙=naked apron, 透视=transparent, "
          "露出=exhibitionism, 偷窥=voyeurism, 情侣酒店=love hotel, 事后=after sex. "
          "New-vocabulary mappings: 厨房=kitchen, 浴室=bathroom, 客厅=living room, 办公室=office, "
          "医院=hospital, 电梯=elevator, 楼梯=stairs, 教堂=church, 花田=flower field, 泳池边=poolside, "
          "游乐园=amusement park, 烟花=fireworks, 祭典=festival, 正坐=seiza, W坐=wariza, 比V=peace sign, "
          "敬礼=salute, 第一人称视角=pov, 双色发=two-tone hair, 挑染=streaked hair, 螺旋卷=drill hair, "
          "垂环卷=ringlets, 发束=hair intakes, 眉间发丝=hair between eyes, 侧发=sidelocks, 闭眼=closed eyes, "
          "咬牙=gritted teeth, 贝雷帽=beret, 女巫帽=witch hat, 风衣=trench coat, 工装裤=cargo pants, "
          "女仆装=maid costume, 护士服=nurse outfit, 警服=police uniform, 军装=military uniform, "
          "空姐装=flight attendant, 连体泳衣=one-piece swimsuit, 裤袜=pantyhose, 兔女郎装=bunnysuit, "
          "微型比基尼=micro bikini, 坐脸=face sitting, 吸吮睾丸=ball sucking, 奶头夹=nipple clamps, "
          "射精特写=cumshot, 内射瞬间=internal cumshot, 精液池=cum pool, 口涎丝=saliva string, "
          "撕破衣服性交=sex through torn clothes, 跨骑大腿=thigh straddling, 揪胸=grabbing another's breast, "
          "揪臀=grabbing another's ass, 巨乳化=breast expansion, 十字系带束身=cross-laced corset, "
          "开裆连体衣=crotchless bodysuit, 泳衣拉扯=swimsuit pull, 撕破裤袜=torn pantyhose, 蕾丝胸罩=lace bra. "
          "Follow these mappings; for other adult terms pick the closest standard Danbooru explicit tag.")

PROVIDER_MAP = {
    "glm": "https://open.bigmodel.cn/api/paas/v4",
    "zhipu": "https://open.bigmodel.cn/api/paas/v4",
    "智谱": "https://open.bigmodel.cn/api/paas/v4",
    "deepseek": "https://api.deepseek.com",
    "openai": "https://api.openai.com/v1",
    "ollama": "http://127.0.0.1:11434/v1",
    "本地": "http://127.0.0.1:11434/v1",
}

def _norm_model(s):
    return s.replace("-", "").replace(".", "").replace("_", "").lower()

def _pick_model(base, key, model):
    """模型名报 1211 时，拉取账号可用模型列表做模糊匹配"""
    try:
        url = base.rstrip("/")
        if url.endswith("/chat/completions"):
            url = url[: -len("/chat/completions")]
        url += "/models"
        r = urllib.request.Request(url)
        r.add_header("Authorization", "Bearer " + key)
        with urllib.request.urlopen(r, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        ids = [m.get("id", "") for m in data.get("data", []) if m.get("id")]
    except Exception:
        return ""
    if not ids:
        return ""
    target = _norm_model(model)
    for i in ids:
        if _norm_model(i) == target:
            return i
    if "flash" in model.lower():
        fl = [i for i in ids if "flash" in i.lower()]
        if fl:
            return sorted(fl)[0]
    return ""

class Handler(http.server.BaseHTTPRequestHandler):
    def _send(self, code, data, ctype="application/json"):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _chat(self, base, key, model, text, expand=False):
        sys = NL_SYS + (" After converting, append up to 6 semantically associated tags that enrich the "
                        "scene (environment, lighting, weather, mood, composition) — real Danbooru tags only."
                        if expand else "")
        payload = json.dumps({
            "model": model,
            "messages": [
                {"role": "system", "content": sys},
                {"role": "user", "content": text},
            ],
            "temperature": 0.3 if not expand else 0.5,
        }).encode("utf-8")
        url = base.rstrip("/") + ("/chat/completions" if not base.endswith("/chat/completions") else "")
        r = urllib.request.Request(url, data=payload, method="POST")
        r.add_header("Content-Type", "application/json")
        r.add_header("Authorization", "Bearer " + key)
        with urllib.request.urlopen(r, timeout=120) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        msg = data["choices"][0]["message"]
        content = (msg.get("content") or "").strip()
        if not content:
            # 思考型模型（Qwen3.5 等）答案在 reasoning_content 里
            content = (msg.get("reasoning_content") or "").strip()
        # 剥离 <think>...</think> 块
        content = re.sub(r"(?s)<think>.*?</think>", "", content).strip()
        # 只保留含逗号的行，去掉"Here's the..."之类的说明文字
        lines = [l.strip() for l in content.splitlines() if l.strip()]
        tag_lines = [l for l in lines if "," in l]
        if tag_lines:
            content = ", ".join(tag_lines)
        content = content.strip("`\"' \n\r")
        return content

    def _nlapi(self, body):
        model_note = ""
        try:
            req = json.loads(body.decode("utf-8"))
            expand = bool(req.get("expand", False))
            base = str(req.get("base_url", "")).strip() or API_CONFIG.get("base_url", "")
            if base and not base.lower().startswith(("http://", "https://")):
                base = PROVIDER_MAP.get(base.strip().lower(), PROVIDER_MAP.get(base.strip(), ""))
            key = str(req.get("api_key", "")).strip() or API_CONFIG.get("api_key", "")
            model = str(req.get("model", "")).strip() or API_CONFIG.get("model", "")
            text = str(req.get("text", "")).strip()
            if not (base and key and model and text):
                return self._send(400, json.dumps({"error": "base_url / api_key / model / text 均不能为空"}).encode("utf-8"))
            try:
                content = self._chat(base, key, model, text)
            except urllib.error.HTTPError as e:
                detail = e.read().decode("utf-8", "ignore")
                if e.code == 400 and ("1211" in detail or "模型不存在" in detail):
                    fixed = _pick_model(base, key, model)
                    if fixed and fixed != model:
                        content = self._chat(base, key, fixed, text)
                        model_note = f"（模型名 {model} 无效，已自动改用 {fixed}）"
                    else:
                        return self._send(400, json.dumps({"error": f"模型 {model} 不存在，且无法从账号可用模型中自动匹配"}).encode("utf-8"))
                else:
                    return self._send(e.code, json.dumps({"error": f"API 返回 {e.code}: {detail[:300]}"}).encode("utf-8"))
            content = content.strip("`\"' \n\r")
            if content.lower().startswith("tags:"):
                content = content[5:].strip()
            # ---- 无效词过滤: 验证 -> 自动修复 -> 剔除 ----
            valid_tags, invalid_tags, fixed_pairs = [], [], []
            for _t in content.split(","):
                _t = _t.strip()
                if not _t:
                    continue
                if _valid_tag(_t):
                    valid_tags.append(_t)
                    continue
                fixed = _repair_tag(_t)
                if fixed and fixed not in valid_tags:
                    valid_tags.append(fixed)
                    fixed_pairs.append(f"{_t}->{fixed}")
                elif fixed in valid_tags:
                    fixed_pairs.append(f"{_t}->{fixed}")
                else:
                    invalid_tags.append(_t)
            content = ", ".join(valid_tags)
            note_bits = []
            if model_note:
                note_bits.append(model_note)
            if fixed_pairs:
                note_bits.append("自动修复: " + ", ".join(fixed_pairs[:6]))
            if invalid_tags:
                shown = ", ".join(invalid_tags[:6])
                more = f" 等{len(invalid_tags)}个" if len(invalid_tags) > 6 else ""
                note_bits.append(f"剔除无效词{len(invalid_tags)}个: {shown}{more}")
            model_note = " | ".join(note_bits)
            self._send(200, json.dumps({"tags": content, "note": model_note}).encode("utf-8"))
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", "ignore")[:300]
            self._send(e.code, json.dumps({"error": f"API 返回 {e.code}: {detail}"}).encode("utf-8"))
        except Exception as e:
            self._send(502, json.dumps({"error": f"请求失败: {e}"}).encode("utf-8"))

    def _proxy(self, method):
        url = COMFY + self.path
        body = None
        if method in ("POST", "PUT"):
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length)
        req = urllib.request.Request(url, data=body, method=method)
        req.add_header("Content-Type", self.headers.get("Content-Type", "application/json"))
        try:
            with urllib.request.urlopen(req, timeout=300) as resp:
                data = resp.read()
                self.send_response(resp.status)
                ctype = resp.headers.get("Content-Type", "application/octet-stream")
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
        except urllib.error.HTTPError as e:
            data = e.read()
            self.send_response(e.code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        except Exception:
            self.send_response(502)
            self.end_headers()
            self.wfile.write(b'{"error":"comfyui unreachable"}')

    def do_GET(self):
        if self.path in ("/", "/index.html", "/ui"):
            self._serve_index()
        elif self.path == "/apicfg":
            hint = API_CONFIG.get("api_key", "")
            hint = ("***" + hint[-4:]) if len(hint) > 4 else ""
            data = json.dumps({"configured": bool(API_CONFIG),
                               "base_url": API_CONFIG.get("base_url", ""),
                               "model": API_CONFIG.get("model", ""),
                               "key_hint": hint}).encode("utf-8")
            self._send(200, data)
        elif self.path == "/tagsdata":
            with open(TAGS_PATH, "rb") as f:
                data = f.read()
            self._send(200, data, ctype="application/json; charset=utf-8")
        else:
            self._proxy("GET")

    def do_POST(self):
        if self.path == "/nlapi":
            length = int(self.headers.get("Content-Length", 0))
            self._nlapi(self.rfile.read(length))
        elif self.path == "/upload_b64":
            length = int(self.headers.get("Content-Length", 0))
            self._upload_b64(self.rfile.read(length))
        elif self.path == "/tagsdata":
            length = int(self.headers.get("Content-Length", 0))
            self._tagsdata_save(self.rfile.read(length))
        else:
            self._proxy("POST")

    def _tagsdata_save(self, body):
        """词库编辑保存: 校验结构 -> 保留 syn/assoc/quality -> 只替换 tag_db"""
        try:
            req = json.loads(body.decode("utf-8"))
            tag_db = req.get("tag_db")
            if not isinstance(tag_db, list) or not tag_db:
                return self._send(400, b'{"error":"tag_db must be a non-empty list"}')
            for g in tag_db:
                if not isinstance(g, dict) or not g.get("cat") \
                        or not isinstance(g.get("tags"), list):
                    return self._send(400, b'{"error":"bad group structure"}')
                for o in g["tags"]:
                    if not isinstance(o, dict) or not o.get("en") or not o.get("cn"):
                        return self._send(400, b'{"error":"bad tag structure"}')
                    if any(c in str(o["en"]) for c in ',"') \
                            or any(c in str(o["cn"]) for c in ',"'):
                        return self._send(400, ("tag contains comma/quote: "
                                                + str(o.get("en"))).encode("utf-8"))
            with open(TAGS_PATH, encoding="utf-8") as f:
                data = json.load(f)
            data["tag_db"] = tag_db
            with open(TAGS_PATH, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=1)
            self._send(200, json.dumps({
                "ok": True, "groups": len(tag_db),
                "tags": sum(len(g["tags"]) for g in tag_db)}).encode("utf-8"))
        except Exception as e:
            self._send(500, json.dumps({"error": str(e)}).encode("utf-8"))

    def _upload_b64(self, body):
        try:
            req = json.loads(body.decode("utf-8"))
            name = os.path.basename(str(req.get("name", "upload.png")))
            data = base64.b64decode(str(req.get("data", "")))
            if not data:
                return self._send(400, json.dumps({"error": "empty data"}).encode("utf-8"))
            dst = os.path.join(COMFY_INPUT_DIR, name)
            with open(dst, "wb") as f:
                f.write(data)
            self._send(200, json.dumps({"name": name, "subfolder": "", "type": "input"}).encode("utf-8"))
        except Exception as e:
            self._send(500, json.dumps({"error": str(e)}).encode("utf-8"))

    def do_PUT(self):
        self._proxy("PUT")

    def _serve_index(self):
        with open(r"C:\AI\easy-ui\index.html", "rb") as f:
            data = f.read()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *args):
        pass

server = http.server.ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
print(f"Easy UI ready -> http://127.0.0.1:{PORT}", flush=True)
server.serve_forever()
