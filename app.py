from flask import Flask, jsonify, request, send_from_directory, make_response
from flask_cors import CORS
import os
import logging
import io
import time
from typing import List, Dict, Any, Optional
from flask import Flask, send_from_directory
from flaskwebgui import FlaskUI  # 1. 导入FlaskUI

app = Flask(__name__)
CORS(app)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 内存存储
todos: List[Dict[str, Any]] = [
    {"id": 1, "text": "学习Python",    "completed": False, "priority": "high", "due_date": None},
    {"id": 2, "text": "开发Flask应用", "completed": True,  "priority": "mid",  "due_date": None},
    {"id": 3, "text": "学习JavaScript","completed": False, "priority": "low",  "due_date": None},
]


# ── 辅助 ────────────────────────────────────────────────

def get_next_id() -> int:
    return max((t["id"] for t in todos), default=0) + 1


def find_todo(todo_id: int) -> Optional[Dict[str, Any]]:
    return next((t for t in todos if t["id"] == todo_id), None)


VALID_PRIORITIES = {"high", "mid", "low"}

def validate_payload(data: Dict[str, Any]) -> tuple[bool, str]:
    if not data:
        return False, "请求体不能为空"
    if "text" in data:
        text = data["text"]
        if not isinstance(text, str) or not text.strip():
            return False, "text 必须是非空字符串"
        if len(text.strip()) > 500:
            return False, "text 过长（最大 500 字符）"
    if "completed" in data and not isinstance(data["completed"], bool):
        return False, "completed 必须是布尔值"
    if "priority" in data and data["priority"] not in VALID_PRIORITIES:
        return False, f"priority 必须是 {VALID_PRIORITIES} 之一"
    if "due_date" in data:
        d = data["due_date"]
        if d is not None:
            if not isinstance(d, str):
                return False, "due_date 必须是 YYYY-MM-DD 字符串或 null"
            try:
                time.strptime(d, "%Y-%m-%d")
            except ValueError:
                return False, "due_date 格式错误，应为 YYYY-MM-DD"
    return True, ""


# ── 静态文件 ────────────────────────────────────────────

@app.route("/")
def index():
    return send_from_directory(".", "index.html")

@app.route("/<path:path>")
def serve_static(path):
    return send_from_directory(".", path)


# ── API ─────────────────────────────────────────────────

@app.route("/api/todos", methods=["GET"])
def get_todos():
    logger.info("GET /api/todos  count=%d", len(todos))
    return jsonify(todos)


@app.route("/api/todos", methods=["POST"])
def add_todo():
    data = request.get_json(silent=True) or {}
    ok, msg = validate_payload(data)
    if not ok:
        return jsonify({"error": msg}), 400
    if "text" not in data:
        return jsonify({"error": "缺少 text 字段"}), 400

    todo = {
        "id":        get_next_id(),
        "text":      data["text"].strip(),
        "completed": False,
        "priority":  data.get("priority", "mid"),
        "due_date":  data.get("due_date", None),
    }
    todos.append(todo)
    logger.info("POST /api/todos  id=%d", todo["id"])
    return jsonify(todo), 201


@app.route("/api/todos/search", methods=["GET"])
def search_todos():
    # 必须在 /<int:todo_id> 路由之前注册
    q = request.args.get("q", "").strip().lower()
    results = todos if not q else [t for t in todos if q in t["text"].lower()]
    logger.info("GET /api/todos/search  q=%r  found=%d", q, len(results))
    return jsonify(results)


@app.route("/api/todos/export", methods=["GET"])
def export_todos():
    try:
        from openpyxl import Workbook
        from openpyxl.styles import Font, Alignment, PatternFill
    except ImportError:
        return jsonify({"error": "缺少 openpyxl，请执行 pip install openpyxl"}), 500

    wb = Workbook()
    ws = wb.active
    ws.title = "待办事项"

    headers = ["ID", "内容", "优先级", "截止日期", "完成状态", "导出时间"]
    fill = PatternFill("solid", fgColor="C0392B")
    now = time.strftime("%Y-%m-%d %H:%M:%S")

    for col, h in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col, value=h)
        cell.font = Font(bold=True, color="FFFFFF")
        cell.alignment = Alignment(horizontal="center")
        cell.fill = fill

    pri_labels = {"high": "高", "mid": "中", "low": "低"}

    if todos:
        for row, t in enumerate(todos, 2):
            ws.cell(row=row, column=1, value=t["id"])
            ws.cell(row=row, column=2, value=t["text"])
            ws.cell(row=row, column=3, value=pri_labels.get(t.get("priority","mid"), "中"))
            ws.cell(row=row, column=4, value=t.get("due_date") or "—")
            ws.cell(row=row, column=5, value="已完成" if t["completed"] else "未完成")
            ws.cell(row=row, column=6, value=now)
    else:
        ws.merge_cells("A2:F2")
        ws.cell(row=2, column=1, value="暂无数据").alignment = Alignment(horizontal="center")

    for col in ws.columns:
        w = max((len(str(c.value or "")) for c in col), default=8) + 4
        ws.column_dimensions[col[0].column_letter].width = min(w, 60)

    buf = io.BytesIO()
    wb.save(buf)

    resp = make_response(buf.getvalue())
    resp.headers["Content-Type"] = (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    resp.headers["Content-Disposition"] = (
        f'attachment; filename="todos_{time.strftime("%Y%m%d_%H%M%S")}.xlsx"'
    )
    logger.info("GET /api/todos/export  count=%d", len(todos))
    return resp


@app.route("/api/todos/<int:todo_id>", methods=["PUT"])
def update_todo(todo_id):
    data = request.get_json(silent=True) or {}
    ok, msg = validate_payload(data)
    if not ok:
        return jsonify({"error": msg}), 400

    todo = find_todo(todo_id)
    if not todo:
        return jsonify({"error": "待办事项未找到"}), 404

    if "text"      in data: todo["text"]      = data["text"].strip()
    if "completed" in data: todo["completed"] = data["completed"]
    if "priority"  in data: todo["priority"]  = data["priority"]
    if "due_date"  in data: todo["due_date"]  = data["due_date"]

    logger.info("PUT /api/todos/%d  %s", todo_id, todo)
    return jsonify(todo)


@app.route("/api/todos/<int:todo_id>", methods=["DELETE"])
def delete_todo(todo_id):
    # 注意：用 target 避免与列表推导变量同名（原代码 bug）
    target = find_todo(todo_id)
    if not target:
        return jsonify({"error": "待办事项未找到"}), 404

    todos[:] = [t for t in todos if t["id"] != todo_id]
    logger.info("DELETE /api/todos/%d", todo_id)
    return jsonify({"message": "删除成功", "deleted_todo": target})


# ── 启动 ────────────────────────────────────────────────

if __name__ == '__main__':
    # 2. 用FlaskUI包装应用并运行，它会自动打开一个桌面窗口
    FlaskUI(app=app, server="flask", width=800, height=600).run()