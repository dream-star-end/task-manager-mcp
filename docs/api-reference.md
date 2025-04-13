# 任务管理MCP服务API参考

本文档详细说明了任务管理MCP服务提供的所有API，包括参数、返回值和示例。

## 工具列表

| 工具ID | 功能描述 |
|---------|---------|
| `decompose_prd` | 解析PRD文档，自动拆解为任务列表 |
| `add_task` | 创建新任务 |
| `update_task` | 更新现有任务信息，包括标记任务为完成 |
| `set_task_dependency` | 设置任务依赖关系 |
| `get_task_list` | 获取任务列表 |
| `get_next_executable_task` | 获取下一个可执行任务 |
| `expand_task` | 为指定任务生成子任务 |
| `update_task_code_references` | 更新任务的代码引用 |
| `use_description` | 获取所有工具的描述和参数信息 |

## 详细API说明

### decompose_prd

解析PRD文档，自动拆解为任务列表。

**参数：**

| 参数名 | 类型 | 必填 | 说明 |
|-------|------|-----|-----|
| `prd_content` | string | 是 | PRD文档内容或资源标识符 |

**返回值：**

```json
[
  {
    "id": "task-a1b2c3d4",
    "name": "实现用户登录功能",
    "description": "开发用户登录界面和后端验证",
    "status": "todo",
    "depends_on": [],
    "subtasks": ["task-e5f6g7h8"],
    "parent_task": null,
    "code_files": [],
    "created_at": "2025-03-31T14:30:00Z",
    "updated_at": "2025-03-31T14:30:00Z"
  },
  ...
]
```

**示例调用：**

```
<mcp:tool name="decompose_prd">
<mcp:parameter name="prd_content">file://path/to/prd.md</mcp:parameter>
</mcp:tool>
```

**Cursor IDE中的调用：**
```
@task-manager 解析这个PRD文档：file://path/to/prd.md
```

### add_task

创建新任务。

**参数：**

| 参数名 | 类型 | 必填 | 说明 |
|-------|------|-----|-----|
| `name` | string | 是 | 任务名称 |
| `description` | string | 否 | 任务描述 |
| `depends_on` | array | 否 | 依赖任务ID列表 |
| `parent_task` | string | 否 | 父任务ID |

**返回值：**

```json
{
  "id": "task-i9j0k1l2",
  "name": "实现用户注册功能",
  "description": "开发用户注册界面和后端处理",
  "status": "todo",
  "depends_on": ["task-a1b2c3d4"],
  "subtasks": [],
  "parent_task": null,
  "code_files": [],
  "created_at": "2025-03-31T15:00:00Z",
  "updated_at": "2025-03-31T15:00:00Z"
}
```

**示例调用：**

```
<mcp:tool name="add_task">
<mcp:parameter name="name">实现用户注册功能</mcp:parameter>
<mcp:parameter name="description">开发用户注册界面和后端处理</mcp:parameter>
<mcp:parameter name="depends_on">["task-a1b2c3d4"]</mcp:parameter>
</mcp:tool>
```

**Cursor IDE中的调用：**
```
@task-manager 创建一个新任务：实现用户注册功能，包括注册界面和后端验证
```

### update_task

更新现有任务信息，包括标记任务为完成。

**参数：**

| 参数名 | 类型 | 必填 | 说明 |
|-------|------|-----|-----|
| `task_id` | string | 是 | 任务ID |
| `name` | string | 否 | 新任务名称 |
| `description` | string | 否 | 新任务描述 |
| `status` | string | 否 | 新任务状态，包括标记任务为完成(`done`)、进行中(`in_progress`)、阻塞(`blocked`)或取消(`cancelled`) |
| `priority` | string | 否 | 新的任务优先级 (low, medium, high, critical) |
| `tags` | string | 否 | 新的任务标签，多个标签以逗号分隔 |
| `assigned_to` | string | 否 | 新的任务负责人 |
| `estimated_hours` | string | 否 | 新的预估工时 |
| `actual_hours` | string | 否 | 实际工时 |

**返回值：**

```json
{
  "id": "task-a1b2c3d4",
  "name": "实现用户登录功能",
  "description": "开发用户登录界面和后端验证 [CODE_FILES: src/auth/login.py, src/models/user.py]",
  "status": "done",
  "dependencies": [],
  "subtasks": ["task-e5f6g7h8"],
  "parent_task_id": null,
  "code_references": ["src/auth/login.py", "src/models/user.py"],
  "created_at": "2025-03-31T14:30:00Z",
  "updated_at": "2025-03-31T16:30:00Z"
}
```

**示例调用：**

```
<mcp:tool name="update_task">
<mcp:parameter name="task_id">task-a1b2c3d4</mcp:parameter>
<mcp:parameter name="status">done</mcp:parameter>
<mcp:parameter name="description">开发用户登录界面和后端验证 [CODE_FILES: src/auth/login.py, src/models/user.py]</mcp:parameter>
<mcp:parameter name="actual_hours">4.5</mcp:parameter>
</mcp:tool>
```

