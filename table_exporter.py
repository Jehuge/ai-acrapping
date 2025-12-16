"""
表格导出抓取工具
自动点击网页上的导出按钮，下载并解析表格数据
"""

import streamlit as st
import asyncio
from playwright.async_api import async_playwright, TimeoutError
import pandas as pd
import os
import tempfile
from pathlib import Path
import json
from bs4 import BeautifulSoup

# 设置页面配置
st.set_page_config(page_title="表格导出抓取工具", layout="wide")

st.title("自动抓取工具")
st.caption("自动点击网页上的导出按钮，下载并解析表格数据")

# 配置选项
st.sidebar.header("配置选项")

url = st.text_input("网页 URL", placeholder="https://example.com")

# 先初始化，避免未定义
button_description = ""
data_description = ""

# 抓取模式选择
scrape_mode = st.radio(
    "抓取模式",
    ["点击导出按钮", "抓取页面数据"],
    help="选择是点击导出按钮下载文件，还是直接从页面抓取数据"
)

if scrape_mode == "点击导出按钮":
    button_description = st.text_input(
        "导出按钮描述",
        placeholder="例如：导出表格、Export、下载 CSV 等",
        help="描述导出按钮的文字或特征，AI 会自动找到并点击"
    )
else:
    data_description = st.text_input(
        "数据描述",
        placeholder="例如：所有仓库、产品列表、表格数据等",
        help="描述要抓取的数据内容，工具会从页面中提取"
    )

# 登录选项
st.sidebar.subheader("🔐 登录选项")
need_login = st.sidebar.checkbox("需要登录", value=False, help="如果网页需要登录才能访问，请勾选此项")
login_url = None
if need_login:
    login_url = st.sidebar.text_input(
        "登录页面 URL",
        placeholder="https://example.com/login",
        help="登录页面的 URL（如果与目标页面不同）"
    )
    use_storage = st.sidebar.checkbox("保存登录状态", value=True, help="保存登录状态，下次使用时自动登录")
    manual_login = st.sidebar.checkbox("手动登录", value=False, help="在浏览器中手动登录（推荐）")

# 高级选项
st.sidebar.subheader("高级选项")
wait_time = st.sidebar.slider("点击后等待时间（秒）", 1, 30, 5)
download_timeout = st.sidebar.slider("下载超时时间（秒）", 10, 120, 60)
headless = st.sidebar.checkbox("无头模式", value=False if need_login and manual_login else True, help="如果手动登录，建议关闭无头模式")
page_wait_strategy = st.sidebar.selectbox(
    "页面加载等待策略",
    ["networkidle", "load", "domcontentloaded"],
    index=0,
    help="networkidle：等待网络空闲；load：等待所有资源加载；domcontentloaded：仅等待 DOM"
)
page_timeout = st.sidebar.slider("页面加载超时（秒）", 30, 180, 60)

# 文件类型选择
file_types = st.sidebar.multiselect(
    "支持的文件类型",
    ["CSV", "Excel (.xlsx)", "JSON", "TSV"],
    default=["CSV", "Excel (.xlsx)"]
)

async def find_and_click_button(page, description):
    """使用 AI 或文本匹配找到并点击按钮"""
    try:
        # 方法1: 通过文本内容查找
        button_texts = [
            description,
            "导出",
            "Export",
            "下载",
            "Download",
            "导出表格",
            "Export Table",
            "导出 CSV",
            "Export CSV",
            "导出 Excel",
            "Export Excel"
        ]
        
        for text in button_texts:
            try:
                # 尝试通过文本查找按钮
                button = await page.query_selector(f'button:has-text("{text}")')
                if button:
                    await button.click()
                    st.success(f"✅ 找到并点击了按钮: {text}")
                    return True
                
                # 尝试通过链接查找
                link = await page.query_selector(f'a:has-text("{text}")')
                if link:
                    await link.click()
                    st.success(f"✅ 找到并点击了链接: {text}")
                    return True
            except:
                continue
        
        # 方法2: 通过属性查找（data-*, class, id）
        selectors = [
            f'button[data-action*="export" i]',
            f'button[class*="export" i]',
            f'button[id*="export" i]',
            f'a[data-action*="export" i]',
            f'a[class*="export" i]',
            f'a[id*="export" i]',
            f'*[aria-label*="export" i]',
            f'*[title*="export" i]',
        ]
        
        for selector in selectors:
            try:
                element = await page.query_selector(selector)
                if element:
                    await element.click()
                    st.success(f"✅ 通过选择器找到并点击了按钮: {selector}")
                    return True
            except:
                continue
        
        st.warning("⚠️ 未找到导出按钮，请检查按钮描述是否正确")
        return False
        
    except Exception as e:
        st.error(f"❌ 查找按钮时出错: {str(e)}")
        return False

