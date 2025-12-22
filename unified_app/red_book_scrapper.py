from pathlib import Path
from typing import List, Dict, Optional
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

# 这是一个带有详细中文注释的版本，便于学习 Playwright 的使用与抓取小红书（RED）的思路。
# 我保留了与原脚本相同的功能点：启动 Playwright、加载/保存会话、搜索并抓取最多 N 条结果、清理资源等。
# 建议把这个文件作为学习参考；如果你想把注释直接写回原文件，我也可以替换原文件内容。

class RedBookScrapper:
	# 构造函数
	def __init__(self, storage_path: Optional[Path] = None, headless: bool = False) -> None:
		"""
		功能概述（中文注释详解）：
		- storage_path: 持久化 Playwright context 的 storage state（json 文件），用于保存登录态（cookie/localStorage）。
		- headless: 控制浏览器是否以无头模式运行。学习和调试时建议 False（可见浏览器更方便观察页面和手动登录）。
		"""
		# Playwright 运行时对象（在 start() 中初始化）
		self.playwright = None
		# 浏览器实例（chromium/firefox/webkit）
		self.browser = None
		# 浏览器上下文（包含 cookies/localStorage），用于在不同任务间隔离状态或持久化登录态
		self.context = None
		# 页面对象，所有页面操作（goto、click、query 等）都通过它执行
		self.page = None
		# 是否无头运行（默认 False，方便手动登录）
		self.headless = headless
		# 存储会话的文件路径（如果用户未提供，则默认放在脚本目录下）
		if storage_path:
			self.storage_path = Path(storage_path)
		else:
			self.storage_path = Path(__file__).parent / "redbook_storage.json"

	# 启动 Playwright 并创建浏览器和页面
	def start(self) -> "RedBookScrapper":
		"""
		要点：
		1) 调用 sync_playwright().start() 启动 Playwright（同步 API）。
		2) 通过 playwright.chromium.launch() 创建浏览器实例（这里选择 Chromium）。
		3) new_context() 可以接受 storage_state 来加载之前保存的登录态，从而实现“免登录”。
		4) new_page() 返回 page 对象，用于后续的导航与选择器操作。
		"""
		# 启动 Playwright 运行时
		self.playwright = sync_playwright().start()
		# 启动浏览器实例，headless 控制是否无头模式
		self.browser = self.playwright.chromium.launch(headless=self.headless)
		# 如果存在之前保存的 storage state 文件，就加载，这样 context 带有登录态
		if self.storage_path.exists():
			# storage_state 可以直接传文件路径字符串或 dict（Playwright 会读取）
			self.context = self.browser.new_context(storage_state=str(self.storage_path))
		else:
			# 没有保存文件就创建全新的 context（无登录态）
			self.context = self.browser.new_context()
		# 在 context 中新建一个页面用于浏览器自动化
		self.page = self.context.new_page()
		return self

	# 确保用户处于登录状态（交互式）
	def ensure_logged_in(self) -> None:
		"""
		说明：
		- 如果 storage state 已存在，则 start() 已在创建 context 时加载，将自动呈现为已登录。
		- 如果不存在，脚本会打开浏览器（headless=False 推荐），请在浏览器中手动登录（例如扫码或输入账号密码），
		  登录完成后在终端按回车，脚本会把当前 context 的 storage_state 保存成 json 文件，供下次复用。
		为什么要保存 storage_state？
		- 因为小红书可能会有复杂的登录流程（二维码、滑块等），自动化登录容易失败且不稳定；
		- 保存了 storage_state 后，下次直接加载就能复用登录态，避免重复登录。
		"""
		# 确保 start() 已被调用，page 对象存在
		if not self.page:
			raise RuntimeError("Playwright not started. Call start() first.")

		# 导航到小红书首页，这是触发（或检查）登录态的常见入口
		self.page.goto("https://www.xiaohongshu.com", timeout=30000)

		# 如果没有保存的 session 文件，就要求用户手动登录并保存
		if not self.storage_path.exists():
			print("No saved session found. Please complete login in the opened browser window.")
			print("After logging in, return here and press Enter to save the session state.")
			# 等待用户完成手动登录（在浏览器里）
			input("Press Enter after you finish logging in...")
			# 将 context 当前的状态写入文件（包含 cookies 和 localStorage）
			self.context.storage_state(path=str(self.storage_path))
			print(f"Saved storage state to {self.storage_path}")
		else:
			# 已有 session 文件，说明我们已经在 start() 时加载了登录态
			print(f"Loaded session from {self.storage_path}")

	# 搜索并抓取最新若干篇笔记（尽量返回 title 和 link）
	def search_latest(self, keyword: str, max_results: int = 5) -> List[Dict]:
		"""
		功能：
		- 根据关键字搜索小红书，尽量返回最新的 `max_results` 条笔记（title + link）。
		实现思路（教学要点）：
		1) 先尝试直接访问常见的搜索或探索页面 URL（有时站点会有专门的 search 路由）。
		2) 如果直接访问 URL 失败，则退回到首页并尝试在页面的搜索输入框中填写关键词并回车（模拟用户行为）。
		3) 页面内容通常由 JS 渲染，需要等待一定时间再去选择 DOM。
		4) 根据多个候选选择器尝试抓取结果，若都失败则作为兜底扫描页面上的 <a> 标签寻找可能的笔记链接。
		注意：小红书前端经常改动，选择器需要以实际页面为准，建议你在浏览器 DevTools 里确认选择器后再调整代码。
		"""
		# 确保 page 已初始化
		if not self.page:
			raise RuntimeError("Playwright not started. Call start() first.")

		# 常见的搜索或探索页 URL（可能随时失效，仅作尝试）
		try_urls = [
			f"https://www.xiaohongshu.com/search_result?keyword={keyword}",
			f"https://www.xiaohongshu.com/search?keyword={keyword}",
			f"https://www.xiaohongshu.com/explore?keyword={keyword}",
		]
		navigated = False
		# 逐个尝试访问这些 URL，如果能成功打开就停止尝试
		for u in try_urls:
			try:
				self.page.goto(u, timeout=20000)
				navigated = True
				break
			except PlaywrightTimeoutError:
				# 超时或导航失败，尝试下一个 URL
				continue
		# 如果无法直接导航到结果页，则尝试在首页的搜索输入框里输入关键词并提交
		if not navigated:
			self.page.goto("https://www.xiaohongshu.com", timeout=20000)
			try:
				# 使用包含“搜索”字样的 placeholder 定位输入框（适配中文站点）
				self.page.fill('input[placeholder*="搜索"]', keyword, timeout=3000)
				self.page.press('input[placeholder*="搜索"]', "Enter")
			except Exception:
				# 如果找不到输入框或执行失败则继续尝试下面的 DOM 选择器抓取
				pass

		# 等待一段时间让前端渲染数据（生产中应使用更可靠的等待策略，如等待特定元素出现）
		self.page.wait_for_timeout(2000)

		# 下面这些是候选选择器：在不同版本的页面中可能对应不同的笔记卡片容器
		possible_post_selectors = [
			"div.note-item",           # 假设的旧选择器
			"div.note",                # 通用名字
			"div.card",                # 卡片式布局
			"div.search-result-item",  # 假设的结果项选择器
			"div._detail_",            # 一些混淆后的 class 名
		]

		posts = []
		# 优先使用明确的选择器抓取结果
		for sel in possible_post_selectors:
			try:
				elements = self.page.query_selector_all(sel)
			except Exception:
				# 如果选择器无效或执行异常（某些选择器会触发错误），则把 elements 设为空继续尝试
				elements = []
			if elements and len(elements) > 0:
				# 遍历元素并提取标题与链接（最多取 max_results 条）
				for el in elements[:max_results]:
					try:
						# inner_text() 返回元素及其子元素的可见文本，作为标题的候选
						title = el.inner_text().strip()
					except Exception:
						title = ""
					link = None
					try:
						# 优先在当前元素中查找 <a> 标签并读取 href
						a = el.query_selector("a")
						if a:
							link = a.get_attribute("href")
					except Exception:
						link = None
					posts.append({"title": title, "link": link})
				# 如果通过当前选择器已成功获取到候选项，则停止对其它选择器的尝试
				break

		# 如果上述方式都没能抓到任何结果，作为兜底我们扫描页面上的所有 <a> 标签，寻找包含典型笔记路径的链接
		if not posts:
			anchors = self.page.query_selector_all("a")
			seen = set()
			for a in anchors:
				try:
					href = a.get_attribute("href")
					text = a.inner_text().strip() or ""
				except Exception:
					continue
				if not href:
					continue
				# 这里用简单的字符串包含判断来过滤笔记类链接，实际使用时请根据页面 URL 规则调整
				if "/note/" in href or "/explore/" in href:
					if href in seen:
						continue
					seen.add(href)
					posts.append({"title": text, "link": href})
				if len(posts) >= max_results:
					break

		# 最终返回不超过 max_results 条记录
		return posts[:max_results]

	# 关闭并清理 Playwright 资源
	def close(self) -> None:
		"""
		清理顺序：
		1) 关闭 context（释放其相关的浏览器标签和存储）
		2) 关闭浏览器实例
		3) 停止 Playwright 运行时
		这些步骤都用 try/except 包裹以避免在清理阶段抛出未捕获异常导致进程崩溃。
		"""
		if self.context:
			try:
				self.context.close()
			except Exception:
				pass
		if self.browser:
			try:
				self.browser.close()
			except Exception:
				pass
		if self.playwright:
			try:
				self.playwright.stop()
			except Exception:
				pass


if __name__ == "__main__":
	# 交互式示例：方便你在本地运行并观察行为
	# 运行方式：
	#   python unified_app/red_book_scrapper_zh.py
	# 首次运行请先安装依赖并执行：python -m playwright install
	scrapper = RedBookScrapper(headless=False)
	scrapper.start()
	try:
		# 确保用户已登录（或保存登录态）
		scrapper.ensure_logged_in()
		# 让用户输入搜索关键字
		keyword = input("请输入搜索关键字: ").strip()
		# 获取最多 5 条最新结果
		results = scrapper.search_latest(keyword, max_results=5)
		print("抓取到的结果（最多 5 条）：")
		for i, item in enumerate(results, start=1):
			# 输出 title 与 link；注意 link 可能是相对路径，如果需要可以拼接站点域名
			print(f"{i}. {item.get('title')!r} -> {item.get('link')}")
	finally:
		# 无论成功或失败，都要关闭 Playwright，防止孤儿进程存在
		scrapper.close()