**Cursor IDE中的调用：**
```
@task-manager 将任务task-a1b2c3d4标记为完成，实现代码在src/auth/login.py和src/models/user.py，实际用时4.5小时
```

### set_task_dependency

设置任务依赖关系。

**参数：**

| 参数名 | 类型 | 必填 | 说明 |
|-------|------|-----|-----|
| `task_id` | string | 是 | 任务ID |
| `depends_on` | array | 是 | 依赖任务ID列表 |

**返回值：**

```json
{
  "id": "task-i9j0k1l2",
  "name": "实现用户注册功能",
  "description": "开发用户注册界面和后端处理",
  "status": "todo",
  "depends_on": ["task-a1b2c3d4", "task-m3n4o5p6"],
  "subtasks": [],
  "parent_task": null,
  "code_files": [],
  "created_at": "2025-03-31T15:00:00Z",
  "updated_at": "2025-03-31T15:10:00Z"
}
```

**示例调用：**

```
<mcp:tool name="set_task_dependency">
<mcp:parameter name="task_id">task-i9j0k1l2</mcp:parameter>
<mcp:parameter name="depends_on">["task-a1b2c3d4", "task-m3n4o5p6"]</mcp:parameter>
</mcp:tool>
```

**Cursor IDE中的调用：**
```
@task-manager 设置任务task-i9j0k1l2依赖于task-a1b2c3d4和task-m3n4o5p6
```

### get_task_list

获取任务列表。

**参数：**

| 参数名 | 类型 | 必填 | 说明 |
|-------|------|-----|-----|
| `status` | string | 否 | 按状态筛选 |
| `parent_task` | string | 否 | 按父任务筛选 |

**返回值：**

```json
[
  {
    "id": "task-a1b2c3d4",
    "name": "实现用户登录功能",
    "description": "开发用户登录界面和后端验证",
    "status": "done",
    "depends_on": [],
    "subtasks": ["task-e5f6g7h8"],
    "parent_task": null,
    "code_files": ["src/auth/login.py", "src/models/user.py"],
    "created_at": "2025-03-31T14:30:00Z",
    "updated_at": "2025-03-31T16:30:00Z"
  },
  {
    "id": "task-i9j0k1l2",
    "name": "实现用户注册功能",
    "description": "开发用户注册界面和后端处理",
    "status": "todo",
    "depends_on": ["task-a1b2c3d4", "task-m3n4o5p6"],
    "subtasks": [],
    "parent_task": null,
    "code_files": [],
    "created_at": "2025-03-31T15:00:00Z",
    "updated_at": "2025-03-31T15:10:00Z"
  }
]
```

**示例调用：**

```
<mcp:tool name="get_task_list">
<mcp:parameter name="status">todo</mcp:parameter>
</mcp:tool>
```

**Cursor IDE中的调用：**
```
@task-manager 获取所有待办任务
```

### get_next_executable_task

获取下一个可执行任务。此接口只返回一个最优先的任务，而不是任务列表。

**参数：**

| 参数名 | 类型 | 必填 | 说明 |
|-------|------|-----|-----|
| `limit` | string | 否 | 内部查询任务的数量限制，默认为5。该参数仅影响内部查询流程，最终只会返回一个任务。 |

**返回值：**

返回一个最优先的可执行任务对象，如果没有可执行的任务，则返回空结果。

```json
{
  "success": true,
  "found": true,
  "task": {
    "id": "task-i9j0k1l2",
    "name": "实现用户注册功能",
    "description": "开发用户注册界面和后端处理",
    "status": "todo",
    "priority": "high",
    "dependencies": ["task-a1b2c3d4"],
    "blocked_by": [],
    "subtasks": [],
    "parent_task_id": null,
    "code_references": [],
    "complexity": "medium",
    "estimated_hours": 8,
    "created_at": "2025-03-31T15:00:00Z",
    "updated_at": "2025-03-31T15:10:00Z"
  }
}
```

如果没有找到可执行任务：

```json
{
  "success": true,
  "found": false,
  "message": "没有找到可执行的任务"
}
```

**示例调用：**

```
<mcp:tool name="get_next_executable_task">
<mcp:parameter name="limit">3</mcp:parameter>
</mcp:tool>
```

**Cursor IDE中的调用：**
```
@task-manager 获取下一个可执行的任务
```

### expand_task

为指定任务生成子任务。

**参数：**

| 参数名 | 类型 | 必填 | 说明 |
|-------|------|-----|-----|
| `task_id` | string | 是 | 要展开的任务ID |
| `num_subtasks` | string | 否 | 希望生成的子任务数量，默认为5 |

**返回值：**

