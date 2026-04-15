"""
analytics.py — 使用行为埋点模块
向 MySQL 异步写入操作数据，不阻塞主流程。
若 MySQL 未配置或连接失败，所有操作静默跳过。
"""
import threading
import uuid
import json
import logging
import os
from datetime import datetime
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

# ── 全局状态 ──────────────────────────────────────────────────
_conn = None
_conn_lock = threading.Lock()
_session_id: Optional[str] = None
_session_action_count = 0
_mysql_available = None        # None=未检测, True/False=已检测

DATA_DIR = os.path.join(os.path.expanduser("~"), ".todo_app")
SETTINGS_FILE = os.path.join(DATA_DIR, "settings.json")


# ── 配置读取 ──────────────────────────────────────────────────
def _get_mysql_cfg() -> dict:
    try:
        with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f).get("mysql", {})
    except Exception:
        return {}


# ── 连接管理 ──────────────────────────────────────────────────
def _get_conn():
    global _conn, _mysql_available
    with _conn_lock:
        if _mysql_available is False:
            return None
        if _conn is not None:
            try:
                _conn.ping(reconnect=True)
                return _conn
            except Exception:
                _conn = None

        cfg = _get_mysql_cfg()
        if not cfg.get("host"):
            _mysql_available = False
            return None

        try:
            import pymysql
            _conn = pymysql.connect(
                host=cfg.get("host", "localhost"),
                port=int(cfg.get("port", 3306)),
                user=cfg.get("user", "root"),
                password=cfg.get("password", ""),
                database=cfg.get("database", "todo_analytics"),
                charset="utf8mb4",
                autocommit=True,
                connect_timeout=5,
            )
            _mysql_available = True
            logger.info("[analytics] MySQL 连接成功")
            return _conn
        except Exception as e:
            _mysql_available = False
            logger.warning(f"[analytics] MySQL 连接失败，埋点将跳过: {e}")
            return None


def _run(fn):
    """在后台线程执行，保证主流程不受影响"""
    threading.Thread(target=fn, daemon=True).start()


# ── 初始化建表 ────────────────────────────────────────────────
def init_db():
    """App 启动时调用，自动建表（幂等）"""
    def _do():
        conn = _get_conn()
        if not conn:
            return
        try:
            with conn.cursor() as cur:
                # 1. 会话表：每次打开 App = 一条记录
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS sessions (
                        id            INT AUTO_INCREMENT PRIMARY KEY,
                        session_id    VARCHAR(36)  NOT NULL,
                        start_time    DATETIME     NOT NULL,
                        end_time      DATETIME,
                        duration_sec  INT,
                        action_count  INT DEFAULT 0,
                        INDEX idx_start (start_time)
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='每次启动App的会话记录'
                """)

                # 2. 事件流水表：所有用户操作的原始记录
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS events (
                        id          BIGINT AUTO_INCREMENT PRIMARY KEY,
                        session_id  VARCHAR(36)  NOT NULL,
                        event_type  VARCHAR(50)  NOT NULL
                            COMMENT 'todo_created|todo_completed|todo_deleted|step_completed|ai_suggest_used|search|export|reorder',
                        event_time  DATETIME     NOT NULL,
                        todo_id     INT,
                        extra       JSON         COMMENT '附加维度：priority, has_due_date, keyword 等',
                        INDEX idx_time   (event_time),
                        INDEX idx_type   (event_type),
                        INDEX idx_sess   (session_id),
                        INDEX idx_todo   (todo_id)
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='操作事件流水（核心分析表）'
                """)

                # 3. 任务生命周期表：每个 todo 从创建到结束的完整画像
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS todo_lifecycle (
                        id              INT AUTO_INCREMENT PRIMARY KEY,
                        todo_id         INT         NOT NULL UNIQUE,
                        priority        VARCHAR(10) COMMENT 'high|mid|low',
                        has_due_date    TINYINT(1)  DEFAULT 0,
                        is_overdue      TINYINT(1)  DEFAULT 0 COMMENT '删除/查看时是否已逾期',
                        step_count      INT         DEFAULT 0,
                        ai_steps_used   TINYINT(1)  DEFAULT 0 COMMENT '是否使用过AI建议步骤',
                        tag_count       INT         DEFAULT 0,
                        created_at      DATETIME    NOT NULL,
                        completed_at    DATETIME,
                        deleted_at      DATETIME,
                        completion_days INT         COMMENT '从创建到完成的天数',
                        outcome         VARCHAR(20) DEFAULT 'pending'
                            COMMENT 'pending|completed|deleted',
                        INDEX idx_created  (created_at),
                        INDEX idx_priority (priority),
                        INDEX idx_outcome  (outcome)
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='任务生命周期（支持完成率/周期分析）'
                """)
            logger.info("[analytics] 数据库表初始化完成")
        except Exception as e:
            logger.error(f"[analytics] 建表失败: {e}")
    _run(_do)


# ── 会话管理 ──────────────────────────────────────────────────
def start_session() -> str:
    global _session_id, _session_action_count
    _session_id = str(uuid.uuid4())
    _session_action_count = 0
    sid = _session_id
    now = datetime.now()

    def _do():
        conn = _get_conn()
        if not conn:
            return
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO sessions (session_id, start_time) VALUES (%s, %s)",
                    (sid, now)
                )
        except Exception as e:
            logger.warning(f"[analytics] 写入会话开始失败: {e}")
    _run(_do)
    return sid


def end_session():
    global _session_id
    if not _session_id:
        return
    sid = _session_id
    count = _session_action_count
    end_time = datetime.now()

    def _do():
        conn = _get_conn()
        if not conn:
            return
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE sessions
                    SET end_time=%s,
                        action_count=%s,
                        duration_sec=TIMESTAMPDIFF(SECOND, start_time, %s)
                    WHERE session_id=%s
                """, (end_time, count, end_time, sid))
        except Exception as e:
            logger.warning(f"[analytics] 写入会话结束失败: {e}")
    _run(_do)


