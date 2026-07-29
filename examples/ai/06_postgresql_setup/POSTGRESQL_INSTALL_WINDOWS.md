# Windows 安装 PostgreSQL 和首次配置

这份文档解决一个前置问题：

```text
我电脑上还没有 PostgreSQL，怎么下载安装并让本模块连上？
```

如果你已经安装过 PostgreSQL，可以跳过安装部分，直接看“创建 ai_learn 数据库”和“连接本模块”。

## 先说结论

Windows 零基础建议使用 PostgreSQL 官方下载页提供的图形化安装程序。

官方下载入口：

[https://www.postgresql.org/download/](https://www.postgresql.org/download/)

Windows 安装页：

[https://www.postgresql.org/download/windows/](https://www.postgresql.org/download/windows/)

PostgreSQL 官方 Windows 页面说明，EDB 提供的交互式安装程序会包含：

- PostgreSQL Server
- pgAdmin 图形化管理工具
- StackBuilder 附加工具管理器

学习本项目时，你主要需要：

- PostgreSQL Server
- pgAdmin
- `psql` 命令行工具

StackBuilder 初学阶段可以先不使用。

## 版本怎么选

下载页面可能会出现多个版本。

建议：

- 选择当前仍受支持的稳定版本。
- 不要选择 Beta、RC、development snapshot 这类测试版。
- 如果你不确定，选择下载页默认推荐的稳定版本即可。

原因：

```text
本项目学习的是连接、建库、建表、SQLAlchemy 切换数据库。
这些基础能力不依赖最新版本特性。
```

## 安装时要记住的几个选项

安装程序会让你选择或填写一些东西。

### 安装目录

默认即可，例如：

```text
C:\Program Files\PostgreSQL\版本号
```

你不需要手动改。

### Data Directory

这是 PostgreSQL 保存数据库文件的目录。

默认即可。

注意：它不是本项目代码目录。

可以理解成：

```text
PostgreSQL 自己保存数据的地方
```

### Password

这里通常是给默认超级用户 `postgres` 设置密码。

一定要记住这个密码。

后面 `.env` 里的连接串要用它：

```text
DATABASE_URL=postgresql+psycopg://postgres:你的密码@localhost:5432/ai_learn
```

学习阶段可以设置一个简单但你能记住的密码。

正式项目不要使用过于简单的密码。

### Port

默认端口通常是：

```text
5432
```

建议保持默认。

如果安装程序提示 `5432` 被占用，你可能会改成 `5433` 或其他端口。

那后面的 `DATABASE_URL` 也必须同步改端口：

```text
DATABASE_URL=postgresql+psycopg://postgres:你的密码@localhost:5433/ai_learn
```

### Locale

默认即可。

初学阶段不需要在这里做复杂设置。

## 安装完成后确认服务是否启动

PostgreSQL 安装完成后，本质上会在 Windows 里运行一个服务。

你可以用两种方式确认。

## 方法一：服务管理器

按 `Win + R`，输入：

```text
services.msc
```

找到类似：

```text
postgresql-x64-版本号
```

确认它的状态是“正在运行”。

如果没运行，右键启动。

## 方法二：PowerShell

在 PowerShell 里执行：

```powershell
Get-Service *postgres*
```

如果看到状态是 `Running`，说明服务正在运行。

如果是 `Stopped`，可以先在服务管理器里启动。

## 打开 pgAdmin

pgAdmin 是图形化数据库管理工具。

安装完成后，可以从开始菜单打开：

```text
pgAdmin
```

第一次打开可能会让你设置 pgAdmin 自己的主密码。

注意区分两个密码：

```text
PostgreSQL postgres 用户密码：数据库连接用
pgAdmin 主密码：打开 pgAdmin 工具用
```

它们可以相同，也可以不同。

## 连接本机 PostgreSQL

pgAdmin 左侧通常会有一个 Servers 节点。

展开本地服务器时，如果提示输入密码，输入你安装时给 `postgres` 用户设置的密码。

连接成功后，你应该能看到类似结构：

```text
Servers
-> PostgreSQL 版本号
-> Databases
```

## 创建 ai_learn 数据库

本模块示例使用的数据库名是：

```text
ai_learn
```

你需要先创建它。

### 用 pgAdmin 创建

1. 展开左侧服务器。
2. 找到 `Databases`。
3. 右键 `Databases`。
4. 选择 `Create` -> `Database...`。
5. Database 名称填写：

```text
ai_learn
```

6. Owner 选择：

```text
postgres
```

7. 保存。

创建完成后，左侧应该能看到：

```text
Databases
-> ai_learn
```

### 用 psql 创建

如果你想练命令行，可以使用 `psql`。

如果 `psql` 已加入 PATH，可以执行：

```powershell
psql -U postgres
```

如果提示找不到 `psql`，可以使用完整路径，版本号按你安装的目录替换：

```powershell
& "C:\Program Files\PostgreSQL\版本号\bin\psql.exe" -U postgres
```

输入密码后，在 `psql` 里执行：

```sql
CREATE DATABASE ai_learn;
```

然后退出：

```sql
\q
```

## 配置本模块的 .env

进入本模块目录：

```powershell
cd C:\Users\wsdjx\Desktop\learn\examples\ai\06_postgresql_setup
```

如果还没有 `.env`，先复制：

```powershell
Copy-Item .env.example .env
```

打开 `.env`，把 SQLite 连接串：

```text
DATABASE_URL=sqlite:///./postgresql_setup.db
```

改成 PostgreSQL：

```text
DATABASE_URL=postgresql+psycopg://postgres:你的密码@localhost:5432/ai_learn
```

例如你的密码是 `123456`：

```text
DATABASE_URL=postgresql+psycopg://postgres:123456@localhost:5432/ai_learn
```

如果你安装时端口不是 `5432`，这里也要同步改。

## 密码里有特殊字符怎么办

如果密码包含这些字符：

```text
@ / : # ? & %
```

连接串可能会解析失败。

最简单的学习方案：

```text
先把 postgres 用户密码设置成不含特殊字符的密码
```

例如只使用字母和数字。

后续真正做项目时，再学习 URL 编码和更安全的密钥管理。

## 启动本模块并验证

安装依赖：

```powershell
python -m pip install -r requirements.txt
```

启动服务：

```powershell
python -m uvicorn main:app --reload
```

打开：

```text
http://127.0.0.1:8000/docs
```

按顺序测试：

1. `GET /health`
2. `GET /db/health`
3. `POST /setup/create-tables`
4. `GET /db/tables`
5. `POST /notes`
6. `GET /notes`

## 你应该看到什么

`GET /db/health` 成功时，应该看到：

```json
{
  "ok": true,
  "database_kind": "postgresql",
  "driver": "psycopg",
  "current_database": "ai_learn",
  "current_schema": "public"
}
```

重点看：

- `ok` 是 `true`。
- `database_kind` 是 `postgresql`。
- `current_database` 是 `ai_learn`。

如果 `database_kind` 还是 `sqlite`，说明 `.env` 没改成功，或者改完没有重启 `uvicorn`。

`GET /db/tables` 成功时，应该能看到：

```text
database_notes
```

这说明本模块的表已经在 PostgreSQL 里创建成功。

## 安装后最常见的问题

### `psql` 不是内部或外部命令

含义：

```text
psql 没有加入 PATH
```

处理方式：

- 用完整路径运行 `psql.exe`。
- 或者暂时只用 pgAdmin，不强制使用命令行。

### `connection refused`

含义：

```text
PostgreSQL 服务没启动，或者端口写错
```

检查：

- `services.msc` 里 PostgreSQL 是否正在运行。
- `.env` 里的端口是否和安装时一致。

### `password authentication failed`

含义：

```text
用户名或密码错误
```

检查：

- `.env` 里的用户名是否是 `postgres`。
- 密码是否是安装时设置的密码。
- 密码是否包含特殊字符。

### `database "ai_learn" does not exist`

含义：

```text
PostgreSQL 服务连上了，但 ai_learn 数据库还没创建
```

处理：

- 用 pgAdmin 创建 `ai_learn`。
- 或用 `psql` 执行 `CREATE DATABASE ai_learn;`。

### `relation "database_notes" does not exist`

含义：

```text
数据库存在，但表还没创建
```

处理：

```text
POST /setup/create-tables
```

然后再调用：

```text
GET /db/tables
```

确认表出现。

## 安装完成后的最小验收标准

你不需要掌握所有 PostgreSQL 管理能力。

本节只要求做到：

- PostgreSQL 服务能启动。
- pgAdmin 能连上本机服务器。
- 能创建 `ai_learn` 数据库。
- `.env` 能切到 PostgreSQL。
- `GET /db/health` 返回 `database_kind: postgresql`。
- `POST /setup/create-tables` 能创建表。
- `POST /notes` 和 `GET /notes` 能写入和读取数据。

达到这些，就足够继续学习下一节 Alembic。
