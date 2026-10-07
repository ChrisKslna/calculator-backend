# 简算后端

前后端分离计算器的 Python 后端。通过 HTTP JSON 接收表达式，安全解析并计算；每次成功计算在返回结果前写入 SQLite。提供历史查询、分页和单条删除接口。

## 技术与运行环境

- Python 3.10 及以上；本地验证版本为 3.12.6，目标系统 Ubuntu 22.04。
- Flask 3.1.3、Waitress 3.0.2。
- Python 标准库 sqlite3、decimal、unittest；不依赖外部数据库服务。
- 前端项目：https://github.com/ChrisKslna/calculator-frontend

## 安装

在本仓库根目录运行：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Linux：

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

## 启动

Windows：

```powershell
.\.venv\Scripts\python.exe -m waitress --listen=127.0.0.1:5000 --call src.app:create_app
```

Linux：

```bash
.venv/bin/waitress-serve --listen=127.0.0.1:5000 --call src.app:create_app
```

访问 http://127.0.0.1:5000/api/health 检查服务。根路径没有前端页面，访问根路径返回 JSON 404 属于预期行为。

开发调试也可使用 `python -m flask --app src.app run`。公网部署使用 Waitress + Nginx + systemd，具体步骤见作业交付包的 deploy/README.md。

## 数据库配置与初始化

默认文件为本仓库的 `instance/history.db`，启动时自动创建目录和表；重复启动不会清空历史。每个请求独立连接并关闭连接，使用参数化 SQL 和事务，开启 WAL。

可通过环境变量 `CALCULATOR_DATABASE` 指定绝对路径。生产部署使用代码目录之外的专用数据目录，避免更新代码覆盖历史。

```sql
CREATE TABLE calculation_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    expression TEXT NOT NULL,
    result TEXT NOT NULL,
    created_at TEXT NOT NULL
);
```

结果以文本保存，以保留十进制结果；时间以带 UTC 时区的 ISO 8601 文本保存，前端按浏览器时区展示。本站没有账户系统，访问同一部署实例的用户共享计算历史。数据库文件不提交到 GitHub。

## API

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | /api/health | 检查服务和数据库 |
| POST | /api/calculate | 计算并保存成功记录 |
| GET | /api/history?page=1&page_size=5 | 新记录在前，按页读取 |
| DELETE | /api/history/12 | 按 ID 真正删除指定记录 |

计算请求的 Content-Type 必须为 application/json：

```json
{"expression":"(1+2)*3"}
```

成功响应示例（ID 和时间由实际请求产生）：

```json
{"success":true,"id":1,"expression":"(1+2)*3","result":"9","created_at":"2026-10-06T10:00:00+00:00"}
```

错误示例：

```json
{"success":false,"code":"DIVISION_BY_ZERO","message":"除数不能为 0。","position":2}
```

`result` 为字符串，前端直接显示，不使用浮点转换或本地重新计算。客户端传入的 result 字段会被忽略。`position` 从 1 开始。

历史响应含 `items`、`total`、`page`、`page_size`、`pages`。每页 1 至 100 条，默认 8 条；页码超出范围时回到最后一页。空列表的页码和总页数均为 1。

成功返回 200；输入错误 400；不存在 404；方法错误 405；请求体过大 413；格式错误 415；数据库暂不可用 503。统一返回 JSON。

## 计算规则

支持加减乘除、括号、小数、一元正负号。优先级为括号、正负号、乘除、加减，同级运算从左到右。接受 ×、÷、− 的显示符号。禁止执行用户代码；不使用 eval 或 exec。

使用 Decimal，算术运算和最终结果采用 28 位有效数字、ROUND_HALF_EVEN 舍入。循环小数仍是近似值。最长 500 个字符、括号嵌套最多 50 层。不支持幂、变量、函数、科学计数法、隐式乘法或全角数字。

## 前后端连接

前端独立运行于 8000 端口；本地 serve.py 将 /api/ 转发至 5000。生产环境由 Nginx 提供静态文件并代理 /api/，后端只监听 127.0.0.1:5001。浏览器通过网络接口访问后端，无需跨域配置。

停止后端后，前端仍可输入，但无法计算新结果；不使用 LocalStorage 保存历史。

## 测试

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

34 项测试覆盖基本运算、优先级、输入限制、HTTP 协议、持久化、指定删除、分页、失败不入库及数据库故障。测试使用独立临时数据库，不修改实际历史。

## 目录

- src/app.py：应用工厂和 HTTP 接口。
- src/calculator.py：词法分析、递归下降解析、Decimal 运算。
- src/database.py：SQLite 初始化、增删查。
- tests/：行为测试。
- docs/step-02-calculation.md：计算模块学习说明。
- codestyle.md：代码规范。

## 参考

[Flask 文档](https://flask.palletsprojects.com/en/stable/) · [SQLite 接口](https://docs.python.org/3.12/library/sqlite3.html) · [Decimal](https://docs.python.org/3.12/library/decimal.html) · [Waitress 部署](https://flask.palletsprojects.com/en/stable/deploying/waitress/)
