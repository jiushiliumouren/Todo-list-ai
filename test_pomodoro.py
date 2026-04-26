"""
测试番茄钟 API
============
使用 Flask 测试客户端，不依赖真实文件系统（使用 tempdir）。
"""

import os
import json
import time
import tempfile
import pytest

from app import app


@pytest.fixture
def client():
    """创建测试客户端，使用临时目录隔离数据文件，并重置共享状态"""
    import app as app_module

    with tempfile.TemporaryDirectory() as tmpdir:
        # 覆盖 DATA_DIR 为临时目录（隔离 pomodoro 和 todo 数据文件）
        original_dir = app_module.DATA_DIR
        app_module.DATA_DIR = tmpdir

        # 重置模块级 todos（不依赖文件）
        app_module.todos[:] = []

        app.config['TESTING'] = True
        with app.test_client() as c:
            yield c

        # 恢复
        app_module.DATA_DIR = original_dir


class TestPomodoroStats:
    """测试 GET /api/pomodoro/stats"""

    def test_returns_default_stats(self, client):
        """未使用过番茄钟时返回默认统计"""
        resp = client.get('/api/pomodoro/stats')
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert data['today_count'] == 0
        assert data['total_count'] == 0
        assert 'settings' in data
        assert data['settings']['work_minutes'] == 25
        assert data['settings']['break_minutes'] == 5
        assert data['settings']['long_break_minutes'] == 15
        assert data['settings']['cycles_before_long_break'] == 4
        assert 'records' in data
        assert data['records'] == []

    def test_today_count_after_complete(self, client):
        """完成一个番茄钟后今日计数增加"""
        client.post('/api/pomodoro/complete',
                    data=json.dumps({'duration': 25}),
                    content_type='application/json')

        resp = client.get('/api/pomodoro/stats')
        data = json.loads(resp.data)
        assert data['today_count'] == 1
        assert data['total_count'] == 1
        assert len(data['records']) == 1


class TestPomodoroComplete:
    """测试 POST /api/pomodoro/complete"""

    def test_complete_without_todo(self, client):
        """不关联待办事项时记录番茄钟"""
        resp = client.post('/api/pomodoro/complete',
                           data=json.dumps({'duration': 25}),
                           content_type='application/json')
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert data['today_count'] == 1
        assert data['total_count'] == 1
        assert 'record' in data
        assert data['record']['duration'] == 25
        assert data['record']['todo_id'] is None

    def test_complete_with_todo(self, client):
        """关联有效待办事项"""
        # 先创建一个待办
        create_resp = client.post('/api/todos',
                                  data=json.dumps({'text': '测试任务'}),
                                  content_type='application/json')
        assert create_resp.status_code == 201
        todo = json.loads(create_resp.data)

        # 关联此待办完成番茄钟
        resp = client.post('/api/pomodoro/complete',
                           data=json.dumps({'todo_id': todo['id'], 'duration': 25}),
                           content_type='application/json')
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert data['record']['todo_id'] == todo['id']

    def test_complete_with_invalid_todo(self, client):
        """关联不存在的待办时返回 404"""
        resp = client.post('/api/pomodoro/complete',
                           data=json.dumps({'todo_id': 99999, 'duration': 25}),
                           content_type='application/json')
        assert resp.status_code == 404

    def test_complete_with_invalid_todo_type(self, client):
        """todo_id 不是整数时返回 400"""
        resp = client.post('/api/pomodoro/complete',
                           data=json.dumps({'todo_id': 'abc', 'duration': 25}),
                           content_type='application/json')
        assert resp.status_code == 400

    def test_complete_with_default_duration(self, client):
        """不传 duration 时使用默认 25 分钟"""
        resp = client.post('/api/pomodoro/complete',
                           data=json.dumps({}),
                           content_type='application/json')
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert data['record']['duration'] == 25

    def test_complete_with_negative_duration(self, client):
        """负值 duration 返回 400"""
        resp = client.post('/api/pomodoro/complete',
                           data=json.dumps({'duration': -5}),
                           content_type='application/json')
        assert resp.status_code == 400

    def test_complete_with_too_large_duration(self, client):
        """超过上限的 duration 返回 400"""
        resp = client.post('/api/pomodoro/complete',
                           data=json.dumps({'duration': 200}),
                           content_type='application/json')
        assert resp.status_code == 400

    def test_multiple_completes_count(self, client):
        """多次完成计数正确"""
        for _ in range(3):
            resp = client.post('/api/pomodoro/complete',
                               data=json.dumps({'duration': 25}),
                               content_type='application/json')
            assert resp.status_code == 200

        resp = client.get('/api/pomodoro/stats')
        data = json.loads(resp.data)
        assert data['today_count'] == 3
        assert data['total_count'] == 3
        assert len(data['records']) == 3

    def test_complete_has_timestamp(self, client):
        """记录包含时间和日期"""
        resp = client.post('/api/pomodoro/complete',
                           data=json.dumps({'duration': 25}),
                           content_type='application/json')
        data = json.loads(resp.data)
        record = data['record']
        assert 'date' in record
        assert 'time' in record
        # 日期应为今天
        assert record['date'] == time.strftime('%Y-%m-%d')


