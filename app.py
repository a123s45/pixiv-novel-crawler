import os
import time
import yaml
import streamlit as st
from threading import Thread

from auth import PixivAuth
from pixiv_api import PixivAPI
from index_manager import IndexManager
from worker import CrawlerWorker

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.yaml")


def load_config():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def save_config(cfg):
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        yaml.dump(cfg, f, allow_unicode=True, indent=2)


PAGES = ["📊 仪表盘", "⚙️ 配置", "🏷️ Tag 管理", "📈 排行榜", "🔍 Tag 检索", "📋 质检结果", "📚 归档库", "📥 下载记录"]


def init_session():
    if "cfg" not in st.session_state:
        st.session_state.cfg = load_config()
    if "worker" not in st.session_state:
        st.session_state.worker = CrawlerWorker(st.session_state.cfg)
    if "page" not in st.session_state:
        st.session_state.page = PAGES[0]
    if "tag_results" not in st.session_state:
        st.session_state.tag_results = []


def sidebar_nav():
    st.sidebar.title("Pixiv 小说爬虫")
    idx = PAGES.index(st.session_state.page) if st.session_state.page in PAGES else 0
    choice = st.sidebar.radio("导航", PAGES, index=idx)
    st.session_state.page = choice
    return choice


def page_config():
    st.header("⚙️ 配置")
    cfg = st.session_state.cfg

    with st.form("config_form"):
        st.text_input("Cookie (PHPSESSID)", key="cfg_cookie", value=cfg["auth"]["cookie"])
        st.text_input("代理地址", key="cfg_proxy", value=cfg.get("proxy", ""))
        st.slider("请求间隔 (秒)", 1, 30, int(cfg["download"]["delay_seconds"]), key="cfg_delay")
        st.checkbox("启用排行榜检索", value=cfg["ranking"]["enabled"], key="cfg_ranking_enabled")
        st.number_input("排行榜前 N 名", 10, 100, cfg["ranking"]["top_n"], key="cfg_top_n")
        st.number_input("收藏阈值", 100, 5000, cfg["ranking"]["bookmark_threshold"], key="cfg_bookmark")

        if st.form_submit_button("💾 保存配置"):
            cfg["auth"]["cookie"] = st.session_state.cfg_cookie
            cfg["proxy"] = st.session_state.cfg_proxy
            cfg["download"]["delay_seconds"] = st.session_state.cfg_delay
            cfg["ranking"]["enabled"] = st.session_state.cfg_ranking_enabled
            cfg["ranking"]["top_n"] = st.session_state.cfg_top_n
            cfg["ranking"]["bookmark_threshold"] = st.session_state.cfg_bookmark
            save_config(cfg)
            st.success("配置已保存")


