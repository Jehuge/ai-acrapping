# Import the required libraries
import streamlit as st
from scrapegraphai.graphs import SmartScraperGraph
import requests
import json
import asyncio
import os
from pathlib import Path
from playwright.async_api import async_playwright, TimeoutError

# Set up the Streamlit app
st.title("Web Scrapping AI Agent 🕵️‍♂️")
st.caption("This app allows you to scrape a website using LM Studio (local model)")

# LM Studio configuration
st.sidebar.header("LM Studio 配置")
lmstudio_base_url = st.sidebar.text_input(
    "LM Studio API URL", 
    value="http://192.168.2.129:1234/v1",
    help="LM Studio 默认运行在 http://192.168.2.129:1234/v1"
)
model_name = st.sidebar.text_input(
    "模型名称", 
    value="qwen/qwen3-4b-2507",
    help="在 LM Studio 中加载的模型名称（例如：llama-3.2-3b-instruct）"
)
api_key = st.sidebar.text_input(
    "API Key (可选)", 
    value="",
    type="password",
    help="LM Studio 通常不需要真实的 API key，可以填写任意值"
)

# Test LM Studio connection
if model_name and st.sidebar.button("🔍 测试连接", help="测试 LM Studio 服务器是否可用"):
    with st.sidebar:
        with st.spinner("正在测试连接..."):
            try:
                test_url = f"{lmstudio_base_url.rstrip('/v1')}/v1/models"
                response = requests.get(test_url, timeout=5)
                if response.status_code == 200:
                    models = response.json()
                    st.success("✅ 连接成功！")
                    if 'data' in models:
                        st.info(f"可用模型数量: {len(models['data'])}")
                        model_names = [m.get('id', 'N/A') for m in models.get('data', [])]
                        if model_names:
                            st.write("可用模型：")
                            for name in model_names[:5]:  # Show first 5
                                st.text(f"  • {name}")
                else:
                    st.error(f"❌ 连接失败: HTTP {response.status_code}")
            except requests.exceptions.ConnectionError:
                st.error("❌ 无法连接到服务器\n请确保 LM Studio 正在运行")
            except requests.exceptions.Timeout:
                st.error("❌ 连接超时\n请检查服务器地址")
            except Exception as e:
                st.error(f"❌ 错误: {str(e)}")

# 登录/抓取辅助：使用 Playwright 获取需要登录的页面 HTML
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
                    if st.button("✅ 我已登录，继续"):
                        pass  # 由按钮触发刷新
                    # 轮询最多 5 分钟
                    waited = 0
                    interval = 3000
                    while waited < 300_000:
                        await page.wait_for_timeout(interval)
                        waited += interval
                        cur = page.url
                        st.info(f"📍 当前页面: {cur}")
                        if "github.com" in cur and "/login" not in cur and "session" not in cur:
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
            target_wait_until = "domcontentloaded" if "github.com" in url else page_wait_strategy
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


