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

1. 在「集日」「街段」确认开市日与可用宽度。
2. 在「摊主」「挡柱」维护需求宽度与障碍位置。
3. 打开「分配图」执行一维开间分配。
4. 在「放不下」查看无法安置的摊位。

## 可分配时段

- 每个集日有「可分配时段」（开始/结束时钟，支持跨午夜窗，如 20:00–02:00）；在「集日」页可改时段，保存后所有入口立即按新窗判定。
- 集日页状态、确认分配、试摆、运行条数共用同一套窗内可写判定。
- 当前时刻在窗外时：确认与试摆被后端拒绝（403，报文点明不在可分配时段），运行条数不变；旧运行只读可看，主图仍显示旧色块，但不新增、不改写运行。
- 种子的「周末夜市」时段窗明显不含当前时刻，故初始确认/试摆皆拒；把窗改回覆盖现在即恢复可写，确认一次运行条数 +1。

## 开发与测试

```bash
docker compose exec api pytest -q
```