def page_tag_manager():
    st.header("🏷️ Tag 管理")
    cfg = st.session_state.cfg
    ts = cfg.setdefault("tag_search", {})
    ts.setdefault("positive_tags", [])
    ts.setdefault("negative_tags", [])
    ts.setdefault("min_bookmarks", 0)
    ts.setdefault("min_words", 0)
    ts.setdefault("max_words", 0)
    ts.setdefault("max_results", 200)
    cfg.setdefault("reverse_tags", [])

    with st.expander("⭐ 我的收藏 Tag（点击展开）", expanded=False):
        try:
            api = PixivAPI(PixivAuth(cfg))
            fav_tags = api.get_favorite_tags()
            if fav_tags:
                st.caption(f"共 {len(fav_tags)} 个收藏 Tag")
                cols = st.columns(4)
                for i, tag in enumerate(fav_tags):
                    ci = i % 4
                    with cols[ci]:
                        c1, c2, c3 = st.columns([1, 1, 1])
                        with c1:
                            if st.button("✅正向", key=f"fav_p_{tag}", use_container_width=True):
                                if tag not in ts["positive_tags"]:
                                    ts["positive_tags"].append(tag)
                                    save_config(cfg)
                                    st.rerun()
                        with c2:
                            if st.button("⛔负面", key=f"fav_n_{tag}", use_container_width=True):
                                if tag not in ts["negative_tags"]:
                                    ts["negative_tags"].append(tag)
                                    save_config(cfg)
                                    st.rerun()
                        with c3:
                            if st.button("🔄反向", key=f"fav_r_{tag}", use_container_width=True):
                                if tag not in cfg["reverse_tags"]:
                                    cfg["reverse_tags"].append(tag)
                                    save_config(cfg)
                                    st.rerun()
                        st.write(f"　{tag}")
            else:
                st.info("没有收藏 Tag，可在 Pixiv 网站上添加")
        except Exception as e:
            st.error(f"获取收藏 Tag 失败: {e}")

    col1, col2 = st.columns([3, 1])
    with col1:
        keyword = st.text_input("搜索 Tag（支持中日英文）", key="tag_search_input")
    with col2:
        st.write("")
        st.write("")
        if st.button("🔍 搜索", use_container_width=True):
            if keyword.strip():
                try:
                    api = PixivAPI(PixivAuth(cfg))
                    st.session_state.tag_results = api.search_tags(keyword.strip())
                except Exception as e:
                    st.error(f"搜索失败: {e}")

    if st.session_state.tag_results:
        st.caption(f"搜索结果: {len(st.session_state.tag_results)} 个匹配")
        for t in st.session_state.tag_results:
            tag_name = t["tag"]
            trans = t.get("translation", "")
            display = f"{tag_name} ({trans})" if trans else tag_name
            cols = st.columns([4, 1, 1, 1])
            with cols[0]:
                st.write(f"**{display}**  `{t.get('type', '')}`")
            with cols[1]:
                if st.button("✅正向", key=f"p_{tag_name}", use_container_width=True):
                    if tag_name not in ts["positive_tags"]:
                        ts["positive_tags"].append(tag_name)
                        save_config(cfg)
                        st.rerun()
            with cols[2]:
                if st.button("⛔负面", key=f"n_{tag_name}", use_container_width=True):
                    if tag_name not in ts["negative_tags"]:
                        ts["negative_tags"].append(tag_name)
                        save_config(cfg)
                        st.rerun()
            with cols[3]:
                if st.button("🔄反向", key=f"r_{tag_name}", use_container_width=True):
                    if tag_name not in cfg["reverse_tags"]:
                        cfg["reverse_tags"].append(tag_name)
                        save_config(cfg)
                        st.rerun()

    st.divider()
    st.info("✅ **正向** = 满足任一即下载 (OR)　　　⛔ **负面** = 含任一即跳过　　　🔄 **反向** = 不自动下载，加入待处理清单手动决定")
    st.divider()
    col_a, col_b, col_c = st.columns(3)

    with col_a:
        st.subheader("✅ 正向 Tag (OR)")
        for tag in list(ts["positive_tags"]):
            c1, c2 = st.columns([4, 1])
            with c1:
                st.write(tag)
            with c2:
                if st.button("✕", key=f"del_p_{tag}", use_container_width=True):
                    ts["positive_tags"].remove(tag)
                    save_config(cfg)
                    st.rerun()

    with col_b:
        st.subheader("⛔ 负面 Tag (排除)")
        for tag in list(ts["negative_tags"]):
            c1, c2 = st.columns([4, 1])
            with c1:
                st.write(tag)
            with c2:
                if st.button("✕", key=f"del_n_{tag}", use_container_width=True):
                    ts["negative_tags"].remove(tag)
                    save_config(cfg)
                    st.rerun()

    with col_c:
        st.subheader("🔄 反向 Tag (待处理)")
        for tag in list(cfg["reverse_tags"]):
            c1, c2 = st.columns([4, 1])
            with c1:
                st.write(tag)
            with c2:
                if st.button("✕", key=f"del_r_{tag}", use_container_width=True):
                    cfg["reverse_tags"].remove(tag)
                    save_config(cfg)
                    st.rerun()

    st.divider()
    with st.form("tag_filter_form"):
        st.subheader("过滤条件")
        cols = st.columns(4)
        with cols[0]:
            min_bm = st.number_input("最低收藏", 0, 50000, ts["min_bookmarks"])
        with cols[1]:
            min_w = st.number_input("最少字数", 0, 100000, ts["min_words"])
        with cols[2]:
            max_w = st.number_input("最大字数 (0=不限)", 0, 100000, ts["max_words"])
        with cols[3]:
            max_r = st.number_input("单Tag上限", 0, 5000, ts["max_results"])
        if st.form_submit_button("💾 保存过滤条件"):
            ts["min_bookmarks"] = min_bm
            ts["min_words"] = min_w
            ts["max_words"] = max_w
            ts["max_results"] = max_r
            save_config(cfg)
            st.success("过滤条件已保存")


