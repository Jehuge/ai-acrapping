import sys
from pathlib import Path
import os
import asyncio
import json

import requests
import streamlit as st
from scrapegraphai.graphs import SmartScraperGraph
from playwright.async_api import async_playwright, TimeoutError

# Ensure project root is on sys.path so absolute imports work when run via `streamlit run unified_app/app.py`
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from unified_app.config import AppConfig, build_graph_config
from unified_app.history import load_history, append_history


st.set_page_config(page_title="统一 Web Scraping AI Agent", layout="wide")


async def fetch_html_with_playwright(
    url: str,
    need_login: bool = False,
    login_url: str | None = None,
    use_storage: bool = True,
    manual_login: bool = False,
    headless: bool = True,
    page_wait_strategy: str = "domcontentloaded",
    page_timeout: int = 60,
):
    """复用原有 LM Studio demo 中的 Playwright 登录抓取逻辑。"""
    storage_state_path = "login_state.json" if need_login and use_storage else None

    async with async_playwright() as p:
        if need_login:
            st.info("🔑 启动带登录的浏览器...")
        browser = await p.chromium.launch(headless=headless)

        # 读取存储状态
        context_options = {"accept_downloads": False}
        if storage_state_path and os.path.exists(storage_state_path):
            try:
                raw_state = Path(storage_state_path).read_text(encoding="utf-8").strip()
                if raw_state:
                    json.loads(raw_state)
                    context_options["storage_state"] = storage_state_path
                    st.info("🔑 检测到保存的登录状态，将自动使用")
                else:
                    st.warning("⚠️ 检测到空的 login_state.json，已忽略并删除，请重新登录")
                    os.remove(storage_state_path)
            except Exception:
                st.warning("⚠️ 登录状态文件不可用，已忽略")

        context = await browser.new_context(**context_options)
        page = await context.new_page()

        try:
            if need_login:
                target_login_url = login_url if login_url else url
                st.info(f"🔐 正在访问登录页面: {target_login_url}")
                try:
                    await page.goto(
                        target_login_url,
                        wait_until=page_wait_strategy,
                        timeout=page_timeout * 1000,
                    )
                except TimeoutError:
                    st.warning("⚠️ 登录页加载超时，改用 domcontentloaded 再试")
                    await page.goto(
                        target_login_url,
                        wait_until="domcontentloaded",
                        timeout=page_timeout * 1000,
                    )
                await page.wait_for_timeout(2000)

                if manual_login:
                    st.warning(
                        "⚠️ 手动登录模式开启，请在弹出的浏览器中完成登录。"
                    )
                    # 这里沿用原 demo 的简化逻辑：等待用户在浏览器中完成登录
                    waited = 0
                    interval = 3000
                    while waited < 300_000:
                        await page.wait_for_timeout(interval)
                        waited += interval
                        cur = page.url
                        st.info(f"📍 当前页面: {cur}")
                        if "/login" not in cur and "signin" not in cur:
                            st.success("✅ 检测到已登录，继续抓取页面")
                            break
                    else:
                        st.error("❌ 登录超时，请重试")
                        return None

                    if storage_state_path:
                        await context.storage_state(path=storage_state_path)
                        st.success("✅ 登录状态已保存到 login_state.json")

            # 访问目标页
            st.info(f"🌐 正在访问: {url}")
            target_wait_until = (
                "domcontentloaded" if "github.com" in url else page_wait_strategy
            )
            try:
                await page.goto(
                    url,
                    wait_until=target_wait_until,
                    timeout=page_timeout * 1000,
                )
            except TimeoutError:
                st.warning("⚠️ 页面加载超时，改用 domcontentloaded 再试")
                await page.goto(
                    url,
                    wait_until="domcontentloaded",
                    timeout=page_timeout * 1000,
                )

            await page.wait_for_timeout(2000)
            html = await page.content()
            st.success("✅ 已获取页面 HTML")
            return html
        finally:
            await browser.close()