async def download_file(page, download_dir, timeout=60):
    """等待文件下载"""
    try:
        # 等待下载事件
        async with page.expect_download(timeout=timeout * 1000) as download_info:
            pass
        
        download = await download_info.value
        file_path = os.path.join(download_dir, download.suggested_filename)
        await download.save_as(file_path)
        
        st.success(f"✅ 文件下载成功: {download.suggested_filename}")
        return file_path
        
    except Exception as e:
        st.error(f"❌ 下载文件时出错: {str(e)}")
        return None

def parse_table_file(file_path):
    """解析表格文件"""
    file_ext = Path(file_path).suffix.lower()
    
    try:
        if file_ext == '.csv':
            df = pd.read_csv(file_path, encoding='utf-8')
            return df, "CSV"
        elif file_ext in ['.xlsx', '.xls']:
            df = pd.read_excel(file_path)
            return df, "Excel"
        elif file_ext == '.json':
            df = pd.read_json(file_path)
            return df, "JSON"
        elif file_ext == '.tsv':
            df = pd.read_csv(file_path, sep='\t', encoding='utf-8')
            return df, "TSV"
        else:
            st.error(f"❌ 不支持的文件类型: {file_ext}")
            return None, None
    except Exception as e:
        st.error(f"❌ 解析文件时出错: {str(e)}")
        return None, None

async def scrape_page_data(page, description, page_wait_strategy="networkidle", page_timeout=60, extra_wait=2):
    """从页面中抓取表格/列表数据"""
    try:
        st.info("📊 正在从页面提取数据...")
        
        # 等待页面完全加载，使用用户选择的策略
        try:
            await page.wait_for_load_state(page_wait_strategy, timeout=page_timeout * 1000)
        except TimeoutError:
            st.warning("⚠️ 页面加载等待超时，改用 domcontentloaded 再试")
            await page.wait_for_load_state("domcontentloaded", timeout=page_timeout * 1000)
        await page.wait_for_timeout(extra_wait * 1000)
        
        # 尝试查找表格
        tables = await page.query_selector_all('table')
        if tables:
            st.info(f"✅ 找到 {len(tables)} 个表格")
            # 返回第一个表格的 HTML
            table_html = await tables[0].inner_html()
            return table_html, "table"

        # GitHub 仓库列表优先处理，避免被通用列表匹配抢走
        if "github.com" in page.url and "repositories" in page.url:
            # 从 URL 提取用户名（用于过滤链接）
            try:
                from urllib.parse import urlparse
                path_parts = urlparse(page.url).path.strip("/").split("/")
                gh_user = path_parts[0] if path_parts else ""
            except Exception:
                gh_user = ""

            # 优先用 JS 直接提取结构化数据，避免 HTML 结构变化
            if gh_user:
                try:
                    # 等待仓库列表元素出现，最多 15 秒
                    await page.wait_for_selector(
                        '[data-testid="repository-list"] li, [data-testid="results-list"] li, article',
                        timeout=15000
                    )
                except Exception:
                    pass

                repos = await page.evaluate(
                    """(user) => {
                        const cards = Array.from(document.querySelectorAll(
                            '[data-testid="repository-list"] li, [data-testid="results-list"] li, article, li'
                        ));
                        const data = [];
                        for (const el of cards) {
                            const link = el.querySelector(`a[href*="/${user}/"]`);
                            if (!link) continue;
                            const name = link.textContent.trim();
                            if (!name) continue;
                            const href = link.getAttribute('href') || '';
                            const descEl = el.querySelector('p, .repo-description, [itemprop="description"]');
                            const langEl = el.querySelector('[itemprop="programmingLanguage"], .repo-language-color + span, [data-testid="repo-card-language"]');
                            const starEl = el.querySelector('a[href$="/stargazers"], [data-testid="stargazers"]');
                            data.push({
                                "仓库名称": name,
                                "链接": href.startsWith('http') ? href : `https://github.com${href}`,
                                "描述": descEl ? descEl.textContent.trim() : "",
                                "语言": langEl ? langEl.textContent.trim() : "",
                                "星标数": starEl ? starEl.textContent.trim() : ""
                            });
                        }
                        return data.filter(item => item["仓库名称"]);
                    }""",
                    gh_user,
                )
                if repos:
                    st.info(f"✅ 直接提取到 {len(repos)} 个仓库")
                    return repos, "github_repos_json"

            # 兜底：HTML 提取
            repo_list = await page.query_selector('[data-testid="repository-list"]')
            if not repo_list:
                repo_list = await page.query_selector('.repo-list')
            if not repo_list:
                repo_list = await page.query_selector('[itemtype="http://schema.org/CodeRepository"]')
            if repo_list:
                st.info("✅ 找到 GitHub 仓库列表")
                repo_html = await repo_list.inner_html()
                return repo_html, "github_repos"

        # 尝试查找列表
        lists = await page.query_selector_all('ul, ol')
        if lists:
            st.info(f"✅ 找到 {len(lists)} 个列表")
            # 查找包含描述关键词的列表
            for list_elem in lists:
                list_text = await list_elem.inner_text()
                if description.lower() in list_text.lower() or len(list_text) > 50:
                    list_html = await list_elem.inner_html()
                    return list_html, "list"
        
        # 如果都没找到，尝试获取整个页面内容
        st.warning("⚠️ 未找到特定数据容器，尝试提取整个页面内容")
        body = await page.query_selector('body')
        if body:
            body_html = await body.inner_html()
            return body_html, "full_page"
        
        return None, None
        
    except Exception as e:
        st.error(f"❌ 抓取页面数据时出错: {str(e)}")
        return None, None