# Set up the configuration for the SmartScraperGraph
if model_name:
    # Advanced scraping options
    st.sidebar.subheader("高级选项")
    wait_for_load = st.sidebar.selectbox(
        "页面加载等待策略",
        ["domcontentloaded", "networkidle", "load"],
        index=1,
        help="networkidle: 等待所有网络请求完成（推荐）\ndomcontentloaded: 仅等待 DOM 加载\nload: 等待所有资源加载"
    )
    enable_js = st.sidebar.checkbox(
        "启用 JavaScript 渲染",
        value=True,
        help="确保 JavaScript 动态内容被正确加载"
    )
    wait_time = st.sidebar.slider(
        "额外等待时间（秒）",
        min_value=0,
        max_value=10,
        value=3,
        help="页面加载后的额外等待时间，确保动态内容渲染完成（已包含在超时设置中）"
    )
    
    # 登录选项
    st.sidebar.subheader("登录选项")
    need_login = st.sidebar.checkbox("需要登录", value=False)
    login_url = st.sidebar.text_input(
        "登录页面 URL",
        value="https://github.com/login",
        help="如果与目标页不同，请填入登录页"
    ) if need_login else ""
    manual_login = st.sidebar.checkbox("手动登录", value=False) if need_login else False
    use_storage = st.sidebar.checkbox("保存登录状态", value=True) if need_login else False
    headless = st.sidebar.checkbox(
        "无头模式",
        value=not manual_login,
        help="手动登录建议关闭无头模式"
    ) if need_login else True
    
    # Build loader_kwargs - only include valid browser config parameters
    loader_kwargs = {
        "load_state": wait_for_load,  # Wait for network to be idle
        "requires_js_support": enable_js,  # Enable JS rendering
        "timeout": 60 + wait_time,  # Increase timeout with additional wait time
    }
    
    # Note: Scroll parameters are not directly supported in loader_kwargs
    # The networkidle load_state should handle most dynamic content loading
    
    graph_config = {
        "llm": {
            "api_key": api_key or "lm-studio",
            "model": f"openai/{model_name}",  # Use openai/provider format for LM Studio
            "base_url": lmstudio_base_url,
            "temperature": 0,
        },
        "embeddings": {
            "model": "ollama/nomic-embed-text",
            "base_url": "http://localhost:11434",  # 如果需要嵌入，可以使用 Ollama
        },
        "verbose": True,
        "loader_kwargs": loader_kwargs,
    }
    
    # Get the URL of the website to scrape
    url = st.text_input("Enter the URL of the website you want to scrape")
    # Get the user prompt
    user_prompt = st.text_input(
        "What you want the AI agent to scrape from the website?",
        value="请提取页面上所有可见的文本内容。包括页面标题、段落文字、列表项、按钮文字、链接文本等所有用户可以看到的文字信息。请忽略导航栏和页脚的版权信息，重点关注页面主体区域的可见文本内容。如果页面有主要内容，请详细列出；如果没有明显的主要内容，请列出页面上所有可见的文字元素。",
        help="例如：提取所有产品名称和价格；提取文章标题和内容；提取所有链接等"
    )
    
    # Debug option
    show_raw_html = st.checkbox("显示原始 HTML（调试用）", value=False, help="显示抓取到的原始 HTML 内容，用于调试")
    
    # Optional: JSON schema for structured output
    use_schema = st.checkbox("使用结构化输出 (JSON Schema)", value=False)
    json_schema = None
    if use_schema:
        schema_text = st.text_area(
            "JSON Schema (可选)",
            value='''{
  "type": "object",
  "properties": {
    "title": {"type": "string"},
    "content": {"type": "string"},
    "links": {
      "type": "array",
      "items": {"type": "string"}
    }
  }
}''',
            help="定义输出数据的结构"
        )
        try:
            import json
            json_schema = json.loads(schema_text)
        except:
            st.warning("JSON Schema 格式不正确，将使用默认输出")
    
    # Scrape the website
    if st.button("Scrape", type="primary"):
        if url and user_prompt:
            with st.spinner("正在抓取网站数据..."):
                try:
                    # 1) 如需登录，先用 Playwright 获取登录态页面的 HTML
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
                            st.stop()
                    
                    # 2) 构建 SmartScraperGraph；若有登录页 HTML，则作为 source 传递
                    # 为避免超过本地模型上下文长度，必要时截断页面 HTML（保守一些）
                    if page_html and len(page_html) > 250_000:
                        st.info("ℹ️ 页面较大，已自动截断部分 HTML 以适配本地模型上下文长度（约 50k 字符）")
                        page_html = page_html[:250_000]
                    graph_source = page_html if page_html else url
                    smart_scraper_graph = SmartScraperGraph(
                        prompt=user_prompt,
                        source=graph_source,
                        config=graph_config,
                        schema=json_schema if json_schema else None
                    )
                    result = smart_scraper_graph.run()
                    st.success("✅ 抓取完成！")
                    
                    # Display results in a better format
                    st.subheader("📊 抓取结果")
                    
                    # Show raw HTML if debug mode is enabled
                    if show_raw_html and page_html:
                        with st.expander("🔍 登录后页面 HTML（调试）", expanded=False):
                            st.code(page_html[:5000] + "\n... (截断)", language='html')
                    elif show_raw_html:
                        with st.expander("🔍 原始 HTML 内容（调试）", expanded=False):
                            try:
                                if hasattr(smart_scraper_graph, 'final_state') and smart_scraper_graph.final_state:
                                    html_content = smart_scraper_graph.final_state.get('chunks', [])
                                    if html_content:
                                        st.code(html_content[0] if isinstance(html_content, list) else str(html_content), language='html')
                                    else:
                                        st.info("无法获取原始 HTML，请检查抓取过程")
                                else:
                                    st.info("无法获取原始 HTML，请检查抓取过程")
                            except Exception as e:
                                st.warning(f"无法显示原始 HTML: {str(e)}")
                    
                    # If result is a dict with 'content' key, extract it
                    if isinstance(result, dict):
                        if 'content' in result:
                            st.markdown("### 内容：")
                            st.markdown(result['content'])
                            
                            # Show full result in expander
                            with st.expander("查看完整结果 (JSON)"):
                                import json
                                st.json(result)
                        else:
                            # Show all keys
                            for key, value in result.items():
                                st.markdown(f"### {key}：")
                                if isinstance(value, (dict, list)):
                                    st.json(value)
                                else:
                                    st.write(value)
                    else:
                        # If result is a string or other type
                        st.markdown("### 内容：")
                        st.write(result)
                        
                        # Show raw result
                        with st.expander("查看原始结果"):
                            st.write(result)
                            
                except Exception as e:
                    error_msg = str(e)
                    st.error(f"❌ 错误: {error_msg}")
                    
                    # Provide specific guidance based on error type
                    if "503" in error_msg or "InternalServerError" in error_msg:
                        st.warning("""
                        **503 错误 - LM Studio 服务器不可用**
                        
                        可能的原因：
                        1. 🔴 LM Studio 服务器未启动
                        2. 🔴 模型未加载或加载失败
                        3. 🔴 服务器地址不正确
                        4. 🔴 服务器过载或崩溃
                        
                        **解决方法：**
                        1. 打开 LM Studio 应用
                        2. 确保模型已加载（在 "Chat" 标签中可以看到模型）
                        3. 切换到 "Server" 标签，点击 "Start Server"
                        4. 确认服务器地址是 `http://localhost:1234/v1`
                        5. 点击侧边栏的 "🔍 测试连接" 按钮验证连接
                        """)
                    elif "ConnectionError" in error_msg or "无法连接" in error_msg:
                        st.warning("""
                        **连接错误**
                        
                        请检查：
                        1. LM Studio 是否正在运行
                        2. 服务器地址是否正确（默认：http://localhost:1234/v1）
                        3. 防火墙是否阻止了连接
                        """)
                    else:
                        st.info("💡 请确保：\n1. LM Studio 正在运行\n2. 模型已加载\n3. 服务器地址正确\n4. 模型名称正确\n5. 网站可以正常访问")
                    
                    with st.expander("查看详细错误信息"):
                        import traceback
                        st.code(traceback.format_exc())
        else:
            st.warning("⚠️ 请填写网站 URL 和抓取提示")
else:
    st.info("👈 请在左侧边栏配置 LM Studio 设置")
    st.markdown("""
    ### 使用说明：
    1. **启动 LM Studio** 并加载一个模型
    2. **确保服务器正在运行**（LM Studio 界面中的 "Server" 标签）
    3. **输入模型名称**（在 LM Studio 中显示的模型名称）
    4. **配置 API URL**（默认：http://localhost:1234/v1）
    5. 填写网站 URL 和抓取提示，然后点击 "Scrape"
    """)

