import streamlit as st  # 导入 Streamlit 构建前端界面
from scrapegraphai.graphs import SmartScraperGraph  # 导入 SmartScraperGraph 进行智能抓取
import requests  # 导入 requests 发送 HTTP 请求
import json  # 导入 json 处理 JSON 数据
import asyncio  # 导入 asyncio 运行异步任务
import os  # 导入 os 处理文件与环境
from pathlib import Path  # 导入 Path 方便文件路径操作
from playwright.async_api import async_playwright, TimeoutError  # 导入 Playwright 异步接口与超时异常

st.title("Web Scrapping AI Agent 🕵️‍♂️")  # 设置页面标题
st.caption("使用本地 LM Studio 模型进行网页抓取")  # 设置页面副标题

st.sidebar.header("LM Studio 配置")  # 侧边栏提示配置标题
lmstudio_base_url = st.sidebar.text_input("LM Studio API URL", value="http://192.168.2.129:1234/v1", help="LM Studio 默认地址为 http://192.168.2.129:1234/v1")  # 输入模型服务地址
model_name = st.sidebar.text_input("模型名称", value="qwen/qwen3-4b-2507", help="在 LM Studio 中已经加载的模型名称")  # 输入模型名称
api_key = st.sidebar.text_input("API Key (可选)", value="", type="password", help="LM Studio 默认不校验密钥，可留空")  # 输入可选密钥

if model_name and st.sidebar.button("🔍 测试连接", help="检查 LM Studio 是否可用"):  # 点击测试连接按钮
    with st.sidebar:  # 在侧边栏显示进度
        with st.spinner("正在测试连接..."):  # 显示加载动画
            try:  # 捕获网络请求异常
                test_url = f"{lmstudio_base_url.rstrip('/v1')}/v1/models"  # 拼接测试接口
                response = requests.get(test_url, timeout=5)  # 发送 GET 请求
                if response.status_code == 200:  # 判断返回码
                    models = response.json()  # 解析模型列表
                    st.success("✅ 连接成功！")  # 成功提示
                    if "data" in models:  # 如果包含模型数据
                        st.info(f"可用模型数量: {len(models['data'])}")  # 显示数量
                        model_names = [m.get("id", "N/A") for m in models.get("data", [])]  # 提取模型名
                        if model_names:  # 如果有模型
                            st.write("可用模型：")  # 标题
                            for name in model_names[:5]:  # 只展示前五个
                                st.text(f"  • {name}")  # 打印模型名
                else:  # 非 200 状态
                    st.error(f"❌ 连接失败: HTTP {response.status_code}")  # 显示错误
            except requests.exceptions.ConnectionError:  # 连接异常
                st.error("❌ 无法连接到服务器，请确认 LM Studio 已启动")  # 提示检查
            except requests.exceptions.Timeout:  # 超时异常
                st.error("❌ 连接超时，请检查服务器地址")  # 提示超时
            except Exception as e:  # 其他异常
                st.error(f"❌ 错误: {str(e)}")  # 显示异常

