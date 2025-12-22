"""GitHub 仓库抓取工具
仅保留针对 GitHub 用户/组织仓库列表的提取逻辑，去除其他表格导出功能。
"""

import streamlit as st
import asyncio
from playwright.async_api import async_playwright, TimeoutError
import pandas as pd
from urllib.parse import urlparse

# 页面配置
st.set_page_config(page_title="GitHub 仓库抓取器", layout="wide")
st.title("GitHub 仓库抓取器")
st.write("输入 GitHub 用户名或个人/组织主页 URL，抓取其仓库列表并展示结构化数据。")

def normalize_username(input_str: str) -> str:
    """从输入中提取 GitHub 用户名或组织名"""
    input_str = (input_str or "").strip()
    if not input_str:
        return ""
    if input_str.startswith("http"):
        try:
            p = urlparse(input_str)
            parts = [p for p in p.path.split("/") if p]
            if parts:
                return parts[0]
            return ""
        except Exception:
            return input_str
    # 允许直接输入包含额外路径，如 "username?tab=repositories"
    return input_str.split("/")[0].split("?")[0]

async def fetch_github_repos(username: str, headless: bool = True, timeout_sec: int = 30):
    """使用 Playwright 抓取 GitHub 用户/组织的仓库信息，返回 list[dict]"""
    target_url = f"https://github.com/{username}?tab=repositories"
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=headless)
        context = await browser.new_context()
        page = await context.new_page()
        try:
            await page.goto(target_url, wait_until="domcontentloaded", timeout=timeout_sec * 1000)
        except TimeoutError:
            # 退回到简单加载等待
            await page.goto(target_url, wait_until="load", timeout=timeout_sec * 1000)
        # 等待仓库列表出现（有些页面会懒加载）
        try:
            await page.wait_for_selector('[data-testid="repository-list"], .repo-list', timeout=8000)
        except Exception:
            # 允许继续尝试，即使选择器没出现
            pass

        # 在页面上下文中抽取结构化仓库信息
        repos = await page.evaluate(
            """(user) => {
                const containers = Array.from(document.querySelectorAll(
                    '[data-testid="repository-list"] li, [data-testid="results-list"] li, article, li'
                ));
                const data = [];
                for (const el of containers) {
                    // 尝试定位与用户名相关的链接
                    const link = el.querySelector(`a[href*="/${user}/"]`);
                    if (!link) continue;
                    const name = link.textContent.trim();
                    if (!name) continue;
                    const href = link.getAttribute('href') || '';
                    const descEl = el.querySelector('p, .repo-description, [itemprop="description"]');
                    const langEl = el.querySelector('[itemprop="programmingLanguage"], .repo-language-color + span, [data-testid="repo-card-language"]');
                    const starEl = el.querySelector('a[href$="/stargazers"], [data-testid="stargazers"]');
                    data.push({
                        "name": name,
                        "url": href.startsWith('http') ? href : `https://github.com${href}`,
                        "description": descEl ? descEl.textContent.trim() : "",
                        "language": langEl ? langEl.textContent.trim() : "",
                        "stars": starEl ? starEl.textContent.trim() : ""
                    });
                }
                // 去重并返回
                const seen = new Set();
                return data.filter(item => {
                    if (!item.name) return false;
                    if (seen.has(item.url)) return false;
                    seen.add(item.url);
                    return true;
                });
            }""",
            username,
        )

        await browser.close()
        return repos

def repos_to_dataframe(repos_list):
    """将抓取到的仓库列表转换为 pandas.DataFrame"""
    if not repos_list:
        return pd.DataFrame()
    return pd.DataFrame(repos_list)

# --- Streamlit UI ---
input_text = st.text_input("GitHub 用户名或主页 URL", placeholder="例如：octocat 或 https://github.com/octocat")
headless = st.checkbox("无头模式 (headless)", value=True, help="调试时取消勾选以查看浏览器行为")
timeout_sec = st.slider("页面加载超时（秒）", 10, 60, 30)

if st.button("抓取仓库列表"):
    username = normalize_username(input_text)
    if not username:
        st.warning("请输入有效的 GitHub 用户名或主页 URL。")
    else:
        with st.spinner(f"正在抓取 {username} 的仓库列表..."):
            try:
                repos = asyncio.run(fetch_github_repos(username, headless=headless, timeout_sec=timeout_sec))
            except Exception as e:
                st.error(f"抓取失败：{e}")
                repos = None

        if repos is None:
            st.error("未能获取仓库数据。")
        else:
            df = repos_to_dataframe(repos)
            if df.empty:
                st.info("未找到仓库或仓库列表为空。")
            else:
                st.success(f"抓取到 {len(df)} 个仓库")
                # 显示基本信息
                st.dataframe(df.astype(str), use_container_width=True)
                # 提供 CSV 下载（简单导出）
                csv_bytes = df.to_csv(index=False).encode("utf-8")
                st.download_button("下载 CSV", data=csv_bytes, file_name=f"{username}_repos.csv", mime="text/csv")