def show_crawler_progress(state):
    if state.running:
        st.info(f"运行中: {'排行榜' if state.task_type == 'ranking' else 'Tag 检索'}")
        if state.total > 0:
            st.progress(min(state.progress, 1.0))
        st.write(f"当前: {state.current_item}")
        st.write(f"已下载: {state.downloaded}")
        with st.container(height=200):
            for line in state.log[-30:]:
                st.text(line)
        return True
    return False


def page_ranking():
    st.header("📈 排行榜检索")
    worker = st.session_state.worker
    state = worker.state

    if not show_crawler_progress(state):
        if st.button("▶ 开始排行榜检索", type="primary", use_container_width=True):
            worker.start_ranking()
            st.rerun()

    if state.running:
        if st.button("■ 停止", use_container_width=True):
            worker.stop()
            st.rerun()


def page_tag_search():
    st.header("🔍 Tag 检索")
    cfg = st.session_state.cfg
    ts = cfg.get("tag_search", {})
    pos = ts.get("positive_tags", [])
    neg = ts.get("negative_tags", [])
    rev = cfg.get("reverse_tags", [])

    st.write(f"正向 Tag: {', '.join(pos) if pos else '未设置'}")
    st.write(f"负面 Tag: {', '.join(neg) if neg else '无'}")
    st.write(f"反向 Tag: {', '.join(rev) if rev else '无'}")

    worker = st.session_state.worker
    state = worker.state

    if not pos:
        st.warning("请在「Tag 管理」页面添加至少一个正向 Tag")
        return

    if not show_crawler_progress(state):
        if st.button("▶ 开始 Tag 检索", type="primary", use_container_width=True):
            worker.start_tag_search()
            st.rerun()

    if state.running:
        if st.button("■ 停止", use_container_width=True):
            worker.stop()
            st.rerun()


