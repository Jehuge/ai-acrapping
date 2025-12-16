# 🤖 AI 网页抓取原理详解

## 📋 目录
1. [整体架构](#整体架构)
2. [工作流程](#工作流程)
3. [核心节点详解](#核心节点详解)
4. [与传统爬虫的区别](#与传统爬虫的区别)
5. [优势与局限](#优势与局限)

---

## 🏗️ 整体架构

**ScrapeGraphAI** 使用**图（Graph）架构**，将网页抓取过程分解为多个**节点（Nodes）**，每个节点负责特定的任务：

```
用户输入 (URL + 提示词)
    ↓
┌─────────────────────────────────────┐
│      SmartScraperGraph              │
│  ┌──────────────────────────────┐  │
│  │  1. FetchNode (获取网页)      │  │
│  │  2. ParseNode (解析内容)     │  │
│  │  3. GenerateAnswerNode (AI提取)│ │
│  └──────────────────────────────┘  │
└─────────────────────────────────────┘
    ↓
结构化数据输出
```

---

## 🔄 工作流程

### 标准流程（3个节点）

```
URL + 提示词
    ↓
[1] FetchNode (获取网页)
    ├─ 使用 Playwright/Chromium 浏览器
    ├─ 加载 JavaScript（如果需要）
    ├─ 等待页面完全加载（networkidle）
    └─ 输出：原始 HTML 文档
    ↓
[2] ParseNode (解析内容)
    ├─ 清理 HTML（移除脚本、样式等）
    ├─ 提取文本内容
    ├─ 分块处理（chunking）
    └─ 输出：清理后的文本块
    ↓
[3] GenerateAnswerNode (AI 提取)
    ├─ 将用户提示词 + 网页内容发送给 LLM
    ├─ LLM 理解并提取所需信息
    ├─ 根据 schema 格式化输出
    └─ 输出：结构化数据
```

### 详细步骤说明

#### 步骤 1: FetchNode - 获取网页内容

**技术实现：**
- 使用 **Playwright** 或 **Chromium** 无头浏览器
- 支持 JavaScript 渲染（`requires_js_support=True`）
- 等待策略：
  - `domcontentloaded`: 仅等待 DOM 加载
  - `networkidle`: 等待所有网络请求完成（推荐）
  - `load`: 等待所有资源加载

**代码位置：**
```python
# scrapegraphai/nodes/fetch_node.py
# 使用 ChromiumLoader 加载网页
loader = ChromiumLoader(
    urls=[url],
    load_state="networkidle",
    requires_js_support=True
)
document = loader.load()  # 返回 HTML 文档
```

**输出：** 完整的 HTML 文档（包含所有标签、脚本等）

---

#### 步骤 2: ParseNode - 解析和清理内容

**功能：**
1. **HTML 清理**：
   - 移除 `<script>`, `<style>`, `<meta>` 等标签
   - 保留文本内容和结构标签

2. **文本提取**：
   - 提取所有可见文本
   - 保留基本的 HTML 结构（标题、段落、列表等）

3. **分块处理（Chunking）**：
   - 将长文本分割成多个块
   - 每个块大小 = `model_token`（模型的最大输入长度）
   - 确保内容可以完整传递给 LLM

**代码位置：**
```python
# scrapegraphai/nodes/parse_node.py
# 清理 HTML，提取文本，分块
parsed_doc = parse_html(html_content)
chunks = chunk_text(parsed_doc, chunk_size=model_token)
```

**输出：** 清理后的文本块列表

---

#### 步骤 3: GenerateAnswerNode - AI 智能提取

**核心原理：**

这是与传统爬虫**最关键的区别**！

**传统爬虫：**
```python
# 需要写固定的选择器
title = soup.select_one('h1.title').text
price = soup.select_one('.price').text
# 如果网站结构改变，代码就失效了
```

**AI 抓取：**
```python
# 只需要自然语言描述
prompt = "提取产品名称和价格"
# AI 自动理解页面结构，找到相关信息
```

**工作流程：**

1. **构建提示词**：
   ```
   用户提示词: "提取首页的文字"
   
   实际发送给 LLM 的提示词:
   """
   请根据以下网页内容回答问题：
   
   用户问题：提取首页的文字
   
   网页内容：
   [这里是 ParseNode 提取的文本内容]
   
   请提取相关信息并以 JSON 格式返回。
   """
   ```

2. **LLM 处理**：
   - LLM 阅读整个网页内容
   - 理解用户的需求
   - 识别相关内容（即使结构复杂）
   - 提取并格式化数据

3. **输出格式化**：
   - 如果提供了 JSON Schema，按 schema 格式化
   - 否则返回自然语言描述

**代码位置：**
```python
# scrapegraphai/nodes/generate_answer_node.py
# 构建提示词
prompt = f"{user_prompt}\n\n网页内容：\n{parsed_content}"

# 调用 LLM
response = llm_model.invoke(prompt)

# 解析响应
result = parse_response(response)
```

**输出：** 结构化的 JSON 数据或文本

---

## 🧩 核心节点详解

### 1. FetchNode（获取节点）

**职责：** 从 URL 获取网页内容

**技术栈：**
- **Playwright**: 无头浏览器，支持现代网页
- **Chromium**: Chrome 内核，支持 JavaScript
- **代理支持**: 可配置代理服务器

**配置选项：**
```python
loader_kwargs = {
    "load_state": "networkidle",      # 等待策略
    "requires_js_support": True,        # 启用 JS
    "timeout": 60,                     # 超时时间
    "headless": True                   # 无头模式
}
```

---

### 2. ParseNode（解析节点）

**职责：** 清理 HTML，提取文本，分块处理

**处理流程：**
```
原始 HTML
  ↓
移除脚本、样式、注释
  ↓
提取文本内容
  ↓
保留结构标签（h1, p, div 等）
  ↓
分块（chunking）
  ↓
清理后的文本块
```

**为什么需要分块？**
- LLM 有最大输入长度限制（如 8192 tokens）
- 长网页需要分割成多个块
- 每个块独立处理，最后合并结果

---

### 3. GenerateAnswerNode（生成答案节点）

**职责：** 使用 LLM 理解和提取信息

**关键优势：**

1. **语义理解**：
   - 理解"首页的文字"的含义
   - 自动识别主要内容区域
   - 忽略导航栏、页脚等

2. **结构适应**：
   - 不需要固定的 CSS 选择器
   - 适应不同的 HTML 结构
   - 处理动态内容

3. **智能提取**：
   - 理解上下文关系
   - 提取相关但分散的信息
   - 格式化输出

**示例：**

**输入：**
```html
<div class="product">
  <h2>iPhone 15</h2>
  <span class="price">¥5999</span>
</div>
```

**传统爬虫：**
```python
# 需要知道具体的类名
name = soup.select_one('.product h2').text
price = soup.select_one('.product .price').text
```

**AI 抓取：**
```python
# 只需要描述需求
prompt = "提取产品名称和价格"
# AI 自动找到相关信息
```

---

## 🆚 与传统爬虫的区别

| 特性 | 传统爬虫 | AI 抓取 |
|------|---------|---------|
| **选择器** | 需要写 CSS/XPath 选择器 | 自然语言描述 |
| **结构变化** | 网站改版后失效 | 自动适应 |
| **理解能力** | 只能提取固定位置 | 语义理解，智能提取 |
| **动态内容** | 需要特殊处理 | 自动处理 JS 渲染 |
| **成本** | 低（代码运行） | 高（需要 LLM API） |
| **速度** | 快 | 较慢（需要 LLM 推理） |
| **准确性** | 高（精确选择） | 中等（依赖 LLM 理解） |

---

## ✅ 优势与局限

### 优势

1. **灵活性**：
   - 不需要写复杂的 CSS 选择器
   - 适应网站结构变化
   - 处理复杂的 HTML 结构

2. **智能理解**：
   - 理解语义，不只是匹配文本
   - 提取相关但分散的信息
   - 处理非结构化内容

3. **自然语言交互**：
   - 用自然语言描述需求
   - 不需要编程知识
   - 快速适应新需求

### 局限

1. **成本**：
   - 需要 LLM API（OpenAI、本地模型等）
   - 每次抓取都需要调用 LLM
   - 成本比传统爬虫高

2. **速度**：
   - LLM 推理需要时间
   - 比传统爬虫慢
   - 不适合大规模批量抓取

3. **准确性**：
   - 依赖 LLM 的理解能力
   - 可能提取错误信息
   - 需要验证结果

4. **Token 限制**：
   - LLM 有最大输入长度限制
   - 超长网页需要分块处理
   - 可能丢失部分信息

---

## 🎯 适用场景

### ✅ 适合使用 AI 抓取：

1. **快速原型开发**：快速验证抓取需求
2. **结构复杂的网站**：难以写选择器的网站
3. **频繁变化的网站**：结构经常变化的网站
4. **非结构化内容**：需要理解语义的内容
5. **小规模抓取**：不需要大规模批量处理

### ❌ 不适合使用 AI 抓取：

1. **大规模批量抓取**：成本太高
2. **需要高精度**：传统爬虫更可靠
3. **实时性要求高**：LLM 推理较慢
4. **简单结构化数据**：传统爬虫更高效

---

## 🔍 实际工作示例

### 示例：抓取产品信息

**输入：**
- URL: `https://example.com/products`
- 提示词: "提取所有产品名称和价格"

**流程：**

1. **FetchNode**：
   ```python
   # 使用 Playwright 加载网页
   browser = await chromium.launch()
   page = await browser.new_page()
   await page.goto(url, wait_until="networkidle")
   html = await page.content()
   ```

2. **ParseNode**：
   ```python
   # 清理 HTML
   soup = BeautifulSoup(html, 'html.parser')
   # 移除脚本和样式
   for script in soup(["script", "style"]):
       script.decompose()
   # 提取文本
   text = soup.get_text()
   # 分块
   chunks = chunk_text(text, size=8192)
   ```

3. **GenerateAnswerNode**：
   ```python
   # 构建提示词
   prompt = f"""
   请从以下网页内容中提取所有产品名称和价格：
   
   {chunks[0]}
   
   请以 JSON 格式返回：
   {{
     "products": [
       {{"name": "...", "price": "..."}}
     ]
   }}
   """
   
   # 调用 LLM
   response = llm.invoke(prompt)
   # 返回: {"products": [{"name": "iPhone 15", "price": "¥5999"}]}
   ```

---

## 📚 总结

AI 网页抓取的核心是**将网页内容理解任务交给 LLM**，而不是依赖固定的选择器规则。这使得抓取过程更加灵活和智能，但同时也带来了成本和速度的权衡。

**关键点：**
- ✅ 使用浏览器获取完整网页（包括 JS 渲染）
- ✅ 清理和解析 HTML 内容
- ✅ 使用 LLM 理解和提取信息
- ✅ 返回结构化数据

**选择建议：**
- 小规模、快速原型 → AI 抓取
- 大规模、高精度 → 传统爬虫
- 复杂结构、频繁变化 → AI 抓取
- 简单结构、固定格式 → 传统爬虫

