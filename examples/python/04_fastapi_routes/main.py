from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI(title="FastAPI Route Types")

# 这里用一个列表临时模拟数据库，方便先学习接口。
# 每个字典就是一条 todo 数据。
# id：唯一编号。
# title：任务标题。
# done：任务是否完成。
todos: list[dict] = [
    {"id": 1, "title": "Learn GET", "done": True},
    {"id": 2, "title": "Learn POST", "done": False},
    {"id": 3, "title": "Learn PUT", "done": False},
]


class TodoCreate(BaseModel):
    # POST /todos 使用这个模型。
    # 新增任务时，客户端只需要传 title，done 默认设为 False。
    title: str


class TodoUpdate(BaseModel):
    # PUT /todos/{todo_id} 使用这个模型。
    # PUT 表示“整体替换”，所以 title 和 done 都必须传。
    title: str
    done: bool


class TodoPatch(BaseModel):
    # PATCH /todos/{todo_id} 使用这个模型。
    # PATCH 表示“局部修改”，所以字段都可以不传。
    title: str | None = None
    done: bool | None = None


@app.get("/todos")
def list_todos(done: bool | None = None,keyword: str | None = None) -> dict:
    # done 是查询参数。
    # 访问 /todos?done=true 时，只返回已完成任务。
    # 访问 /todos?done=false 时，只返回未完成任务。
    # 如果不传 done，就返回全部任务。
    if done is None and keyword is None:
        return {"items": todos}
    if done is None:
        filtered = [todo for todo in todos if keyword.lower() in todo["title"].lower()]
        return {"items": filtered}
    if keyword is None:
        filtered = [todo for todo in todos if todo["done"] == done]
        return {"items": filtered}
    filtered = [todo for todo in todos if todo["done"] == done and keyword.lower() in todo["title"].lower()]
    return {"items": filtered}

    


@app.get("/todos/{todo_id}")
def get_todo(todo_id: int) -> dict:
    # todo_id 是路径参数。
    # 访问 /todos/1 时，todo_id 的值就是 1。
    for todo in todos:
        if todo["id"] == todo_id:
            return todo

    # 如果找不到对应 id，就返回 404。
    raise HTTPException(status_code=404, detail="Todo not found")

@app.get("/stats")
def get_stats() -> dict:
    total_all = len(todos)
    total_done = sum(1 for todo in todos if todo["done"])
    return {
        "total": total_all,
        "done": total_done,}

@app.post("/todos")
def create_todo(payload: TodoCreate) -> dict:
    # payload 是请求体，也就是客户端传来的 JSON。
    # 这里期望的 JSON 格式是：{"title": "..."}
    # POST 通常用于新增资源。
    next_id = max(todo["id"] for todo in todos) + 1
    new_todo = {"id": next_id, "title": payload.title, "done": False}
    todos.append(new_todo)
    return new_todo


@app.put("/todos/{todo_id}")
def replace_todo(todo_id: int, payload: TodoUpdate) -> dict:
    # todo_id 来自 URL 路径。
    # payload 来自请求体 JSON。
    # 这里期望的 JSON 格式是：{"title": "...", "done": true}
    # PUT 通常用于整体替换资源。
    for todo in todos:
        if todo["id"] == todo_id:
            todo["title"] = payload.title
            todo["done"] = payload.done
            return todo

    raise HTTPException(status_code=404, detail="Todo not found")


@app.patch("/todos/{todo_id}")
def patch_todo(todo_id: int, payload: TodoPatch) -> dict:
    # PATCH 通常只更新客户端传来的字段。
    # 客户端可以只传 title，只传 done，也可以两个都传。
    # 示例：{"done": true}
    for todo in todos:
        if todo["id"] == todo_id:
            if payload.title is not None:
                todo["title"] = payload.title
            if payload.done is not None:
                todo["done"] = payload.done
            return todo

    raise HTTPException(status_code=404, detail="Todo not found")


@app.delete("/todos/{todo_id}")
def delete_todo(todo_id: int) -> dict:
    # DELETE 根据 id 删除一条资源。
    # enumerate 会同时给出索引和数据，方便用 pop(index) 删除。
    for index, todo in enumerate(todos):
        if todo["id"] == todo_id:
            removed = todos.pop(index)
            return {"deleted": removed}

    raise HTTPException(status_code=404, detail="Todo not found")
