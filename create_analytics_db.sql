-- ============================================================
-- 轻清单 Todo App — 行为分析数据库
-- 执行方式: mysql -u root -p < create_analytics_db.sql
-- ============================================================

CREATE DATABASE IF NOT EXISTS todo_analytics
    DEFAULT CHARACTER SET utf8mb4
    DEFAULT COLLATE utf8mb4_unicode_ci;

USE todo_analytics;

-- ── 表1: sessions（会话表）─────────────────────────────────
-- 每次启动 App = 一条记录
-- 分析：日均使用时长、使用频率、单次操作密度
DROP TABLE IF EXISTS sessions;
CREATE TABLE sessions (
    id            INT          AUTO_INCREMENT PRIMARY KEY,
    session_id    VARCHAR(36)  NOT NULL          COMMENT '会话UUID',
    start_time    DATETIME     NOT NULL          COMMENT '启动时间',
    end_time      DATETIME                       COMMENT '关闭时间',
    duration_sec  INT                            COMMENT '持续秒数',
    action_count  INT          DEFAULT 0         COMMENT '本次会话操作次数',
    INDEX idx_start (start_time)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
  COMMENT='每次启动App的会话记录';

-- ── 表2: events（操作事件流水）────────────────────────────
-- 所有用户操作的原始记录（核心分析表）
-- 分析：活跃时段、功能使用率、操作频率趋势
DROP TABLE IF EXISTS events;
CREATE TABLE events (
    id          BIGINT       AUTO_INCREMENT PRIMARY KEY,
    session_id  VARCHAR(36)  NOT NULL    COMMENT '关联 sessions.session_id',
    event_type  VARCHAR(50)  NOT NULL    COMMENT '事件类型（见下方枚举）',
    event_time  DATETIME     NOT NULL    COMMENT '事件发生时间',
    todo_id     INT                      COMMENT '关联的任务ID（可为空）',
    extra       JSON                     COMMENT '附加维度数据',
    INDEX idx_time   (event_time),
    INDEX idx_type   (event_type),
    INDEX idx_sess   (session_id),
    INDEX idx_todo   (todo_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
  COMMENT='操作事件流水 — event_type枚举: todo_created|todo_completed|todo_uncompleted|todo_deleted|step_completed|ai_suggest_used|search|export|reorder';

-- ── 表3: todo_lifecycle（任务生命周期）────────────────────
-- 每个任务从创建到完成/删除的完整画像
-- 分析：完成率、平均完成天数、优先级效果、AI功能效果、截止日期效果
DROP TABLE IF EXISTS todo_lifecycle;
CREATE TABLE todo_lifecycle (
    id              INT          AUTO_INCREMENT PRIMARY KEY,
    todo_id         INT          NOT NULL UNIQUE  COMMENT '对应 App 内的任务ID',
    priority        VARCHAR(10)                   COMMENT '优先级: high|mid|low',
    has_due_date    TINYINT(1)   DEFAULT 0        COMMENT '是否设置了截止日期',
    is_overdue      TINYINT(1)   DEFAULT 0        COMMENT '删除/完成时是否已逾期',
    step_count      INT          DEFAULT 0        COMMENT '子步骤数量',
    ai_steps_used   TINYINT(1)   DEFAULT 0        COMMENT '是否使用过AI建议步骤',
    tag_count       INT          DEFAULT 0        COMMENT '标签数量',
    created_at      DATETIME     NOT NULL         COMMENT '任务创建时间',
    completed_at    DATETIME                      COMMENT '完成时间',
    deleted_at      DATETIME                      COMMENT '删除时间',
    completion_days INT                           COMMENT '从创建到完成的天数',
    outcome         VARCHAR(20)  DEFAULT 'pending' COMMENT '结局: pending|completed|deleted',
    INDEX idx_created  (created_at),
    INDEX idx_priority (priority),
    INDEX idx_outcome  (outcome)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
  COMMENT='任务生命周期画像 — 支持完成率/周期/优先级/AI效果分析';


-- ============================================================
-- 常用分析查询示例
-- ============================================================

-- 1. 各功能使用频率排行
-- SELECT event_type, COUNT(*) AS cnt
-- FROM events
-- GROUP BY event_type ORDER BY cnt DESC;

-- 2. 按小时统计活跃度（找出用户最常用的时段）
-- SELECT HOUR(event_time) AS hour, COUNT(*) AS ops
-- FROM events
-- GROUP BY HOUR(event_time) ORDER BY hour;

-- 3. 任务整体完成率
-- SELECT
--     outcome,
--     COUNT(*) AS cnt,
--     ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER(), 1) AS pct
-- FROM todo_lifecycle GROUP BY outcome;

-- 4. 不同优先级的完成率对比
-- SELECT
--     priority,
--     SUM(outcome='completed') AS completed,
--     COUNT(*) AS total,
--     ROUND(SUM(outcome='completed') * 100.0 / COUNT(*), 1) AS complete_rate
-- FROM todo_lifecycle GROUP BY priority;

-- 5. 设截止日期 vs 不设截止日期的完成率
-- SELECT
--     has_due_date,
--     ROUND(SUM(outcome='completed') * 100.0 / COUNT(*), 1) AS complete_rate,
--     COUNT(*) AS total
-- FROM todo_lifecycle GROUP BY has_due_date;

-- 6. 使用AI步骤 vs 不使用的任务完成率
-- SELECT
--     ai_steps_used,
--     ROUND(SUM(outcome='completed') * 100.0 / COUNT(*), 1) AS complete_rate,
--     COUNT(*) AS total
-- FROM todo_lifecycle GROUP BY ai_steps_used;

-- 7. 平均任务完成天数（按优先级）
-- SELECT priority, ROUND(AVG(completion_days), 1) AS avg_days
-- FROM todo_lifecycle WHERE outcome='completed'
-- GROUP BY priority;

-- 8. 日均会话时长（分钟）
-- SELECT DATE(start_time) AS day, ROUND(AVG(duration_sec)/60, 1) AS avg_min
-- FROM sessions WHERE duration_sec IS NOT NULL
-- GROUP BY DATE(start_time) ORDER BY day DESC LIMIT 30;