def render_provider_settings(app_cfg: AppConfig) -> AppConfig:
    st.sidebar.header("模型与厂商配置")

    provider = st.sidebar.selectbox(
        "选择厂商",
        options=["openai", "ollama", "lmstudio"],
        format_func=lambda v: {
            "openai": "OpenAI（云端）",
            "ollama": "Ollama（本地）",
            "lmstudio": "LM Studio（本地）",
        }[v],
        index=["openai", "ollama", "lmstudio"].index(app_cfg.provider),
    )
    app_cfg.provider = provider  # type: ignore[assignment]

    if provider == "openai":
        st.sidebar.subheader("OpenAI 设置")
        app_cfg.openai.api_key = st.sidebar.text_input(
            "OpenAI API Key",
            value=app_cfg.openai.api_key,
            type="password",
        )
        app_cfg.openai.model = st.sidebar.text_input(
            "当前模型名称",
            value=app_cfg.openai.model,
            help="例如：gpt-4o, gpt-4.1, gpt-5 等",
        )

        # 测试 OpenAI 连接并拉取模型列表
        if st.sidebar.button("🔍 测试连接", help="测试 OpenAI API 是否可用，并列出部分模型"):
            with st.sidebar:
                if not app_cfg.openai.api_key:
                    st.error("❌ 请先填写 OpenAI API Key")
                else:
                    with st.spinner("正在测试 OpenAI 连接并获取模型列表..."):
                        try:
                            resp = requests.get(
                                "https://api.openai.com/v1/models",
                                headers={
                                    "Authorization": f"Bearer {app_cfg.openai.api_key}"
                                },
                                timeout=10,
                            )
                            if resp.status_code == 200:
                                data = resp.json()
                                # OpenAI 返回 data 数组，每项包含 id
                                ids = [
                                    m.get("id", "unknown")
                                    for m in data.get("data", [])
                                ]
                                if ids:
                                    st.success("✅ 连接成功！已获取模型列表")
                                    st.info(f"可用模型数量: {len(ids)}")
                                    st.session_state["openai_models"] = ids
                                    st.write("部分模型示例：")
                                    for name in ids[:5]:
                                        st.text(f"  • {name}")
                                else:
                                    st.warning("连接成功，但未从返回结果中解析到模型 ID")
                            else:
                                st.error(f"❌ 连接失败: HTTP {resp.status_code}")
                        except requests.exceptions.Timeout:
                            st.error("❌ 连接超时，请检查网络或稍后重试")
                        except Exception as e:
                            st.error(f"❌ 错误: {e}")

        # OpenAI 模型下拉选择（若已有缓存列表）
        openai_models = st.session_state.get("openai_models", [])
        if openai_models:
            try:
                default_index = (
                    openai_models.index(app_cfg.openai.model)
                    if app_cfg.openai.model in openai_models
                    else 0
                )
            except ValueError:
                default_index = 0

            selected = st.sidebar.selectbox(
                "从 OpenAI 模型中选择",
                options=openai_models,
                index=default_index,
                help="从 OpenAI 返回的模型列表中选择一个模型",
            )
            app_cfg.openai.model = selected
    elif provider == "ollama":
        st.sidebar.subheader("Ollama 设置")
        app_cfg.ollama.base_url = st.sidebar.text_input(
            "Ollama Base URL",
            value=app_cfg.ollama.base_url,
        )
        app_cfg.ollama.model = st.sidebar.text_input(
            "当前模型名称",
            value=app_cfg.ollama.model,
            help="例如：llama3.2、qwen2.5 等（不需要前缀 ollama/）",
        )

        # 测试 Ollama 连接并拉取模型列表
        if st.sidebar.button("🔍 测试连接", help="测试 Ollama Server 是否可用，并列出本地模型"):
            with st.sidebar:
                with st.spinner("正在测试 Ollama 连接并获取模型列表..."):
                    try:
                        # Ollama 的标签接口通常是 /api/tags
                        base = app_cfg.ollama.base_url.rstrip("/")
                        # 兼容用户既填 http://localhost:11434 又填 http://localhost:11434/
                        if base.endswith("/v1"):
                            base = base.rsplit("/v1", 1)[0]
                        resp = requests.get(f"{base}/api/tags", timeout=10)
                        if resp.status_code == 200:
                            data = resp.json()
                            # tags 接口一般返回 {"models": [{"name": "...", ...}, ...]}
                            models = data.get("models") or data.get("data") or []
                            names = [
                                m.get("name", "unknown") for m in models if m.get("name")
                            ]
                            if names:
                                st.success("✅ 连接成功！已获取本地模型列表")
                                st.info(f"本地模型数量: {len(names)}")
                                st.session_state["ollama_models"] = names
                                st.write("部分模型示例：")
                                for name in names[:5]:
                                    st.text(f"  • {name}")
                            else:
                                st.warning("连接成功，但未从返回结果中解析到模型名称")
                        else:
                            st.error(f"❌ 连接失败: HTTP {resp.status_code}")
                    except requests.exceptions.Timeout:
                        st.error("❌ 连接超时，请检查 Ollama Server 是否正在运行")
                    except Exception as e:
                        st.error(f"❌ 错误: {e}")

        # Ollama 模型下拉选择
        ollama_models = st.session_state.get("ollama_models", [])
        if ollama_models:
            try:
                default_index = (
                    ollama_models.index(app_cfg.ollama.model)
                    if app_cfg.ollama.model in ollama_models
                    else 0
                )
            except ValueError:
                default_index = 0

            selected = st.sidebar.selectbox(
                "从 Ollama 模型中选择",
                options=ollama_models,
                index=default_index,
                help="从本地 Ollama Server 返回的模型列表中选择一个模型",
            )
            app_cfg.ollama.model = selected
    elif provider == "lmstudio":
        st.sidebar.subheader("LM Studio 设置")
        app_cfg.lmstudio.base_url = st.sidebar.text_input(
            "LM Studio API URL",
            value=app_cfg.lmstudio.base_url,
            help="LM Studio 默认运行在 http://localhost:1234/v1",
        )
        # 先用文本框输入/回显当前模型
        app_cfg.lmstudio.model = st.sidebar.text_input(
            "当前模型名称",
            value=app_cfg.lmstudio.model,
            help="在 LM Studio 中加载的模型名称（例如：llama-3.2-3b-instruct）",
        )
        app_cfg.lmstudio.api_key = st.sidebar.text_input(
            "API Key（可选）",
            value=app_cfg.lmstudio.api_key,
            type="password",
            help="LM Studio 通常不校验 Key，可填写任意字符串",
        )

        # 测试 LM Studio 连接并列出模型
        if st.sidebar.button("🔍 测试连接", help="测试 LM Studio 服务器是否可用"):
            with st.sidebar:
                with st.spinner("正在测试连接..."):
                    try:
                        test_url = f"{app_cfg.lmstudio.base_url.rstrip('/v1')}/v1/models"
                        response = requests.get(test_url, timeout=5)
                        if response.status_code == 200:
                            models = response.json()
                            st.success("✅ 连接成功！")
                            if "data" in models:
                                st.info(f"可用模型数量: {len(models['data'])}")
                                model_names = [
                                    m.get("id", "N/A")
                                    for m in models.get("data", [])
                                ]
                                if model_names:
                                    # 把模型列表存到 session_state，方便下拉选择
                                    st.session_state["lmstudio_models"] = model_names
                                    st.write("可用模型：")
                                    for name in model_names[:5]:
                                        st.text(f"  • {name}")
                        else:
                            st.error(f"❌ 连接失败: HTTP {response.status_code}")
                    except requests.exceptions.ConnectionError:
                        st.error("❌ 无法连接到服务器\n请确保 LM Studio 正在运行")
                    except requests.exceptions.Timeout:
                        st.error("❌ 连接超时\n请检查服务器地址")
                    except Exception as e:
                        st.error(f"❌ 错误: {str(e)}")

        # 如果有缓存的模型列表，提供下拉选择并同步回配置
        lmstudio_models = st.session_state.get("lmstudio_models", [])
        if lmstudio_models:
            try:
                # 若当前配置的模型在列表中，则默认选中；否则选第一个
                default_index = (
                    lmstudio_models.index(app_cfg.lmstudio.model)
                    if app_cfg.lmstudio.model in lmstudio_models
                    else 0
                )
            except ValueError:
                default_index = 0

            selected = st.sidebar.selectbox(
                "从服务器模型中选择",
                options=lmstudio_models,
                index=default_index,
                help="从 LM Studio 返回的模型列表中选择一个模型",
            )
            app_cfg.lmstudio.model = selected

    if st.sidebar.button("💾 保存配置"):
        app_cfg.save()
        st.sidebar.success("配置已保存到本地 unified_config.json")

    return app_cfg


