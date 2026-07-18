# FastAPI 接口类型练习

启动服务：

```powershell
cd C:\Users\wsdjx\Desktop\learn\examples\python\04_fastapi_routes
python -m uvicorn main:app --reload
```

打开接口文档：

```text
http://127.0.0.1:8000/docs
```

## 这次要学什么

`GET` 表示查询数据。

```text
GET /todos
GET /todos/1
```

`POST` 表示新增数据。

```text
POST /todos
```

`PUT` 表示整体替换一条数据。

```text
PUT /todos/1
```

`PATCH` 表示局部修改一条数据。

```text
PATCH /todos/1
```

`DELETE` 表示删除数据。

```text
DELETE /todos/1
```

## 三种参数来源

路径参数：

```text
/todos/1
```

这里的 `1` 会传给代码里的 `todo_id`。

查询参数：

```text
/todos?done=true
```

这里的 `done=true` 会传给代码里的 `done`。

请求体：

```json
{
  "title": "Learn FastAPI routes"
}
```

这种 JSON 数据常用于 `POST`、`PUT`、`PATCH`。

## 本课练习

1. 在 `todos` 列表里手动加一条初始数据。
2. 给 `GET /todos` 增加一个 `keyword` 查询参数，按标题搜索。
3. 新增一个 `GET /stats` 接口，返回总任务数和已完成任务数。
4. 在 `/docs` 页面分别测试 `POST`、`PUT`、`PATCH`、`DELETE`。