# ── 事件埋点 ──────────────────────────────────────────────────
def record_event(event_type: str,
                 todo_id: Optional[int] = None,
                 extra: Optional[Dict] = None):
    """
    event_type 枚举：
      todo_created       新建任务
      todo_completed     勾选完成
      todo_uncompleted   取消完成
      todo_deleted       删除任务
      step_completed     子步骤完成
      ai_suggest_used    触发AI建议步骤
      search             执行搜索
      export             导出Excel
      reorder            手动拖拽排序
    """
    global _session_action_count
    if not _session_id:
        return
    _session_action_count += 1

    sid = _session_id
    now = datetime.now()
    extra_json = json.dumps(extra, ensure_ascii=False) if extra else None

    def _do():
        conn = _get_conn()
        if not conn:
            return
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO events (session_id, event_type, event_time, todo_id, extra)"
                    " VALUES (%s,%s,%s,%s,%s)",
                    (sid, event_type, now, todo_id, extra_json)
                )
        except Exception as e:
            logger.warning(f"[analytics] 写入事件失败: {e}")
    _run(_do)


# ── 任务生命周期 ──────────────────────────────────────────────
def on_todo_created(todo: Dict[str, Any]):
    """任务创建时记录初始画像"""
    import time as _t
    today = _t.strftime("%Y-%m-%d")
    due = todo.get("due_date")
    tid = todo["id"]
    priority = todo.get("priority", "mid")
    has_due = 1 if due else 0
    tag_cnt = len(todo.get("tags", []))
    now = datetime.now()

    def _do():
        conn = _get_conn()
        if not conn:
            return
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT IGNORE INTO todo_lifecycle
                    (todo_id, priority, has_due_date, step_count, tag_count, created_at, outcome)
                    VALUES (%s,%s,%s,0,%s,%s,'pending')
                """, (tid, priority, has_due, tag_cnt, now))
        except Exception as e:
            logger.warning(f"[analytics] 写入生命周期(created)失败: {e}")
    _run(_do)


def on_todo_updated(todo: Dict[str, Any], prev_completed: bool):
    """任务更新时同步画像（重点：捕捉完成时刻）"""
    import time as _t
    today = _t.strftime("%Y-%m-%d")
    due = todo.get("due_date")
    tid = todo["id"]
    now = datetime.now()
    newly_completed = todo.get("completed") and not prev_completed
    steps = todo.get("steps", [])

    def _do():
        conn = _get_conn()
        if not conn:
            return
        try:
            with conn.cursor() as cur:
                if newly_completed:
                    cur.execute("""
                        UPDATE todo_lifecycle SET
                            priority=%s,
                            has_due_date=%s,
                            is_overdue=%s,
                            step_count=%s,
                            tag_count=%s,
                            completed_at=%s,
                            completion_days=DATEDIFF(%s, created_at),
                            outcome='completed'
                        WHERE todo_id=%s
                    """, (
                        todo.get("priority", "mid"),
                        1 if due else 0,
                        1 if (due and due < today) else 0,
                        len(steps),
                        len(todo.get("tags", [])),
                        now, now,
                        tid
                    ))
                else:
                    # 仅同步 step_count / tag_count / priority 等变化
                    cur.execute("""
                        UPDATE todo_lifecycle SET
                            priority=%s,
                            has_due_date=%s,
                            step_count=%s,
                            tag_count=%s,
                            outcome=IF(outcome='completed','completed','pending')
                        WHERE todo_id=%s
                    """, (
                        todo.get("priority", "mid"),
                        1 if due else 0,
                        len(steps),
                        len(todo.get("tags", [])),
                        tid
                    ))
        except Exception as e:
            logger.warning(f"[analytics] 写入生命周期(updated)失败: {e}")
    _run(_do)


def on_todo_deleted(todo: Dict[str, Any]):
    """任务删除时标记结局"""
    import time as _t
    today = _t.strftime("%Y-%m-%d")
    tid = todo["id"]
    due = todo.get("due_date")
    now = datetime.now()

    def _do():
        conn = _get_conn()
        if not conn:
            return
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE todo_lifecycle SET
                        is_overdue=%s,
                        deleted_at=%s,
                        outcome=IF(outcome='completed','completed','deleted')
                    WHERE todo_id=%s
                """, (
                    1 if (due and not todo.get("completed") and due < today) else 0,
                    now,
                    tid
                ))
        except Exception as e:
            logger.warning(f"[analytics] 写入生命周期(deleted)失败: {e}")
    _run(_do)


def on_ai_steps_used(todo_id: int):
    """AI建议步骤被使用，标记该任务"""
    def _do():
        conn = _get_conn()
        if not conn:
            return
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE todo_lifecycle SET ai_steps_used=1 WHERE todo_id=%s",
                    (todo_id,)
                )
        except Exception as e:
            logger.warning(f"[analytics] 标记ai_steps_used失败: {e}")
    _run(_do)