class TestPomodoroSettings:
    """测试 GET/PUT /api/pomodoro/settings"""

    def test_get_default_settings(self, client):
        """获取默认设置"""
        resp = client.get('/api/pomodoro/settings')
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert data['work_minutes'] == 25
        assert data['break_minutes'] == 5

    def test_update_settings(self, client):
        """更新设置成功"""
        resp = client.put('/api/pomodoro/settings',
                          data=json.dumps({
                              'work_minutes': 30,
                              'break_minutes': 10,
                          }),
                          content_type='application/json')
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert data['settings']['work_minutes'] == 30
        assert data['settings']['break_minutes'] == 10

    def test_partial_update(self, client):
        """只更新部分字段不影响其他字段"""
        # 先更新一个
        client.put('/api/pomodoro/settings',
                   data=json.dumps({'work_minutes': 50}),
                   content_type='application/json')
        # 再更新另一个
        resp = client.put('/api/pomodoro/settings',
                          data=json.dumps({'break_minutes': 15}),
                          content_type='application/json')
        data = json.loads(resp.data)
        assert data['settings']['work_minutes'] == 50
        assert data['settings']['break_minutes'] == 15
        assert data['settings']['long_break_minutes'] == 15  # 默认值不变

    def test_invalid_work_minutes(self, client):
        """无效的工作时长返回 400"""
        resp = client.put('/api/pomodoro/settings',
                          data=json.dumps({'work_minutes': 0}),
                          content_type='application/json')
        assert resp.status_code == 400

    def test_invalid_work_minutes_too_large(self, client):
        """过大时长返回 400"""
        resp = client.put('/api/pomodoro/settings',
                          data=json.dumps({'work_minutes': 200}),
                          content_type='application/json')
        assert resp.status_code == 400

    def test_invalid_cycles(self, client):
        """无效的周期数返回 400"""
        resp = client.put('/api/pomodoro/settings',
                          data=json.dumps({'cycles_before_long_break': 0}),
                          content_type='application/json')
        assert resp.status_code == 400

    def test_cycles_too_large(self, client):
        """过大的周期数返回 400"""
        resp = client.put('/api/pomodoro/settings',
                          data=json.dumps({'cycles_before_long_break': 15}),
                          content_type='application/json')
        assert resp.status_code == 400

    def test_settings_persistence(self, client):
        """设置保存后再次读取应保持"""
        client.put('/api/pomodoro/settings',
                   data=json.dumps({'work_minutes': 45}),
                   content_type='application/json')
        resp = client.get('/api/pomodoro/settings')
        data = json.loads(resp.data)
        assert data['work_minutes'] == 45

    def test_settings_affect_stats_response(self, client):
        """settings 更新后 /stats 中也反映出来"""
        client.put('/api/pomodoro/settings',
                   data=json.dumps({'work_minutes': 35}),
                   content_type='application/json')
        resp = client.get('/api/pomodoro/stats')
        data = json.loads(resp.data)
        assert data['settings']['work_minutes'] == 35


class TestPomodoroDataIsolation:
    """测试数据文件和隔离性"""

    def test_data_file_created(self, client):
        """完成番茄钟后数据文件应存在"""
        import app as app_module

        client.post('/api/pomodoro/complete',
                    data=json.dumps({'duration': 25}),
                    content_type='application/json')

        pomo_file = os.path.join(app_module.DATA_DIR, 'pomodoro_stats.json')
        assert os.path.exists(pomo_file), "番茄钟数据文件应被创建"

        with open(pomo_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        assert data['today_count'] == 1
        assert data['total_count'] == 1

    def test_todo_file_not_affected(self, client):
        """番茄钟操作不应影响待办事项文件"""
        import app as app_module

        # 记录番茄钟
        client.post('/api/pomodoro/complete',
                    data=json.dumps({'duration': 25}),
                    content_type='application/json')

        # 创建待办
        client.post('/api/todos',
                    data=json.dumps({'text': '独立任务'}),
                    content_type='application/json')

        # 加载待办
        resp = client.get('/api/todos')
        todos = json.loads(resp.data)
        assert len(todos) == 1
        assert todos[0]['text'] == '独立任务'

        # 番茄钟统计也应正确
        resp = client.get('/api/pomodoro/stats')
        data = json.loads(resp.data)
        assert data['today_count'] == 1


class TestPomodoroEmptyBody:
    """测试空请求体"""

    def test_complete_empty_body(self, client):
        """POST 空 body 使用默认值"""
        resp = client.post('/api/pomodoro/complete',
                           data=json.dumps({}),
                           content_type='application/json')
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert data['today_count'] == 1

    def test_complete_no_content_type(self, client):
        """无 Content-Type 应正常处理"""
        resp = client.post('/api/pomodoro/complete', data='{}')
        assert resp.status_code == 200

    def test_settings_empty_body(self, client):
        """PUT 空 body 不改变设置"""
        resp = client.put('/api/pomodoro/settings',
                          data=json.dumps({}),
                          content_type='application/json')
        assert resp.status_code == 200
        # 确认设置未被改变
        resp = client.get('/api/pomodoro/settings')
        data = json.loads(resp.data)
        assert data['work_minutes'] == 25


if __name__ == '__main__':
    pytest.main(['-v', __file__])
