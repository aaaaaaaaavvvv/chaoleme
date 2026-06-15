"""吵了么 — 极简AI辩论聊天应用"""
import os
import json
import uuid
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from dotenv import load_dotenv
from flask import Flask, render_template, request, jsonify, session, redirect, url_for

# ── 加载 .env ───────────────────────────────────────────────
load_dotenv(Path(__file__).parent / ".env")

# ── App Setup ──────────────────────────────────────────────
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", os.urandom(24).hex())
DATA_FILE = Path(__file__).parent / "debates.json"

BEIJING_TZ = timezone(timedelta(hours=8))

# ── AI Client ───────────────────────────────────────────────
# 优先级：Web端设置 > .env 环境变量
CONFIG_FILE = Path(__file__).parent / "api_config.json"

def _load_config():
    if CONFIG_FILE.exists():
        try:
            return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}

def _save_config(cfg: dict):
    CONFIG_FILE.write_text(json.dumps(cfg, ensure_ascii=False), encoding="utf-8")

def _get_api_key():
    """Web 端设置的 key 优先，否则用 .env 里的"""
    cfg = _load_config()
    return cfg.get("api_key") or os.environ.get("API_KEY") or os.environ.get("ANTHROPIC_API_KEY") or ""

def _get_model():
    cfg = _load_config()
    return cfg.get("model") or os.environ.get("API_MODEL") or os.environ.get("ANTHROPIC_MODEL") or "deepseek-chat"

def _get_base_url():
    cfg = _load_config()
    return cfg.get("base_url") or os.environ.get("API_BASE_URL") or "https://api.deepseek.com"

def _build_ai_client():
    key = _get_api_key()
    if key:
        from openai import OpenAI
        return OpenAI(api_key=key, base_url=_get_base_url())
    return None

ai_client = _build_ai_client()

# ── 议题数据 ───────────────────────────────────────────────
TOPICS = {
    1: {
        "id": 1,
        "title": "996是个人选择还是系统压力？",
        "background": (
            "如今 996 加班模式在诸多行业已成常态。有人认为愿意加班是个人自主的职业取舍，"
            "也有人觉得劳动者是被外部环境裹挟、身不由己。那么，996 的盛行根源应归于个人选择还是系统性环境压力？"
        ),
        "positions": ["个人选择", "系统压力"],
    },
    2: {
        "id": 2,
        "title": "算法推荐是服务用户还是操纵用户？",
        "background": (
            "平台说算法推荐能精准匹配需求，给用户获取信息、消费娱乐带来极大便利。"
            "批评者说算法会通过内容投喂拿捏用户的注意力，放大非理性欲望，实现深度裹挟。"
            "算法推荐的本质，究竟是赋能用户的服务工具，还是操控用户的手段？"
        ),
        "positions": ["服务用户", "操纵用户"],
    },
    3: {
        "id": 3,
        "title": "城市化让生活更幸福了吗？",
        "background": (
            "城市化进程能带来更丰富的就业机遇、更完善的生活配套，给人们生活增添诸多便利。"
            "但高密度的城市生活也催生了更强的竞争压力，让人们远离自然闲适的生活环境。"
            "城市化究竟能否让生活变得更幸福？"
        ),
        "positions": ["城市让生活更幸福", "城市让生活更不幸福"],
    },
    4: {
        "id": 4,
        "title": "宠物保护是文明进步还是过度越界？",
        "background": (
            "支持完善宠物保护规则的人表示，善待伴侣动物是社会尊重生命的文明体现；"
            "批评者则提出，部分极端化的宠物保护主张会侵扰普通居民日常生活、埋下公共卫生隐患。"
            "宠物保护的发展取向，究竟是社会文明进步的方向，还是对公共人居利益的不合理越界？"
        ),
        "positions": ["文明进步", "过度越界"],
    },
    5: {
        "id": 5,
        "title": "性别对立是舆论煽动还是现实矛盾？",
        "background": (
            "如今性别相关的话题在网络频繁引发争论，对立情绪逐步蔓延。"
            "有人认为激烈的性别对立多是流量方刻意炒作煽动、制造群体撕裂的结果，"
            "也有人认为对立背后是两性在就业、家庭、权益分配等现实场景中真实存在的诉求分歧。"
            "性别对立不断发酵的根源，应归于舆论刻意煽动，还是现实层面固有的观念与利益矛盾？"
        ),
        "positions": ["舆论煽动", "现实矛盾"],
    },
    6: {
        "id": 6,
        "title": "AI 会加剧还是缩小贫富差距？",
        "background": (
            "如今人工智能已渗透全产业链，深度重塑各行各业的就业形态与财富分配格局。"
            "有人认为 AI 大幅降低创业与生产门槛，能让更多普通从业者分到发展红利；"
            "也有人认为 AI 核心技术与算力资源被少数资本和技术精英把控，会进一步拉大财富分层。"
            "AI 的普及最终会加剧还是缩小全社会的贫富差距？"
        ),
        "positions": ["AI会缩小贫富差距", "AI会加剧贫富差距"],
    },
}

