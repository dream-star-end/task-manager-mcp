# 任务管理MCP服务API参考

本文档详细说明了任务管理MCP服务提供的所有API，包括参数、返回值和示例。

## 工具列表

| 工具ID | 功能描述 |
|---------|---------|
| `decompose_prd` | 解析PRD文档，自动拆解为任务列表 |
| `add_task` | 创建新任务 |
| `update_task` | 更新现有任务信息，包括状态、依赖关系、代码引用等 |
| `get_task` | 获取任务详情 |
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
| `prd_content` | string | 是 | PRD文档内容或文件路径，支持直接文本或以file://开头的文件路径。**注意：使用file://格式时必须提供绝对路径** |

**返回值：**

```json
{
  "success": true,
  "tasks": [
    {
      "id": "1",
      "name": "用户认证模块",
      "description": "实现用户注册、登录和认证功能",
      "status": "todo",
      "priority": "high",
      "dependencies": [],
      "blocked_by": [],
      "subtasks": [],
      "tags": ["核心功能", "前端", "后端"],
      "estimated_hours": 24,
      "code_references": []
    },
    // 更多任务...
  ],
  "message": "已从PRD中提取13个主任务"
}
```

**示例调用：**

```
@task-manager decompose_prd prd_content="file:///D:/projects/my-project/docs/prd.md"
```

### add_task

创建新任务。

**参数：**

| 参数名 | 类型 | 必填 | 说明 |
|-------|------|-----|-----|
| `name` | string | 是 | 任务名称 |
| `description` | string | 否 | 任务描述 |
| `id` | string | 否 | 任务ID（可选，如未提供则自动生成） |
| `priority` | string | 否 | 任务优先级，可选值为：low, medium, high, critical |
| `tags` | string | 否 | 任务标签，多个标签以逗号分隔 |
| `assigned_to` | string | 否 | 任务分配给谁 |
| `estimated_hours` | string | 否 | 预估完成时间（小时） |
| `dependencies` | string | 否 | 依赖的任务ID，多个依赖以逗号分隔 |

**返回值：**

```json
{
  "success": true,
  "task": {
    "id": "4",
    "name": "实现用户注册功能",
    "description": "开发用户注册界面和后端处理",
    "status": "todo",
    "priority": "high",
    "dependencies": ["1", "2"],
    "blocked_by": ["1", "2"],
    "subtasks": [],
    "parent_task_id": null,
    "tags": ["前端", "用户功能"],
    "code_references": [],
    "complexity": "medium",
    "estimated_hours": 8,
    "created_at": "2025-03-31T15:00:00Z",
    "updated_at": "2025-03-31T15:00:00Z"
  },
  "task_json_path": "/path/to/output/tasks/task-4.json"
}
```

**示例调用：**

```
@task-manager add_task name="实现用户注册功能" description="开发用户注册界面和后端处理" priority="high" tags="前端,用户功能" dependencies="1,2"
```

### update_task

更新现有任务信息，包括标记任务为完成和更新依赖关系。

**参数：**

| 参数名 | 类型 | 必填 | 说明 |
|-------|------|-----|-----|
| `task_id` | string | 是 | 任务ID，对于子任务使用`父任务ID.子任务编号`格式，如`1.1` |
| `name` | string | 否 | 新任务名称 |
| `description` | string | 否 | 新任务描述 |
| `status` | string | 否 | 新任务状态，包括标记任务为完成(`done`)、进行中(`in_progress`)、阻塞(`blocked`)或取消(`cancelled`) |
| `priority` | string | 否 | 新的任务优先级 (low, medium, high, critical) |
| `tags` | string | 否 | 新的任务标签，多个标签以逗号分隔 |
| `assigned_to` | string | 否 | 新的任务负责人 |
| `estimated_hours` | string | 否 | 新的预估工时 |
| `actual_hours` | string | 否 | 实际工时 |
| `dependencies` | string | 否 | 逗号分隔的新依赖任务ID列表。**此操作会覆盖任务现有的所有依赖关系**。如果提供空字符串 `""`，则会清空任务的所有依赖。如果不提供此参数，则依赖关系保持不变。 |

**返回值：**

