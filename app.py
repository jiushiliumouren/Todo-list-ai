from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
import os
import logging
from typing import List, Dict, Any, Optional

app = Flask(__name__)
CORS(app)  # 允许跨域请求

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 内存存储待办事项
todos: List[Dict[str, Any]] = [
    {"id": 1, "text": "学习Python", "completed": False},
    {"id": 2, "text": "开发Flask应用", "completed": True},
    {"id": 3, "text": "学习JavaScript", "completed": False}
]

# 辅助函数
def get_next_id() -> int:
    """获取下一个可用的ID"""
    if not todos:
        return 1
    return max(todo['id'] for todo in todos) + 1

def find_todo_by_id(todo_id: int) -> Optional[Dict[str, Any]]:
    """根据ID查找待办事项"""
    for todo in todos:
        if todo['id'] == todo_id:
            return todo
    return None

def validate_todo_data(data: Dict[str, Any]) -> tuple[bool, str]:
    """验证待办事项数据"""
    if not data:
        return False, "请求体不能为空"
    
    if 'text' in data:
        text = data['text']
        if not isinstance(text, str):
            return False, "text必须是字符串"
        if not text.strip():
            return False, "待办事项文本不能为空"
        if len(text.strip()) > 500:
            return False, "待办事项文本过长（最大500字符）"
    
    if 'completed' in data:
        completed = data['completed']
        if not isinstance(completed, bool):
            return False, "completed必须是布尔值"
    
    return True, ""

# 静态文件服务
@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

@app.route('/<path:path>')
def serve_static(path):
    return send_from_directory('.', path)

# API路由
@app.route('/api/todos', methods=['GET'])
def get_todos():
    """获取所有待办事项"""
    logger.info(f"获取待办事项，当前数量: {len(todos)}")
    return jsonify(todos)

@app.route('/api/todos', methods=['POST'])
def add_todo():
    """添加新的待办事项"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "请求体不能为空"}), 400
        
        # 验证数据
        is_valid, error_message = validate_todo_data(data)
        if not is_valid:
            return jsonify({"error": error_message}), 400
        
        if 'text' not in data:
            return jsonify({"error": "缺少待办事项文本"}), 400
        
        # 创建新待办事项
        new_todo = {
            "id": get_next_id(),
            "text": data['text'].strip(),
            "completed": False
        }
        
        todos.append(new_todo)
        logger.info(f"添加待办事项: {new_todo}")
        
        return jsonify(new_todo), 201
    except Exception as e:
        logger.error(f"添加待办事项时出错: {str(e)}")
        return jsonify({"error": "服务器内部错误"}), 500

@app.route('/api/todos/<int:todo_id>', methods=['PUT'])
def update_todo(todo_id):
    """更新待办事项"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "请求体不能为空"}), 400
        
        # 验证数据
        is_valid, error_message = validate_todo_data(data)
        if not is_valid:
            return jsonify({"error": error_message}), 400
        
        # 查找待办事项
        todo = find_todo_by_id(todo_id)
        if not todo:
            return jsonify({"error": "待办事项未找到"}), 404
        
        # 更新字段
        if 'text' in data:
            todo['text'] = data['text'].strip()
        if 'completed' in data:
            todo['completed'] = data['completed']
        
        logger.info(f"更新待办事项 {todo_id}: {todo}")
        return jsonify(todo)
    except Exception as e:
        logger.error(f"更新待办事项 {todo_id} 时出错: {str(e)}")
        return jsonify({"error": "服务器内部错误"}), 500

@app.route('/api/todos/search', methods=['GET'])
def search_todos():
    """搜索待办事项"""
    try:
        search_term = request.args.get('q', '').strip().lower()
        
        if not search_term:
            return jsonify(todos)
        
        # 搜索匹配的待办事项
        filtered_todos = [
            todo for todo in todos
            if search_term in todo['text'].lower()
        ]
        
        logger.info(f"搜索 '{search_term}', 找到 {len(filtered_todos)} 个结果")
        return jsonify(filtered_todos)
    except Exception as e:
        logger.error(f"搜索待办事项时出错: {str(e)}")
        return jsonify({"error": "服务器内部错误"}), 500