async def fetch_html_with_playwright(url: str, need_login: bool = False, login_url: str | None = None, use_storage: bool = True, manual_login: bool = False, headless: bool = True, page_wait_strategy: str = "domcontentloaded", page_timeout: int = 60):  # 定义异步函数获取页面 HTML
    storage_state_path = "login_state.json" if need_login and use_storage else None  # 若需登录并保存状态则指定路径
    async with async_playwright() as p:  # 启动 Playwright
        if need_login:  # 如果需要登录
            st.info("🔑 启动带登录的浏览器...")  # 提示启动
        browser = await p.chromium.launch(headless=headless)  # 启动浏览器
        context_options = {"accept_downloads": False}  # 初始化上下文参数
        if storage_state_path and os.path.exists(storage_state_path):  # 若存在登录状态文件
            try:  # 尝试读取
                raw_state = Path(storage_state_path).read_text(encoding="utf-8").strip()  # 读取文件内容
                if raw_state:  # 如果内容非空
                    json.loads(raw_state)  # 校验 JSON 合法性
                    context_options["storage_state"] = storage_state_path  # 应用登录态
                    st.info("🔑 检测到保存的登录状态，将自动使用")  # 提示使用
                else:  # 空文件
                    st.warning("⚠️ login_state.json 为空，已删除，请重新登录")  # 提示并删除
                    os.remove(storage_state_path)  # 删除空文件
            except Exception:  # 读取失败
                st.warning("⚠️ 登录状态文件不可用，已忽略")  # 忽略损坏文件
        context = await browser.new_context(**context_options)  # 创建浏览上下文
        page = await context.new_page()  # 创建新页面
        try:  # 开始导航与抓取
            if need_login:  # 若需要登录
                target_login_url = login_url if login_url else url  # 确定登录页地址
                st.info(f"🔐 正在访问登录页面: {target_login_url}")  # 显示登录页
                try:  # 尝试打开
                    await page.goto(target_login_url, wait_until=page_wait_strategy, timeout=page_timeout * 1000)  # 按策略等待
                except TimeoutError:  # 如果超时
                    st.warning("⚠️ 登录页加载超时，改用 domcontentloaded 再试")  # 提示改策略
                    await page.goto(target_login_url, wait_until="domcontentloaded", timeout=page_timeout * 1000)  # 使用 DOM 等待
                await page.wait_for_timeout(2000)  # 额外等待
                if manual_login:  # 如果选择手动登录
                    st.warning("⚠️ 手动登录模式开启，请在弹出的浏览器中完成登录。")  # 提示手动
                    if st.button("✅ 我已登录，继续"):  # 确认按钮
                        pass  # 按钮用于手动刷新
                    waited = 0  # 初始化等待时间
                    interval = 3000  # 轮询间隔
                    while waited < 300_000:  # 最长等待五分钟
                        await page.wait_for_timeout(interval)  # 等待间隔
                        waited += interval  # 累计等待
                        cur = page.url  # 获取当前 URL
                        st.info(f"📍 当前页面: {cur}")  # 显示当前页
                        if "github.com" in cur and "/login" not in cur and "session" not in cur:  # 判断是否已登录
                            st.success("✅ 检测到已登录，继续抓取页面")  # 提示成功
                            break  # 跳出循环
                    else:  # 超时未登录
                        st.error("❌ 登录超时，请重试")  # 提示失败
                        return None  # 返回空
                    if storage_state_path:  # 若需要保存状态
                        await context.storage_state(path=storage_state_path)  # 保存登录态
                        st.success("✅ 登录状态已保存到 login_state.json")  # 提示保存成功
            st.info(f"🌐 正在访问: {url}")  # 提示访问目标页
            target_wait_until = "domcontentloaded" if "github.com" in url else page_wait_strategy  # 针对 GitHub 采用 DOM 等待
            try:  # 尝试打开目标页
                await page.goto(url, wait_until=target_wait_until, timeout=page_timeout * 1000)  # 导航并等待
            except TimeoutError:  # 打开超时
                st.warning("⚠️ 页面加载超时，改用 domcontentloaded 再试")  # 提示改策略
                await page.goto(url, wait_until="domcontentloaded", timeout=page_timeout * 1000)  # 使用 DOM 等待
            await page.wait_for_timeout(2000)  # 额外等待
            html = await page.content()  # 获取页面 HTML
            st.success("✅ 已获取页面 HTML")  # 提示成功
            return html  # 返回 HTML 内容
        finally:  # 不论成功失败都执行
            await browser.close()  # 关闭浏览器

