# 任务管理 MCP 服务设计文档

## 1. 项目目标

构建一个基于模型上下文协议 (MCP) 的任务管理服务，旨在自动化和简化项目管理流程。该服务能够：

*   根据项目需求文档 (PRD) 自动拆解和规划任务及子任务。
*   管理任务之间的依赖关系。
*   提供查询任务列表的功能。
*   智能推荐下一个可执行的任务。
*   支持任务展开为子任务（使用LLM智能生成）。
*   支持与代码实现的关联（代码引用管理）。

## 2. 核心架构

*   **框架:** 使用 Python 和 `fastmcp` 库构建 MCP 服务。
*   **LLM集成:** 支持与不同LLM供应商（如Gemini、OpenAI）集成，用于PRD解析和任务展开。
*   **数据存储:**
    *   **初期:** 使用内存数据结构存储任务信息，包括任务依赖关系图。
    *   **后期:** 可扩展为使用数据库（如 SQLite, PostgreSQL）进行持久化存储。
*   **数据输出:** 支持将任务导出为JSON和Markdown格式。

## 3. 数据模型

核心的 `Task` 数据模型：

```python
from enum import Enum
from typing import Dict, List, Optional, Set, Union, Any
from datetime import datetime
from pydantic import BaseModel, Field

class TaskStatus(str, Enum):
    """任务状态枚举"""
    TODO = "todo"           # 待办
    IN_PROGRESS = "in_progress"  # 进行中
    DONE = "done"           # 已完成
    BLOCKED = "blocked"     # 被阻塞
    CANCELLED = "cancelled"  # 已取消

class TaskPriority(str, Enum):
    """任务优先级枚举"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class TaskComplexity(str, Enum):
    """任务复杂度枚举"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"

class Task(BaseModel):
    """任务数据模型"""
    id: str = Field(..., description="任务唯一标识符")
    name: str = Field(..., description="任务名称")
    description: str = Field("", description="任务详细描述")
    status: TaskStatus = Field(default=TaskStatus.TODO, description="任务状态")
    priority: TaskPriority = Field(default=TaskPriority.MEDIUM, description="任务优先级")
    complexity: TaskComplexity = Field(default=TaskComplexity.MEDIUM, description="任务复杂度")
    
    dependencies: Set[str] = Field(default_factory=set, description="依赖任务的ID集合")
    blocked_by: Set[str] = Field(default_factory=set, description="阻塞该任务的任务ID集合")
    
    created_at: datetime = Field(default_factory=datetime.now, description="创建时间")
    updated_at: datetime = Field(default_factory=datetime.now, description="最后更新时间")
    completed_at: Optional[datetime] = Field(None, description="完成时间")
    
    tags: List[str] = Field(default_factory=list, description="任务标签")
    assigned_to: Optional[str] = Field(None, description="分配给谁")
    
    metadata: Dict[str, Union[str, int, float, bool]] = Field(
        default_factory=dict, description="附加元数据"
    )
    
    estimated_hours: Optional[float] = Field(None, description="预估工时")
    actual_hours: Optional[float] = Field(None, description="实际工时")
    
    code_references: List[str] = Field(default_factory=list, description="关联的代码引用")
    
    parent_task_id: Optional[str] = Field(None, description="父任务ID")
    subtasks: List[Dict[str, Any]] = Field(default_factory=list, description="子任务列表")
```

## 4. MCP Tools 设计

服务提供以下MCP工具接口：

### 4.1 任务解析工具

*   **`decompose_prd(prd_content: str) -> list[types.TextContent]`**
    *   **功能:** 解析PRD文档，自动拆解为主任务列表。
    *   **输入:** PRD文档内容或文件路径（支持直接文本或`file://`开头的文件路径）。
    *   **处理:** 使用LLM解析PRD内容，识别主要任务和依赖关系；如LLM解析失败，回退到基本标题解析。
    *   **输出:** 提取的主任务列表、优先级分布、标签统计等信息，同时生成Markdown和JSON文件。

### 4.2 任务管理工具