```json
{
  "success": true,
  "task": {
    "id": "4",
    "name": "实现用户注册功能",
    "description": "正在实现后端注册逻辑",
    "status": "in_progress",
    "priority": "high",
    "dependencies": ["1"],
    "blocked_by": ["1"],
    "subtasks": [],
    "parent_task_id": null,
    "tags": ["前端", "用户功能"],
    "code_references": [],
    "complexity": "medium",
    "estimated_hours": 8,
    "created_at": "2025-03-31T15:00:00Z",
    "updated_at": "2025-04-20T11:00:00Z"
  },
  "message": "Task 4 updated successfully",
  "task_json_path": "/path/to/output/tasks/task-4.json"
}
```

**子任务更新说明：**

当更新子任务状态时，系统会自动同步父任务状态，遵循以下规则：
1. 如果所有子任务都完成，则父任务自动更新为完成状态
2. 如果有任何子任务被阻塞，则父任务自动更新为阻塞状态
3. 如果有任何子任务进行中，则父任务自动更新为进行中状态

**示例调用：**

更新任务状态、描述并设置新的依赖：
```
@task-manager update_task task_id="4" status="in_progress" description="正在实现后端注册逻辑" dependencies="1"
```

清空任务依赖：
```
@task-manager update_task task_id="4" dependencies=""
```

更新子任务状态：
```
@task-manager update_task task_id="1.1" status="done" actual_hours="5.5"
```

### get_task

获取任务详情。

**参数：**

| 参数名 | 类型 | 必填 | 说明 |
|-------|------|-----|-----|
| `task_id` | string | 是 | 要获取的任务ID |

**返回值：**

返回包含任务详细信息的格式化文本，包括基本信息、详细内容、工时信息、标签、依赖关系和代码引用。

**示例调用：**

```
@task-manager get_task task_id="1"
```

### get_task_list

获取任务列表。

**参数：**

| 参数名 | 类型 | 必填 | 说明 |
|-------|------|-----|-----|
| `status` | string | 否 | 按状态筛选，可选值为：todo, in_progress, done, blocked, cancelled |
| `priority` | string | 否 | 按优先级筛选，可选值为：low, medium, high, critical |
| `tag` | string | 否 | 按标签筛选 |
| `assigned_to` | string | 否 | 按负责人筛选 |
| `page` | string | 否 | 页码，默认为1 |
| `page_size` | string | 否 | 每页任务数量，默认为100 |

**返回值：**

返回符合条件的任务列表，以表格和JSON格式展示。

**示例调用：**

```
@task-manager get_task_list status="todo" priority="high" tag="前端"
```

### get_next_executable_task

获取下一个可执行任务。此接口只返回一个最优先的任务，而不是任务列表。

**参数：**

| 参数名 | 类型 | 必填 | 说明 |
|-------|------|-----|-----|
| `limit` | string | 否 | 内部查询任务的数量限制，默认为5。该参数仅影响内部查询流程，最终只会返回一个任务。 |

**返回值：**

返回一个最优先的可执行任务，如果没有可执行的任务，则返回相应提示。

**示例调用：**

```
@task-manager get_next_executable_task
```

### expand_task

为指定任务生成子任务。

**参数：**

| 参数名 | 类型 | 必填 | 说明 |
|-------|------|-----|-----|
| `task_id` | string | 是 | 要展开的任务ID |
| `num_subtasks` | string | 否 | 希望生成的子任务数量，默认为5 |

**返回值：**

返回父任务信息和生成的子任务列表，以及保存的文件路径。

**示例调用：**

```
@task-manager expand_task task_id="1" num_subtasks="3"
```

### update_task_code_references

更新任务的代码引用。

**参数：**

| 参数名 | 类型 | 必填 | 说明 |
|-------|------|-----|-----|
| `task_id` | string | 是 | 任务ID |
| `code_files` | string | 是 | 代码文件路径列表，以逗号分隔 |

**返回值：**

返回更新后的任务信息，包括更新后的代码引用。

**示例调用：**

```
@task-manager update_task_code_references task_id="1" code_files="src/auth/login.py,src/models/user.py"
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
  "success": false,
  "error": "指定的任务ID不存在",
  "error_code": "task_not_found"
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
| `prd_parse_error` | PRD解析失败 |
| `expand_task_error` | 任务展开失败 |

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
| `tags` | array | 任务标签列表 | 