def page_downloads():
    st.header("📥 下载记录")
    cfg = st.session_state.cfg
    index = IndexManager()

    tab1, tab2, tab3 = st.tabs(["📥 已下载", "⏳ 待处理", "📦 已归档"])

    with tab1:
        st.subheader(f"已下载 ({len(index.data['downloaded_ids'])} 篇)")
        download_dir = cfg["download"]["output_dir"]
        if os.path.exists(download_dir):
            files = sorted(os.listdir(download_dir), reverse=True)
            search = st.text_input("搜索文件名", key="dl_search")
            for f in files[:100]:
                if search and search.lower() not in f.lower():
                    continue
                size = os.path.getsize(os.path.join(download_dir, f))
                st.text(f"{f}  ({size/1024:.1f} KB)")

    with tab2:
        pending = index.get_pending_list()
        if not pending:
            st.info("暂无待处理作品")
        else:
            st.subheader(f"待处理 ({len(pending)} 篇)")
            for item in pending:
                with st.expander(f"{item.title} ({item.novel_id})"):
                    st.write(f"匹配 Tag: {', '.join(item.matched_tags)}")
                    st.write(f"来源: {item.source}")
                    st.write(f"链接: {item.url}")
                    c1, c2 = st.columns(2)
                    with c1:
                        if st.button(f"下载 {item.novel_id}", key=f"dl_{item.novel_id}"):
                            try:
                                api = PixivAPI(PixivAuth(cfg))
                                from downloader import Downloader
                                from ai_client import AIClient
                                from series_judge import SeriesJudge
                                dl = Downloader(api, index, cfg)
                                ai = AIClient(cfg)
                                judge = SeriesJudge(api, ai, index, cfg)
                                novel = api.get_novel_detail(item.novel_id)
                                decision, chapter_ids, series_info = judge.judge(novel)
                                if decision == "merge":
                                    path = dl.download_series(novel, series_info, chapter_ids)
                                else:
                                    path = dl.download(novel)
                                index.remove_pending(item.novel_id)
                                st.success(f"下载成功: {path}")
                            except Exception as e:
                                st.error(f"下载失败: {e}")
                    with c2:
                        if st.button(f"跳过 {item.novel_id}", key=f"sk_{item.novel_id}"):
                            index.remove_pending(item.novel_id)
                            st.rerun()
            if st.button("全部跳过", key="skip_all"):
                for item in pending:
                    index.remove_pending(item.novel_id)
                st.rerun()

    with tab3:
        st.caption("已归档作品请到「📚 归档库」页面查看")
        from archiver import Archiver
        archiver = Archiver(cfg)
        summary = archiver.get_summary()
        cols = st.columns(3)
        cols[0].metric("已归档", summary["qualified_count"])
        cols[1].metric("翻译作品", summary["translated_count"])
        cols[2].metric("总字数", f"{summary['total_words']:,}")


def page_eval_results():
    st.header("📋 质检结果")
    cfg = st.session_state.cfg
    from archiver import Archiver
    archiver = Archiver(cfg)
    failed = archiver.get_failed()

    if not failed:
        st.info("暂无不合格作品")
        return

    st.caption(f"共 {len(failed)} 篇不合格作品")
    for item in failed:
        score = item.get("quality_score", 0)
        reasons = item.get("reasons", [])
        tf = item.get("tag_fraud", False)
        fraud_tags = item.get("fraud_tags", [])

        color = "🔴" if tf else "🟡"
        with st.expander(f"{color} {item['title']} ({item['novel_id']})  评分:{score}"):
            cols = st.columns(2)
            with cols[0]:
                st.write(f"**字数**: {item.get('word_count', '?')}")
                st.write(f"**收藏**: {item.get('bookmarks', '?')}")
                st.write(f"**Tag**: {', '.join(item.get('tags', []))}")
            with cols[1]:
                st.write(f"**不合格原因**:")
                for r in reasons:
                    st.error(f"  • {r}")
                if tf:
                    st.error(f"  **Tag欺诈**: {', '.join(fraud_tags) if fraud_tags else '是'}")
            if item.get("summary"):
                st.caption(f"AI简介: {item['summary']}")