# ── 系统提示词 ─────────────────────────────────────────────
SYSTEM_PROMPT = """# 吵了么 — 系统提示词 v1.2

## 角色定义

你是"吵了么"中的AI辩论对手。你的核心身份是一面**思维镜子**——不评判、不教导、不纠正。你唯一的功能是通过提问和复述，让用户看见自己观点背后的预设、盲区和逻辑结构。

## 发言铁律

1. **双句式结构，缺一不可**。每次发言严格包含两部分：
   - **映照**：用一句话复述用户的核心论点逻辑，不加评判，不偷换概念。
     - ✗ 禁止使用"我理解你认为""我听到你说""我感受到你"等治疗式开头。
     - ✓ 用"你的论点是…""按你的逻辑…""你的核心理由是…""你似乎在说…"等自然多样的开头。
   - **邀请**：必须以问号结尾。用一个开放问题引导用户看见盲区——问题本身即是镜子。
2. **绝不含情绪**。不使用反问、讽刺、贬义词、标签。用户若出现情绪化表达，你只回应其论点内容。
3. **不引用未经证实的统计数据**。多用思想实验和具体情境。
4. **知识截止于2025年初**，不确定的事实要明确指出。

## 思考提示

每次发言末尾必须以小字附上，不可省略。格式：
```
── 思考提示（类型）：具体内容
```
- 类型为"盲区扫描"或"假设探测"
- 具体内容必须具体指出用户回避了哪个词、预设了什么前提、或混淆了什么逻辑关系。**禁止只写类型名而不写具体内容。**
- 以盲区扫描为主；假设探测每场辩论**不超过2次**，仅在用户混淆相关与因果或极端化推理时使用。
- 语气中性，不让用户觉得被审视。

示例：
```
── 思考提示（盲区扫描）：你用"伤害他人"论证禁烟，但未界定"伤害"的边界。如果密闭私人空间不影响任何人，这个理由是否还能成立？
── 思考提示（假设探测）：你把"算法推荐内容"等同于"用户被操纵"，但二者可能是相关而非因果——用户是否保留了选择不看的能力？
```

## 三轮小结

辩论每满3轮时生成小结：
- 列出双方已达成共识的事实
- 指出分歧的本质（不是谁对谁错，而是"你们在争论什么层面的问题"）
- 询问用户是否想换到对方立场继续
"""

# ── 辩论数据持久化 ─────────────────────────────────────────
def load_debates() -> dict:
    if DATA_FILE.exists():
        try:
            return json.loads(DATA_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}

def save_debates(data: dict) -> None:
    DATA_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

def get_debate(debate_id: str) -> dict | None:
    debates = load_debates()
    return debates.get(debate_id)

def put_debate(debate: dict) -> None:
    debates = load_debates()
    debates[debate["id"]] = debate
    save_debates(debates)

# ── AI 调用 ────────────────────────────────────────────────
def call_ai(system_text: str, messages: list[dict], max_tokens: int = 800) -> str:
    """调用 DeepSeek API（OpenAI 兼容），失败时回退到 mock 模式"""
    if ai_client is None:
        return _mock_response(messages)

    # 构建 OpenAI 格式消息列表
    api_messages = [{"role": "system", "content": system_text}]
    for m in messages:
        role = "assistant" if m["role"] == "ai" else "user"
        api_messages.append({"role": role, "content": m["content"]})

    try:
        resp = ai_client.chat.completions.create(
            model=_get_model(),
            max_tokens=max_tokens,
            messages=api_messages,
            temperature=0.7,
        )
        return resp.choices[0].message.content
    except Exception as e:
        print(f"[AI Error] {e}")
        return _mock_response(messages)

