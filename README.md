# 🕷️ AI 智能网页抓取工具

一个基于 AI 的智能网页抓取工具，支持多种 LLM 提供商（OpenAI、Ollama、LM Studio），使用自然语言描述抓取需求，自动解析网页内容并输出结构化数据。

## ✨ 主要特性

- 🤖 **多 LLM 支持**：统一支持 OpenAI、Ollama、LM Studio 三种模型提供商
- 🎯 **自然语言抓取**：用自然语言描述抓取需求，无需编写 CSS/XPath 选择器
- 🔐 **登录支持**：支持需要登录的网站，可保存登录状态
- 🌐 **动态页面处理**：使用 Playwright 处理 JavaScript 渲染的动态内容
- 📊 **结构化输出**：支持 JSON Schema 约束，输出结构化数据
- 📝 **历史记录**：自动保存抓取历史，方便回溯和对比
- 📋 **表格导出工具**：专门用于自动点击导出按钮并解析表格数据
- 🎨 **友好界面**：基于 Streamlit 的现代化 Web 界面

## 🚀 快速开始

### 环境要求

- Python 3.8+
- 已安装的 LLM 服务（OpenAI API / Ollama / LM Studio）

### 安装步骤

1. **克隆项目**

```bash
git clone <repository-url>
cd ai-acrapping
```

2. **安装依赖**

```bash
pip install -r unified_app/requirements.txt
```

3. **安装 Playwright 浏览器**

```bash
playwright install chromium
```

### 运行应用

#### 统一 Web Scraping 应用（推荐）

```bash
streamlit run unified_app/app.py
```

这是主要的应用入口，支持所有功能。

#### 表格导出工具

```bash
streamlit run table_exporter.py
```

专门用于自动点击导出按钮并解析表格数据。

#### 其他示例脚本

```bash
# OpenAI 示例
streamlit run ai_scrapper.py

# LM Studio 示例
streamlit run lmstudio_ai_scrapper.py

# 本地 AI 示例
streamlit run local_ai_scrapper.py
```

## 📖 使用指南

### 统一 Web Scraping 应用

#### 1. 配置模型提供商

在侧边栏选择并配置你的 LLM 提供商：

**OpenAI（云端）**

- 输入 OpenAI API Key
- 选择或输入模型名称（如 `gpt-4o`、`gpt-4.1`）
- 点击"🔍 测试连接"验证并获取可用模型列表

**Ollama（本地）**

- 输入 Ollama Base URL（默认：`http://localhost:11434`）
- 输入模型名称（如 `llama3.2`、`qwen2.5`）
- 点击"🔍 测试连接"获取本地模型列表

**LM Studio（本地）**

- 输入 LM Studio API URL（默认：`http://localhost:1234/v1`）
- 输入当前加载的模型名称
- 点击"🔍 测试连接"验证连接

配置完成后，点击"💾 保存配置"将设置保存到本地。

#### 2. 配置抓取参数

**基本配置**

- **目标网页 URL**：要抓取的网页地址
- **抓取提示**：用自然语言描述你想要抓取的内容
  - 例如："提取所有产品名称和价格"
  - 例如："获取文章标题、作者和发布日期"

**高级选项**

- **页面加载等待策略**：
  - `networkidle`：等待所有网络请求完成（推荐）
  - `domcontentloaded`：仅等待 DOM 加载
  - `load`：等待所有资源加载
- **启用 JavaScript 渲染**：确保动态内容被正确加载
- **额外等待时间**：页面加载后的额外等待时间（秒）

**登录选项**（需要登录的网站）

- 勾选"需要登录"
- 输入登录页面 URL（如果与目标页不同）
- 选择登录方式：
  - **手动登录**：在浏览器窗口中手动完成登录（推荐）
  - **自动登录**：使用保存的登录状态
- 勾选"保存登录状态"以保存登录信息到 `login_state.json`

**结构化输出**（可选）

- 勾选"使用结构化 JSON 输出"
- 输入 JSON Schema 定义输出结构

#### 3. 开始抓取

点击"🚀 开始抓取"按钮，工具会：

1. 如果需要登录，先使用 Playwright 打开浏览器完成登录
2. 访问目标网页并获取 HTML 内容
3. 使用 LLM 根据你的提示解析网页内容
4. 返回结构化结果
5. 自动保存到历史记录

#### 4. 查看结果

- 结果会以 Markdown 或 JSON 格式显示
- 可以展开查看完整的 JSON 结果
- 如果启用了"显示原始 HTML"，可以查看抓取到的 HTML（用于调试）

#### 5. 历史记录

侧边栏会显示最近的抓取历史（最多 200 条），包括：

- 时间戳
- 使用的提供商
- URL 和提示
- 结果摘要

### 表格导出工具

专门用于自动点击网页上的导出按钮并解析表格数据。

#### 使用步骤

1. **输入网页 URL**
2. **选择抓取模式**：
   - **点击导出按钮**：自动查找并点击导出按钮，下载文件
   - **抓取页面数据**：直接从页面提取表格/列表数据
3. **输入描述**：
   - 导出按钮模式：描述按钮文字（如"导出表格"、"Export CSV"）
   - 页面数据模式：描述要抓取的数据（如"所有仓库"、"产品列表"）
4. **配置选项**（可选）：
   - 登录选项（与统一应用相同）
   - 等待时间、超时时间等
5. **开始抓取**

#### 支持的文件格式

- CSV (.csv)
- Excel (.xlsx, .xls)
- JSON (.json)
- TSV (.tsv)

#### 数据预览和导出

抓取成功后，可以：

