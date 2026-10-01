# StallSpan 市集摊档开间

沿街段一维 First-Fit 开间分配，挡柱不可被摊位跨越，输出分配图与放不下清单。

技术栈：Python 3.12 / FastAPI / SQLAlchemy / PostgreSQL / Vue 3 / TypeScript / Vite

## 启动

```bash
docker compose up --build
```

| 服务 | 地址 |
| --- | --- |
| 前端 | http://localhost:4700 |
| API | http://localhost:9700 |
| API 文档 | http://localhost:9700/docs |
| Postgres | localhost:5448 |

健康检查：`GET http://localhost:9700/api/health`

## 使用说明

1. 在「集日」设置开市日期与**可分配时段（开始/结束时钟）**，页面即时显示窗内/窗外。
2. 在「街段」确认可用宽度，在「摊主」「挡柱」维护需求宽度与障碍位置。
3. 打开「分配图」：窗内可「试摆」（不落库）与「确认开市」（新增一条运行）；
   窗外两者都被后端拒绝（403，提示不在可分配时段），旧运行只读可看、不可新增或改写。
4. 在「放不下」查看无法安置的摊位（读旧运行，窗外亦可打开）。

> 窗内可写判定全应用只有一套口径（`app/services/window.py`）：集日页、确认、试摆、运行条数均以服务器当前墙钟与该集日时段比较；改完时段立即按新窗判定。

## 开发与测试

```bash
docker compose exec api pytest -q
```
