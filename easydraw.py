# -*- coding: utf-8 -*-
"""Easy Draw 桌面版 —— 不依赖浏览器的原生 Tkinter 界面 (iOS 设计风格)
浅色 grouped 布局 / #007AFF 主色 / 分段控件 / iOS 开关 / 圆角胶囊标签 / 发丝线
直接对话 ComfyUI(8188) 出图；本地词典/API 双通道中文转标签；
标签库 17 分类 377 词；R18 分级联动；三档生成模式。
运行: pythonw easydraw.py   自检: python easydraw.py --selftest
"""
import os, sys, json, re, csv, time, random, shutil, socket, threading, subprocess, io
import urllib.request, urllib.error
from urllib.parse import quote as urlquote
import tkinter as tk
from tkinter import ttk, filedialog, font as tkfont
from PIL import Image, ImageTk, ImageDraw

BASE = os.path.dirname(os.path.abspath(__file__))
# 打包为 exe 后: 只读数据(tags_data/danbooru)从临时解包目录取;
# 与 exe 同目录的文件优先(供外置 api_config.json 等可编辑文件)
FROZEN = bool(getattr(sys, "frozen", False))
if FROZEN:
    BASE = getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
    EXE_DIR = os.path.dirname(sys.executable)
else:
    EXE_DIR = BASE
COMFY = "http://127.0.0.1:8188"
COMFY_INPUT = r"C:\AI\ComfyUI\input"
COMFY_OUTPUT = r"C:\AI\ComfyUI\output"
COMFY_PY = r"C:\AI\ComfyUI\venv\Scripts\python.exe"
LLAMA_EXE = r"C:\Users\ZE XUAN\llama.cpp\llama-server.exe"
LLAMA_MODEL = r"C:\Users\ZE XUAN\models\Qwen3.5-9B-abliterated-Q4_K_M.gguf"
# 配置文件: exe 同目录优先(可外置编辑), 否则用打包内置的
API_CFG = os.path.join(EXE_DIR, "api_config.json")
if not os.path.exists(API_CFG):
    API_CFG = os.path.join(BASE, "api_config.json")
CREATE_NO_WINDOW = 0x08000000

# ================= iOS 设计系统 (Light) =================
C_PAGE = "#F2F2F7"       # systemGroupedBackground
C_CARD = "#FFFFFF"       # 卡片
C_HAIR = "#E5E5EA"       # separator
C_FIELD = "#E9E9EB"      # 输入框/未选中段/关态开关
C_TRACK = "#D1D1D6"      # 滑轨
C_BLUE = "#007AFF"       # systemBlue
C_GREEN = "#34C759"      # systemGreen
C_RED = "#FF3B30"        # systemRed
C_ORANGE = "#FF9500"     # systemOrange
C_LABEL = "#1C1C1E"      # 主文字
C_SEC = "#8E8E93"        # 次文字
C_SEC2 = "#6D6D72"       # 分组头
C_SEG_TXT = "#3A3A3C"    # 未选中段文字
C_CHIP_OFF = "#E9E9EB"
C_CHIP_OFF_H = "#D8D8DC"
C_DISABLED_BG = "#E9E9EB"
C_DISABLED_FG = "#AEAEB2"

F = ("Segoe UI", 9)
FB = ("Segoe UI", 9, "bold")
F11 = ("Segoe UI", 11)
F12B = ("Segoe UI", 11, "bold")
FTITLE = ("Segoe UI", 19, "bold")
FSEG = ("Segoe UI", 9)
FBTN = ("Segoe UI", 13, "bold")
BUILD = "build 20261109a"

# ================= 数据加载 =================
_DATA_PATH = os.path.join(EXE_DIR, "tags_data.json")
if not os.path.exists(_DATA_PATH):
    _DATA_PATH = os.path.join(BASE, "tags_data.json")
DATA_PATH = _DATA_PATH
_DATA = json.load(open(_DATA_PATH, encoding="utf-8"))
TAG_DB = _DATA["tag_db"]
SYN = [(a, b) for a, b in _DATA["syn"]]
ASSOC = _DATA["assoc"]
QUALITY_PREFIX = _DATA["quality"].rstrip(", ") + ", "

DANBOORU_TAGS = set()
try:
    with open(os.path.join(BASE, "danbooru.csv"), "r", encoding="utf-8", errors="ignore") as f:
        for row in csv.reader(f):
            if not row:
                continue
            t = row[0].strip().lower().replace("_", " ")
            if t:
                DANBOORU_TAGS.add(t)
            if len(row) >= 4:
                for a in row[3].split("|"):
                    a = a.strip().lower().replace("_", " ")
                    if a:
                        DANBOORU_TAGS.add(a)
except Exception:
    pass

FORCE_ALLOW = {"masterpiece", "best quality", "very aesthetic", "absurdres", "highres",
               "nsfw", "sfw", "explicit", "questionable", "sensitive", "general"}
# 词库编辑器硬拦截 (未成年相关内容绝对禁止入库)
TAG_BLOCK = {"loli", "shota", "child", "children", "kid", "toddler", "toddlercon",
             "lolicon", "shotacon", "little girl", "young girl"}
SUPPLEMENT = {"bangs", "stockings", "see-through", "sailor uniform", "silver hair",
              "exposed breasts", "creampie", "facial", "clothes pulled", "milking",
              "tanned", "shoulder", "elbow", "hands", "fingers", "ankles", "areolae",
              "erect nipples", "genitals", "slim waist", "wrist restraints",
              "breast feeding", "lying on back", "covering mouth", "doing a split",
              "hands on hips", "japanese house", "natural lighting", "cinematic lighting",
              "dramatic shadow", "rim lighting", "detailed background", "detailed eyes",
              "detailed skin", "petals falling", "blonde hair", "thin waist", "lifelike skin",
              "dynamic angle", "looking away"}
_VALID_LIST = sorted(DANBOORU_TAGS | SUPPLEMENT)


def norm_tag(t):
    t = t.strip().lower().replace("_", " ")
    return re.sub(r"\s+", " ", t)


def repair_tag(t):
    """无效 tag 自动修复: 去前缀/去尾词/去 -ing/复数/模糊匹配; 失败返回空串"""
    n = norm_tag(t)
    if not n:
        return ""
    words = n.split()
    for i in range(len(words)):
        cand = " ".join(words[i:])
        if cand in DANBOORU_TAGS or cand in SUPPLEMENT:
            return cand
    for i in range(len(words), 0, -1):
        cand = " ".join(words[:i])
        if cand in DANBOORU_TAGS or cand in SUPPLEMENT:
            return cand
    if n.endswith("ing") and len(n) > 5:
        for cand in (n[:-3] + "e", n[:-3]):
            if cand in DANBOORU_TAGS or cand in SUPPLEMENT:
                return cand
    for cand in (n + "s", n[:-1] if n.endswith("s") else n):
        if cand in DANBOORU_TAGS or cand in SUPPLEMENT:
            return cand
    import difflib
    m = difflib.get_close_matches(n, _VALID_LIST, n=1, cutoff=0.88)
    return m[0] if m else ""


def valid_tag(t):
    t = norm_tag(t)
    if not t:
        return False
    if t in FORCE_ALLOW or t.startswith("rating:"):
        return True
    return t in DANBOORU_TAGS or t in SUPPLEMENT


def filter_tags(content):
    """校验 -> 自动修复 -> 剔除; 返回 (有效串, 备注)"""
    valid, invalid, fixed = [], [], []
    for t in content.split(","):
        t = t.strip()
        if not t:
            continue
        if valid_tag(t):
            valid.append(t)
            continue
        r = repair_tag(t)
        if r and r not in valid:
            valid.append(r)
            fixed.append(f"{t}->{r}")
        elif r in valid:
            fixed.append(f"{t}->{r}")
        else:
            invalid.append(t)
    notes = []
    if fixed:
        notes.append("自动修复: " + ", ".join(fixed[:6]))
    if invalid:
        shown = ", ".join(invalid[:6])
        more = f" 等{len(invalid)}个" if len(invalid) > 6 else ""
        notes.append(f"剔除无效{len(invalid)}个: {shown}{more}")
    return ", ".join(valid), " | ".join(notes)


# ================= 中文转标签 =================
def nl2tags_local(text):
    """本地词典: 最长匹配优先替换; 返回 (tags, leftover)"""
    work = text
    found = []
    for cn, en in sorted(SYN, key=lambda p: -len(p[0])):
        if cn not in work:
            continue
        found.append(en)
        work = work.replace(cn, "▪")
    leftover = re.sub(r"[\s,，。.、;；!！?？的是的着一在里上和与穿戴着有很]+", "", work.replace("▪", "")).strip()
    out = []
    for t in found:
        if t not in out:
            out.append(t)
    return out, leftover


def expand_semantics(tags):
    added, out = set(), list(tags)
    for t in tags:
        for a in ASSOC.get(t.lower(), []):
            if a not in tags and a not in added:
                added.add(a)
                out.append(a)
    return out, len(added)


