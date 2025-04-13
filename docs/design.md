# 任务管理 MCP 服务设计文档

## 1. 项目目标

构建一个基于模型上下文协议 (MCP) 的任务管理服务，旨在自动化和简化项目管理流程。该服务能够：

*   根据项目需求文档 (PRD) 自动拆解和规划任务及子任务。
*   管理任务之间的依赖关系。
*   提供查询任务列表的功能。
*   智能推荐下一个可执行的任务。

## 2. 核心架构

*   **框架:** 使用 Python 和 `mcp.server.fastmcp` 库构建 MCP 服务。
*   **数据存储:**
    *   **初期:** 使用内存数据结构（例如，字典或列表）存储任务信息，便于快速开发和原型验证。
    *   **后期:** 可扩展为使用数据库（如 SQLite, PostgreSQL）或 NoSQL 数据库（如 Redis, MongoDB）进行持久化存储，以支持更大规模的数据和更强的可靠性。
*   **任务解析:** 利用自然语言处理 (NLP) 技术或集成现有的 LLM 能力来解析 PRD 文档，提取关键任务和潜在依赖。

## 3. 数据模型

定义核心的 `Task` 数据结构：

```python
# 示例性的 Python 类定义 (实际实现可能不同)
class Task:
    def __init__(self, id: str, name: str, description: str = "", status: str = "todo", depends_on: list[str] = None, subtasks: list[str] = None, parent_task: str = None, code_files: list[str] = None):
        self.id = id  # 唯一标识符
        self.name = name # 任务名称
        self.description = description # 任务详细描述
        self.status = status # 任务状态 ('todo', 'doing', 'done', 'blocked')
        self.depends_on = depends_on if depends_on is not None else [] # 依赖的前置任务 ID 列表
        self.subtasks = subtasks if subtasks is not None else [] # 子任务 ID 列表
        self.parent_task = parent_task # 父任务 ID (如果存在)
        self.code_files = code_files if code_files is not None else [] # 实现该任务的代码文件路径列表
        # 可以添加创建时间、截止日期、负责人等字段
```

*   **状态 (status):**
    *   `todo`: 待办
    *   `doing`: 进行中
    *   `done`: 已完成
    *   `blocked`: 被阻塞（依赖未完成）

## 4. MCP Tools 设计

将服务功能封装为 MCP Tools，供 LLM 或其他客户端调用：

*   **`decompose_prd(prd_content: str) -> list[dict]`**
    *   **功能:** 接收 PRD 的文本内容或指向 PRD 的资源标识符 (如 `file://path/to/prd.md`)。
    *   **处理:** 解析 PRD，识别主要任务、子任务和初步的依赖关系。
    *   **输出:** 返回一个包含任务字典的列表，每个字典代表一个新创建的任务及其属性 (符合 `Task` 结构)。
    *   **实现:** 内部可能调用 LLM 进行文本分析和任务提取。

*   **`add_task(name: str, description: str = "", depends_on: list[str] = None, parent_task: str = None) -> dict`**
    *   **功能:** 手动添加一个新任务。
    *   **处理:** 创建一个新的 `Task` 对象，并将其添加到任务存储中。自动生成 `id`。
    *   **输出:** 返回新创建的任务字典。

*   **`update_task(task_id: str, name: str = None, description: str = None, status: str = None, code_files: list[str] = None) -> dict`**
    *   **功能:** 更新指定 `task_id` 的任务信息。
    *   **处理:** 查找对应任务并更新其属性。不允许直接修改依赖和子任务列表（应使用专用工具）。状态更新可能会影响依赖任务的状态。当任务状态更新为 `done` 时，应提供 `code_files` 参数或在 `description` 中包含实现代码的文件路径信息，格式为 `[CODE_FILES: file1.py, file2.py]`。
    *   **输出:** 返回更新后的任务字典。

*   **`set_task_dependency(task_id: str, depends_on: list[str]) -> dict`**
    *   **功能:** 设置或更新指定任务的依赖关系。
    *   **处理:** 修改 `task_id` 对应任务的 `depends_on` 列表。需要进行循环依赖检查。
    *   **输出:** 返回更新后的任务字典。

*   **`get_task_list(status: str = None, parent_task: str = None) -> list[dict]`**
    *   **功能:** 获取任务列表。
    *   **处理:** 从任务存储中检索任务，可根据 `status` 或 `parent_task` 进行过滤。
    *   **输出:** 返回符合条件的任务字典列表。

*   **`get_next_executable_task() -> dict | None`**
    *   **功能:** 获取当前最适合开始执行的任务。
    *   **处理:**
        1.  首先查找状态为 `doing` 的任务，如果存在，优先返回（应优先完成已开始的任务）。
        2.  如果没有 `doing` 状态的任务，则查找所有状态为 `todo` 的任务。
        3.  检查每个 `todo` 任务的 `depends_on` 列表中的所有依赖任务。
        4.  如果一个 `todo` 任务的所有依赖任务状态都是 `done`，则该任务是可执行的。
        5.  可以根据优先级、创建时间等因素从可执行任务中选择一个返回。
    *   **输出:** 返回一个可执行的任务字典，如果没有可执行的任务，则返回 `None`。

## 5. 实现说明

*   **任务 ID:** 使用 UUID 或其他唯一标识符生成方案。
*   **依赖管理:** 实现循环依赖检测逻辑，防止出现无法完成的任务链。当一个任务完成时，需要检查哪些后续任务的阻塞状态可以解除。
*   **PRD 解析:** `decompose_prd` 的实现复杂度较高，初期可以简化为手动添加任务，或使用非常结构化的 PRD 模板。后期可以引入更强大的 NLP 模型或服务。
*   **错误处理:** 为所有 Tool 添加健壮的错误处理逻辑（例如，任务 ID 不存在、无效的状态转换、循环依赖等）。
*   **异步处理:** 对于可能耗时的操作（如复杂的 PRD 解析），应使用 `async` 函数。

## 6. 未来扩展

*   **持久化存储:** 将内存存储替换为数据库，确保数据持久性。
*   **用户认证与授权:** 添加用户系统，区分不同用户的任务和权限。
*   **任务优先级:** 增加任务优先级字段，并在 `get_next_executable_task` 中考虑。
*   **任务分配:** 增加负责人字段，实现任务分配功能。
*   **时间估算与跟踪:** 添加任务时间估算和实际用时跟踪。
*   **提醒与通知:** 集成通知系统，在任务状态变更或临近截止日期时提醒相关人员。
*   **Web UI:** 开发一个简单的前端界面，方便用户交互式地管理任务。
*   **与其他工具集成:** 例如，与 Git 仓库、日历应用等集成。