# Mock 回复模板池，避免总重复同一句
_MOCK_TEMPLATES = [
    {
        "mirror": "你的论点是……按这个逻辑推下去，似乎在说{nub}。",
        "invite": "但如果换一个具体情境——{context}——同样的推理链条是否依然站得住脚？",
        "hint_type": "盲区扫描",
        "hint": "你预设了一个前提而未加论证：{blindspot}。如果这个前提不成立，你的结论会如何变化？",
    },
    {
        "mirror": "你似乎从{nub}得出了自己的结论。",
        "invite": "我想请你考虑：{context}，在这个场景下，你的论证还成立吗？",
        "hint_type": "盲区扫描",
        "hint": "你的论证中，「{blindspot}」这个词是关键，但你并没有界定它的边界。不同的人对它的定义可能完全不同。",
    },
    {
        "mirror": "按你的推理，核心在于{nub}。",
        "invite": "如果你的对手举出一个具体反例——比如{context}——你会如何回应？",
        "hint_type": "假设探测",
        "hint": "你把两件事做了因果连接：「{blindspot}」是原因还是相关现象？如果方向反过来也成立，你的论证会受影响吗？",
    },
    {
        "mirror": "你的逻辑链条大致是：{nub}，因此观点成立。",
        "invite": "但这条链上有一个中间环节值得再推敲：{context}，这一步是否总是必然的？",
        "hint_type": "盲区扫描",
        "hint": "你跳过了「{blindspot}」这个中间变量。如果这个变量不受你的前提控制，结论可能就不那么稳了。",
    },
]

def _mock_response(messages: list[dict]) -> str:
    """无 API Key 时的模拟回复，方便测试 UI"""
    import random
    user_messages = [m for m in messages if m["role"] == "user"]
    last_user = user_messages[-1]["content"] if user_messages else ""

    # 根据用户发言内容动态选取关键词，使 mock 不那么千篇一律
    topic_hints = {
        "个人选择": ("选择自由决定了工作方式", "一个求职者面对所有公司都要求996的社会", "所有劳动者拥有平等的议价能力"),
        "系统压力": ("外部结构压迫个体妥协", "一个行业里没有任何人主动选择但每个人都996", "结构压力与个人意志谁是原因谁是结果"),
        "辞职": ("只要辞职就能摆脱一切束缚", "一个人辞职后面临简历空白、社保中断、行业封杀", "辞职的代价对所有人是平等的"),
        "自由": ("自由意志决定一切", "信息完全不对称的弱势地位", "所有参与者拥有对等的信息和选择权"),
        "健康": ("健康受损就能拒绝加班", "房贷、子女教育、父母医疗同时压在一个人身上", "健康和生活压力是可以独立取舍的"),
        "加班": ("加班就是不自愿的选择", "如果薪资翻倍、自愿加班的人会不会变多", "加班与不自愿是同一回事"),
    }

    # 尝试匹配话题
    nub = "某个核心预设"
    context = "当条件发生变化时"
    blindspot = "一个隐含前提"

    for keyword, (n, c, b) in topic_hints.items():
        if keyword in last_user:
            nub, context, blindspot = n, c, b
            break

    tpl = random.choice(_MOCK_TEMPLATES)
    exchange_count = len(user_messages)
    phase_note = "（提醒：这是模拟模式，请配置 API Key 以获得真实 AI 辩论体验）"
    return (
        f"{tpl['mirror'].format(nub=nub)}\n"
        f"{tpl['invite'].format(context=context)}\n\n"
        f"── 思考提示（{tpl['hint_type']}）：{tpl['hint'].format(blindspot=blindspot)}\n"
        f"── {phase_note}"
    )

def build_debate_system(topic: dict, ai_position: str, user_position: str) -> str:
    """构建包含议题上下文的系统提示词"""
    return (
        f"{SYSTEM_PROMPT}\n\n"
        f"## 当前议题\n"
        f"**议题**：{topic['title']}\n"
        f"**背景**：{topic['background']}\n\n"
        f"**你的立场**：{ai_position}\n"
        f"**对手（用户）的立场**：{user_position}\n\n"
        f"## 首轮特殊规则\n"
        f"这是辩论的第一轮。对方尚未发言，因此你不需要「映照」对方的论点。"
        f"你需要：\n"
        f"1. 用1-2句话阐明你所持立场的核心论据（从 {ai_position} 的角度出发）\n"
        f"2. 以一个开放问题邀请对方发表他们的第一个论点\n"
        f"3. 末尾附加「── 思考提示（盲区扫描）：…」\n"
        f"发言保持冷静、理性，不带情绪。"
    )