def page_archive():
    st.header("📚 归档库")
    cfg = st.session_state.cfg
    from archiver import Archiver
    archiver = Archiver(cfg)

    search = st.text_input("搜索标题或 Tag", key="archive_search")
    col_f1, col_f2 = st.columns(2)
    with col_f1:
        lang_filter = st.selectbox("语言", ["全部", "中文", "翻译"])
    with col_f2:
        min_score = st.slider("最低质量分", 0, 100, 0)

    items = archiver.get_qualified(search=search)
    if lang_filter == "中文":
        items = [i for i in items if not i.get("translated")]
    elif lang_filter == "翻译":
        items = [i for i in items if i.get("translated")]
    if min_score > 0:
        items = [i for i in items if i.get("quality_score", 0) >= min_score]

    if not items:
        st.info("暂无归档作品")
        return

    st.caption(f"共 {len(items)} 篇")
    for item in items:
        score = item.get("quality_score", 0)
        translated = item.get("translated", False)
        tag_label = "🌐 翻译" if translated else "📄 中文"
        ad_flag = " 📢广告" if item.get("has_advertisement") else ""
        pay_flag = " 💰付费" if item.get("requires_payment") else ""

        with st.expander(f"{tag_label} {item['title']}  ({item.get('novel_id', '')})  评分:{score}{ad_flag}{pay_flag}"):
            cols = st.columns(3)
            with cols[0]:
                st.write(f"**字数**: {item.get('word_count', '?')}")
                st.write(f"**收藏**: {item.get('bookmarks', '?')}")
                st.write(f"**Tag**: {', '.join(item.get('tags', []))}")
            with cols[1]:
                st.write(f"**AI简介**: {item.get('ai_summary', '无')}")
                st.write(f"**质量分**: {score}")
                if ad_flag:
                    st.warning("含广告/推广标记")
                if pay_flag:
                    st.warning("含付费平台标记")
            with cols[2]:
                orig = item.get("original_file", "")
                trans = item.get("translated_file", "")
                if orig and os.path.exists(orig):
                    if st.button(f"📖 查看原文", key=f"view_orig_{item['novel_id']}", use_container_width=True):
                        with open(orig, "r", encoding="utf-8") as f:
                            st.text_area("原文", f.read(), height=300)
                if trans and os.path.exists(trans):
                    if st.button(f"📖 查看译文", key=f"view_trans_{item['novel_id']}", use_container_width=True):
                        with open(trans, "r", encoding="utf-8") as f:
                            st.text_area("译文", f.read(), height=300)


def page_dashboard():
    st.header("📊 仪表盘")
    cfg = st.session_state.cfg
    index = IndexManager()
    from archiver import Archiver
    archiver = Archiver(cfg)
    summary = archiver.get_summary()

    downloaded = len(index.data["downloaded_ids"])
    scanned = len(index.data["ranking_scanned"])
    pending = len(index.get_pending_list())
    tags = cfg.get("tag_search", {}).get("positive_tags", [])

    cols = st.columns(5)
    cols[0].metric("已下载", downloaded)
    cols[1].metric("已归档", summary["qualified_count"])
    cols[2].metric("不合格", summary["failed_count"])
    cols[3].metric("待处理", pending)
    cols[4].metric("平均质量分", summary["avg_score"])

    st.subheader("最近下载")
    download_dir = cfg["download"]["output_dir"]
    if os.path.exists(download_dir):
        files = sorted(os.listdir(download_dir), key=lambda f: os.path.getmtime(os.path.join(download_dir, f)), reverse=True)
        for f in files[:10]:
            st.text(f"  {f}")

    st.subheader("配置概览")
    st.json({
        "Cookie": cfg["auth"]["cookie"][:8] + "..." if cfg["auth"]["cookie"] else "未设置",
        "代理": cfg.get("proxy", "无"),
        "延迟": f"{cfg['download']['delay_seconds']}s",
        "排行榜": "启用" if cfg["ranking"]["enabled"] else "禁用",
        "正向 Tag": tags,
        "负面 Tag": cfg.get("tag_search", {}).get("negative_tags", []),
    })


def main():
    st.set_page_config(page_title="Pixiv 小说爬虫", page_icon="📖", layout="wide")
    st.markdown("""
        <style>
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        header {visibility: hidden;}
        .stAppDeployButton {display:none !important;}
        </style>
    """, unsafe_allow_html=True)
    init_session()
    page = sidebar_nav()

    {
        "📊 仪表盘": page_dashboard,
        "⚙️ 配置": page_config,
        "🏷️ Tag 管理": page_tag_manager,
        "📈 排行榜": page_ranking,
        "🔍 Tag 检索": page_tag_search,
        "📋 质检结果": page_eval_results,
        "📚 归档库": page_archive,
        "📥 下载记录": page_downloads,
    }[page]()


if __name__ == "__main__":
    main()