- 查看表格预览
- 查看数据统计信息
- 下载为 CSV、Excel 或 JSON 格式

## 🏗️ 项目结构

```
ai-acrapping/
├── unified_app/              # 统一应用（主要入口）
│   ├── app.py               # Streamlit 主应用
│   ├── config.py            # 配置管理（多 LLM 支持）
│   ├── history.py           # 历史记录管理
│   └── requirements.txt     # 依赖列表
├── table_exporter.py         # 表格导出工具
├── ai_scrapper.py           # OpenAI 示例脚本
├── lmstudio_ai_scrapper.py  # LM Studio 示例脚本
├── local_ai_scrapper.py     # 本地 AI 示例脚本
├── AI_SCRAPING_PRINCIPLES.md # 技术原理文档
├── GITHUB_LOGIN_GUIDE.md    # GitHub 登录指南
└── README.md                # 本文件
```

## 🔧 配置说明

### 配置文件位置

- **应用配置**：`unified_config.json`（自动生成）
- **历史记录**：`scrape_history.json`（自动生成）
- **登录状态**：`login_state.json`（可选，包含敏感信息）

### 配置示例

`unified_config.json` 示例：

```json
{
  "provider": "openai",
  "openai": {
    "api_key": "sk-...",
    "model": "gpt-4o"
  },
  "ollama": {
    "base_url": "http://localhost:11434",
    "model": "ollama/llama3.2"
  },
  "lmstudio": {
    "base_url": "http://localhost:1234/v1",
    "model": "qwen/qwen3-4b-2507",
    "api_key": ""
  }
}
```

## 🎯 使用场景

### 适合使用本项目的场景

- ✅ **数据探索和原型验证**：快速验证某个页面能否抓取到所需信息
- ✅ **非技术用户**：运营、产品、分析师等无需写代码即可抓取数据
- ✅ **复杂网站结构**：网站结构复杂、变化频繁，写选择器成本高
- ✅ **语义理解需求**：需要理解文本语义，如"提取候选人的核心经历"
- ✅ **小规模交互式抓取**：需要人工交互和验证的抓取任务

### 更适合传统爬虫的场景

- ❌ 高并发大规模批量抓取
- ❌ 强实时性、强稳定性要求
- ❌ 结构高度稳定且简单的页面

## 🔐 登录功能详解

### 支持的登录方式

1. **手动登录**（推荐）

   - 适用于需要验证码、两步验证的网站
   - 在浏览器窗口中手动完成登录
   - 登录状态会保存到 `login_state.json`
2. **自动登录**

   - 使用保存的登录状态
   - 适用于已登录过的网站

### 登录状态管理

- 登录状态保存在 `login_state.json` 文件中
- 包含网站的 cookies 和 session 信息
- **安全提示**：该文件包含敏感信息，请妥善保管，不要提交到 Git

### GitHub 登录示例

详细指南请参考 [GITHUB_LOGIN_GUIDE.md](./GITHUB_LOGIN_GUIDE.md)

## 🐛 常见问题

### 1. 连接失败（503 错误）

**问题**：本地 LLM 服务（LM Studio / Ollama）返回 503 错误

**解决方案**：

- 检查 LM Studio / Ollama Server 是否正在运行
- 确认已在 Server 面板中加载了对应模型
- 检查统一应用中填写的 Base URL 与实际 Server 地址/端口是否一致

### 2. 模型不存在

**问题**：提示 "Model does not exist" 或 "Failed to load model"

**解决方案**：

- 在 LM Studio / Ollama 中确认模型已下载并成功加载
- 检查 Server 页面中当前服务的模型名称，与侧边栏选择的名称是否完全一致
- 如果刚刚修改了模型，重新点击"🔍 测试连接"刷新模型列表

### 3. 登录失败

**问题**：无法登录或登录状态失效

**解决方案**：

- 删除 `login_state.json` 文件重新登录
- 使用手动登录模式，确保在浏览器中完成所有验证步骤
- 检查登录页面 URL 是否正确

### 4. 页面加载超时

**问题**：页面加载超时

**解决方案**：

- 增加页面加载超时时间
- 切换到 `domcontentloaded` 等待策略
- 检查网络连接和目标网站是否可访问

### 5. 抓取结果不准确

**问题**：LLM 解析结果不符合预期

**解决方案**：

- 优化抓取提示，更具体地描述需求
- 使用 JSON Schema 约束输出结构
- 增加额外等待时间，确保动态内容已加载
- 查看原始 HTML 调试页面结构

## 🛠️ 技术栈

- **Web 框架**：Streamlit
- **网页抓取**：Playwright（浏览器自动化）
- **AI 解析**：ScrapeGraphAI（基于 LangChain）
- **LLM 支持**：
  - OpenAI API
  - Ollama（本地）
  - LM Studio（本地）
- **数据处理**：pandas、BeautifulSoup
- **文件处理**：openpyxl（Excel 支持）

## 📚 技术原理

详细的技术原理和架构设计请参考 [AI_SCRAPING_PRINCIPLES.md](./AI_SCRAPING_PRINCIPLES.md)

## 🔒 安全注意事项

1. **API Key 安全**

   - 不要将包含 API Key 的配置文件提交到公开仓库
   - 使用环境变量或密钥管理工具存储敏感信息
2. **登录状态文件**

   - `login_state.json` 包含敏感信息
   - 不要分享给他人或提交到 Git
   - 建议添加到 `.gitignore`
3. **数据隐私**

   - 抓取的数据可能包含敏感信息
   - 遵守目标网站的 robots.txt 和使用条款
   - 不要用于非法用途