if model_name:  # 如果已经填写模型名称
    st.sidebar.subheader("高级选项")  # 显示高级选项标题
    wait_for_load = st.sidebar.selectbox("页面加载等待策略", ["domcontentloaded", "networkidle", "load"], index=1, help="networkidle: 等待网络空闲（推荐）；domcontentloaded: 仅等待 DOM；load: 等所有资源")  # 选择等待策略
    enable_js = st.sidebar.checkbox("启用 JavaScript 渲染", value=True, help="确保动态内容加载完成")  # 是否启用 JS
    wait_time = st.sidebar.slider("额外等待时间（秒）", min_value=0, max_value=10, value=3, help="页面加载后再额外等待的时间")  # 选择额外等待
    st.sidebar.subheader("登录选项")  # 登录选项标题
    need_login = st.sidebar.checkbox("需要登录", value=False)  # 是否需要登录
    login_url = st.sidebar.text_input("登录页面 URL", value="https://github.com/login", help="若登录页与目标页不同请填写") if need_login else ""  # 登录页地址
    manual_login = st.sidebar.checkbox("手动登录", value=False) if need_login else False  # 是否手动登录
    use_storage = st.sidebar.checkbox("保存登录状态", value=True) if need_login else False  # 是否保存状态
    headless = st.sidebar.checkbox("无头模式", value=not manual_login, help="若要手动登录请关闭无头") if need_login else True  # 是否无头
    loader_kwargs = {"load_state": wait_for_load, "requires_js_support": enable_js, "timeout": 60 + wait_time}  # 组装页面加载参数
    graph_config = {"llm": {"api_key": api_key or "lm-studio", "model": f"openai/{model_name}", "base_url": lmstudio_base_url, "temperature": 0}, "embeddings": {"model": "ollama/nomic-embed-text", "base_url": "http://localhost:11434"}, "verbose": True, "loader_kwargs": loader_kwargs}  # 组装抓取配置
    url = st.text_input("Enter the URL of the website you want to scrape")  # 输入目标 URL
    user_prompt = st.text_input("What you want the AI agent to scrape from the website?", value="请提取页面上所有可见的文本内容。包括页面标题、段落文字、列表项、按钮文字、链接文本等所有用户可以看到的文字信息。请忽略导航栏和页脚的版权信息，重点关注页面主体区域的可见文本内容。如果页面有主要内容，请详细列出；如果没有明显的主要内容，请列出页面上所有可见的文字元素。", help="例如提取产品名称、价格、文章内容或链接等")  # 输入抓取提示
    show_raw_html = st.checkbox("显示原始 HTML（调试用）", value=False, help="勾选后会展示抓到的 HTML 片段")  # 是否显示原始 HTML
    use_schema = st.checkbox("使用结构化输出 (JSON Schema)", value=False)  # 是否使用 JSON Schema
    json_schema = None  # 初始化 Schema
    if use_schema:  # 如果选择 Schema
        schema_text = st.text_area("JSON Schema (可选)", value='''{
  "type": "object",
  "properties": {
    "title": {"type": "string"},
    "content": {"type": "string"},
    "links": {
      "type": "array",
      "items": {"type": "string"}
    }
  }
}''', help="定义希望输出的数据结构")  # 输入 Schema
        try:  # 尝试解析
            import json  # 导入 json
            json_schema = json.loads(schema_text)  # 解析 Schema
        except:  # 解析失败
            st.warning("JSON Schema 格式不正确，将使用默认输出")  # 提示错误
    if st.button("Scrape", type="primary"):  # 点击抓取按钮
        if url and user_prompt:  # 校验必填
            with st.spinner("正在抓取网站数据..."):  # 显示加载状态
                try:  # 捕获异常
                    page_html = None  # 初始化页面 HTML
                    if need_login:  # 如果需要登录
                        page_html = asyncio.run(fetch_html_with_playwright(url=url, need_login=need_login, login_url=login_url, use_storage=use_storage, manual_login=manual_login, headless=headless, page_wait_strategy=wait_for_load, page_timeout=60 + wait_time))  # 获取登录后 HTML
                        if not page_html:  # 若未获取到
                            st.error("❌ 未能获取页面内容，请检查登录状态")  # 提示错误
                            st.stop()  # 终止执行
                    if page_html and len(page_html) > 250_000:  # 如果 HTML 过长
                        st.info("ℹ️ 页面较大，已截断部分 HTML 以适配本地模型上下文")  # 提示截断
                        page_html = page_html[:250_000]  # 截断 HTML
                    graph_source = page_html if page_html else url  # 确定抓取源
                    smart_scraper_graph = SmartScraperGraph(prompt=user_prompt, source=graph_source, config=graph_config, schema=json_schema if json_schema else None)  # 创建抓取图
                    result = smart_scraper_graph.run()  # 执行抓取
                    st.success("✅ 抓取完成！")  # 提示成功
                    st.subheader("📊 抓取结果")  # 显示结果标题
                    if show_raw_html and page_html:  # 如果需要显示登录后 HTML
                        with st.expander("🔍 登录后页面 HTML（调试）", expanded=False):  # 折叠展示
                            st.code(page_html[:5000] + "\n... (截断)", language="html")  # 展示部分 HTML
                    elif show_raw_html:  # 如果需要显示抓取器内部 HTML
                        with st.expander("🔍 原始 HTML 内容（调试）", expanded=False):  # 折叠展示
                            try:  # 尝试读取
                                if hasattr(smart_scraper_graph, "final_state") and smart_scraper_graph.final_state:  # 判断状态存在
                                    html_content = smart_scraper_graph.final_state.get("chunks", [])  # 获取 HTML 列表
                                    if html_content:  # 如果有内容
                                        st.code(html_content[0] if isinstance(html_content, list) else str(html_content), language="html")  # 展示 HTML
                                    else:  # 列表为空
                                        st.info("无法获取原始 HTML，请检查抓取过程")  # 提示无法获取
                                else:  # final_state 不存在
                                    st.info("无法获取原始 HTML，请检查抓取过程")  # 提示无法获取
                            except Exception as e:  # 捕获异常
                                st.warning(f"无法显示原始 HTML: {str(e)}")  # 提示异常
                    if isinstance(result, dict):  # 如果结果是字典
                        if "content" in result:  # 如果包含 content
                            st.markdown("### 内容：")  # 内容标题
                            st.markdown(result["content"])  # 显示内容
                            with st.expander("查看完整结果 (JSON)"):  # 展开完整 JSON
                                import json  # 导入 json
                                st.json(result)  # 显示 JSON
                        else:  # 字典但无 content
                            for key, value in result.items():  # 遍历键值
                                st.markdown(f"### {key}：")  # 显示键
                                if isinstance(value, (dict, list)):  # 如果值是嵌套
                                    st.json(value)  # 展示 JSON
                                else:  # 普通值
                                    st.write(value)  # 显示值
                    else:  # 如果结果不是字典
                        st.markdown("### 内容：")  # 标题
                        st.write(result)  # 显示结果
                        with st.expander("查看原始结果"):  # 展开原始输出
                            st.write(result)  # 显示原始
                except Exception as e:  # 捕获顶层异常
                    error_msg = str(e)  # 转成字符串
                    st.error(f"❌ 错误: {error_msg}")  # 显示错误
                    if "503" in error_msg or "InternalServerError" in error_msg:  # 处理 503
                        st.warning("""
                        **503 错误 - LM Studio 服务器不可用**
                        
                        可能的原因：
                        1. 🔴 服务器未启动
                        2. 🔴 模型未加载
                        3. 🔴 地址不正确
                        4. 🔴 服务器过载
                        
                        解决方法：
                        1. 打开 LM Studio
                        2. 确保模型已加载（在 Chat 标签可见）
                        3. 在 Server 标签点击 Start Server
                        4. 确认地址 http://localhost:1234/v1
                        5. 点击侧边栏“测试连接”验证
                        """)  # 提示 503 处理
                    elif "ConnectionError" in error_msg or "无法连接" in error_msg:  # 处理连接错误
                        st.warning("""
                        连接错误
                        
                        请检查：
                        1. LM Studio 是否运行
                        2. 服务器地址是否正确（默认：http://localhost:1234/v1）
                        3. 防火墙是否阻止连接
                        """)  # 提示连接问题
                    else:  # 其他错误
                        st.info("请确认：\n1. LM Studio 正在运行\n2. 模型已加载\n3. 服务器地址正确\n4. 模型名称正确\n5. 目标网站可访问")  # 通用排查
                    with st.expander("查看详细错误信息"):  # 展开错误详情
                        import traceback  # 导入 traceback
                        st.code(traceback.format_exc())  # 显示堆栈
        else:  # 未填写 URL 或提示
            st.warning("⚠️ 请填写网站 URL 和抓取提示")  # 提示必填
else:  # 未填写模型名称时
    st.info("👈 请在左侧边栏配置 LM Studio 设置")  # 提示用户配置
    st.markdown("""
    使用说明：
    1. 启动 LM Studio 并加载模型
    2. 确保服务器运行（Server 标签）
    3. 输入模型名称（与 LM Studio 一致）
    4. 配置 API URL（默认 http://localhost:1234/v1）
    5. 填写网站 URL 和抓取提示后点击 Scrape
    """)  # 展示操作步骤