```json
{
  "success": true,
  "parent_task": {
    "id": "task-a1b2c3d4",
    "name": "实现用户登录功能",
    "description": "开发用户登录界面和后端验证",
    "status": "todo",
    "priority": "high",
    "dependencies": [],
    "blocked_by": [],
    "subtasks": [
      {
        "id": "task-a1b2c3d4.1",
        "name": "设计登录界面",
        "description": "设计用户友好的登录界面",
        "status": "todo",
        "priority": "high",
        "dependencies": [],
        "parent_task_id": "task-a1b2c3d4",
        "complexity": "medium",
        "estimated_hours": 4,
        "created_at": "2025-03-31T14:35:00Z",
        "updated_at": "2025-03-31T14:35:00Z"
      },
      // 更多子任务...
    ],
    "created_at": "2025-03-31T14:30:00Z",
    "updated_at": "2025-03-31T14:35:00Z"
  },
  "subtasks": [
    // 子任务列表，格式与parent_task中的subtasks相同
  ]
}
```

**示例调用：**

```
<mcp:tool name="expand_task">
<mcp:parameter name="task_id">task-a1b2c3d4</mcp:parameter>
<mcp:parameter name="num_subtasks">3</mcp:parameter>
</mcp:tool>
```

**Cursor IDE中的调用：**
```
@task-manager 为任务task-a1b2c3d4生成3个子任务
```

### update_task_code_references

更新任务的代码引用。

**参数：**

| 参数名 | 类型 | 必填 | 说明 |
|-------|------|-----|-----|
| `task_id` | string | 是 | 任务ID |
| `code_references` | array | 是 | 新的代码引用列表 |

**返回值：**

```json
{
  "id": "task-a1b2c3d4",
  "name": "实现用户登录功能",
  "description": "开发用户登录界面和后端验证 [CODE_FILES: src/auth/login.py, src/models/user.py]",
  "status": "done",
  "depends_on": [],
  "subtasks": ["task-e5f6g7h8"],
  "parent_task": null,
  "code_files": ["src/auth/login.py", "src/models/user.py"],
  "created_at": "2025-03-31T14:30:00Z",
  "updated_at": "2025-03-31T16:30:00Z"
}
```

**示例调用：**

```
<mcp:tool name="update_task_code_references">
<mcp:parameter name="task_id">task-a1b2c3d4</mcp:parameter>
<mcp:parameter name="code_references">["src/auth/login.py", "src/models/user.py"]</mcp:parameter>
</mcp:tool>
```

**Cursor IDE中的调用：**
```
@task-manager 更新任务task-a1b2c3d4的代码引用
```

### use_description

获取所有可用工具的描述和参数信息。

**参数：** 无

**返回值：**

```json
{
  "tools": [
    {
      "name": "decompose_prd",
      "description": "解析PRD文档，自动拆解为任务列表",
      "parameters": {
        "prd_content": {
          "type": "string",
          "description": "PRD文档内容或资源标识符",
          "required": true
        }
      }
    },
    ... // 其他工具的描述
  ]
}
```

**示例调用：**

```
<mcp:tool name="use_description">
</mcp:tool>
```

**Cursor IDE中的调用：**
```
@task-manager 列出所有可用工具
```

## 错误响应

当API调用出现错误时，将返回以下格式的错误信息：

```json
{
  "error": {
    "code": "task_not_found",
    "message": "指定的任务ID不存在"
  }
}
```

常见错误代码：

| 错误代码 | 说明 |
|---------|-----|
| `task_not_found` | 任务ID不存在 |
| `invalid_status` | 无效的任务状态 |
| `circular_dependency` | 检测到循环依赖 |
| `invalid_parameter` | 无效的参数值 |
| `missing_parameter` | 缺少必要参数 |

## 数据模型

### Task

任务对象的数据结构：

| 字段 | 类型 | 说明 |
|------|------|-----|
| `id` | string | 任务唯一标识符 |
| `name` | string | 任务名称 |
| `description` | string | 任务详细描述 |
| `status` | string | 任务状态 (todo, in_progress, done, blocked, cancelled) |
| `priority` | string | 任务优先级 (low, medium, high, critical) |
| `complexity` | string | 任务复杂度 (low, medium, high) |
| `dependencies` | array | 依赖的前置任务ID列表 |
| `blocked_by` | array | 阻塞该任务的任务ID列表 |
| `subtasks` | array | 子任务对象列表，结构与Task相同 |
| `parent_task_id` | string | 父任务ID |
| `code_references` | array | 实现该任务的代码文件路径列表 |
| `created_at` | string | 创建时间 (ISO 8601格式) |
| `updated_at` | string | 最后更新时间 (ISO 8601格式) |
| `completed_at` | string | 完成时间 (ISO 8601格式) |
| `estimated_hours` | number | 预估工时 |
| `actual_hours` | number | 实际工时 |
| `assigned_to` | string | 任务负责人 | 