def parse_html_to_dataframe(html_content, data_type, url=""):
    """将 HTML 内容解析为 DataFrame"""
    try:
        # 直接支持结构化列表（例如 GitHub JS 抽取）
        if data_type == "github_repos_json" and isinstance(html_content, list):
            if html_content:
                return pd.DataFrame(html_content)
            return None

        soup = BeautifulSoup(html_content, 'html.parser')
        
        if data_type == "table":
            # 解析表格
            table = soup.find('table')
            if table:
                df = pd.read_html(str(table))[0]
                return df
        
        elif data_type == "github_repos":
            # 解析 GitHub 仓库列表
            repos = []
            repo_items = soup.find_all(['article', 'li'], class_=lambda x: x and ('repo' in x.lower() or 'repository' in x.lower()))
            
            if not repo_items:
                # 尝试其他选择器
                repo_items = soup.find_all('div', class_=lambda x: x and 'repo' in x.lower())
            
            for item in repo_items:
                repo_data = {}
                
                # 提取仓库名称
                name_elem = item.find('a', href=lambda x: x and '/Jehuge/' in x)
                if name_elem:
                    repo_data['仓库名称'] = name_elem.get_text(strip=True)
                    repo_data['链接'] = 'https://github.com' + name_elem.get('href', '')
                
                # 提取描述
                desc_elem = item.find('p', class_=lambda x: x and 'description' in x.lower())
                if not desc_elem:
                    desc_elem = item.find('p')
                if desc_elem:
                    repo_data['描述'] = desc_elem.get_text(strip=True)
                
                # 提取语言
                lang_elem = item.find('span', itemprop='programmingLanguage')
                if lang_elem:
                    repo_data['语言'] = lang_elem.get_text(strip=True)
                
                # 提取星标数
                star_elem = item.find('a', href=lambda x: x and 'stargazers' in x)
                if star_elem:
                    repo_data['星标数'] = star_elem.get_text(strip=True)
                
                if repo_data:
                    repos.append(repo_data)
            
            if repos:
                df = pd.DataFrame(repos)
                return df
        
        elif data_type == "list":
            # 解析列表
            items = soup.find_all('li')
            data = []
            for item in items:
                text = item.get_text(strip=True)
                if text:
                    data.append({'内容': text})
            if data:
                df = pd.DataFrame(data)
                return df
        
        # 如果以上都不匹配，尝试提取所有链接和文本
        st.info("📝 尝试提取页面中的链接和文本...")
        links = soup.find_all('a', href=True)
        data = []
        for link in links[:100]:  # 限制数量
            text = link.get_text(strip=True)
            href = link.get('href', '')
            if text and len(text) < 200:  # 过滤太长的文本
                data.append({
                    '文本': text,
                    '链接': href if href.startswith('http') else url + href
                })
        
        if data:
            df = pd.DataFrame(data)
            return df
        
        return None
        
    except Exception as e:
        st.error(f"❌ 解析 HTML 时出错: {str(e)}")
        import traceback
        st.code(traceback.format_exc())
        return None