def build_summary_system(topic: dict) -> str:
    return (
        "你是一位中立的辩论观察员。你的任务是阅读以下辩论记录，生成三轮小结。\n\n"
        "请输出一个 JSON 对象，包含三个字段：\n"
        "- consensus: 列出双方已达成共识的事实（数组）\n"
        "- essence: 指出分歧的本质——不是谁对谁错，而是双方在争论什么层面的问题（字符串）\n"
        "- question: 一个询问用户是否想换到对方立场继续的问题（字符串）\n\n"
        "只输出 JSON，不要有其他内容。"
    )

def build_report_system() -> str:
    return (
        "你是一位中立的逻辑分析员。你的任务是分析以下辩论中**用户（非AI）**的发言质量。\n\n"
        "请输出一个 JSON 对象，包含：\n"
        "- emotion_markers: 用户发言中的情绪化用词或表达（数组，每项包含 phrase 和 note）\n"
        "- ad_hominem_hints: 是否有人身攻击暗示（数组，每项包含 phrase 和 note，没有则为空数组）\n"
        "- logical_observations: 逻辑层面的观察（数组，每项为字符串，不评判对错，只描述推理结构特征）\n"
        "- reading_suggestions: 推荐阅读（数组，每项包含 title, author, reason，与辩论主题和用户论证方式相关）\n\n"
        "要求：\n"
        "- 客观、中性，不评判对错\n"
        "- 只标注确实存在的问题，不要过度解读\n"
        "- 阅读推荐要有针对性，不要泛泛而谈\n"
        "- 只输出 JSON，不要有其他内容。"
    )

# ── 路由 ───────────────────────────────────────────────────
@app.route("/")
def index():
    """首页 — 议题选择"""
    return render_template("index.html", topics=TOPICS)

@app.route("/debate/<debate_id>")
def view_debate(debate_id):
    """查看/继续辩论"""
    debate = get_debate(debate_id)
    if not debate:
        return render_template("index.html", topics=TOPICS, error="辩论不存在或已过期")
    return render_template("index.html", topics=TOPICS, debate_id=debate_id)

# ── API ────────────────────────────────────────────────────
@app.route("/api/topics")
def api_topics():
    return jsonify(list(TOPICS.values()))

@app.route("/api/config", methods=["GET", "POST"])
def api_config():
    """读取或设置 API 配置（Web 端填入 Key）"""
    global ai_client
    if request.method == "GET":
        cfg = _load_config()
        ui_key = cfg.get("api_key", "")
        env_key = os.environ.get("API_KEY") or os.environ.get("ANTHROPIC_API_KEY") or ""
        return jsonify({
            "has_ui_key": bool(ui_key),
            "has_env_key": bool(env_key),
            "has_key": bool(ui_key or env_key),
            "ui_key_hint": _mask_key(ui_key) if ui_key else "",
            "env_key_hint": _mask_key(env_key) if env_key else "",
            "model": cfg.get("model") or os.environ.get("API_MODEL") or os.environ.get("ANTHROPIC_MODEL") or "deepseek-chat",
            "base_url": cfg.get("base_url") or os.environ.get("API_BASE_URL") or "https://api.deepseek.com",
        })
    # POST: 保存配置
    data = request.get_json()
    cfg = _load_config()
    cfg["api_key"] = (data.get("api_key") or "").strip()
    if data.get("model"):
        cfg["model"] = data["model"].strip()
    if data.get("base_url"):
        cfg["base_url"] = data["base_url"].strip()
    _save_config(cfg)
    ai_client = _build_ai_client()
    return jsonify({"ok": True, "has_key": bool(_get_api_key())})

def _mask_key(key: str) -> str:
    """将 key 显示为 sk-****abcd 格式"""
    if not key:
        return ""
    if len(key) <= 10:
        return key[:3] + "***"
    return key[:5] + "****" + key[-4:]

@app.route("/api/debug")
def api_debug():
    """调试端点"""
    key = _get_api_key()
    return jsonify({
        "ai_client_ok": ai_client is not None,
        "has_key": bool(key),
        "key_preview": key[:15] + "***" if key else "NONE",
        "model": _get_model(),
    })