def render_history():
    st.sidebar.markdown("---")
    st.sidebar.subheader("历史记录")
    history_items = load_history()
    if not history_items:
        st.sidebar.caption("暂无历史记录")
        return

    for item in history_items[:20]:
        with st.sidebar.expander(f"{item.timestamp} · {item.provider}", expanded=False):
            st.write(f"**URL**: {item.url}")
            st.write(f"**Prompt**: {item.prompt}")
            if item.summary:
                st.write("**摘要：**")
                st.write(item.summary)


def main():
    st.title("统一 Web Scraping AI Agent 🕷️")
    st.caption("支持 OpenAI / Ollama / LM Studio，多厂商统一配置，结果本地存储与历史记录浏览")

    app_cfg = AppConfig.load()
    app_cfg = render_provider_settings(app_cfg)
    render_history()

    # 高级选项（页面加载）
    st.sidebar.subheader("高级选项")
    wait_for_load = st.sidebar.selectbox(
        "页面加载等待策略",
        ["domcontentloaded", "networkidle", "load"],
        index=1,
        help="networkidle: 等待所有网络请求完成（推荐）\ndomcontentloaded: 仅等待 DOM 加载\nload: 等待所有资源加载",
    )
    enable_js = st.sidebar.checkbox(
        "启用 JavaScript 渲染",
        value=True,
        help="确保 JavaScript 动态内容被正确加载",
    )
    wait_time = st.sidebar.slider(
        "额外等待时间（秒）",
        min_value=0,
        max_value=10,
        value=3,
        help="页面加载后的额外等待时间，确保动态内容渲染完成",
    )

    # 登录选项（Playwright）
    st.sidebar.subheader("登录选项（需要登录的网站）")
    need_login = st.sidebar.checkbox("需要登录", value=False)
    login_url = (
        st.sidebar.text_input(
            "登录页面 URL",
            value="https://github.com/login",
            help="如果与目标页不同，请填入登录页",
        )
        if need_login
        else ""
    )
    manual_login = st.sidebar.checkbox("手动登录", value=False) if need_login else False
    use_storage = (
        st.sidebar.checkbox("保存登录状态", value=True) if need_login else False
    )
    headless = (
        st.sidebar.checkbox(
            "无头模式",
            value=not manual_login,
            help="手动登录建议关闭无头模式",
        )
        if need_login
        else True
    )

    st.markdown("### 抓取配置")
    col_url, col_prompt = st.columns(2)
    with col_url:
        url = st.text_input("目标网页 URL", placeholder="https://example.com")
    with col_prompt:
        user_prompt = st.text_input(
            "你希望 AI 从网页中抓取什么？",
            placeholder="例如：提取所有产品名称和价格",
        )

    use_schema = st.checkbox("使用结构化 JSON 输出（可选）", value=False)
    json_schema = None
    if use_schema:
        schema_text = st.text_area(
            "JSON Schema",
            value='''{
  "type": "object",
  "properties": {
    "items": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "title": {"type": "string"},
          "value": {"type": "string"}
        }
      }
    }
  }
}''',
            height=220,
        )
        try:
            json_schema = json.loads(schema_text)
        except Exception:
            st.warning("JSON Schema 解析失败，将忽略结构化约束")
            json_schema = None

    show_raw_html = st.checkbox(
        "显示原始 HTML（调试用）", value=False, help="显示抓取到的原始 HTML 内容，用于调试"
    )

    st.markdown("---")
    if st.button("🚀 开始抓取", type="primary"):
        if not url or not user_prompt:
            st.warning("请填写 URL 和抓取提示")
        elif app_cfg.provider == "openai" and not app_cfg.openai.api_key:
            st.warning("请选择 OpenAI 时需要填写 API Key")
        else:
            graph_config = build_graph_config(app_cfg)

            # loader_kwargs 复用原有高级选项配置
            loader_kwargs = {
                "load_state": wait_for_load,
                "requires_js_support": enable_js,
                "timeout": 60 + wait_time,
            }
            graph_config["loader_kwargs"] = loader_kwargs

            with st.spinner("正在抓取并解析网页数据..."):
                try:
                    # 如需登录，先用 Playwright 获取登录态页面的 HTML
                    page_html = None
                    if need_login:
                        page_html = asyncio.run(
                            fetch_html_with_playwright(
                                url=url,
                                need_login=need_login,
                                login_url=login_url,
                                use_storage=use_storage,
                                manual_login=manual_login,
                                headless=headless,
                                page_wait_strategy=wait_for_load,
                                page_timeout=60 + wait_time,
                            )
                        )
                        if not page_html:
                            st.error("❌ 未能获取页面内容，请检查登录状态")
                            return

                        if page_html and len(page_html) > 250_000:
                            st.info(
                                "ℹ️ 页面较大，已自动截断部分 HTML 以适配模型上下文长度（约 250k 字符）"
                            )
                            page_html = page_html[:250_000]

                    source = page_html if page_html else url
                    graph = SmartScraperGraph(
                        prompt=user_prompt,
                        source=source,
                        config=graph_config,
                        schema=json_schema if json_schema else None,
                    )
                    result = graph.run()

                    append_history(
                        provider=app_cfg.provider,
                        url=url,
                        prompt=user_prompt,
                        result=result,
                    )

                    st.success("✅ 抓取完成")
                    st.subheader("📊 抓取结果")

                    # 调试：显示 HTML
                    if show_raw_html and page_html:
                        with st.expander("🔍 登录后页面 HTML（调试）", expanded=False):
                            st.code(
                                page_html[:5000] + "\n... (截断)", language="html"
                            )

                    if isinstance(result, dict):
                        if "content" in result and isinstance(result["content"], str):
                            st.markdown("#### 内容")
                            st.markdown(result["content"])
                        with st.expander("查看完整 JSON 结果", expanded=False):
                            st.json(result)
                    else:
                        st.write(result)
                except Exception as e:
                    import traceback

                    err_text = str(e)
                    st.error(f"抓取失败：{err_text}")

                    # 针对常见的本地 LLM / OpenAI 兼容错误给出更友好的提示
                    if "503" in err_text or "InternalServerError" in err_text:
                        st.warning(
                            "📡 检测到 503 错误：本地 LLM 服务（如 LM Studio 或 Ollama）未就绪、模型未加载或服务器过载。\n\n"
                            "请检查：\n"
                            "1. LM Studio / Ollama Server 是否正在运行；\n"
                            "2. 是否已经在 Server 面板中加载了对应模型；\n"
                            "3. 统一应用中填写的 Base URL 与实际 Server 地址/端口是否一致。"
                        )
                    elif "Model does not exist" in err_text or "Failed to load model" in err_text:
                        st.warning(
                            "🧠 当前选择的模型在本地服务中不存在或尚未正确加载。\n\n"
                            "请在 LM Studio / Ollama 中确认：\n"
                            "1. 模型已经下载并成功 Load；\n"
                            "2. Server 页面中当前服务的模型名称，与侧边栏下拉选择的名称完全一致；\n"
                            "3. 如果刚刚修改了模型，请重新点击侧边栏的“🔍 测试连接”刷新模型列表后再重试。"
                        )

                    with st.expander("错误详情"):
                        st.code(traceback.format_exc())


if __name__ == "__main__":
    main()