async def scrape_table(url, description, wait_time, download_timeout, headless, 
                       need_login=False, login_url=None, use_storage=False, manual_login=False,
                       scrape_mode="点击导出按钮",
                       page_wait_strategy="networkidle",
                       page_timeout=60):
    """主抓取函数"""
    with tempfile.TemporaryDirectory() as download_dir:
        async with async_playwright() as p:
            # 检查是否有保存的登录状态
            storage_state_path = None
            if need_login and use_storage:
                storage_state_path = "login_state.json"
                if os.path.exists(storage_state_path):
                    try:
                        # 先验证 JSON 是否有效，避免空文件/损坏文件导致 JSONDecodeError
                        raw_state = Path(storage_state_path).read_text(encoding="utf-8").strip()
                        if raw_state:
                            json.loads(raw_state)
                            st.info("🔑 检测到保存的登录状态，将自动使用")
                        else:
                            st.warning("⚠️ 检测到空的 login_state.json，已忽略并删除，请重新登录")
                            try:
                                os.remove(storage_state_path)
                            except OSError:
                                pass
                            storage_state_path = None
                    except json.JSONDecodeError:
                        st.warning("⚠️ 保存的登录状态文件已损坏，已忽略并删除，请重新登录")
                        try:
                            os.remove(storage_state_path)
                        except OSError:
                            pass
                        storage_state_path = None
                    except Exception as e:
                        st.warning(f"⚠️ 读取登录状态时出错，已忽略: {e}")
                        storage_state_path = None
            
            # 启动浏览器
            browser = await p.chromium.launch(headless=headless)
            
            # 创建上下文，如果有保存的状态则加载
            context_options = {
                "accept_downloads": True,
            }
            if storage_state_path and os.path.exists(storage_state_path):
                context_options["storage_state"] = storage_state_path
            
            context = await browser.new_context(**context_options)
            page = await context.new_page()
            
            try:
                # 如果需要登录
                if need_login:
                    login_target_url = login_url if login_url else url
                    st.info(f"🔐 正在访问登录页面: {login_target_url}")
                    login_wait_until = "domcontentloaded" if "github.com" in login_target_url else page_wait_strategy
                    try:
                        # 使用与页面抓取相同的等待策略与超时，避免 networkidle 卡死（如 GitHub 长轮询）
                        await page.goto(
                            login_target_url,
                            wait_until=login_wait_until,
                            timeout=page_timeout * 1000
                        )
                    except TimeoutError:
                        st.warning("⚠️ 登录页加载等待超时，尝试使用 domcontentloaded 再试")
                        await page.goto(
                            login_target_url,
                            wait_until="domcontentloaded",
                            timeout=page_timeout * 1000
                        )
                    await page.wait_for_timeout(2000)
                    
                    if manual_login:
                        # 手动登录模式
                        st.warning("""
                        ⚠️ **手动登录模式已启用**
                        
                        请在浏览器窗口中：
                        1. 输入用户名和密码
                        2. 完成登录流程（包括验证码、两步验证等）
                        3. 确保已成功登录到目标页面
                        4. 登录成功后，工具会自动检测并继续
                        """)
                        
                        # 等待用户手动登录
                        st.info("⏳ 等待您完成登录...")
                        
                        # 初始化登录确认状态
                        if 'login_confirmed' not in st.session_state:
                            st.session_state.login_confirmed = False
                        
                        # 创建状态显示占位符
                        status_placeholder = st.empty()
                        # 创建“我已登录，继续”按钮（允许手动跳过检测）
                        if st.button("✅ 我已登录，继续", type="secondary"):
                            st.session_state.login_confirmed = True
                        
                        # 轮询检查登录状态（每3秒检查一次）
                        max_wait_time = 300  # 最多等待5分钟
                        wait_interval = 3000  # 每3秒检查一次
                        waited_time = 0
                        login_confirmed = False
                        
                        while waited_time < max_wait_time * 1000 and not login_confirmed:
                            await page.wait_for_timeout(wait_interval)
                            waited_time += wait_interval
                            
                            # 检查当前 URL
                            current_url = page.url
                            # GitHub 登录成功后常见的已登录元素
                            github_authed = False
                            if "github.com" in current_url:
                                try:
                                    # 用户头像菜单或 profile 链接
                                    if await page.query_selector('[data-testid="user-profile-link"], summary[aria-label*="profile" i], summary[aria-label*="View profile" i]'):
                                        github_authed = True
                                except Exception:
                                    pass
                            
                            
                            # 更新状态显示（不包含按钮，避免重复创建）
                            with status_placeholder.container():
                                st.info(f"📍 当前页面: {current_url}")
                                st.info(f"⏱️ 已等待: {waited_time // 1000} 秒")
                                
                                # 对于 GitHub，自动检测是否已登录
                                if "github.com" in current_url:
                                    # GitHub 登录成功后会跳转到主页或用户页面，或检测到头像
                                    if github_authed or ("/login" not in current_url and "session" not in current_url):
                                        st.success("✅ 检测到已登录 GitHub，自动继续...")
                                        login_confirmed = True
                                        break
                                else:
                                    # 其他网站，检查是否还在登录页面
                                    if "/login" not in current_url.lower() and "signin" not in current_url.lower():
                                        st.success("✅ 检测到已离开登录页面，自动继续...")
                                        login_confirmed = True
                                        break
                        
                        # 清除状态显示
                        status_placeholder.empty()
                        
                        if not login_confirmed:
                            st.error("❌ 登录超时，请重试")
                            return None
                        
                        # 保存登录状态
                        if use_storage:
                            await context.storage_state(path=storage_state_path)
                            st.success("✅ 登录状态已保存到 login_state.json")
                    else:
                        # 自动登录（需要用户提供登录信息）
                        st.info("💡 提示：如果自动登录失败，请使用手动登录模式")
                        # 这里可以添加自动填写表单的逻辑
                        # 但为了安全，建议使用手动登录
                
                # 访问目标网页
                st.info(f"🌐 正在访问: {url}")
                target_wait_until = "domcontentloaded" if "github.com" in url else page_wait_strategy
                try:
                    await page.goto(url, wait_until=target_wait_until, timeout=page_timeout * 1000)
                except TimeoutError:
                    st.warning("⚠️ 页面加载超时，尝试使用 domcontentloaded 再试一次")
                    await page.goto(url, wait_until="domcontentloaded", timeout=page_timeout * 1000)
                await page.wait_for_timeout(wait_time * 1000)  # 等待页面完全加载/动态渲染
                
                # 根据模式选择不同的处理方式
                if scrape_mode == "点击导出按钮":
                    # 查找并点击按钮
                    st.info("🔍 正在查找导出按钮...")
                    clicked = await find_and_click_button(page, button_description)
                    
                    if not clicked:
                        return None
                    
                    # 等待文件下载
                    st.info(f"⏳ 等待文件下载（最多 {download_timeout} 秒）...")
                    await page.wait_for_timeout(wait_time * 1000)  # 等待按钮响应
                    
                    file_path = await download_file(page, download_dir, download_timeout)
                    
                    if file_path:
                        # 解析文件
                        st.info("📊 正在解析表格数据...")
                        df, file_type = parse_table_file(file_path)
                        
                        if df is not None:
                            return df, file_type, file_path
                    
                    return None
                else:
                    # 抓取页面数据
                    html_content, data_type = await scrape_page_data(
                        page,
                        data_description,
                        page_wait_strategy=page_wait_strategy,
                        page_timeout=page_timeout,
                        extra_wait=wait_time
                    )
                    
                    if html_content:
                        st.info("📊 正在解析页面数据...")
                        df = parse_html_to_dataframe(html_content, data_type)
                        
                        if df is not None and not df.empty:
                            return df, "page_data", url
                        else:
                            st.error("❌ 未能从页面中提取到有效数据")
                            return None
                    else:
                        st.error("❌ 未能获取页面内容")
                        return None
                
            except Exception as e:
                st.error(f"❌ 抓取过程中出错: {str(e)}")
                return None
            finally:
                await browser.close()

