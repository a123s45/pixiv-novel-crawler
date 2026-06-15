# PixivNovelCrawler - Pixiv 小说智能爬虫

> 基于 AI 质检与翻译的 Pixiv 小说下载、评估与归档工具

## 功能概览

- **排行榜检索** — 自动扫描 Pixiv R18 周榜历史期数，按收藏数阈值过滤下载
- **Tag 搜索** — 正向/负面/反向三态 Tag 匹配，批量检索并下载目标作品
- **AI 质量评估** — 接入 DeepSeek API，对每篇小说进行完结检测、广告/付费推广识别、Tag 欺诈判断、综合评分
- **多语言翻译** — 非中文小说自动 AI 翻译（人名对照表 + 风格保持 + 分段处理）
- **智能归档** — 质检合格作品归档（中文/翻译双目录），不合格作品记录原因待审
- **Streamlit GUI** — 8 页面可视化面板：仪表盘、配置、Tag 管理、排行榜、Tag 检索、质检结果、归档库、下载记录
- **自适应限流** — 429 错误自动翻倍延迟（4s→30s），成功 20 次后恢复

## 目录结构

```
PixivNovelCrawler/
├── app.py              # Streamlit GUI 主入口
├── config.yaml         # 全局配置文件
├── auth.py             # Cookie 认证 + 代理 + 自适应限流
├── pixiv_api.py        # Pixiv API 封装（详情/正文/搜索/排行/系列/Tag）
├── models.py           # 数据模型（Novel/Series/QualityResult/ArchiveRecord）
├── downloader.py       # 下载器 + 质检→翻译→归档后处理流水线
├── evaluator.py        # AI 质量评估引擎
├── translator.py       # AI 翻译流水线（人名一致性 + 分段翻译）
├── archiver.py         # 归档管理（索引 JSON + 中文/翻译双目录）
├── worker.py           # 后台工作线程（排行榜 / Tag 检索）
├── ranking_crawler.py  # 排行榜扫描逻辑
├── tag_crawler.py      # Tag 匹配检索逻辑
├── series_judge.py     # 系列小说合并判断（AI / 启发式）
├── index_manager.py    # 进度索引 JSON 读写
├── ai_client.py        # DeepSeek API 统一调用层
├── pending_handler.py  # 待处理列表
├── download/           # 原始下载目录
└── archive/            # 归档目录
    ├── index.json      # 归档索引（含 AI 分析数据）
    ├── qualified/      # 合格作品
    │   ├── 中文/       # 中文作品
    │   └── 翻译/       # 外文原件 + 译文
    └── failed/         # 不合格记录
```

## 环境要求

- Python 3.10+
- Streamlit
- DeepSeek API Key（可选，不配置则跳过 AI 质检和翻译）

## 安装

```bash
git clone https://github.com/yourname/PixivNovelCrawler.git
cd PixivNovelCrawler
pip install streamlit requests pyyaml
```

## 配置

编辑 `config.yaml`：

```yaml
ai:
  provider: deepseek
  api_key: "sk-your-deepseek-api-key"   # DeepSeek API Key（可选）
  quality_check_threshold: 500           # 低于此收藏数启用严格质检

auth:
  cookie: "4380493_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"  # Pixiv PHPSESSID

proxy: "http://127.0.0.1:7890/"          # 代理地址（Pixiv 被墙地区需要）

download:
  delay_seconds: 4                        # 请求间隔（秒）
  output_dir: ./download

ranking:
  enabled: true
  bookmark_threshold: 600                 # 排行榜收藏数阈值
  mode: weekly_r18

archive:
  output_dir: ./archive
```

## 使用

### 方式一：Streamlit GUI（推荐）

```bash
python -m streamlit run app.py --server.headless=true
```

打开 `http://localhost:8501`，8 个页面：

1. **📊 仪表盘** — 全局统计（已下载/已归档/不合格/平均质量分）
2. **⚙️ 配置** — Cookie/代理/延迟/阈值
3. **🏷️ Tag 管理** — 查看 Pixiv 收藏 Tag，管理正向/负面/反向 Tag 列表
4. **📈 排行榜** — 一键启动 R18 周榜历史扫描
5. **🔍 Tag 检索** — 按配置的 Tag 列表批量检索
6. **📋 质检结果** — 不合格作品列表（Tag欺诈/广告/付费/过短/低分）
7. **📚 归档库** — 浏览已归档作品（AI 简介/质量分/原文/译文）
8. **📥 下载记录** — 已下载 / 待处理(反向Tag) / 已归档

### 方式二：直接运行

```bash
python main.py
```

## 核心工作流

```
下载完成
  │
  ├─ 全文 < 3000字 → ❌ 不合格（过短）
  │
  ├─ 取前1500字 + 后1500字 → AI 质检
  │   (检查: 完结/广告/付费/Tag欺诈/综合评分)
  │
  ├─ Tag欺诈 == true → ❌ 不合格（记录欺诈 Tag 详情）
  │
  ├─ Tag欺诈 == false:
  │   ├─ bookmark ≥ 阈值 → ✅ 合格（广告/付费/未完结仅标记）
  │   └─ bookmark < 阈值:
  │       ├─ quality_score < 50 或 多项异常 → ❌ 不合格
  │       └─ 否则 → ✅ 合格
  │
  ├─ ❌ 不合格 → archive/failed（记录原因 + 评分）
  │
  └─ ✅ 合格:
       ├─ 中文 → 归档 archive/qualified/中文/
       └─ 外文 → AI 翻译 → 归档 archive/qualified/翻译/
```

## Tag 系统

| 类型 | 逻辑 | 用途 |
|------|------|------|
| ✅ 正向 | OR 匹配 | 命中任一即下载 |
| ⛔ 负面 | 排除 | 含任一即跳过 |
| 🔄 反向 | 手动确认 | 匹配后放入待处理清单 |

## AI 质检字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `is_completed` | bool/null | 作品是否完结 |
| `has_advertisement` | bool | 是否含引流广告/推广 |
| `requires_payment` | bool | 是否需要付费平台解锁 |
| `tag_fraud.exists` | bool | Tag 是否与内容不符 |
| `tag_fraud.fraud_tags` | list[str] | 存在欺诈的 Tag 列表 |
| `quality_score` | 0-100 | 综合质量评分 |
| `summary` | str | AI 生成的一句话简介 |
| `reason` | str | 评估说明 |

## 翻译特性

- 自动语言检测（zh/ja/en/ko）
- AI 提取人名对照表，确保全文翻译一致性
- 分段翻译，保留原文段落结构
- 双文件存储（原件 + 译文）
- 专有名词首次出现可附注原文

## 限流策略

- 初始延迟：4 秒
- 收到 429 后延迟翻倍（8s → 16s → 30s 封顶）
- 每成功 20 次请求延迟恢复至初始值

## 许可证

MIT