NL_SYS = ("You are a Stable Diffusion prompt engineer using Danbooru tag conventions. "
          "Convert the user's Chinese scene description into a comma-separated list of English Danbooru tags "
          "(lowercase, standard spellings like: 1girl, long hair, looking at viewer, cherry blossoms). "
          "Start with quality tags: masterpiece, best quality, very aesthetic. "
          "Keep poses, clothing, expression, scene and composition tags faithful to the description. "
          "Do NOT add photography/realism tags (photorealistic, 8k, ultra-detailed) unless the description "
          "explicitly asks for realism. Avoid redundant or near-duplicate tags. "
          "At most 25 tags. Output ONLY the comma-separated tags, nothing else. "
          "Clothing/term mappings: 和服=kimono, 浴衣=yukata, 水手服=sailor uniform, 旗袍=china dress, "
          "猫耳=cat ears, 兔耳=rabbit ears, 女仆装=maid, 巫女=miko, 女佣装=school swimsuit. "
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


def nl2api(text, expand):
    """API 模式(本地 Qwen 等): 调 OpenAI 兼容接口; 返回 (tags_str, note)"""
    cfg = {}
    if os.path.exists(API_CFG):
        try:
            cfg = json.load(open(API_CFG, encoding="utf-8"))
        except Exception:
            pass
    base = str(cfg.get("base_url", "")).rstrip("/")
    key = str(cfg.get("api_key", "local"))
    model = str(cfg.get("model", ""))
    if not (base and model):
        raise RuntimeError("api_config.json 未配置 base_url/model")
    sys_prompt = NL_SYS + (" After converting, append up to 6 semantically associated tags that enrich the "
                           "scene (environment, lighting, weather, mood, composition) — real Danbooru tags only."
                           if expand else "")
    payload = json.dumps({
        "model": model,
        "messages": [{"role": "system", "content": sys_prompt},
                     {"role": "user", "content": text}],
        "temperature": 0.5 if expand else 0.3,
    }).encode("utf-8")
    url = base + ("/chat/completions" if not base.endswith("/chat/completions") else "")
    req = urllib.request.Request(url, data=payload, method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("Authorization", "Bearer " + key)
    with urllib.request.urlopen(req, timeout=120) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    msg = data["choices"][0]["message"]
    content = (msg.get("content") or "").strip()
    if not content:
        content = (msg.get("reasoning_content") or "").strip()
    content = re.sub(r"(?s)<think>.*?</think>", "", content).strip()
    lines = [l.strip() for l in content.splitlines() if l.strip()]
    tag_lines = [l for l in lines if "," in l]
    if tag_lines:
        content = ", ".join(tag_lines)
    content = content.strip("`\"' \n\r")
    if content.lower().startswith("tags:"):
        content = content[5:].strip()
    return filter_tags(content)


# ================= 各模型提示词生成系统 =================
PROMPT_STYLES = {
    "qwen": {
        "label": "Qwen 自然语言散文",
        "system": (
            "You are a professional image prompt writer for Qwen-Image 2.1. "
            "Convert the user's scene description (usually Chinese) into ONE fluent natural-language "
            "paragraph prompt for text-to-image generation. Include: subject (adult age, appearance), "
            "action/pose, setting, lighting, composition/camera, and key details. "
            "Reply in English. Do NOT use booru tags or comma-separated tag lists. No quality words. "
            "Output only the prompt."
        ),
        "example": "一个穿白衬衫的年轻女人坐在湖边木栈道上看日出，薄雾，柔和金色光线，全身，清晰对焦",
    },
    "noctq": {
        "label": "Noct-Q 照片描述",
        "system": (
            "You are a prompt writer for photorealistic image models. Convert the user's scene "
            "description (usually Chinese) into ONE fluent English photo-caption style prompt: "
            "who the person is (adult age, appearance), what she does, where she is, the light and "
            "the framing (full body / upper body / close-up). "
            "Reply in English. No booru tags, no quality words, no tag lists. Output only the prompt."
        ),
        "example": "一位二十多岁的长发女人穿着白色亚麻衬衫，坐在湖边木栈道上看日出，薄雾，晨光，全身镜头",
    },
    "sdxl": {
        "label": "SDXL 写实摄影",
        "system": (
            "You are a prompt writer for a photorealistic SDXL model. Convert the user's scene "
            "description (usually Chinese) into a concise English prompt. Write a natural photo "
            "description of the subject (adult, appearance), pose, setting and light, then append "
            "a few photographic modifiers (e.g. photograph, 35mm, natural light, detailed skin "
            "texture, sharp focus). A few booru tags are acceptable. Output only the prompt."
        ),
        "example": "二十多岁的女人，白色衬衫，坐在窗边木椅上，午后自然光，写实摄影",
    },
}

LOCAL_STYLE_SUFFIX = {
    "qwen": "cinematic lighting, detailed, natural composition",
    "noctq": "photograph, natural lighting, full body, detailed skin texture",
    "sdxl": "photograph, 35mm, natural light, detailed skin texture, sharp focus",
}


def model_style_key(model_name):
    if model_name.startswith("Qwen-Image"):
        return "qwen"
    if model_name.startswith("Noct-Q"):
        return "noctq"
    if model_name.startswith("SDXL 写实"):
        return "sdxl"
    return "noobai"


def nl2natural(text, kind):
    """调本地 LLM 把描述生成对应模型风格的提示词（OpenAI 兼容接口）"""
    cfg = {}
    if os.path.exists(API_CFG):
        try:
            cfg = json.load(open(API_CFG, encoding="utf-8"))
        except Exception:
            pass
    base = str(cfg.get("base_url", "")).rstrip("/")
    key = str(cfg.get("api_key", "local"))
    model = str(cfg.get("model", ""))
    if not (base and model):
        raise RuntimeError("api_config.json 未配置 base_url/model")
    style = PROMPT_STYLES[kind]
    payload = json.dumps({
        "model": model,
        "messages": [{"role": "system", "content": style["system"]},
                     {"role": "user", "content": text}],
        "temperature": 0.7,
        "max_tokens": 420,
        "chat_template_kwargs": {"enable_thinking": False},
    }).encode("utf-8")
    url = base + ("/chat/completions" if not base.endswith("/chat/completions") else "")
    req = urllib.request.Request(url, data=payload, method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("Authorization", "Bearer " + key)
    with urllib.request.urlopen(req, timeout=180) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    msg = data["choices"][0]["message"]
    content = (msg.get("content") or "").strip()
    if not content:
        content = (msg.get("reasoning_content") or "").strip()
    content = re.sub(r"(?s)<think>.*?</think>", "", content).strip()
    content = content.strip("`\"' \n\r")
    # 有些模型会输出思考过程/前言，取最后一段实际内容
    low = content.lower()
    if low.startswith("thinking") or "thinking process" in low[:40] or \
            "思考过程" in content[:40] or "reasoning:" in low[:40]:
        paras = [p.strip() for p in content.split("\n\n") if p.strip()]
        content = paras[-1] if paras else content
    if "\n\n" in content:
        content = content.split("\n\n")[0]
    return content.strip()


def local_style_expand(text, kind):
    """LLM 不可用时的本地兜底：中文原样 + 风格后缀（SDXL 先转标签）"""
    if kind == "sdxl":
        tags, leftover = nl2tags_local(text)
        base = ", ".join(tags) if tags else text
        return (base + ", " + LOCAL_STYLE_SUFFIX[kind]).strip(", ")
    suffix = LOCAL_STYLE_SUFFIX.get(kind, "")
    return (text + (", " + suffix if suffix else "")).strip()


# ================= Comfy 交互 =================
def port_open(port, timeout=0.4):
    try:
        s = socket.create_connection(("127.0.0.1", port), timeout)
        s.close()
        return True
    except Exception:
        return False


def upload_ref(path):
    """把参考图复制进 ComfyUI input（同名覆盖，与浏览器 overwrite 一致）"""
    name = os.path.basename(path)
    dst = os.path.join(COMFY_INPUT, name)
    if os.path.abspath(path) != os.path.abspath(dst):
        shutil.copy(path, dst)
    return name


def build_workflow(mode, pos, neg, w, h, steps, cfg, seed, denoise, ipweight, refname):
    """与浏览器版逐节点一致的 workflow JSON"""
    wf = {
        "1": {"class_type": "CheckpointLoaderSimple",
              "inputs": {"ckpt_name": "NoobAI-XL-Vpred-v1.0.safetensors"}},
        "2": {"class_type": "ModelSamplingDiscrete",
              "inputs": {"model": ["1", 0], "sampling": "v_prediction", "zsnr": True}},
        "15": {"class_type": "RescaleCFG",
               "inputs": {"model": ["2", 0], "multiplier": 0.7}},
        "3": {"class_type": "CLIPTextEncode", "inputs": {"text": pos, "clip": ["1", 1]}},
        "4": {"class_type": "CLIPTextEncode", "inputs": {"text": neg, "clip": ["1", 1]}},
        "6": {"class_type": "KSampler",
              "inputs": {"seed": seed, "steps": steps, "cfg": cfg,
                         "sampler_name": "euler_ancestral", "scheduler": "normal",
                         "denoise": 1.0 if mode == "t2i" else denoise,
                         "model": ["15", 0], "positive": ["3", 0], "negative": ["4", 0],
                         "latent_image": ["10", 0] if mode == "i2i"
                         else (["10", 0] if mode == "charref" and denoise < 1
                               else (["14", 0] if mode == "charref" else ["5", 0]))}},
        "7": {"class_type": "VAEDecode", "inputs": {"samples": ["6", 0], "vae": ["1", 2]}},
        "8": {"class_type": "SaveImage", "inputs": {"images": ["7", 0], "filename_prefix": "easy_ui"}},
    }
    if mode == "i2i":
        wf["5"] = {"class_type": "LoadImage", "inputs": {"image": refname}}
        wf["10"] = {"class_type": "VAEEncode", "inputs": {"pixels": ["5", 0], "vae": ["1", 2]}}
    elif mode == "charref":
        wf["5"] = {"class_type": "LoadImage", "inputs": {"image": refname}}
        wf["10"] = {"class_type": "VAEEncode", "inputs": {"pixels": ["5", 0], "vae": ["1", 2]}}
        wf["11"] = {"class_type": "IPAdapterModelLoader",
                    "inputs": {"ipadapter_file": "ip-adapter-plus_sdxl_vit-h.safetensors"}}
        wf["12"] = {"class_type": "CLIPVisionLoader",
                    "inputs": {"clip_name": "clip_vision_h_vith.safetensors"}}
        wf["13"] = {"class_type": "IPAdapterAdvanced",
                    "inputs": {"model": ["1", 0], "ipadapter": ["11", 0], "image": ["5", 0],
                               "clip_vision": ["12", 0], "weight": ipweight,
                               "weight_type": "ease out", "combine_embeds": "concat",
                               "start_at": 0, "end_at": 1, "embeds_scaling": "V only"}}
        wf["2"]["inputs"]["model"] = ["13", 0]
        wf["14"] = {"class_type": "EmptyLatentImage",
                    "inputs": {"width": w, "height": h, "batch_size": 1}}
    else:
        wf["5"] = {"class_type": "EmptyLatentImage",
                   "inputs": {"width": w, "height": h, "batch_size": 1}}
    return wf


QWEN_TURBO_UNET = "qwen_image_2.1_turbo_w4a8_convrot.safetensors"
QWEN_NOCTQ_UNET = "NoctQ_V4_int8_convrot.safetensors"
QWEN_CLIP = "qwen3vl_8b_w4a8.safetensors"
QWEN_VAE = "qwen_image_2.1_vae_bf16.safetensors"
# Qwen-Image 2.1 Turbo 蒸馏 checkpoint 内置的 8 步 sigma 调度（不能换普通 euler/simple）
QWEN_TURBO_SIGMAS = ("1.0, 0.978453, 0.95418, 0.926626, 0.89508, "
                     "0.845148, 0.704534, 0.414568, 0")
# Noct-Q 推荐的通用负向词（结构/手部/画质）
QWEN_NEG = ("artifacts, washed-out colors, low quality, low resolution, blurry, "
            "sloppy lines, rough sketch, malformed limbs, bad hands, extra fingers, "
            "fused fingers, distorted anatomy, deformed face")

# 画幅：Qwen 用 1MP 官方比例（~1024），NoobAI 用 SDXL 比例
QWEN_RATIOS = ["1024x1024  方图", "1024x1280  竖图", "896x1152  小竖图",
               "1152x896  横图", "768x1344  长竖图"]
NOOBAI_RATIOS = ["832x1216  竖图", "1024x1024  方图", "1216x832  横图",
                 "768x1152  小竖图"]


def build_workflow_qwen(kind, pos, neg, w, h, steps, cfg, seed):
    """Qwen-Image 2.1 工作流。
    kind='turbo' 原版 8 步蒸馏（自然语言）；kind='noctq' 无审查 25 步 merge。
    SaveImage 固定节点 8，后端 _gen_worker 按节点 8 取图。"""
    unet = QWEN_TURBO_UNET if kind == "turbo" else QWEN_NOCTQ_UNET
    wf = {
        "1": {"class_type": "UNETLoader",
              "inputs": {"unet_name": unet, "weight_dtype": "default"}},
        "2": {"class_type": "CLIPLoader",
              "inputs": {"clip_name": QWEN_CLIP, "type": "qwen_image",
                         "device": "default"}},
        "3": {"class_type": "VAELoader", "inputs": {"vae_name": QWEN_VAE}},
        "4": {"class_type": "TextEncodeQwenImage21",
              "inputs": {"clip": ["2", 0], "prompt": pos,
                         "negative_prompt": neg or " ", "resolution": 1024}},
        "5": {"class_type": "EmptyLatentImage",
              "inputs": {"width": w, "height": h, "batch_size": 1}},
    }
    if kind == "turbo":
        wf.update({
            "6": {"class_type": "QwenImage21Cache",
                  "inputs": {"model": ["1", 0], "device": "cpu", "dtype": "int8"}},
            "7": {"class_type": "CFGGuider",
                  "inputs": {"model": ["6", 0], "positive": ["4", 0],
                             "negative": ["4", 1], "cfg": 1.0}},
            "9": {"class_type": "KSamplerSelect",
                  "inputs": {"sampler_name": "euler"}},
            "10": {"class_type": "RandomNoise", "inputs": {"noise_seed": seed}},
            "11": {"class_type": "ManualSigmas",
                   "inputs": {"sigmas": QWEN_TURBO_SIGMAS}},
            "12": {"class_type": "SamplerCustomAdvanced",
                   "inputs": {"noise": ["10", 0], "guider": ["7", 0],
                              "sampler": ["9", 0], "sigmas": ["11", 0],
                              "latent_image": ["5", 0]}},
            "13": {"class_type": "VAEDecodeTiled",
                   "inputs": {"samples": ["12", 0], "vae": ["3", 0],
                              "tile_size": 512, "overlap": 64,
                              "temporal_size": 64, "temporal_overlap": 8}},
            "8": {"class_type": "SaveImage",
                  "inputs": {"images": ["13", 0], "filename_prefix": "easy_qwen"}},
        })
    else:
        wf.update({
            "6": {"class_type": "KSampler",
                  "inputs": {"seed": seed, "steps": steps, "cfg": cfg,
                             "sampler_name": "euler", "scheduler": "simple",
                             "denoise": 1.0, "model": ["1", 0],
                             "positive": ["4", 0], "negative": ["4", 1],
                             "latent_image": ["5", 0]}},
            "7": {"class_type": "VAEDecodeTiled",
                  "inputs": {"samples": ["6", 0], "vae": ["3", 0],
                             "tile_size": 512, "overlap": 64,
                             "temporal_size": 64, "temporal_overlap": 8}},
            "8": {"class_type": "SaveImage",
                  "inputs": {"images": ["7", 0], "filename_prefix": "easy_noctq"}},
        })
    return wf


REAL_SDXL_CKPT = "pornworksRealPornPhoto_v04.safetensors"
# 写实 SDXL 的默认负向词（人体/画质）
REAL_SDXL_NEG = ("lowres, bad anatomy, bad hands, extra fingers, fused fingers, "
                 "missing fingers, deformed, distorted face, blurry, jpeg artifacts, "
                 "worst quality, low quality, watermark, text")


def build_workflow_sdxl(pos, neg, w, h, steps, cfg, seed):
    """写实 SDXL checkpoint 工作流（epsilon 预测，dpmpp_2m + karras）。
    SaveImage 固定节点 8，后端按 8 取图。"""
    return {
        "1": {"class_type": "CheckpointLoaderSimple",
              "inputs": {"ckpt_name": REAL_SDXL_CKPT}},
        "3": {"class_type": "CLIPTextEncode", "inputs": {"text": pos, "clip": ["1", 1]}},
        "4": {"class_type": "CLIPTextEncode", "inputs": {"text": neg, "clip": ["1", 1]}},
        "5": {"class_type": "EmptyLatentImage",
              "inputs": {"width": w, "height": h, "batch_size": 1}},
        "6": {"class_type": "KSampler",
              "inputs": {"seed": seed, "steps": steps, "cfg": cfg,
                         "sampler_name": "dpmpp_2m", "scheduler": "karras",
                         "denoise": 1.0, "model": ["1", 0],
                         "positive": ["3", 0], "negative": ["4", 0],
                         "latent_image": ["5", 0]}},
        "7": {"class_type": "VAEDecode",
              "inputs": {"samples": ["6", 0], "vae": ["1", 2]}},
        "8": {"class_type": "SaveImage",
              "inputs": {"images": ["7", 0], "filename_prefix": "easy_real"}},
    }


def http_json(url, payload=None, timeout=60):
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(url, data=data, method="POST" if data else "GET")
    if data:
        req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


# ================= iOS 控件 =================
def _hover(btn, normal, hover):
    """普通按钮悬停变色"""
    btn.bind("<Enter>", lambda e: btn.configure(bg=hover))
    btn.bind("<Leave>", lambda e: btn.configure(bg=normal))


# ---- PIL 抗锯齿渲染 (Tk canvas 无抗锯齿, 圆角用超采样绘制) ----
_AA = 4


def _hex_rgb(c):
    """#RRGGBB -> (r, g, b)"""
    c = c.lstrip("#")
    return tuple(int(c[i:i + 2], 16) for i in (0, 2, 4))


def _mixc(c1, c2, t):
    """两个 #RRGGBB 颜色线性插值"""
    a, b = _hex_rgb(c1), _hex_rgb(c2)
    return "#%02X%02X%02X" % tuple(
        max(0, min(255, round(a[i] + (b[i] - a[i]) * t))) for i in range(3))


def _aa_roundrect(w, h, r, fill, fill2=None):
    """4x 超采样 + LANCZOS 缩小 -> 抗锯齿圆角矩形 RGBA 图;
    fill2 给定时做垂直渐变 (顶部 fill -> 底部 fill2)"""
    w, h = max(int(w), 1), max(int(h), 1)
    if fill2 and fill2 != fill:
        mask = Image.new("L", (w * _AA, h * _AA), 0)
        dm = ImageDraw.Draw(mask)
        dm.rounded_rectangle([0, 0, w * _AA - 1, h * _AA - 1],
                             radius=max(int(r * _AA), 0), fill=255)
        grad = Image.new("RGB", (1, h * _AA))
        c1, c2 = _hex_rgb(fill), _hex_rgb(fill2)
        px = grad.load()
        for y in range(h * _AA):
            t = y / max(h * _AA - 1, 1)
            px[0, y] = tuple(round(c1[i] + (c2[i] - c1[i]) * t) for i in range(3))
        grad = grad.resize((w * _AA, h * _AA))
        img = Image.new("RGBA", (w * _AA, h * _AA), (0, 0, 0, 0))
        img.paste(grad, (0, 0), mask)
        return img.resize((w, h), Image.LANCZOS)
    img = Image.new("RGBA", (w * _AA, h * _AA), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([0, 0, w * _AA - 1, h * _AA - 1],
                        radius=max(int(r * _AA), 0), fill=fill)
    return img.resize((w, h), Image.LANCZOS)


def _aa_pill(w, h, fill):
    return _aa_roundrect(w, h, h / 2, fill)


def _aa_switch_img(on, w=46, h=26):
    """整颗 iOS 开关(轨道+滑钮)一次性渲染"""
    img = Image.new("RGBA", (w * _AA, h * _AA), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    track = C_GREEN if on else "#E9E9EB"
    d.rounded_rectangle([0, 0, w * _AA - 1, h * _AA - 1],
                        radius=h * _AA // 2, fill=track)
    kr = 11 * _AA
    cx = (33 if on else 13) * _AA
    cy = h * _AA // 2
    d.ellipse([cx - kr, cy - kr, cx + kr, cy + kr],
              fill="#FFFFFF", outline="#D1D1D6", width=max(_AA // 2, 1))
    return img.resize((w, h), Image.LANCZOS)


class IOSButton(tk.Canvas):
    """圆角按钮 (canvas 实现, 支持悬停/禁用)"""

    def __init__(self, parent, text, command, bg=C_BLUE, fg="#FFFFFF",
                 hover_bg=None, base=None, h=44, r=10, font=FBTN, padx=24):
        super().__init__(parent, height=h, highlightthickness=0, cursor="hand2",
                         bg=base or str(parent.cget("bg")))
        self._text, self._cmd = text, command
        self._bg, self._fg = bg, fg
        self._hover_bg = hover_bg or bg
        self._base = base or str(parent.cget("bg"))
        self._r, self._font, self._padx = r, font, padx
        self._enabled = True
        self._hover = False
        self._pressed = False
        self.bind("<Configure>", lambda e: self._draw())
        self.bind("<Button-1>", self._click)
        self.bind("<Enter>", self._enter)
        self.bind("<Leave>", self._leave)

    def _colors(self):
        if not self._enabled:
            return C_DISABLED_BG, C_DISABLED_FG
        return (self._hover_bg if self._hover else self._bg), self._fg

    def _draw(self):
        w = self.winfo_width()
        if w < 4:
            return
        self.delete("all")
        bg, fg = self._colors()
        h = int(self.cget("height"))
        if self._enabled:
            # 垂直微渐变: 顶部提亮 -> 底部压暗; 按压时整体加深
            top = _mixc(bg, "#FFFFFF", .14 if not self._pressed else .04)
            bot = _mixc(bg, "#000000", .05 + (.10 if self._pressed else 0))
            self._bgimg = ImageTk.PhotoImage(
                _aa_roundrect(w - 2, h - 2, self._r, top, bot))
        else:
            self._bgimg = ImageTk.PhotoImage(
                _aa_roundrect(w - 2, h - 2, self._r, bg))
        self.create_image(1, 1, image=self._bgimg, anchor="nw")
        self.create_text(w / 2, h / 2, text=self._text, font=self._font, fill=fg)

    def _click(self, _e):
        if self._enabled and self._cmd and not self._pressed:
            self._pressed = True
            self._draw()

            def _fire():
                self._pressed = False
                self._draw()
                try:
                    self._cmd()
                except Exception:
                    pass
            self.after(90, _fire)

    def _enter(self, _e):
        if self._enabled:
            self._hover = True
            self._draw()

    def _leave(self, _e):
        if self._hover:
            self._hover = False
            self._draw()

    def set_enabled(self, on):
        self._enabled = bool(on)
        self.configure(cursor="hand2" if on else "arrow")
        self._draw()

    def set_text(self, t):
        self._text = t
        self._draw()


def ios_segment(parent, options, variable, onchange=None, base=C_FIELD, font=FSEG):
    """UISegmentedControl: options=[(value, label)]"""
    box = tk.Frame(parent, bg=base, padx=2, pady=2)
    segs = []

    def paint():
        cur = variable.get()
        for val, w in segs:
            on = (val == cur)
            w.configure(bg=C_CARD if on else base,
                        fg=C_LABEL if on else C_SEG_TXT)

    def pick(val):
        variable.set(val)
        paint()
        if onchange:
            onchange()

    for val, label in options:
        w = tk.Label(box, text=label, font=font, padx=12, pady=4,
                     bg=base, fg=C_SEG_TXT, cursor="hand2")
        w.pack(side="left")
        w.bind("<Button-1>", lambda e, v=val: pick(v))
        segs.append((val, w))
    paint()
    return box


def ios_switch(parent, variable, base=C_CARD, onchange=None):
    """UISwitch: 绿色开 / 灰色关 (PIL 抗锯齿整图)"""
    cv = tk.Canvas(parent, width=46, height=26, bg=base, highlightthickness=0,
                   cursor="hand2")
    img_on = ImageTk.PhotoImage(_aa_switch_img(True))
    img_off = ImageTk.PhotoImage(_aa_switch_img(False))
    cv._imgs = (img_on, img_off)          # 持有引用防止被垃圾回收
    item = cv.create_image(0, 0, image=img_off, anchor="nw")

    def paint():
        on = bool(variable.get())
        cv.itemconfig(item, image=img_on if on else img_off)

    def toggle():
        variable.set(not variable.get())
        paint()
        if onchange:
            onchange()

    cv.bind("<Button-1>", lambda e: toggle())
    paint()
    return cv


# ================= 主界面 =================
class EasyDraw(tk.Tk):
    def __init__(self, selftest=False):
        super().__init__()
        self.title("Easy Draw 桌面版 · NoobAI-XL v-pred")
        self.geometry("1460x940")
        self.minsize(1180, 760)
        self.configure(bg=C_PAGE)
        self._img_photo = None
        self._last_img_bytes = None
        self._last_filename = None
        self._gen_busy = False
        self.chips = {}          # en -> {cv, img_id, txt_id, w, sel}
        self._chipkey2en = {}    # canvas tag key -> en
        self._pill_cache = {}    # (w,h,fill) -> PhotoImage
        self._hover_en = None
        self._sel_set = set()
        self._search_after_id = None
        self._pos_after_id = None
        self._resize_after_id = None
        self._last_avail = 0
        self._expose_pend = False
        # 窗口被遮挡期间的排版更新, 暴露时屏幕可能残留旧画面;
        # 画布获得 Expose 时防抖一次 update() 推到屏幕 (无视觉位移, 不闪烁)
        self.ref_path = None
        if selftest:
            self.withdraw()
        else:
            # 两阶段启动: 先秒开窗口骨架, 再构建完整 UI
            self._splash = tk.Label(self, text="正在加载…", font=F11,
                                    bg=C_PAGE, fg=C_SEC)
            self._splash.pack(expand=True)
            self.update()
        t0 = time.perf_counter()
        self._build_ui()
        self._build_ms = (time.perf_counter() - t0) * 1000
        # 端口探测与首批标签延迟执行, 保证窗口秒开
        self.after(200, self._poll_services)
        self.after(1, self.rebuild_tags)
        self.after(4000, self._poll_services_loop)

    # ---------- 通用小件 ----------
    def _hair(self, parent, padx=0):
        return tk.Frame(parent, height=1, bg=C_HAIR)

    def _section(self, parent, title, padx=10, top=10):
        """灰色分组头 + 白色卡片; 返回 (card, inner)。card._hdr 为标题(可随卡片显隐)"""
        hdr = None
        if title:
            hdr = tk.Label(parent, text=title, font=F12B, bg=C_PAGE, fg=C_SEC2)
            hdr.pack(anchor="w", padx=16, pady=(top, 4))
        card = tk.Frame(parent, bg=C_CARD)
        card.pack(fill="x", padx=padx)
        card._hdr = hdr
        inner = tk.Frame(card, bg=C_CARD)
        inner.pack(fill="both", expand=True)
        return card, inner

    # ---------- UI 构建 ----------
    def _build_ui(self):
        sp = getattr(self, "_splash", None)
        if sp is not None:
            sp.destroy()
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except Exception:
            pass
        style.configure(".", background=C_CARD, foreground=C_LABEL,
                        fieldbackground=C_CARD, bordercolor=C_HAIR)
        style.configure("TLabel", background=C_CARD, foreground=C_LABEL)
        style.configure("TFrame", background=C_CARD)
        style.configure("TCheckbutton", background=C_CARD, foreground=C_LABEL)
        style.configure("TRadiobutton", background=C_CARD, foreground=C_LABEL)
        style.configure("TCombobox", fieldbackground=C_CARD, background=C_CARD,
                        foreground=C_LABEL, arrowcolor=C_SEC, bordercolor=C_HAIR)
        style.map("TCombobox",
                  fieldbackground=[("readonly", C_CARD)],
                  foreground=[("readonly", C_LABEL)],
                  selectbackground=[("readonly", C_CARD)],
                  selectforeground=[("readonly", C_LABEL)],
                  arrowcolor=[("active", C_LABEL)])
        style.configure("Vertical.TScrollbar", background=C_TRACK, troughcolor=C_CARD,
                        bordercolor=C_CARD, arrowcolor=C_SEC, relief="flat")

        self._chip_font = tkfont.Font(family="Segoe UI", size=9)
        self.CHIP_H = 24
        self.ROW_GAP = 6
        self.CHIP_GAP = 6

        # ================= 顶栏 (iOS 导航栏) =================
        nav = tk.Frame(self, bg=C_CARD, height=64)
        nav.pack(fill="x")
        nav.pack_propagate(False)
        nrow = tk.Frame(nav, bg=C_CARD)
        nrow.pack(fill="both", expand=True, padx=16)
        left = tk.Frame(nrow, bg=C_CARD)
        left.pack(side="left")
        tk.Label(left, text="Easy Draw", font=FTITLE, bg=C_CARD, fg=C_LABEL).pack(
            side="left", pady=8)
        tk.Label(left, text="  NoobAI-XL v-pred", font=F, bg=C_CARD, fg=C_SEC).pack(
            side="left")

        right = tk.Frame(nrow, bg=C_CARD)
        right.pack(side="right")

        def svc_group(name, command):
            g = tk.Frame(right, bg=C_CARD)
            lbl = tk.Label(g, text=f"● {name}", font=F, bg=C_CARD, fg=C_SEC)
            lbl.pack(side="left")
            btn = tk.Button(g, text="启动", font=F, command=command, bg=C_CARD,
                            fg=C_BLUE, activebackground=C_PAGE, activeforeground=C_BLUE,
                            relief="flat", padx=6, cursor="hand2")
            btn.pack(side="left", padx=(4, 14))
            _hover(btn, C_CARD, C_PAGE)
            g.pack(side="left")
            return lbl

        self.lbl_comfy = svc_group("ComfyUI", self.start_comfy)
        self.lbl_llm = svc_group("本地LLM", self.start_llm)
        tk.Label(right, text=BUILD, font=F, bg=C_CARD, fg=C_SEC).pack(side="left")

        tk.Frame(self, height=1, bg=C_TRACK).pack(fill="x")

        # ================= 主体三分栏 =================
        main = tk.PanedWindow(self, orient="horizontal", sashwidth=5,
                              bg=C_PAGE, bd=0, relief="flat")
        main.pack(fill="both", expand=True, padx=0, pady=0)

        # ---------------- 左栏 ----------------
        left_col = tk.Frame(main, bg=C_PAGE, width=470)
        main.add(left_col, width=470)

        # 提示词
        prompt_card, pc = self._section(left_col, "提示词", top=12)
        self._prompt_sec = prompt_card
        phdr = tk.Frame(pc, bg=C_CARD)
        phdr.pack(fill="x", padx=12, pady=(10, 2))
        tk.Label(phdr, text="正面提示词（点右侧标签自动补进）", font=F, bg=C_CARD,
                 fg=C_SEC).pack(side="left")
        btn_clear = tk.Button(phdr, text="清空", font=F, bg=C_CARD, fg=C_RED,
                              activebackground="#FFE5E4", activeforeground=C_RED,
                              relief="flat", bd=0, padx=8, pady=0, cursor="hand2",
                              command=self._clear_positive)
        btn_clear.pack(side="right")
        _hover(btn_clear, C_CARD, "#FFE5E4")
        self.pos_text = tk.Text(pc, height=7, font=F, bg=C_CARD, fg=C_LABEL,
                                insertbackground=C_LABEL, relief="flat", wrap="word",
                                padx=8, pady=6, highlightthickness=1,
                                highlightbackground=C_HAIR, highlightcolor=C_BLUE)
        self.pos_text.pack(fill="x", padx=12, pady=(0, 8))
        self.pos_text.insert("1.0", "masterpiece, best quality, very aesthetic, 1girl, upper body, "
                                    "looking at viewer, cherry blossoms, night, wind")
        self.pos_text.bind("<KeyRelease>", self._on_pos_key)
        tk.Label(pc, text="负面提示词（留默认即可）", font=F, bg=C_CARD,
                 fg=C_SEC).pack(anchor="w", padx=12)
        self.neg_text = tk.Text(pc, height=3, font=F, bg=C_CARD, fg=C_LABEL,
                                insertbackground=C_LABEL, relief="flat", wrap="word",
                                padx=8, pady=6, highlightthickness=1,
                                highlightbackground=C_HAIR, highlightcolor=C_BLUE)
        self.neg_text.pack(fill="x", padx=12, pady=(2, 12))
        self.neg_text.insert("1.0", "worst quality, bad quality, lowres, bad anatomy, bad hands, jpeg artifacts")

        # 自然语言转换
        nl_card, nc = self._section(left_col, "自然语言 → 标准提示词", top=12)
        self._nl_sec = nl_card
        nrow1 = tk.Frame(nc, bg=C_CARD)
        nrow1.pack(fill="x", padx=12, pady=(10, 6))
        self.nl_mode = tk.StringVar(value="local")
        ios_segment(nrow1, [("local", "本地词典"), ("api", "API")],
                    self.nl_mode).pack(side="left")
        self.nl_expand = tk.BooleanVar(value=False)
        tk.Label(nrow1, text="语义扩展", font=F, bg=C_CARD, fg=C_LABEL).pack(
            side="left", padx=(14, 4))
        ios_switch(nrow1, self.nl_expand).pack(side="left")
        self.nl_replace = tk.BooleanVar(value=False)
        tk.Label(nrow1, text="替换", font=F, bg=C_CARD, fg=C_LABEL).pack(
            side="left", padx=(10, 4))
        ios_switch(nrow1, self.nl_replace).pack(side="left")
        self.nl_text = tk.Text(nc, height=3, font=F, bg=C_CARD, fg=C_LABEL,
                               insertbackground=C_LABEL, relief="flat", wrap="word",
                               padx=8, pady=6, highlightthickness=1,
                               highlightbackground=C_HAIR, highlightcolor=C_BLUE)
        self.nl_text.pack(fill="x", padx=12, pady=(2, 8))
        self.nl_text.insert("1.0", "一个金发双马尾少女穿着水手服，坐在教室里看镜头，微笑，夜晚，樱花花瓣飘落")
        nrow2 = tk.Frame(nc, bg=C_CARD)
        nrow2.pack(fill="x", padx=12, pady=(0, 10))
        self.btn_nl = IOSButton(nrow2, "转换为标签", self.do_nl_convert,
                                h=34, r=8, font=FB, padx=16, base=C_CARD)
        self.btn_nl.pack(side="left")
        self.nl_status = tk.Label(nrow2, text="", font=F, bg=C_CARD, fg=C_SEC,
                                  wraplength=270, justify="left")
        self.nl_status.pack(side="left", padx=10)

        # Qwen 指令（选 Qwen 模型时显示；隐藏标签体系时用）
        qwen_card, qc = self._section(left_col, "Qwen 指令（自然语言描述）", top=12)
        self._qwen_sec = qwen_card
        self.qwen_text = tk.Text(qc, height=6, font=F, bg=C_CARD, fg=C_LABEL,
                                 insertbackground=C_LABEL, relief="flat", wrap="word",
                                 padx=8, pady=6, highlightthickness=1,
                                 highlightbackground=C_HAIR, highlightcolor=C_BLUE)
        self.qwen_text.pack(fill="x", padx=12, pady=(10, 8))
        self.qwen_text.insert(
            "1.0", "A photograph of a woman in her twenties wearing an oversized white "
                   "linen shirt, sitting on a wooden jetty over a calm lake at sunrise, "
                   "soft golden light, mist on the lake, full body, sharp focus, "
                   "natural skin texture")
        qrow = tk.Frame(qc, bg=C_CARD)
        qrow.pack(fill="x", padx=12, pady=(0, 4))
        self.btn_qgen = IOSButton(qrow, "生成提示词", self.do_qwen_gen, h=34, r=8,
                                  font=FB, padx=16, base=C_CARD)
        self.btn_qgen.pack(side="left")
        self.qwen_status = tk.Label(qc, text="写中文场景，点「生成提示词」按当前模型风格扩写",
                                    font=F, bg=C_CARD, fg=C_SEC, wraplength=300,
                                    justify="left", anchor="w")
        self.qwen_status.pack(fill="x", padx=12, pady=(0, 10))
        qwen_card.pack_forget()
        if qwen_card._hdr is not None:
            qwen_card._hdr.pack_forget()

        # 生成参数 (iOS 分组列表)
        param_card, param = self._section(left_col, "生成参数", top=12)
        self._param_sec = param_card
        self._param = param
        self._prow = {}   # name -> (row, hair)

        def prow(name, label, factory, with_hair=True):
            """factory(parent) -> widget: 以行容器为 master 创建, 避免 z-order 遮挡"""
            row = tk.Frame(param, bg=C_CARD)
            hair = self._hair(param) if with_hair else None
            tk.Label(row, text=label, font=F, bg=C_CARD, fg=C_LABEL).pack(
                side="left", padx=(12, 6), pady=7)
            widget = factory(row)
            widget.pack(side="right", padx=(6, 12), pady=7)
            if hair is not None:
                hair.pack(fill="x", padx=12)
            self._prow[name] = (row, hair)
            return row

        def srow(name, label, var, lo, hi, step, fmt, with_hair=True):
            """滑杆行: 标签左 | 滑杆中 | 数值右"""
            row = tk.Frame(param, bg=C_CARD)
            hair = self._hair(param) if with_hair else None
            tk.Label(row, text=label, font=F, bg=C_CARD, fg=C_LABEL).pack(
                side="left", padx=(12, 6), pady=7)
            val = tk.Label(row, text=fmt(var.get()), font=F, bg=C_CARD, fg=C_BLUE,
                           width=6, anchor="e")
            val.pack(side="right", padx=(6, 12), pady=7)
            sc = tk.Scale(row, from_=lo, to=hi, resolution=step, orient="horizontal",
                          variable=var, showvalue=False, bg=C_CARD, fg=C_LABEL,
                          troughcolor=C_TRACK, highlightthickness=0, bd=0,
                          sliderlength=18, sliderrelief="flat",
                          activebackground="#3395FF")
            sc.pack(side="left", fill="x", expand=True, padx=(2, 6), pady=7)
            var.trace_add("write", lambda *a, l=val, f=fmt, v=var:
                          l.config(text=f(v.get())))
            if hair is not None:
                hair.pack(fill="x", padx=12)
            self._prow[name] = (row, hair)
            return row

        self.model_var = tk.StringVar(value="NoobAI-XL（动漫标签）")

        def _mk_model(p):
            cb = ttk.Combobox(p, textvariable=self.model_var, state="readonly",
                              font=F, width=21,
                              values=["NoobAI-XL（动漫标签）",
                                      "Qwen-Image 2.1（原版）",
                                      "Noct-Q V4（无审查）",
                                      "SDXL 写实（NSFW）"])
            cb.current(0)
            cb.bind("<<ComboboxSelected>>", self._on_model_change)
            self.model_cb = cb
            return cb
        prow("model", "模型", _mk_model)

        self.mode_var = tk.StringVar(value="t2i")
        prow("mode", "模式", lambda p: ios_segment(
            p, [("t2i", "文生图"), ("i2i", "图生图"), ("charref", "角色参考")],
            self.mode_var, onchange=self._update_mode_ui))

        self._rating_labels = {"": "普通向（不加 tag）", "rating:sensitive": "擦边 / 诱感",
                               "rating:questionable": "暗示向", "nsfw, rating:explicit": "R18 成人向"}
        self._rating_values = {v: k for k, v in self._rating_labels.items()}
        self._rating_value = ""

        def _mk_rating(p):
            cb = ttk.Combobox(p, state="readonly", font=F, width=16,
                              values=list(self._rating_labels.values()))
            cb.set(self._rating_labels[""])
            cb.bind("<<ComboboxSelected>>", self._on_rating)
            self.rating_cb = cb
            return cb
        prow("rating", "分级", _mk_rating)

        self.ratio_var = tk.StringVar(value="832x1216")

        def _mk_ratio(p):
            cb = ttk.Combobox(p, textvariable=self.ratio_var, state="readonly",
                              font=F, width=14,
                              values=["832x1216  竖图", "1024x1024  方图",
                                      "1216x832  横图", "768x1152  小竖图"])
            cb.current(0)
            self.ratio_cb = cb
            return cb
        prow("ratio", "画幅", _mk_ratio)

        self.steps_var = tk.IntVar(value=28)
        self.cfg_var = tk.DoubleVar(value=5.5)
        self.denoise_var = tk.DoubleVar(value=0.55)
        self.ipw_var = tk.DoubleVar(value=0.5)
        srow("steps", "步数", self.steps_var, 4, 40, 1, lambda v: str(int(v)))
        srow("cfg", "CFG", self.cfg_var, 0.5, 9, 0.5, lambda v: f"{v:.1f}")
        srow("denoise", "重绘幅度", self.denoise_var, 0.1, 1, 0.05, lambda v: f"{v:.2f}")
        srow("ipw", "角色相似度", self.ipw_var, 0.3, 1, 0.05, lambda v: f"{v:.2f}")
        self.seed_var = tk.StringVar(value="-1")
        prow("seed", "种子 (-1 随机)", lambda p: tk.Entry(
            p, textvariable=self.seed_var, font=F, width=12,
            bg=C_CARD, fg=C_LABEL, insertbackground=C_LABEL,
            relief="flat", highlightthickness=1,
            highlightbackground=C_HAIR, justify="right"), with_hair=False)

        # 参考图
        self.ref_card, rc = self._section(left_col, "参考图", top=12)
        rr = tk.Frame(rc, bg=C_CARD)
        rr.pack(fill="x", padx=12, pady=(8, 12))
        self.btn_ref = IOSButton(rr, "选择文件", self.pick_ref, bg=C_FIELD, fg=C_LABEL,
                                 hover_bg="#D8D8DC", h=34, r=8, font=FB, padx=16,
                                 base=C_CARD)
        self.btn_ref.pack(side="left")
        self.ref_label = tk.Label(rr, text="未选择", font=F, bg=C_CARD, fg=C_SEC)
        self.ref_label.pack(side="left", padx=10)
        self.ref_thumb = tk.Label(rr, bg=C_PAGE, width=10, height=4,
                                  highlightthickness=1, highlightbackground=C_HAIR)
        self.ref_thumb.pack(side="right")

        # 生成按钮 + 状态
        btnwrap = tk.Frame(left_col, bg=C_PAGE)
        btnwrap.pack(fill="x", padx=10, pady=(14, 4))
        self._btnwrap = btnwrap
        self.btn_go = IOSButton(btnwrap, "开始生成", self.generate, h=46, r=12,
                                font=FBTN, base=C_PAGE)
        self.btn_go.pack(fill="x")
        self.status = tk.Label(left_col, text="就绪", font=F, bg=C_PAGE, fg=C_SEC,
                               wraplength=450, justify="left")
        self.status.pack(anchor="w", padx=16)

        # ---------------- 中栏: 标签库 ----------------
        mid = tk.Frame(main, bg=C_CARD, width=580)
        main.add(mid, width=580)
        hd = tk.Frame(mid, bg=C_CARD)
        hd.pack(fill="x", padx=14, pady=(12, 6))
        tk.Label(hd, text="标签库", font=F12B, bg=C_CARD, fg=C_LABEL).pack(side="left")
        tk.Label(hd, text="点标签拼进正面提示词", font=F, bg=C_CARD, fg=C_SEC).pack(
            side="right")
        btn_ed = tk.Button(hd, text="编辑词库", font=F, bg=C_CARD, fg=C_BLUE,
                           activebackground=C_PAGE, activeforeground=C_BLUE,
                           relief="flat", bd=0, padx=6, cursor="hand2",
                           command=self.open_tag_editor)
        btn_ed.pack(side="right")
        _hover(btn_ed, C_CARD, C_PAGE)
        sr = tk.Frame(mid, bg=C_CARD)
        sr.pack(fill="x", padx=14, pady=(0, 8))
        tk.Label(sr, text="搜索", font=F, bg=C_CARD, fg=C_SEC).pack(side="left", padx=(0, 8))
        self.search_var = tk.StringVar()
        se = tk.Entry(sr, textvariable=self.search_var, font=F, bg=C_FIELD, fg=C_LABEL,
                      insertbackground=C_LABEL, relief="flat", highlightthickness=0)
        se.pack(side="left", fill="x", expand=True, ipady=5)
        se.bind("<KeyRelease>", self._on_search_key)

        wrap = tk.Frame(mid, bg=C_CARD)
        wrap.pack(fill="both", expand=True, padx=(14, 6), pady=(0, 10))
        self.canvas = tk.Canvas(wrap, bg=C_CARD, highlightthickness=0, width=540)
        self.vsb = ttk.Scrollbar(wrap, orient="vertical", command=self.canvas.yview,
                                 style="Vertical.TScrollbar")
        self.canvas.configure(yscrollcommand=self.vsb.set)
        self.vsb.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)
        self.tag_inner = tk.Frame(self.canvas, bg=C_CARD)
        self._inner_win = self.canvas.create_window((0, 0), window=self.tag_inner, anchor="nw")
        self.tag_inner.bind("<Configure>",
                            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>", self._on_canvas_configure)
        self.canvas.bind("<Expose>", self._on_any_expose, add="+")
        self._canvas_path = str(self.canvas)
        self.canvas.bind_all("<MouseWheel>", self._on_wheel)

        # ---------------- 右栏: 成品 ----------------
        right = tk.Frame(main, bg=C_PAGE, width=400)
        main.add(right, width=400)
        tk.Label(right, text="成品", font=F12B, bg=C_PAGE, fg=C_SEC2).pack(
            anchor="w", padx=16, pady=(12, 4))
        self.img_frame = tk.Frame(right, bg=C_CARD, height=660,
                                  highlightthickness=1, highlightbackground=C_HAIR)
        self.img_frame.pack(fill="both", expand=True, padx=10)
        self.img_frame.pack_propagate(False)
        self.img_label = tk.Label(self.img_frame, bg=C_CARD,
                                  text="生成完成后显示这里", fg=C_SEC, font=F)
        self.img_label.pack(fill="both", expand=True)
        self.btn_save = IOSButton(right, "保存图片", self.save_image, bg=C_FIELD,
                                  fg=C_LABEL, hover_bg="#D8D8DC", h=40, r=10,
                                  font=FB, base=C_PAGE)
        self.btn_save.pack(fill="x", padx=10, pady=(8, 12))
        self.btn_save.set_enabled(False)

        self._relayout_params()
        self._update_mode_ui()
        self._update_model_ui()

    # ---------- 参数行显隐 ----------
    def _relayout_params(self):
        m = self._current_mode()
        visible = {"model": True, "mode": True, "rating": True, "ratio": m != "i2i",
                   "steps": True, "cfg": True, "denoise": m != "t2i",
                   "ipw": m == "charref", "seed": True}
        for row, hair in self._prow.values():
            row.pack_forget()
            if hair is not None:
                hair.pack_forget()
        order = ["model", "mode", "rating", "ratio", "steps", "cfg", "denoise", "ipw", "seed"]
        shown = [n for n in order if visible[n]]
        for i, name in enumerate(shown):
            row, hair = self._prow[name]
            row.pack(fill="x")
            if hair is not None and i < len(shown) - 1:
                hair.pack(fill="x", padx=12)

    # ---------- 模型切换：标签体系 / Qwen 指令区 显隐 ----------
    def _update_model_ui(self, *_):
        m = self.model_var.get()
        is_qwen = m.startswith("Qwen-Image") or m.startswith("Noct-Q")
        kind = model_style_key(m)
        before = getattr(self, "_param_sec", None)

        def show(card, visible):
            if card is None:
                return
            hdr = getattr(card, "_hdr", None)
            if visible:
                card.pack(fill="x", padx=10, before=before)
                if hdr is not None:
                    hdr.pack(anchor="w", padx=16, pady=(12, 4), before=before)
            else:
                card.pack_forget()
                if hdr is not None:
                    hdr.pack_forget()

        show(getattr(self, "_prompt_sec", None), not is_qwen)
        show(getattr(self, "_nl_sec", None), not is_qwen)
        show(getattr(self, "_qwen_sec", None), is_qwen)

        # 画幅选项按模型切换（Qwen 用 1MP 官方比例，SDXL 用原来的）
        ratios = QWEN_RATIOS if is_qwen else NOOBAI_RATIOS
        try:
            self.ratio_cb["values"] = ratios
            if self.ratio_var.get() not in ratios:
                self.ratio_cb.current(0)
        except Exception:
            pass

        # 提示词生成系统的文案随模型变化
        try:
            nl_hdr = getattr(self._nl_sec, "_hdr", None)
            if nl_hdr is not None:
                if kind == "sdxl":
                    nl_hdr.configure(text="提示词生成 · SDXL 写实摄影")
                    self.btn_nl.set_text("生成提示词")
                else:
                    nl_hdr.configure(text="自然语言 → 标准提示词")
                    self.btn_nl.set_text("转换为标签")
        except Exception:
            pass
        if is_qwen:
            try:
                qhdr = getattr(self._qwen_sec, "_hdr", None)
                if qhdr is not None:
                    qhdr.configure(text="Noct-Q 指令（英文照片描述）" if kind == "noctq"
                                   else "Qwen 指令（自然语言散文）")
            except Exception:
                pass

    # ---------- 各模型提示词生成 ----------
    def do_qwen_gen(self):
        text = self.qwen_text.get("1.0", "end").strip()
        if not text:
            self.qwen_status.configure(text="先写下场景描述（中文即可）", fg=C_ORANGE)
            return
        kind = model_style_key(self.model_var.get())
        self.qwen_status.configure(text="正在生成提示词…", fg=C_BLUE)
        self.update_idletasks()

        def work():
            note = ""
            try:
                out = nl2natural(text, kind)
            except Exception:
                out = local_style_expand(text, kind)
                note = "LLM 不可用，已用本地模板"
            self.after(0, lambda out=out, note=note: self._qwen_gen_done(out, note))
        threading.Thread(target=work, daemon=True).start()

    def _qwen_gen_done(self, out, note=""):
        if not out:
            self.qwen_status.configure(text="生成结果为空，请重试", fg=C_RED)
            return
        self.qwen_text.delete("1.0", "end")
        self.qwen_text.insert("1.0", out)
        self.qwen_status.configure(text="已生成提示词" + (f"（{note}）" if note else ""),
                                   fg=C_GREEN)

    def _nl_natural_done(self, out, kind, note=""):
        if not out:
            self.nl_status.configure(text="生成结果为空，请重试", fg=C_RED)
            return
        self.pos_text.delete("1.0", "end")
        self.pos_text.insert("1.0", out)
        self.refresh_chips()
        self.nl_status.configure(text="已生成提示词" + (f"（{note}）" if note else ""),
                                 fg=C_GREEN)

    # ---------- 交互 ----------
    def _on_wheel(self, e):
        wpath = str(e.widget)
        if wpath == self._canvas_path or wpath.startswith(self._canvas_path + "."):
            self.canvas.yview_scroll(int(-1 * (e.delta / 120)), "units")

    def _on_canvas_configure(self, e):
        self.canvas.itemconfig(self._inner_win, width=e.width)
        # 宽度变化 >=8px 即防抖重建, 避免胶囊排版超出画布被裁切
        if abs(e.width - self._last_avail) >= 8:
            self._last_avail = e.width
            if self._resize_after_id:
                try:
                    self.after_cancel(self._resize_after_id)
                except Exception:
                    pass
            self._resize_after_id = self.after(250, self.rebuild_tags)

    def _on_any_expose(self, _e=None):
        """顶层窗口任何区域重新暴露时, 防抖一次全量重绘 (修复遮挡期间的残影)"""
        if self._expose_pend:
            return
        self._expose_pend = True
        self.after_idle(self._force_resync)

    def _force_resync(self):
        """无视觉位移地把最新排版压到屏幕: 只处理排队中的绘制事件, 不滚动不重绘"""
        self._expose_pend = False
        if self.winfo_exists() and not self.winfo_ismapped():
            return  # 窗口未显示 (自检/加载中) 无需同步
        try:
            self.update_idletasks()
            self.update()
        except Exception:
            pass
        if os.environ.get("EASYDRAW_DEBUG"):
            self._dump_layout_metrics()

    def _dump_layout_metrics(self):
        """探针: 实测每个分类画布宽度与胶囊最右边缘, 找排版/实体宽度不一致"""
        try:
            rows = []
            cvw_all = []
            overflow = 0
            seen = {}
            for en, info in self.chips.items():
                cv = info.get("cv")
                if cv is None:
                    continue
                co = cv.coords(info["img_id"])
                if not co:
                    continue
                right = co[0] + info["w"]
                ent = seen.setdefault(cv, [-1.0, -1])
                if right > ent[0]:
                    ent[0] = right
                ent[1] = cv.winfo_width()
            for cv, (maxright, cvw) in seen.items():
                cvw_all.append(cvw)
                if maxright > cvw - 2:
                    overflow += 1
                    # 找出该 cv 里越界的具体胶囊
                    worst = None
                    for en2, info2 in self.chips.items():
                        if info2.get("cv") is not cv:
                            continue
                        co2 = cv.coords(info2["img_id"])
                        if co2 and co2[0] + info2["w"] > cvw - 2:
                            if worst is None or co2[0] + info2["w"] > worst[2]:
                                worst = (en2, co2[0], co2[0] + info2["w"])
                    rows.append(f"OVERFLOW cv_w={cvw} chipmax={maxright:.0f} "
                                f"worst={worst}")
            avail = getattr(self, "_avail_used", -1)
            msg = (f"probe: canvas_w={self.canvas.winfo_width()} "
                   f"inner_w={self.tag_inner.winfo_width()} avail={avail} "
                   f"n_cv={len(seen)} cvw_min={min(cvw_all) if cvw_all else -1} "
                   f"cvw_max={max(cvw_all) if cvw_all else -1} overflow={overflow}")
            with open(os.path.join(BASE, "_layout_debug.log"), "a",
                      encoding="utf-8") as f:
                f.write(msg + "\n")
                for r in rows[:6]:
                    f.write("  " + r + "\n")
        except Exception:
            pass

    def _on_search_key(self, _event=None):
        if self._search_after_id:
            try:
                self.after_cancel(self._search_after_id)
            except Exception:
                pass
        self._search_after_id = self.after(200, self.rebuild_tags)

    def _on_pos_key(self, _event=None):
        if self._pos_after_id:
            try:
                self.after_cancel(self._pos_after_id)
            except Exception:
                pass
        self._pos_after_id = self.after(300, self.refresh_chips)

    # ---------- 标签面板 (canvas 胶囊) ----------
    @staticmethod
    def _chipkey(en):
        return en.replace(" ", "_")

    def rebuild_tags(self):
        q = self.search_var.get().strip().lower()
        r18on = self.rating_value() == "nsfw, rating:explicit"
        sel = set(self.pos_tokens())
        for w in self.tag_inner.winfo_children():
            w.destroy()
        for _aid in getattr(self, "_chip_anim", {}).values():
            try:
                self.after_cancel(_aid)
            except Exception:
                pass
        self._chip_anim = {}
        self.chips = {}
        self._chipkey2en = {}
        self._hover_en = None
        avail = max(self.canvas.winfo_width() - 14, 300)
        if os.environ.get("EASYDRAW_DEBUG"):
            try:
                with open(os.path.join(BASE, "_layout_debug.log"), "a", encoding="utf-8") as f:
                    f.write(f"rebuild: canvas_w={self.canvas.winfo_width()} "
                            f"inner_w={self.tag_inner.winfo_width()} avail={avail} "
                            f"q={q!r}\n")
            except Exception:
                pass
        m = self._chip_font.measure
        H, GAP = self.CHIP_H, self.ROW_GAP

        for g in TAG_DB:
            cnsfw = bool(g.get("cnsfw"))
            if cnsfw and not r18on:
                continue
            items = [o for o in g["tags"]
                     if not q or q in o["en"].lower() or q in o["cn"]]
            if q and not items:
                continue
            catname = re.sub(r"^[^\w（(]+", "", g["cat"]).strip()
            tk.Label(self.tag_inner, text=catname, font=F12B, bg=C_CARD,
                     fg=C_SEC2).pack(anchor="w", padx=8, pady=(10, 2))
            tk.Frame(self.tag_inner, height=1, bg=C_HAIR).pack(fill="x", padx=8)
            body = tk.Frame(self.tag_inner, bg=C_CARD)
            body.pack(fill="x", padx=6, pady=(4, 2))
            # 排版 (起点 x=8 与绘制一致; x 含 CHIP_GAP, 否则行尾会被裁切)
            rows, row, x = [], [], 8
            for o in items:
                w = m(o["cn"]) + 22
                if x + w > avail and row:
                    rows.append(row)
                    row, x = [], 8   # 与绘制时的每行起点一致 (之前是 0 → 每行漂移 8px)
                row.append((o, w))
                x += w + self.CHIP_GAP
            if row:
                rows.append(row)
            ch = len(rows) * (H + GAP) + GAP
            cv = tk.Canvas(body, height=ch, bg=C_CARD, highlightthickness=0,
                           width=avail)
            cv.pack(fill="x")
            cv.bind("<Button-1>", self._on_chip_click)
            cv.bind("<Motion>", self._on_chip_motion)
            cv.bind("<Leave>", self._on_chip_leave)
            for ri, r in enumerate(rows):
                x = 8
                y = GAP + ri * (H + GAP)
                for o, w in r:
                    en = o["en"]
                    key = self._chipkey(en)
                    on = en in sel
                    fill = C_BLUE if on else C_CHIP_OFF
                    txtc = "#FFFFFF" if on else C_LABEL
                    img = self._pill_photo(w, H, fill)
                    img_id = cv.create_image(x, y, image=img, anchor="nw",
                                             tags=(key,))
                    txt_id = cv.create_text(x + w / 2, y + H / 2, text=o["cn"],
                                            font=self._chip_font, fill=txtc,
                                            tags=(key,))
                    self.chips[en] = {"cv": cv, "img_id": img_id, "txt_id": txt_id,
                                      "w": w, "sel": on,
                                      "fill": C_BLUE if on else C_CHIP_OFF,
                                      "txt": "#FFFFFF" if on else C_LABEL}
                    self._chipkey2en[key] = en
                    x += w + self.CHIP_GAP
        self._sel_set = sel
        self._avail_used = avail
        self.after_idle(self._force_resync)

    def _en_from_event(self, e):
        """用事件坐标做命中检测 (比 current 标签可靠, 兼容合成事件)"""
        items = e.widget.find_overlapping(e.x - 1, e.y - 1, e.x + 1, e.y + 1)
        for it in items:   # find_overlapping 自上而下返回
            for t in e.widget.gettags(it):
                if t in self._chipkey2en:
                    return self._chipkey2en[t]
        return None

    def _on_chip_click(self, e):
        en = self._en_from_event(e)
        if en:
            self.toggle_tag(en)

    def _on_chip_motion(self, e):
        en = self._en_from_event(e)
        if en == self._hover_en:
            return
        # 还原旧悬停
        if self._hover_en and self._hover_en in self.chips:
            self._paint_chip(self._hover_en, hover=False)
        self._hover_en = en
        if en and en in self.chips:
            self._paint_chip(en, hover=True)

    def _on_chip_leave(self, _e):
        if self._hover_en and self._hover_en in self.chips:
            self._paint_chip(self._hover_en, hover=False)
        self._hover_en = None

    def _pill_photo(self, w, h, fill):
        """抗锯齿胶囊图 (带缓存, 避免重复渲染)"""
        key = (w, h, fill)
        img = self._pill_cache.get(key)
        if img is None:
            img = ImageTk.PhotoImage(_aa_pill(w, h, fill))
            self._pill_cache[key] = img
        return img

    def _paint_chip(self, en, hover=False):
        info = self.chips.get(en)
        if not info:
            return
        aid = self._chip_anim.pop(en, None)
        if aid:
            try:
                self.after_cancel(aid)
            except Exception:
                pass
        selected = en in self._sel_set     # 以实时选中集为准, 不用过期的 info["sel"]
        info["sel"] = selected
        if selected:
            fill = "#3395FF" if hover else C_BLUE
            txtc = "#FFFFFF"
        else:
            fill = C_CHIP_OFF_H if hover else C_CHIP_OFF
            txtc = C_LABEL
        info["fill"], info["txt"] = fill, txtc
        cv = info["cv"]
        cv.itemconfig(info["img_id"],
                      image=self._pill_photo(info["w"], self.CHIP_H, fill))
        cv.itemconfig(info["txt_id"], fill=txtc)

    @staticmethod
    def _mix_hex(c1, c2, t):
        """两个 #RRGGBB 颜色线性插值"""
        a = [int(c1[i:i + 2], 16) for i in (1, 3, 5)]
        b = [int(c2[i:i + 2], 16) for i in (1, 3, 5)]
        return "#%02X%02X%02X" % tuple(
            max(0, min(255, round(a[i] + (b[i] - a[i]) * t))) for i in range(3))

    def _animate_chip(self, en, hover=False):
        """选中/取消的微渐变: 4 步 x 28ms (~110ms); 选中带轻微过冲的弹出感,
        取消平滑回落。只改颜色不动几何, 防闪烁。"""
        info = self.chips.get(en)
        if not info:
            return
        aid = self._chip_anim.pop(en, None)
        if aid:
            try:
                self.after_cancel(aid)
            except Exception:
                pass
        selected = en in self._sel_set
        if selected:
            t_fill = "#3395FF" if hover else C_BLUE
            t_txt = "#FFFFFF"
        else:
            t_fill = C_CHIP_OFF_H if hover else C_CHIP_OFF
            t_txt = C_LABEL
        start_fill = info.get("fill", t_fill)
        start_txt = info.get("txt", t_txt)
        if start_fill == t_fill and start_txt == t_txt:
            return
        if selected:
            seq_fill = [self._mix_hex(start_fill, t_fill, .30),
                        self._mix_hex(start_fill, t_fill, .62),
                        self._mix_hex(t_fill, "#FFFFFF", .26),
                        t_fill]
            seq_txt = [self._mix_hex(start_txt, t_txt, .50),
                       self._mix_hex(start_txt, t_txt, .95),
                       t_txt, t_txt]
        else:
            seq_fill = [self._mix_hex(start_fill, t_fill, .35),
                        self._mix_hex(start_fill, t_fill, .70),
                        self._mix_hex(start_fill, t_fill, .90),
                        t_fill]
            seq_txt = [self._mix_hex(start_txt, t_txt, .40),
                       self._mix_hex(start_txt, t_txt, .80),
                       t_txt, t_txt]
        info["fill"], info["txt"] = t_fill, t_txt
        cv = info["cv"]

        def _step(i):
            def _run():
                if self.chips.get(en) is not info:
                    self._chip_anim.pop(en, None)
                    return
                try:
                    if cv.winfo_exists():
                        cv.itemconfig(info["img_id"], image=self._pill_photo(
                            info["w"], self.CHIP_H, seq_fill[i]))
                        cv.itemconfig(info["txt_id"], fill=seq_txt[i])
                except Exception:
                    pass
                if i + 1 < len(seq_fill):
                    self._chip_anim[en] = self.after(28, _step(i + 1))
                else:
                    self._chip_anim.pop(en, None)
            return _run

        self._chip_anim[en] = self.after(0, _step(0))

    def refresh_chips(self):
        """差量刷新: 只更新状态发生变化的标签"""
        sel = set(self.pos_tokens())
        changed = getattr(self, "_sel_set", set()) ^ sel
        self._sel_set = sel          # 先同步状态, 再绘制
        for en in changed:
            self._animate_chip(en, hover=(en == self._hover_en))

    def _clear_positive(self):
        """一键清空正面提示词 (与网页版一致: 全清 + 芯片取消选中)"""
        self.pos_text.delete("1.0", "end")
        self.refresh_chips()

    # ---------- 词库编辑器 ----------
    def open_tag_editor(self):
        win = getattr(self, "_ed_win", None)
        if win is not None and win.winfo_exists():
            win.deiconify()
            win.lift()
            return
        win = tk.Toplevel(self)
        self._ed_win = win
        win.title("词库编辑 · 按组增删提示词")
        win.geometry("1020x640")
        win.configure(bg=C_PAGE)
        work = json.loads(json.dumps(TAG_DB))
        st = {"gi": 0}

        body = tk.Frame(win, bg=C_PAGE)
        body.pack(fill="both", expand=True, padx=10, pady=10)

        lf = tk.Frame(body, bg=C_CARD, highlightthickness=1,
                      highlightbackground=C_HAIR)
        lf.pack(side="left", fill="y", padx=(0, 8))
        tk.Label(lf, text="分组", font=FB, bg=C_CARD, fg=C_LABEL).pack(
            anchor="w", padx=10, pady=(8, 2))
        lb_g = tk.Listbox(lf, width=32, font=F, bg=C_CARD, fg=C_LABEL,
                          relief="flat", highlightthickness=0, exportselection=False)
        lb_g.pack(fill="both", expand=True, padx=6, pady=(0, 8))

        rf = tk.Frame(body, bg=C_CARD, highlightthickness=1,
                      highlightbackground=C_HAIR)
        rf.pack(side="left", fill="both", expand=True)
        tk.Label(rf, text="待选提示词（选中后点 ✗ 删除）", font=FB, bg=C_CARD,
                 fg=C_LABEL).pack(anchor="w", padx=10, pady=(8, 2))
        lb_t = tk.Listbox(rf, font=F, bg=C_CARD, fg=C_LABEL, relief="flat",
                          highlightthickness=0, exportselection=False)
        lb_t.pack(fill="both", expand=True, padx=8, pady=(0, 4))

        arow = tk.Frame(rf, bg=C_CARD)
        arow.pack(fill="x", padx=10, pady=(4, 2))
        tk.Label(arow, text="中文", font=F, bg=C_CARD, fg=C_SEC).pack(side="left")
        ent_cn = tk.Entry(arow, font=F, width=16, bg=C_FIELD, fg=C_LABEL,
                          insertbackground=C_LABEL, relief="flat",
                          highlightthickness=0)
        ent_cn.pack(side="left", padx=(4, 10), ipady=3)
        tk.Label(arow, text="英文 tag", font=F, bg=C_CARD, fg=C_SEC).pack(side="left")
        ent_en = tk.Entry(arow, font=F, width=26, bg=C_FIELD, fg=C_LABEL,
                          insertbackground=C_LABEL, relief="flat",
                          highlightthickness=0)
        ent_en.pack(side="left", padx=(4, 10), ipady=3)
        IOSButton(arow, "＋ 添加", lambda: add_tag(), bg=C_BLUE, h=30, r=8,
                  font=FB, padx=14, base=C_CARD).pack(side="left")

        brow = tk.Frame(rf, bg=C_CARD)
        brow.pack(fill="x", padx=10, pady=(4, 8))
        IOSButton(brow, "✗ 删除选中", lambda: del_sel(), bg="#FFEBEE", fg=C_RED,
                  hover_bg="#FFD9D7", h=30, r=8, font=FB, padx=14,
                  base=C_CARD).pack(side="left")
        lbl_msg = tk.Label(brow, text="改动点「保存并应用」后生效并写入 tags_data.json",
                           font=F, bg=C_CARD, fg=C_SEC)
        lbl_msg.pack(side="left", padx=10)

        frow = tk.Frame(win, bg=C_PAGE)
        frow.pack(fill="x", padx=10, pady=(0, 10))
        IOSButton(frow, "💾 保存并应用", lambda: save_all(), bg=C_GREEN, h=40, r=10,
                  font=FB, padx=20, base=C_PAGE).pack(side="right")
        IOSButton(frow, "关闭", win.destroy, bg=C_FIELD, fg=C_LABEL,
                  hover_bg="#D8D8DC", h=40, r=10, font=FB, padx=20,
                  base=C_PAGE).pack(side="right", padx=(0, 8))

        def msg(text, ok=False):
            lbl_msg.config(text=text, fg=C_GREEN if ok else C_RED)

        def refresh_groups():
            lb_g.delete(0, "end")
            for g in work:
                lb_g.insert("end", "%s   %d" % (g["cat"], len(g["tags"])))
            lb_g.selection_clear(0, "end")
            lb_g.selection_set(st["gi"])
            lb_g.see(st["gi"])

        def fill_tags():
            lb_t.delete(0, "end")
            for o in work[st["gi"]]["tags"]:
                lb_t.insert("end", "%s    [%s]" % (o["cn"], o["en"]))

        def on_group(_e=None):
            sel = lb_g.curselection()
            if sel:
                st["gi"] = sel[0]
            fill_tags()
        lb_g.bind("<<ListboxSelect>>", on_group)

        def add_tag():
            cn = ent_cn.get().strip()
            en = ent_en.get().strip().lower()
            if not cn or not en:
                msg("中文名和英文 tag 都要填")
                return
            if any(c in en for c in ',"'):
                msg("英文 tag 不能含逗号或双引号")
                return
            if en in TAG_BLOCK:
                msg("涉及未成年内容的 tag 禁止添加")
                return
            if any(t["en"] == en for g in work for t in g["tags"]):
                msg("已存在: " + en)
                return
            work[st["gi"]]["tags"].append({"en": en, "cn": cn})
            ent_cn.delete(0, "end")
            ent_en.delete(0, "end")
            refresh_groups()
            fill_tags()
            lb_t.see("end")
            msg("已加入，保存后生效", True)

        def del_sel():
            sel = lb_t.curselection()
            if not sel:
                msg("先在列表里选中一条")
                return
            o = work[st["gi"]]["tags"][sel[0]]
            if o["en"] == "nsfw":
                msg("nsfw 总开关不可删除")
                return
            del work[st["gi"]]["tags"][sel[0]]
            refresh_groups()
            fill_tags()
            msg("已删除（未保存）", True)

        def save_all():
            _DATA["tag_db"] = work
            try:
                with open(DATA_PATH, "w", encoding="utf-8") as f:
                    json.dump(_DATA, f, ensure_ascii=False, indent=1)
            except Exception as e:
                msg("保存失败: %s" % e)
                return
            globals()["TAG_DB"] = work
            self.rebuild_tags()
            msg("已保存并应用 ✓ 共 %d 组 / %d 个" % (
                len(work), sum(len(g["tags"]) for g in work)), True)

        refresh_groups()
        fill_tags()

    # ---------- 提示词操作 ----------
    def pos_tokens(self):
        return [t.strip() for t in self.pos_text.get("1.0", "end").split(",") if t.strip()]

    def set_pos(self, tokens):
        self.pos_text.delete("1.0", "end")
        self.pos_text.insert("1.0", ", ".join(tokens))

    def toggle_tag(self, en):
        toks = self.pos_tokens()
        if en in toks:
            toks.remove(en)
        else:
            toks.append(en)
        self.set_pos(toks)
        self.refresh_chips()

    # ---------- 模型切换 ----------
    def _on_model_change(self, _event=None):
        m = self.model_var.get()
        if m.startswith("Qwen-Image"):
            self.steps_var.set(8)
            self.cfg_var.set(1.0)
            tip = "Qwen-Image 2.1 原版：8 步 / CFG 1，提示词写自然语言（散文描述）"
        elif m.startswith("Noct-Q"):
            self.steps_var.set(25)
            self.cfg_var.set(3.0)
            tip = "Noct-Q V4 无审查：25 步 / CFG 3，提示词写自然语言（散文描述）"
        elif m.startswith("SDXL 写实"):
            self.steps_var.set(30)
            self.cfg_var.set(5.0)
            tip = "SDXL 写实（NSFW）：30 步 / CFG 5，标签或自然语言都可以"
        else:
            self.steps_var.set(28)
            self.cfg_var.set(5.5)
            tip = "NoobAI-XL：danbooru 标签式提示词"
        self._update_model_ui()
        if m != "NoobAI-XL（动漫标签）":
            # Qwen 走文生图；图生图/角色参考是 SDXL IPAdapter 路径
            if self.mode_var.get() != "t2i":
                self.mode_var.set("t2i")
                self._update_mode_ui()
        self.status.configure(text=tip, fg=C_SEC)

    # ---------- 分级联动 ----------
    def _on_rating(self, _event=None):
        label = self.rating_cb.get()
        value = self._rating_values.get(label, "")
        self._rating_value = value
        r18on = value == "nsfw, rating:explicit"
        if r18on:
            toks = self.pos_tokens()
            if "nsfw" not in toks:
                toks.append("nsfw")
                self.set_pos(toks)
        else:
            cnsfw_tags = {"nsfw"}
            for g in TAG_DB:
                if g.get("cnsfw"):
                    for o in g["tags"]:
                        cnsfw_tags.add(o["en"])
            toks = self.pos_tokens()
            kept = [t for t in toks if t not in cnsfw_tags]
            if len(kept) != len(toks):
                self.set_pos(kept)
        self.rebuild_tags()

    def rating_value(self):
        return self._rating_values.get(self.rating_cb.get(), "")

    # ---------- 模式显隐 ----------
    def _current_mode(self):
        return self.mode_var.get()

    def _update_mode_ui(self, *_):
        self._relayout_params()
        m = self._current_mode()
        hdr = getattr(self.ref_card, "_hdr", None)
        if m == "t2i":
            self.ref_card.pack_forget()
            if hdr is not None:
                hdr.pack_forget()
        else:
            self.ref_card.pack(fill="x", padx=10, pady=(12, 0),
                               before=self._btnwrap)
            if hdr is not None:
                hdr.pack(anchor="w", padx=16, pady=(12, 4), before=self.ref_card)

    # ---------- 参考图 ----------
    def pick_ref(self):
        path = filedialog.askopenfilename(
            title="选择参考图",
            filetypes=[("图片", "*.png *.jpg *.jpeg *.webp *.bmp"), ("所有文件", "*.*")])
        if not path:
            return
        self.ref_path = path
        self.ref_label.configure(text=os.path.basename(path), fg=C_LABEL)
        try:
            im = Image.open(path)
            im.thumbnail((72, 72))
            self._ref_photo = ImageTk.PhotoImage(im)
            self.ref_thumb.configure(image=self._ref_photo, text="")
        except Exception:
            self.ref_thumb.configure(image="", text="预览失败")

    # ---------- NL 转换 ----------
    def do_nl_convert(self):
        text = self.nl_text.get("1.0", "end").strip()
        if not text:
            self.nl_status.configure(text="先输入中文描述", fg=C_ORANGE)
            return
        kind = model_style_key(self.model_var.get())
        if kind == "sdxl":
            self.nl_status.configure(text="正在生成提示词…", fg=C_BLUE)
            self.update_idletasks()

            def work():
                note = ""
                try:
                    out = nl2natural(text, "sdxl")
                except Exception:
                    out = local_style_expand(text, "sdxl")
                    note = "LLM 不可用，已用本地模板"
                self.after(0, lambda out=out, note=note:
                           self._nl_natural_done(out, "sdxl", note))
            threading.Thread(target=work, daemon=True).start()
            return
        if kind in ("qwen", "noctq"):
            self.nl_status.configure(text="Qwen/Noct-Q 请在上方指令框点「生成提示词」",
                                     fg=C_ORANGE)
            return
        expand = self.nl_expand.get()
        if self.nl_mode.get() == "api":
            self.nl_status.configure(text="正在调用本地 LLM…", fg=C_BLUE)
            self.update_idletasks()

            def work():
                try:
                    tags_str, note = nl2api(text, expand)
                    self.after(0, lambda: self._nl_done(tags_str, note))
                except Exception as e:
                    err = str(e)
                    self.after(0, lambda err=err: self.nl_status.configure(
                        text=f"API 失败: {err}（确认本地 LLM 已启动）", fg=C_RED))
            threading.Thread(target=work, daemon=True).start()
            return
        tags, leftover = nl2tags_local(text)
        expanded = 0
        if expand and tags:
            tags, expanded = expand_semantics(tags)
        self._nl_done(", ".join(tags),
                      (f"；未识别: \"{leftover}\"（可切 API 模式）" if leftover else "，全部识别成功"),
                      tags, expanded)

    def _nl_done(self, tags_str, note, tags=None, expanded=0):
        if tags is None:
            tags = [t.strip() for t in tags_str.split(",") if t.strip()]
        if self.nl_replace.get():
            self.set_pos(tags)
        else:
            existing = set(self.pos_tokens())
            add = [t for t in tags if t not in existing]
            if add:
                cur = self.pos_text.get("1.0", "end").strip().rstrip(",")
                self.pos_text.delete("1.0", "end")
                self.pos_text.insert("1.0", (cur + ", " if cur else "") + ", ".join(add))
        self.refresh_chips()
        prefix = f"已转换 {len(tags)} 个标签"
        if expanded:
            prefix += f"（含语义关联 {expanded} 个）"
        self.nl_status.configure(text=prefix + (f" {note}" if note else ""), fg=C_GREEN)

    # ---------- 服务 ----------
    def _poll_services(self):
        ok_c = port_open(8188)
        ok_l = port_open(8080)
        self.lbl_comfy.configure(
            text=f"● ComfyUI {'就绪' if ok_c else '未启动'}",
            fg=C_GREEN if ok_c else C_RED)
        self.lbl_llm.configure(
            text=f"● 本地LLM {'就绪' if ok_l else '未启动'}",
            fg=C_GREEN if ok_l else C_RED)
        return ok_c, ok_l

    def _poll_services_loop(self):
        self._poll_services()
        self.after(4000, self._poll_services_loop)

    def start_comfy(self):
        if port_open(8188):
            return
        log = open(os.path.join(EXE_DIR, "comfyui_desktop.log"), "ab", buffering=0)
        subprocess.Popen([COMFY_PY, "main.py", "--disable-auto-launch"],
                         cwd=r"C:\AI\ComfyUI", creationflags=CREATE_NO_WINDOW,
                         stdout=log, stderr=subprocess.STDOUT)
        self.status.configure(text="正在启动 ComfyUI（首次约 20-40 秒）…", fg=C_BLUE)

    def start_llm(self):
        if port_open(8080):
            return
        if not os.path.exists(LLAMA_EXE):
            self.status.configure(text="未找到 llama-server.exe", fg=C_RED)
            return
        log = open(os.path.join(EXE_DIR, "llm_desktop.log"), "ab", buffering=0)
        subprocess.Popen([LLAMA_EXE, "-m", LLAMA_MODEL, "--host", "127.0.0.1",
                          "--port", "8080", "-ngl", "20", "-c", "4096"],
                         creationflags=CREATE_NO_WINDOW, stdout=log, stderr=subprocess.STDOUT)
        self.status.configure(text="正在启动本地 LLM…", fg=C_BLUE)

    # ---------- 生成 ----------
    def generate(self):
        if self._gen_busy:
            return
        mode = self._current_mode()
        model = self.model_var.get()
        is_qwen = model.startswith("Qwen-Image") or model.startswith("Noct-Q")
        is_sdxl = model.startswith("SDXL 写实")
        if is_qwen:
            mode = "t2i"  # Qwen 走自然语言文生图
            pos = self.qwen_text.get("1.0", "end").strip().rstrip(",")
            neg = QWEN_NEG
        else:
            pos = self.pos_text.get("1.0", "end").strip().rstrip(",")
            neg = self.neg_text.get("1.0", "end").strip()
        if not pos:
            self.status.configure(text="正面提示词不能为空", fg=C_RED)
            return
        refname = None
        if mode in ("i2i", "charref"):
            if not self.ref_path:
                self.status.configure(text=f"{mode} 模式：请先选择参考图", fg=C_RED)
                return
            try:
                refname = upload_ref(self.ref_path)
            except Exception as e:
                self.status.configure(text=f"参考图复制失败: {e}", fg=C_RED)
                return

        if not is_qwen:
            # 质量词前缀 + 分级注入（仅 NoobAI 标签体系）
            toks = self.pos_tokens()
            if pos and not pos.startswith("masterpiece"):
                pos = QUALITY_PREFIX + pos
            rating = self.rating_value()
            if rating:
                r18 = rating == "nsfw, rating:explicit"
                extra = "rating:explicit" if (r18 and "nsfw" in toks) else rating
                pos = (pos + ", " + extra) if pos else extra

        ratio = self.ratio_cb.get().split()[0]
        w, h = (int(x) for x in ratio.split("x"))
        steps = int(self.steps_var.get())
        cfg = float(self.cfg_var.get())
        seed_s = self.seed_var.get().strip()
        try:
            seed = random.randint(0, 4294967295) if seed_s in ("-1", "") else int(seed_s)
        except ValueError:
            seed = random.randint(0, 4294967295)
        denoise = float(self.denoise_var.get())
        ipweight = float(self.ipw_var.get())

        if is_qwen:
            kind = "turbo" if model.startswith("Qwen-Image") else "noctq"
            wf = build_workflow_qwen(kind, pos, neg, w, h, steps, cfg, seed)
        elif is_sdxl:
            wf = build_workflow_sdxl(pos, neg, w, h, steps, cfg, seed)
        else:
            wf = build_workflow(mode, pos, neg, w, h, steps, cfg, seed, denoise, ipweight, refname)

        self._gen_busy = True
        self.btn_go.set_enabled(False)
        self.btn_go.set_text("生成中…")
        self.status.configure(text="已提交，等待 ComfyUI…", fg=C_BLUE)
        threading.Thread(target=self._gen_worker, args=(wf, steps, w, h),
                         daemon=True).start()

    def _gen_worker(self, wf, steps, w, h):
        try:
            j = http_json(COMFY + "/prompt", {"prompt": wf}, timeout=60)
            if j.get("error"):
                m = j["error"].get("message", "提交失败")
                parts = []
                for nid, ne in (j.get("node_errors") or {}).items():
                    ets = "; ".join(e.get("message", "") +
                                    (f"({e['details']})" if e.get("details") else "")
                                    for e in (ne.get("errors") or []))
                    if ets:
                        parts.append(f"节点{nid}: {ets}")
                if parts:
                    m += " — " + " | ".join(parts)
                raise RuntimeError(m)
            pid = j["prompt_id"]
        except Exception as e:
            err = str(e)
            self.after(0, lambda err=err: self._gen_fail(f"提交失败: {err}"))
            return

        total = round(steps * (3.2 if w * h >= 1048576 else 2.5) / 1.2)
        waited = 0
        while waited < 600:
            time.sleep(2)
            waited += 2
            try:
                hist = http_json(f"{COMFY}/history/{pid}", timeout=10)
            except Exception:
                self.after(0, lambda: self.status.configure(
                    text="后端暂时无响应（模型加载中），继续等待…", fg=C_ORANGE))
                continue
            if pid in hist:
                node = (hist[pid].get("outputs") or {}).get("8")
                imgs = (node or {}).get("images") or []
                if not imgs:
                    self.after(0, lambda: self._gen_fail("生成出错，查看 ComfyUI 日志"))
                    return
                im = imgs[0]
                self._last_filename = im.get("filename")
                try:
                    url = (f"{COMFY}/view?filename={urlquote(im['filename'])}"
                           f"&subfolder={urlquote(im.get('subfolder',''))}&type=output")
                    with urllib.request.urlopen(url, timeout=60) as r:
                        data = r.read()
                except Exception as e:
                    err = str(e)
                    self.after(0, lambda err=err: self._gen_fail(f"取图失败: {err}"))
                    return
                self.after(0, lambda: self._gen_done(data))
                return
            left = max(0, total - waited)
            msg = (f"生成中… 约 {left}s" if left > 0
                   else f"已等 {waited // 60} 分钟（首次加载大模型较慢属正常）")
            self.after(0, lambda m=msg: self.status.configure(text=m, fg=C_BLUE))
        self.after(0, lambda: self._gen_fail(
            "超过 10 分钟未完成：ComfyUI 可能卡住了，点上方‘启动’旁重启或用 StopEasyDraw"))

    def _gen_fail(self, msg):
        self._gen_busy = False
        self.btn_go.set_enabled(True)
        self.btn_go.set_text("开始生成")
        self.status.configure(text=msg, fg=C_RED)

    def _gen_done(self, data):
        self._gen_busy = False
        self._last_img_bytes = data
        self.btn_go.set_enabled(True)
        self.btn_go.set_text("开始生成")
        self.status.configure(text=f"完成! {self._last_filename or ''}", fg=C_GREEN)
        self.btn_save.set_enabled(True)
        self._show_image(data)

    def _show_image(self, data):
        try:
            im = Image.open(io.BytesIO(data))
            fw = self.img_frame.winfo_width()
            fh = self.img_frame.winfo_height()
            avail_w = (fw - 8) if fw > 50 else 380
            avail_h = (fh - 8) if fh > 50 else 640
            im.thumbnail((avail_w, avail_h))
            self._img_photo = ImageTk.PhotoImage(im)
            self.img_label.configure(image=self._img_photo, text="")
        except Exception as e:
            self.img_label.configure(image="", text=f"图片解码失败: {e}")

    def save_image(self):
        if not self._last_img_bytes:
            return
        path = filedialog.asksaveasfilename(
            title="保存图片", defaultextension=".png",
            initialfile=self._last_filename or "easy_draw.png",
            filetypes=[("PNG 图片", "*.png"), ("所有文件", "*.*")])
        if not path:
            return
        with open(path, "wb") as f:
            f.write(self._last_img_bytes)
        self.status.configure(text=f"已保存到 {path}", fg=C_GREEN)


def selftest():
    """无头自检: 数据/转换/工作流 + UI 构建 + 性能基线"""
    print("[1] 数据加载: 分类", len(TAG_DB), "标签",
          sum(len(g["tags"]) for g in TAG_DB), "词典", len(SYN), "关联", len(ASSOC))
    tags, leftover = nl2tags_local("一个金发双马尾少女穿着水手服，坐在教室里，夜晚，樱花飘落")
    print("[2] 本地转换:", tags, "| leftover:", leftover or "(无)")
    tags2, n = expand_semantics(tags)
    print("[3] 语义扩展:", len(tags2), "个 (+%d)" % n)
    v, note = filter_tags("1girl, wearing kimono, smiling, summer night, xyznotexist")
    print("[4] 校验修复:", v, "|", note)
    for mode in ("t2i", "i2i", "charref"):
        wf = build_workflow(mode, "masterpiece, 1girl", "worst quality",
                            832, 1216, 28, 5.5, 42, 0.55, 0.5, "ref.png")
        nodes = sorted(wf.keys(), key=int)
        print(f"[5] workflow {mode}: {len(wf)} 节点 {nodes}")
    assert valid_tag("nsfw") and valid_tag("rating:explicit")
    assert not valid_tag("xyznotexist")

    app = EasyDraw(selftest=True)
    print(f"[6] UI 构建耗时 {app._build_ms:.0f}ms")
    assert app._build_ms < 1500, "构建过慢"
    for _ in range(6):
        app.update()
        time.sleep(0.05)
    n_chips = len(app.chips)
    assert n_chips > 150, f"标签过少: {n_chips}"
    # 点击路径依赖 items 上的 tag key, 必须存在
    en0 = next(iter(app.chips))
    info0 = app.chips[en0]
    tags0 = info0["cv"].gettags(info0["img_id"])
    assert app._chipkey(en0) in tags0, f"chip tag 缺失: {tags0}"
    t0 = time.perf_counter()
    app.rebuild_tags()
    dt_rebuild = (time.perf_counter() - t0) * 1000
    print(f"[7] 标签全量重建 {dt_rebuild:.0f}ms ({n_chips} 标签)")
    assert dt_rebuild < 600, "重建过慢"
    t0 = time.perf_counter()
    app.toggle_tag("long hair")
    app.toggle_tag("long hair")
    dt_toggle = (time.perf_counter() - t0) * 1000
    print(f"[8] 点击标签(增+删) {dt_toggle:.1f}ms")
    assert dt_toggle < 60, "点击响应过慢"
    # 分级联动
    app.rating_cb.set("R18 成人向")
    app._on_rating()
    n_r18 = len(app.chips)
    assert "nsfw" in app.pos_tokens()
    app.rating_cb.set("普通向（不加 tag）")
    app._on_rating()
    n_back = len(app.chips)
    assert "nsfw" not in app.pos_tokens()
    print(f"[9] 分级联动: 普通向 {n_chips} / R18 {n_r18} / 切回 {n_back}")
    assert n_r18 > n_chips and n_back == n_chips
    # 模式分段控件 + 行显隐
    app.mode_var.set("charref")
    app._update_mode_ui()
    app.mode_var.set("i2i")
    app._update_mode_ui()
    app.mode_var.set("t2i")
    app._update_mode_ui()
    # iOS 开关
    app.nl_expand.set(True)
    app.nl_replace.set(True)
    print("[10] 分段控件/参数行/开关 OK")
    app.destroy()
    print("SELFTEST PASS")


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        selftest()
    else:
        EasyDraw().mainloop()