*   **`add_task(name: str, description: str = "", id: str = "", priority: str = "medium", tags: str = "", assigned_to: str = "", estimated_hours: str = "", dependencies: str = "") -> list[types.TextContent]`**
    *   **功能:** 创建新任务。
    *   **处理:** 创建任务并处理标签、依赖关系，支持自定义或自动生成ID。
    *   **输出:** 新创建任务的详细信息。

*   **`update_task(task_id: str, name: str = "", description: str = "", status: str = "", priority: str = "", tags: str = "", assigned_to: str = "", estimated_hours: str = "", actual_hours: str = "", dependencies: str = "") -> list[types.TextContent]`**
    *   **功能:** 更新任务信息，包括状态、依赖关系、标签等。
    *   **处理:** 支持更新普通任务和子任务，更新依赖关系时验证循环依赖等。
    *   **输出:** 更新后任务的详细信息。

*   **`get_task(task_id: str) -> list[types.TextContent]`**
    *   **功能:** 获取任务详情。
    *   **输出:** 任务的完整信息，包括基本信息、依赖关系、代码引用等。

*   **`get_task_list(status: str = "", priority: str = "", tag: str = "", assigned_to: str = "", page: str = "1", page_size: str = "100") -> list[types.TextContent]`**
    *   **功能:** 获取任务列表，支持按状态、优先级、标签和负责人筛选，支持分页。
    *   **输出:** 符合条件的任务列表和统计信息。

*   **`get_next_executable_task(limit: str = "5") -> list[types.TextContent]`**
    *   **功能:** 获取下一个可执行任务。
    *   **处理:**
        1. 首先查找状态为"in_progress"的任务。
        2. 如果没有进行中的任务，查找"todo"状态且依赖已满足的任务。
        3. 按优先级排序(critical > high > medium > low)。
        4. 同等优先级下，被更多任务依赖的排前面。
        5. 进行中父任务的子任务优先。
    *   **输出:** 下一个最优先执行的任务详情。

*   **`expand_task(task_id: str, num_subtasks: str = "5") -> list[types.TextContent]`**
    *   **功能:** 为指定任务生成子任务。
    *   **处理:** 使用LLM分析任务内容，生成适当数量的子任务，处理子任务ID和依赖关系。
    *   **输出:** 生成的子任务列表。

*   **`update_task_code_references(task_id: str, code_files: str) -> list[types.TextContent]`**
    *   **功能:** 更新任务关联的代码文件引用。
    *   **处理:** 将代码文件路径与任务关联，便于追踪任务实现。
    *   **输出:** 更新后任务的详细信息。

## 5. 实现特性

*   **层级ID系统:** 支持层级化的任务ID (如 1、1.1、1.2、2 等)，便于表示任务的组织结构。
*   **依赖关系管理:** 实现了依赖关系图和循环依赖检测，保证任务依赖的合理性。
*   **状态同步机制:** 子任务状态变更会自动触发父任务状态的更新。
*   **LLM集成:** 支持多种LLM供应商(Gemini/OpenAI)，通过抽象接口适配不同的模型。
*   **PRD解析策略:**
    *   主要使用LLM智能解析PRD内容。
    *   如LLM解析失败，回退到基本的标题解析机制。
    *   使用两次LLM调用：第一次提取任务，第二次分析依赖关系。
*   **文件输出:** 将任务数据保存为JSON和Markdown格式，支持自定义输出目录。
*   **完整优先级系统:** 实现了任务优先级、标签和复杂度等属性，支持更精细的任务管理。

## 6. 未来扩展

*   **持久化存储:** 实现SQLite或PostgreSQL数据库存储。
*   **Web界面:** 开发简单的Web UI进行交互式任务管理。
*   **团队协作:** 添加多用户支持，任务分配和状态追踪。
*   **任务时间线:** 可视化任务依赖和执行顺序。
*   **统计分析:** 添加任务完成率、耗时统计等分析功能。
*   **代码集成:** 增强与代码库的集成，支持自动关联代码变更与任务。
*   **自动化测试:** 增加全面的单元测试和集成测试。
*   **任务模板:** 支持根据项目类型生成常见任务模板。
*   **导出导入:** 支持任务数据的导出和导入，便于跨项目复用。