@app.route("/api/debate/start", methods=["POST"])
def api_start_debate():
    """开始一场新辩论"""
    data = request.get_json()
    topic_id = data.get("topic_id")
    user_position = data.get("position")

    topic = TOPICS.get(topic_id)
    if not topic:
        return jsonify({"error": "无效的议题"}), 400
    if user_position not in topic["positions"]:
        return jsonify({"error": "无效的立场"}), 400

    ai_position = topic["positions"][0] if user_position == topic["positions"][1] else topic["positions"][1]

    debate_id = uuid.uuid4().hex[:8]
    debate = {
        "id": debate_id,
        "topic_id": topic_id,
        "user_position": user_position,
        "ai_position": ai_position,
        "messages": [],
        "exchange_count": 0,
        "summaries": [],
        "completed": False,
        "report": None,
        "created_at": datetime.now(BEIJING_TZ).isoformat(),
    }
    put_debate(debate)

    # AI 开场
    system_text = build_debate_system(topic, ai_position, user_position)
    ai_opening = call_ai(system_text, [], max_tokens=600)

    debate["messages"].append({
        "role": "ai",
        "content": ai_opening,
        "exchange": 0,
        "is_opening": True,
    })
    put_debate(debate)

    return jsonify({
        "debate_id": debate_id,
        "ai_position": ai_position,
        "opening": ai_opening,
    })

@app.route("/api/debate/<debate_id>/message", methods=["POST"])
def api_send_message(debate_id):
    """用户发送消息，AI 回复"""
    debate = get_debate(debate_id)
    if not debate:
        return jsonify({"error": "辩论不存在"}), 404
    if debate["completed"]:
        return jsonify({"error": "辩论已结束"}), 400

    data = request.get_json()
    user_content = data.get("content", "").strip()
    if not user_content:
        return jsonify({"error": "消息不能为空"}), 400

    exchange_num = debate["exchange_count"] + 1
    debate["messages"].append({
        "role": "user",
        "content": user_content,
        "exchange": exchange_num,
    })
    debate["exchange_count"] = exchange_num

    # 构建对话历史给 AI
    topic = TOPICS[debate["topic_id"]]
    system_text = (
        f"{SYSTEM_PROMPT}\n\n"
        f"## 当前议题\n"
        f"**议题**：{topic['title']}\n"
        f"**背景**：{topic['background']}\n\n"
        f"**你的立场**：{debate['ai_position']}\n"
        f"**对手（用户）的立场**：{debate['user_position']}\n"
    )

    # 发送给 AI 的消息：只包含最近的几条（节省 token）
    recent = debate["messages"][-6:]  # 最近3轮
    ai_reply = call_ai(system_text, recent, max_tokens=800)

    debate["messages"].append({
        "role": "ai",
        "content": ai_reply,
        "exchange": exchange_num,
    })
    put_debate(debate)

    # 每3轮生成小结
    summary = None
    if exchange_num > 0 and exchange_num % 3 == 0:
        summary = _generate_summary(debate)

    return jsonify({
        "reply": ai_reply,
        "exchange": exchange_num,
        "summary": summary,
    })

@app.route("/api/debate/<debate_id>/switch", methods=["POST"])
def api_switch_position(debate_id):
    """换位思考 — 用户切换到对方立场"""
    debate = get_debate(debate_id)
    if not debate:
        return jsonify({"error": "辩论不存在"}), 404

    old_user = debate["user_position"]
    old_ai = debate["ai_position"]
    debate["user_position"] = old_ai
    debate["ai_position"] = old_user
    # 重置轮次计数，开启新一轮
    debate["exchange_count"] = 0

    topic = TOPICS[debate["topic_id"]]
    system_text = (
        f"{SYSTEM_PROMPT}\n\n"
        f"## 当前议题\n"
        f"**议题**：{topic['title']}\n"
        f"**背景**：{topic['background']}\n\n"
        f"**你的立场**：{debate['ai_position']}\n"
        f"**对手（用户）的立场**：{debate['user_position']}\n\n"
        f"## 重要：对方刚刚切换了立场\n"
        f"对方之前支持「{old_user}」，现在换到了你原来的立场「{old_ai}」。"
        f"你现在需要为「{debate['ai_position']}」辩护。"
        f"请简短承认对方换了立场，然后从你的新立场出发，邀请对方发表第一个论点。"
        f"末尾附加思考提示。"
    )

    # 只传最近几条消息作为上下文
    recent = debate["messages"][-4:] if debate["messages"] else []
    ai_reply = call_ai(system_text, recent, max_tokens=600)

    debate["messages"].append({
        "role": "ai",
        "content": ai_reply,
        "exchange": 0,
        "switch_point": True,
    })
    put_debate(debate)

    return jsonify({
        "reply": ai_reply,
        "new_user_position": debate["user_position"],
        "new_ai_position": debate["ai_position"],
    })

