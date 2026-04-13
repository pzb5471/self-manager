# 个人统计周报 API 规范

## 目标

为已登录用户提供最近 7 天的个人统计周报，统一聚合以下数据：

- 任务完成情况
- 四象限与分类分布
- 番茄专注统计
- 工位打卡与克制玩手机记录
- 本周亮点与待改进项

该文档是前后端并行开发时唯一的接口契约来源。

## Endpoint

`GET /api/reports/weekly`

## Query Parameters

| 参数 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `end_date` | `string` | 否 | 当天 | 周报统计结束日期，格式 `YYYY-MM-DD` |
| `days` | `int` | 否 | `7` | 统计窗口，当前版本固定支持 `1-31`，前端默认传 `7` |

## Authentication

- 必须携带 `Authorization: Bearer <token>`
- 未登录返回 `401`

## Response Shape

```json
{
  "ok": true,
  "report": {
    "range": {
      "start_date": "2026-04-06",
      "end_date": "2026-04-12",
      "days": 7,
      "label": "2026-04-06 ~ 2026-04-12"
    },
    "summary": {
      "tasks_created": 4,
      "tasks_completed": 3,
      "completion_rate": 75,
      "focus_minutes": 150,
      "focus_sessions": 5,
      "checkin_days": 4,
      "full_checkin_days": 2,
      "phone_focus_minutes": 95,
      "phone_focus_sessions": 3
    },
    "tasks": {
      "created": 4,
      "completed": 3,
      "completion_rate": 75,
      "by_quadrant": {
        "1": 1,
        "2": 2,
        "3": 1,
        "4": 0
      },
      "by_category": {
        "工作": 2,
        "学习": 1,
        "生活": 1,
        "健康": 0
      },
      "top_completed_titles": [
        "完成接口设计",
        "整理每周复盘",
        "周会准备"
      ]
    },
    "pomodoro": {
      "focus_minutes": 150,
      "focus_sessions": 5,
      "completed_sessions": 7,
      "by_date": [
        { "date": "2026-04-06", "focus_minutes": 30, "focus_sessions": 1 },
        { "date": "2026-04-07", "focus_minutes": 0, "focus_sessions": 0 }
      ]
    },
    "habits": {
      "checkin_days": 4,
      "full_checkin_days": 2,
      "phone_focus_minutes": 95,
      "phone_focus_sessions": 3,
      "checkins_by_date": [
        { "date": "2026-04-06", "period_count": 3, "is_full": true },
        { "date": "2026-04-07", "period_count": 1, "is_full": false }
      ],
      "phone_focus_by_date": [
        { "date": "2026-04-06", "minutes": 30, "sessions": 1 },
        { "date": "2026-04-07", "minutes": 0, "sessions": 0 }
      ]
    },
    "insights": {
      "highlight": "本周完成 3 个任务，任务完成率 75%。",
      "focus": "本周累计专注 150 分钟，共完成 5 次专注番茄。",
      "habit": "本周有 4 天完成工位打卡，其中 2 天达成三段全勤。",
      "improvement": "第二象限任务占比更高，建议继续保持长期重要事项投入。"
    }
  }
}
```

## 字段口径

### range

- `start_date`: 统计开始日期，包含
- `end_date`: 统计结束日期，包含
- `days`: 实际统计天数
- `label`: 前端直接展示使用

### summary

- `tasks_created`: 时间窗口内创建的任务数
- `tasks_completed`: 时间窗口内“已完成任务”数量
- `completion_rate`: `tasks_completed / max(tasks_created, tasks_completed, 1)` 后取整百分比
- `focus_minutes`: 时间窗口内已完成 `work` 类型番茄的分钟数
- `focus_sessions`: 时间窗口内已完成 `work` 类型番茄次数
- `checkin_days`: 至少完成 1 次工位打卡的天数
- `full_checkin_days`: 完成早/中/晚三段打卡的天数
- `phone_focus_minutes`: 克制玩手机累计分钟数
- `phone_focus_sessions`: 克制玩手机记录条数

### tasks

- 任务统计窗口使用：
  - `created_at` 落在时间窗口内的任务，计入 `created`、`by_quadrant`、`by_category`
  - 同一窗口内 `completed = true` 的任务计入 `completed`
- `top_completed_titles` 最多返回 3 条，按 `updated_at DESC, id DESC`

### pomodoro

- 仅统计 `session_type = work AND completed = true`
- `by_date` 必须补齐整个日期窗口，没有数据的日期返回 0

### habits

- `checkins_by_date`、`phone_focus_by_date` 必须补齐整个日期窗口
- `period_count` 取值范围 `0-3`
- `is_full = period_count == 3`

### insights

- 后端生成面向中文用户的简短文案
- 所有字段都必须返回字符串，即使数据较少也要给出可读描述

## Error Response

```json
{
  "detail": "start_date must not be later than end_date"
}
```

可能的错误码：

- `400`: 日期参数非法、`days` 超范围
- `401`: 未登录

## 前端集成约定

- 将周报入口放入现有静态前端导航
- 默认读取 `GET /api/reports/weekly`
- 支持手动切换 `end_date`
- 页面至少展示：
  - 周报摘要指标
  - 任务、番茄、习惯三块统计
  - 每日趋势
  - `insights` 文案

## 测试约定

- 单测放到 `tests/unit/`
- 后端至少覆盖：
  - 周报聚合正确性
  - 日期补齐逻辑
  - 鉴权与参数校验