@app.route('/api/todos/export', methods=['GET'])
def export_todos():
    """导出所有待办事项为Excel"""
    try:
        from flask import make_response
        from openpyxl import Workbook
        from openpyxl.styles import Font, Alignment
        import io
        import time
        import os
        
        # 检查是否有现有的Excel文件
        excel_file_path = os.path.join(os.path.dirname(__file__), 'todos_export.xlsx')
        file_exists = os.path.exists(excel_file_path)
        
        # 创建工作簿
        wb = Workbook()
        ws = wb.active
        ws.title = "待办事项"
        
        # 设置标题行
        headers = ['ID', '待办事项内容', '完成状态', '导出时间']
        for col, header in enumerate(headers, 1):
            cell = ws.cell(row=1, column=col, value=header)
            cell.font = Font(bold=True)
            cell.alignment = Alignment(horizontal='center')
        
        # 添加数据行
        row = 2
        for todo in todos:
            ws.cell(row=row, column=1, value=todo['id'])
            ws.cell(row=row, column=2, value=todo['text'])
            ws.cell(row=row, column=3, value='已完成' if todo['completed'] else '未完成')
            ws.cell(row=row, column=4, value=time.strftime("%Y-%m-%d %H:%M:%S"))
            row += 1
        
        # 如果没有数据，添加提示
        if not todos:
            ws.cell(row=2, column=1, value="暂无待办事项")
            ws.merge_cells('A2:D2')
            ws.cell(row=2, column=1).alignment = Alignment(horizontal='center')
        
        # 调整列宽
        for column in ws.columns:
            max_length = 0
            column_letter = column[0].column_letter
            for cell in column:
                try:
                    if len(str(cell.value)) > max_length:
                        max_length = len(str(cell.value))
                except:
                    pass
            adjusted_width = min(max_length + 2, 50)
            ws.column_dimensions[column_letter].width = adjusted_width
        
        # 保存到内存
        output = io.BytesIO()
        wb.save(output)
        excel_data = output.getvalue()
        
        # 创建响应
        response = make_response(excel_data)
        response.headers['Content-Type'] = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        response.headers['Content-Disposition'] = f'attachment; filename=todos_export_{time.strftime("%Y%m%d_%H%M%S")}.xlsx'
        
        logger.info(f"导出待办事项到Excel，总数: {len(todos)}")
        return response
    except Exception as e:
        logger.error(f"导出待办事项到Excel时出错: {str(e)}")
        return jsonify({"error": "服务器内部错误"}), 500

@app.route('/api/todos/<int:todo_id>', methods=['DELETE'])
def delete_todo(todo_id):
    """删除待办事项"""
    try:
        # 查找待办事项
        todo = find_todo_by_id(todo_id)
        if not todo:
            return jsonify({"error": "待办事项未找到"}), 404
        
        # 删除待办事项
        todos[:] = [todo for todo in todos if todo['id'] != todo_id]
        
        logger.info(f"删除待办事项: {todo}")
        return jsonify({"message": "删除成功", "deleted_todo": todo}), 200
    except Exception as e:
        logger.error(f"删除待办事项 {todo_id} 时出错: {str(e)}")
        return jsonify({"error": "服务器内部错误"}), 500

if __name__ == '__main__':
    # 确保静态文件目录存在
    static_dir = os.path.join(os.path.dirname(__file__), 'static')
    if not os.path.exists(static_dir):
        os.makedirs(static_dir)
    
    logger.info("待办事项应用启动中...")
    logger.info("访问地址: http://localhost:5000")
    logger.info(f"当前待办事项数量: {len(todos)}")
    
    app.run(debug=True, port=5000, use_reloader=False)