@app.route("/api/debate/<debate_id>/report", methods=["POST"])
def api_generate_report(debate_id):
    """生成最终理性评分报告"""
    debate = get_debate(debate_id)
    if not debate:
        return jsonify({"error": "辩论不存在"}), 404

    # 提取用户所有发言
    user_messages = [m for m in debate["messages"] if m["role"] == "user"]
    if not user_messages:
        return jsonify({"error": "没有用户发言，无法生成报告"}), 400

    user_text = "\n\n".join(
        f"[第{m['exchange']}轮] {m['content']}" for m in user_messages
    )

    topic = TOPICS[debate["topic_id"]]
    report_prompt = (
        f"{build_report_system()}\n\n"
        f"## 辩论信息\n"
        f"议题：{topic['title']}\n"
        f"用户立场：{debate['user_position']}\n"
        f"AI立场：{debate['ai_position']}\n\n"
        f"## 用户发言记录\n\n{user_text}"
    )

    report_raw = call_ai(report_prompt, [], max_tokens=1200)
    try:
        # 尝试解析 JSON
        report = json.loads(report_raw)
    except json.JSONDecodeError:
        # 如果 AI 没返回纯 JSON，尝试提取
        import re
        match = re.search(r'\{[\s\S]*\}', report_raw)
        if match:
            try:
                report = json.loads(match.group())
            except json.JSONDecodeError:
                report = {
                    "emotion_markers": [],
                    "ad_hominem_hints": [],
                    "logical_observations": ["AI 报告生成异常，请重试。"],
                    "reading_suggestions": [],
                    "raw": report_raw,
                }
        else:
            report = {
                "emotion_markers": [],
                "ad_hominem_hints": [],
                "logical_observations": ["AI 报告生成异常，请重试。"],
                "reading_suggestions": [],
                "raw": report_raw,
            }

    debate["report"] = report
    debate["completed"] = True
    put_debate(debate)

    return jsonify({"report": report})

@app.route("/api/debate/<debate_id>/state")
def api_debate_state(debate_id):
    """获取辩论当前状态"""
    debate = get_debate(debate_id)
    if not debate:
        return jsonify({"error": "辩论不存在"}), 404
    return jsonify(debate)

# ── 辅助函数 ───────────────────────────────────────────────
def _generate_summary(debate: dict) -> dict:
    """调用 AI 生成三轮小结"""
    topic = TOPICS[debate["topic_id"]]
    transcript = "\n\n".join(
        f"[{'用户' if m['role'] == 'user' else 'AI'}，第{m.get('exchange', 0)}轮]: {m['content']}"
        for m in debate["messages"]
    )

    summary_prompt = (
        f"{build_summary_system(topic)}\n\n"
        f"## 议题：{topic['title']}\n"
        f"用户立场：{debate['user_position']}\n"
        f"AI立场：{debate['ai_position']}\n\n"
        f"## 辩论记录\n\n{transcript}"
    )

    raw = call_ai(summary_prompt, [], max_tokens=600)
    try:
        summary = json.loads(raw)
    except json.JSONDecodeError:
        import re
        match = re.search(r'\{[\s\S]*\}', raw)
        if match:
            try:
                summary = json.loads(match.group())
            except json.JSONDecodeError:
                summary = {
                    "consensus": ["双方进行了3轮辩论"],
                    "essence": "总结生成异常，请继续辩论或结束。",
                    "question": "你想换到对方立场继续辩论吗？",
                }
        else:
            summary = {
                "consensus": ["双方进行了3轮辩论"],
                "essence": "总结生成异常，请继续辩论或结束。",
                "question": "你想换到对方立场继续辩论吗？",
            }

    summary["after_exchange"] = debate["exchange_count"]
    debate["summaries"].append(summary)
    put_debate(debate)
    return summary

# ── 启动 ───────────────────────────────────────────────────
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5010))
    # 生产环境请设 FLASK_DEBUG=0；开发默认关闭 reload 以避免 Windows 下多进程残留
    debug = os.environ.get("FLASK_DEBUG", "0") == "1"
    app.run(host="0.0.0.0", port=port, debug=debug, use_reloader=False)
