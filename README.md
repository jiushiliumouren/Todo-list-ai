```markdown
# 轻清单 · 桌面待办

一个极简、优雅的桌面待办事项应用，**双击即用，无需安装 Python 环境**。  
采用 Flask + 原生 JavaScript 构建，并封装为独立桌面程序。

## ✨ 功能亮点

- ✅ 增 / 删 / 改（双击编辑）待办事项
- ✅ 标记完成状态，实时统计（总计、已完成、未完成）
- ✅ 搜索过滤待办事项
- ✅ 一键导出为 Excel（含优先级、截止日期）
- ✅ 深色 / 浅色主题切换，偏好自动保存
- ✅ 本地数据持久化（自动保存到文件，重启不丢失）
- ✅ 键盘快捷键（Ctrl+Enter 添加、Esc 清空输入、F5 刷新）
- ✅ 响应式界面，支持移动端浏览器访问

## 📦 技术栈

- **后端**：Python Flask + Flask-CORS
- **前端**：原生 HTML/CSS/JavaScript（无框架）
- **桌面封装**：FlaskWebGUI + PyInstaller（生成独立 .exe）
- **数据存储**：JSON 文件（位于用户目录 `~/.todo_app/todos.json`）


## 🚀 快速体验（开发模式）

如果你有 Python 环境，可以直接运行源码：

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 启动应用（自动打开桌面窗口）
python app.py
```

如需在浏览器中调试，可临时修改 `app.py` 末尾启动方式为 `app.run(debug=True)`。

## 📦 打包为独立 .exe 文件（单文件版）

我们已经配置好 `app.spec`，只需执行：

```bash
pyinstaller app.spec
```

生成的 `dist/轻清单.exe` 即为独立可执行文件，**可以复制到任何 Windows 电脑直接运行**，无需安装 Python 或任何依赖。

> 提示：首次打包若提示缺少 `pathlib` 包，执行 `pip uninstall pathlib` 即可。

## 🔌 API 接口说明

| 方法   | 路径                      | 说明                     |
|--------|---------------------------|--------------------------|
| GET    | `/api/todos`              | 获取全部待办             |
| POST   | `/api/todos`              | 添加待办                 |
| PUT    | `/api/todos/<id>`         | 更新待办（文本/完成状态/优先级/截止日期） |
| DELETE | `/api/todos/<id>`         | 删除待办                 |
| GET    | `/api/todos/search?q=关键词` | 搜索待办               |
| GET    | `/api/todos/export`       | 导出 Excel 文件          |

请求体示例（POST/PUT）：
```json
{
    "text": "完成项目文档",
    "priority": "high",
    "due_date": "2026-12-31"
}
```

## 🎨 界面预览

- 渐变紫色主题，支持一键切换深色模式
- 卡片式待办列表，悬停有微动效
- 统计面板动态更新，数字跳动反馈

## 📝 设计哲学

- **最小依赖**：后端仅需 Flask、Flask-CORS、FlaskWebGUI、openpyxl
- **开箱即用**：打包后零配置，双击启动
- **数据自主**：所有数据保存在本地，无网络请求，隐私安全

## 🔮 未来可扩展方向

- 分类标签、多清单切换
- 定时提醒（系统通知）
- 数据云同步（可选 WebDAV）
- Mac / Linux 平台打包支持

## 📄 许可证

MIT License - 自由使用、修改和分发。

---

**Enjoy your productive day with 轻清单 ☑️**
```