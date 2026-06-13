# 🔥 吵了么 — AI 辩论对手

一面思维镜子，不评判、不教导、只映照。

## 这是什么

一个极简的 AI 辩论聊天应用。你选议题和立场，AI 自动扮演对立立场与你辩论。AI 被严格约束——不带情绪、不人身攻击、不贴标签，只陈述逻辑、提问引导。每轮回复末尾附"思考提示"，帮你看见自己论证中的盲区。

## 功能

- **6 个高冲突议题**：996、算法推荐、城市化、宠物保护、性别对立、AI 贫富差距
- **AI 辩论对手**：双句式结构（映照 + 邀请），严格中立，不带情绪
- **思考提示**：每轮 AI 回复末尾标注盲区扫描或假设探测
- **3 轮小结**：自动总结共识事实 + 分歧本质，支持换位思考
- **理性评分报告**：辩论结束生成报告，标注情绪化用词、逻辑观察、推荐阅读
- **分享链接**：复制 URL 即可分享辩论，任何人可继续

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置 API Key

```bash
cp .env.example .env
```

编辑 `.env`，填入你的 API Key（支持 DeepSeek / OpenAI 兼容接口）：

```
API_KEY=sk-你的key
API_MODEL=deepseek-chat
API_BASE_URL=https://api.deepseek.com
```

### 3. 启动

```bash
python app.py
```

浏览器打开 `http://127.0.0.1:5000`，开始辩论。

> **没有 API Key 也能跑**——Mock 模式会返回模拟回复，方便体验完整 UI 流程。

## 项目结构

```
├── app.py              # Flask 后端
├── templates/
│   └── index.html      # 单页前端
├── requirements.txt    # Python 依赖
├── .env.example        # 环境变量模板
└── README.md
```

## 技术栈

- Python Flask
- DeepSeek / OpenAI 兼容 API
- 纯 HTML + CSS + JavaScript（无前端框架）

