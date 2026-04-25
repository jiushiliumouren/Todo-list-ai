# 轻清单 (Light Todo List)

桌面待办事项 App，Flask 后端 + 原生 HTML/JS 前端，PyInstaller 打包为 Windows 单文件 exe。

## 技术栈

- **后端**: Python 3.13+ / Flask 2.3.3
- **前端**: 原生 HTML5 + CSS3 + JS (单文件 SPA, index.html ~2440 行)
- **桌面窗口**: FlaskWebGUI (WebView 包装)
- **打包**: PyInstaller → `dist/干!.exe` (~37MB), 命令: `pyinstaller app.spec`
- **数据存储**: JSON 文件 (`~/.todo_app/todos.json`, `settings.json`, `pet_state.json`)
- **Excel 导出**: openpyxl
- **AI 集成**: 兼容 OpenAI 格式 API (需用户自配 Key)
- **埋点(可选)**: PyMySQL + MySQL (后台线程, 优雅降级)

## 核心文件

| 文件 | 说明 |
|------|------|
| `app.py` | Flask 后端 ~695 行，所有 API 端点、CRUD、宠物算法 |
| `index.html` | 前端 SPA ~2440 行，HTML/CSS/JS 全在单文件 |
| `analytics.py` | MySQL 埋点模块 ~370 行 |
| `guide.html` | 宠物图鉴页面 |
| `app.spec` | PyInstaller 构建配置 |

## 数据模型 (Todo)

```python
{
  "id": int,
  "text": str,          # 待办内容
  "completed": bool,     # 是否完成
  "priority": str,       # "高"/"中"/"低"
  "due_date": str|None,  # "YYYY-MM-DD" 格式
  "note": str,           # 备注, 最长 2000 字
  "tags": str,           # 空格分隔的标签字符串
  "order": int,          # 排序序号
  "steps": [             # 子步骤列表
    {
      "id": str,         # 格式 "step_xxx"
      "text": str,
      "completed": bool,
      "due_date": str|None
    }
  ]
}
```

## API 端点

| 方法 | 路由 | 功能 |
|------|------|------|
| GET | `/api/todos` | 列所有待办 |
| POST | `/api/todos` | 创建待办 |
| PUT | `/api/todos/<id>` | 更新待办 |
| DELETE | `/api/todos/<id>` | 删除待办 |
| GET | `/api/todos/search?q=` | 搜索 |
| GET | `/api/todos/export` | 导出 Excel |
| PUT | `/api/todos/reorder` | 拖拽排序 |
| POST | `/api/todos/<id>/steps` | 添加步骤 |
| PUT | `/api/todos/<id>/steps/<step_id>` | 更新步骤 |
| DELETE | `/api/todos/<id>/steps/<step_id>` | 删除步骤 |
| GET | `/api/stats` | 统计摘要 |
| GET/POST/PUT | `/api/pet*` | 宠物状态/互动/设置 |
| GET/PUT | `/api/settings` | 设置 |
| POST | `/api/ai/suggest-steps` | AI 建议步骤 |

## 前端要点

- 所有 UI 在 `index.html` 一个文件中（含全部 CSS 和 JS）
- 无前端框架，直接 `fetch()` 调后端 API
- 数据属性 `data-id` 关联 DOM 与数据
- 主题通过 CSS 变量 + `document.documentElement.dataset.theme` 切换
- 桌面宠物用 Canvas 绘制像素风动画

## 关键行为约定

- 所有 API 返回 `{ "code": 200, "data": ..., "message": "xxx" }` 格式
- 前端是乐观 UI：先更新 DOM，再发请求，失败回滚
- 删除有 5 秒撤销窗口
- 数据变更后立即写 JSON 文件
- 宠物在 app 使用 7 天后通过 RFM 算法孵化
- AI 建议步骤功能需用户在设置中手动开启并配置
- FlaskWebGUI 启动方式: `FlaskUI(app=app, server="flask", width=1000, height=700).run()`

## 构建与运行

```bash
# 开发运行
python app.py

# 打包 exe
pyinstaller app.spec

# 产物
dist/干!.exe
```

调试时可以直接访问 `http://127.0.0.1:5000/`（Flask 原生端口）。