# 主界面
if st.button("🚀 开始抓取", type="primary"):
    if not url:
        st.warning("⚠️ 请输入网页 URL")
    elif scrape_mode == "点击导出按钮" and not button_description:
        st.warning("⚠️ 请输入导出按钮描述")
    elif scrape_mode == "抓取页面数据" and not data_description:
        st.warning("⚠️ 请输入数据描述")
    elif need_login and not login_url and manual_login:
        st.warning("⚠️ 如果使用手动登录，请输入登录页面 URL")
    else:
        with st.spinner("正在抓取表格数据..."):
            result = asyncio.run(
                scrape_table(
                    url, 
                    button_description if scrape_mode == "点击导出按钮" else data_description, 
                    wait_time, 
                    download_timeout, 
                    headless,
                    need_login,
                    login_url,
                    use_storage if need_login else False,
                    manual_login if need_login else False,
                    scrape_mode,
                    page_wait_strategy,
                    page_timeout
                )
            )
            
            if result and result[0] is not None:
                df, file_type, file_path = result
                
                st.success(f"✅ 成功抓取 {file_type} 表格数据！")
                
                # 显示表格信息
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("行数", len(df))
                with col2:
                    st.metric("列数", len(df.columns))
                with col3:
                    st.metric("文件类型", file_type)
                
                # 显示表格
                st.subheader("📋 表格数据预览")
                # 规避 Arrow 类型推断报错，展示前转为字符串副本
                df_display = df.copy()
                for col in df_display.columns:
                    df_display[col] = df_display[col].astype(str)
                st.dataframe(df_display, width="stretch")
                
                # 下载选项
                st.subheader("💾 下载数据")
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    csv = df.to_csv(index=False).encode('utf-8')
                    st.download_button(
                        label="📥 下载 CSV",
                        data=csv,
                        file_name="exported_table.csv",
                        mime="text/csv"
                    )
                
                with col2:
                    import io
                    try:
                        excel_buffer = io.BytesIO()
                        with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
                            df.to_excel(writer, index=False)
                        excel_data = excel_buffer.getvalue()
                        st.download_button(
                            label="📥 下载 Excel",
                            data=excel_data,
                            file_name="exported_table.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                        )
                    except ModuleNotFoundError:
                        st.warning("⚠️ 未安装 openpyxl，无法生成 Excel。请运行：pip install openpyxl")
                
                with col3:
                    json_data = df.to_json(orient='records', force_ascii=False, indent=2)
                    st.download_button(
                        label="📥 下载 JSON",
                        data=json_data.encode('utf-8'),
                        file_name="exported_table.json",
                        mime="application/json"
                    )
                
                # 显示统计信息
                with st.expander("📊 数据统计"):
                    st.write(df.describe())
                
                # 显示列信息
                with st.expander("📝 列信息"):
                    st.write(df.dtypes)
            else:
                st.error("❌ 未能成功抓取表格数据")

# 使用说明
with st.expander("📖 使用说明"):
    st.markdown("""
    ### 功能说明
    
    这个工具可以自动：
    1. **访问网页**：使用浏览器打开指定网页
    2. **查找按钮**：根据描述自动找到导出按钮
    3. **点击按钮**：自动点击导出按钮
    4. **下载文件**：等待并下载导出的文件
    5. **解析表格**：自动解析 CSV、Excel、JSON 等格式
    6. **显示数据**：在界面中展示表格数据
    
    ### 使用步骤
    
    1. **输入网页 URL**：要抓取的网页地址
    2. **输入按钮描述**：导出按钮的文字或特征
       - 例如："导出表格"、"Export"、"下载 CSV" 等
    3. **配置选项**（可选）：
       - 点击后等待时间：按钮点击后等待的时间
       - 下载超时时间：等待文件下载的最大时间
       - 无头模式：是否显示浏览器窗口
    4. **点击"开始抓取"**：开始自动抓取过程
    
    ### 支持的格式
    
    - ✅ CSV (.csv)
    - ✅ Excel (.xlsx, .xls)
    - ✅ JSON (.json)
    - ✅ TSV (.tsv)
    
    ### 登录功能
    
    **支持需要登录的网页：**
    
    1. **手动登录（推荐）**：
       - 勾选"需要登录"
       - 勾选"手动登录"
       - 关闭"无头模式"（可以看到浏览器窗口）
       - 在浏览器中手动输入用户名和密码
       - 登录成功后点击"我已登录，继续"
       - 勾选"保存登录状态"可以保存登录信息，下次自动使用
    
    2. **自动登录**：
       - 勾选"需要登录"
       - 输入登录页面 URL（如果与目标页面不同）
       - 工具会尝试自动登录（需要网站支持）
    
    **登录状态保存：**
    - 登录状态会保存在 `login_state.json` 文件中
    - 下次使用时如果检测到保存的状态，会自动使用
    - 如果登录失效，删除 `login_state.json` 文件重新登录
    
    ### 注意事项
    
    - 确保网页可以正常访问
    - 导出按钮需要可见且可点击
    - **需要登录的网站**：使用手动登录模式更可靠
    - 如果按钮是动态加载的，可能需要增加等待时间
    - 登录状态文件包含敏感信息，请妥善保管
    """)

