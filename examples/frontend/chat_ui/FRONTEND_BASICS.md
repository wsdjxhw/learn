# 前端最小基础

这个文件只讲本模块需要的最小前端知识。

如果你之前主要写 Python 或 Java，可以先把浏览器页面理解成：

```text
HTML 是结构
CSS 是样式
JavaScript 是行为
```

## HTML 解决什么问题

HTML 负责告诉浏览器页面上有哪些东西。

比如本模块的 `static/index.html` 里有：

```html
<nav class="session-list" id="session-list"></nav>
<section class="message-list" id="message-list"></section>
<textarea id="message-input"></textarea>
```

可以理解成先在页面上放好几个“容器”：

- `session-list`：放会话列表。
- `message-list`：放消息历史。
- `message-input`：输入用户消息。

这些容器一开始可以是空的，后面由 JavaScript 调接口拿数据，再填进去。

## CSS 解决什么问题

CSS 负责页面长什么样。

比如 `static/styles.css` 里：

```css
.app-shell {
  display: grid;
  grid-template-columns: 280px minmax(0, 1fr) 320px;
}
```

这表示页面使用三列布局：

```text
左侧会话列表 | 中间聊天区 | 右侧任务和 sources
```

CSS 不负责请求后端，也不负责保存数据。它只负责布局、颜色、间距、字体和响应式适配。

## JavaScript 解决什么问题

JavaScript 负责页面行为。

本模块的 `static/app.js` 做这些事：

```text
调用后端 API
把接口返回的数据渲染到页面
监听按钮点击
监听表单提交
轮询任务状态
更新 sources 面板
```

如果类比后端：

```text
HTML 像页面模板
CSS 像样式配置
JavaScript 像浏览器里的 Controller
```

## DOM 是什么

DOM 可以理解成浏览器把 HTML 解析后得到的页面对象树。

JavaScript 可以通过 `document.getElementById()` 找到页面上的某个元素：

```javascript
const messageList = document.getElementById("message-list");
```

然后修改它：

```javascript
messageList.innerHTML = "";
```

这表示清空消息列表区域。

## 事件是什么

用户点击按钮、提交表单、输入文字，都会产生事件。

本模块里：

```javascript
composer.addEventListener("submit", sendMessage);
```

意思是：

```text
当发送表单被提交时，执行 sendMessage 函数
```

这和后端接口被 HTTP 请求触发有点像，只不过这里的触发来源是浏览器里的用户操作。

## `fetch()` 是什么

`fetch()` 是浏览器自带的 HTTP 请求函数。

本模块里封装了：

```javascript
async function api(path, options = {}) {
  const response = await fetch(path, ...);
  return response.json();
}
```

之后页面调用：

```javascript
const payload = await api("/api/sessions");
```

就等于浏览器请求后端：

```text
GET /api/sessions
```

## `async` 和 `await` 是什么

请求后端需要等待网络返回。

`async` 和 `await` 可以让异步代码读起来像同步流程：

```javascript
const payload = await api("/api/sessions");
renderSessions(payload.items);
```

意思是：

```text
先等接口返回
再用返回数据渲染页面
```

如果不等待，页面可能会在数据还没回来时就开始渲染，结果就是空数据或报错。

## 前端状态 `state`

`app.js` 开头有：

```javascript
const state = {
  sessions: [],
  activeSessionId: null,
  pollingTimer: null,
};
```

它保存页面当前状态：

- `sessions`：当前会话列表。
- `activeSessionId`：当前选中的会话。
- `pollingTimer`：当前是否正在轮询任务。

这不是数据库，只是浏览器内存里的临时状态。刷新页面后会重新从后端加载。

## 渲染是什么

渲染就是把数据变成页面元素。

比如后端返回：

```json
{"title": "学习聊天", "message_count": 2}
```

`renderSessions()` 会把它变成左侧的一个会话按钮。

这个过程可以理解成：

```text
后端 JSON -> JavaScript 对象 -> HTML 元素 -> 浏览器显示
```

## 本模块的完整前端链路

页面打开：

```text
GET / -> index.html
加载 styles.css
加载 app.js
app.js 调 GET /api/sessions
渲染会话列表
选中默认会话
调 GET /api/sessions/{id}/messages
渲染消息历史
```

用户发送消息：

```text
submit 表单
POST /api/sessions/{id}/messages
后端返回 task_id
前端开始 pollTask(task_id)
GET /api/tasks/{task_id}
任务 succeeded
刷新消息历史
展示 sources
```

这就是本模块真正要学的内容。

## 为什么现在不直接上 React

React、Vue 这类框架能让复杂前端更好维护，但它们会引入很多新概念：

```text
组件
props
state
构建工具
npm
前端路由
状态管理
```

当前阶段的目标是先理解“前端如何调用后端并更新页面”。等这条链路清楚后，再上框架会更稳。
