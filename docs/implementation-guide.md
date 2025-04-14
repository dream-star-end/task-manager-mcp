# 任务管理MCP服务实现指南

## 1. 项目结构

实际项目结构如下：

```
task-manager-mcp/
├── src/                     # 源代码目录
│   ├── server.py            # 主程序入口 (MCP服务定义)
│   ├── config.py            # 配置模块 (LLM客户端工厂等)
│   ├── models/
│   │   └── task.py          # 任务数据模型
│   ├── services/
│   │   ├── task_service.py  # 任务管理核心逻辑
│   │   └── prd_parser.py    # PRD解析服务
│   ├── storage/
│   │   └── task_storage.py  # 任务存储实现
│   ├── llm/                 # LLM集成模块
│   │   ├── base.py          # LLM接口抽象基类
│   │   └── gemini.py        # Google Gemini实现
│   └── utils/               # 工具函数
│       ├── logging_config.py   # 日志配置
│       ├── file_operations.py  # 文件操作
│       └── task_utils.py       # 任务工具函数
└── docs/
    ├── design.md            # 设计文档
    ├── mcp-rules.md         # MCP调用规则
    └── getting-started.md   # 快速入门指南
```

## 2. 核心组件实现

### 2.1 服务器入口 (src/server.py)

服务器入口定义了MCP服务所有接口，包括PRD解析、任务管理等功能：

```python
from mcp.server.fastmcp import FastMCP
from services.task_service import TaskService
from config import get_llm_client
import mcp.types as types
import logging
import os
import json

# 设置日志
logger = setup_logging(log_file_path, logging.INFO)

# 初始化LLM客户端
llm_client = get_llm_client()  # 从环境变量获取配置

# 创建MCP实例
mcp = FastMCP("task-manager-mcp")

# 创建任务服务实例，注入LLM客户端
task_service = TaskService(llm_client=llm_client)

@mcp.tool("decompose_prd")
async def decompose_prd(prd_content: str) -> list[types.TextContent]:
    """解析PRD文档，自动拆解为主任务列表
    
    Args:
        prd_content: PRD文档内容或文件路径，支持直接文本或以file://开头的文件路径
        
    Returns:
        List: 包含提取的主任务列表的格式化响应
    """
    # 实现略...

@mcp.tool("add_task")
async def add_task(
    name: str,
    description: str = "",
    id: str = "",
    priority: str = "medium",
    tags: str = "",
    assigned_to: str = "",
    estimated_hours: str = "",
    dependencies: str = ""
) -> list[types.TextContent]:
    """创建新任务"""
    # 实现略...

@mcp.tool("update_task")
async def update_task(
    task_id: str,
    name: str = "",
    description: str = "",
    status: str = "",
    priority: str = "",
    tags: str = "",
    assigned_to: str = "",
    estimated_hours: str = "",
    actual_hours: str = "",
    dependencies: str = ""
) -> list[types.TextContent]:
    """更新现有任务信息"""
    # 实现略...

@mcp.tool("get_task")
async def get_task(task_id: str) -> list[types.TextContent]:
    """获取任务详情"""
    # 实现略...

@mcp.tool("get_task_list")
async def get_task_list(
    status: str = "",
    priority: str = "",
    tag: str = "",
    assigned_to: str = "",
    page: str = "1",
    page_size: str = "100"
) -> list[types.TextContent]:
    """获取任务列表"""
    # 实现略...

@mcp.tool("get_next_executable_task")
async def get_next_executable_task(limit: str = "5") -> list[types.TextContent]:
    """获取下一个可执行任务"""
    # 实现略...

@mcp.tool("expand_task")
async def expand_task(task_id: str, num_subtasks: str = "5") -> list[types.TextContent]:
    """展开任务为子任务"""
    # 实现略...

@mcp.tool("update_task_code_references")
async def update_task_code_references(task_id: str, code_files: str) -> list[types.TextContent]:
    """更新任务实现的代码文件引用"""
    # 实现略...

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("MCP_SERVICE_PORT", 8000))
    uvicorn.run("server:mcp", host="0.0.0.0", port=port, reload=True)
```

### 2.2 任务模型 (src/models/task.py)

任务模型定义了系统中的核心数据结构:

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
    
    class Config:
        use_enum_values = True

    # 方法略...
```

### 2.3 任务存储 (src/storage/task_storage.py)

任务存储提供了对任务数据的CRUD操作和依赖关系管理：

```python
from typing import Dict, List, Optional, Set, Tuple, Union
from datetime import datetime
import logging

from ..models.task import Task, TaskStatus, TaskPriority, TaskComplexity

class TaskStorage:
    """任务内存存储类"""
    
    def __init__(self):
        """初始化内存存储"""
        self.tasks: Dict[str, Task] = {}
        # 依赖关系图（任务ID -> 被该任务阻塞的任务ID集合）
        self.dependency_graph: Dict[str, Set[str]] = {}
    
    def create_task(
        self, 
        name: str, 
        description: str = "", 
        id: Optional[str] = None,
        priority: TaskPriority = TaskPriority.MEDIUM,
        complexity: TaskComplexity = TaskComplexity.MEDIUM,
        tags: List[str] = None,
        assigned_to: Optional[str] = None,
        estimated_hours: Optional[float] = None,
        dependencies: List[str] = None,
        code_references: List[str] = None
    ) -> Task:
        """创建新任务"""
        # 实现略...
    
    def get_task(self, task_id: str) -> Optional[Task]:
        """获取任务信息"""
        return self.tasks.get(task_id)
    
    def update_task(self, task_id: str, **kwargs) -> Optional[Task]:
        """更新任务信息"""
        # 实现略...
    
    def set_task_dependency(self, task_id: str, depends_on_id: str) -> Tuple[bool, Optional[str]]:
        """设置任务依赖关系"""
        # 实现略...
    
    def remove_task_dependency(self, task_id: str, depends_on_id: str) -> bool:
        """移除任务依赖关系"""
        # 实现略...
    
    def _would_create_cycle(self, task_id: str, depends_on_id: str) -> bool:
        """检查添加依赖是否会导致循环依赖"""
        # 实现略...
        
    def clear_all_tasks(self) -> None:
        """清空所有任务"""
        self.tasks.clear()
        self.dependency_graph.clear()
```

## 3. 核心服务实现

### 3.1 任务服务 (src/services/task_service.py)

任务服务是系统核心业务逻辑的实现，提供任务管理的所有功能：

```python
from typing import Dict, List, Optional, Any, Tuple
import logging
from datetime import datetime

from ..models.task import Task, TaskStatus, TaskPriority
from ..storage.task_storage import TaskStorage
from ..services.prd_parser import PrdParser
from ..llm.base import LLMInterface

class TaskService:
    """任务服务类，提供任务管理的业务逻辑"""
    
    def __init__(self, storage: Optional[TaskStorage] = None, llm_client: Optional[LLMInterface] = None):
        """
        初始化任务服务
        
        Args:
            storage: 任务存储实例，如果为None则创建新实例。
            llm_client: 可选的 LLM 客户端实例，用于 PRD 解析。
        """
        self.storage = storage or TaskStorage()
        self.prd_parser = PrdParser(storage=self.storage, llm_client=llm_client)
    
    async def decompose_prd(self, prd_content: str) -> Dict[str, Any]:
        """
        解析PRD文档，自动拆解为任务列表
        
        Args:
            prd_content: PRD文档内容或文件路径
            
        Returns:
            Dict: 包含提取任务信息的响应
        """
        # 处理文件路径和内容
        # 调用 PrdParser 进行解析
        # 返回格式化响应
    
    def add_task(self, name: str, description: str = "", **kwargs) -> Dict[str, Any]:
        """
        创建新任务
        
        Args:
            name: 任务名称
            description: 任务描述
            **kwargs: 其他任务属性
            
        Returns:
            Dict: 包含新创建任务信息的响应
        """
        # 实现任务创建
    
    def update_task(self, task_id: str, **kwargs) -> Dict[str, Any]:
        """
        更新现有任务信息，包括依赖关系
        
        Args:
            task_id: 任务ID
            **kwargs: 要更新的任务属性
            
        Returns:
            Dict: 包含更新后任务信息的响应
        """
        # 处理子任务更新和普通任务更新
        # 管理任务依赖关系
    
    def _sync_parent_task_status(self, parent_task_id: str) -> None:
        """
        根据子任务状态同步更新父任务状态
        
        Args:
            parent_task_id: 父任务ID
        """
        # 实现父任务状态同步
    
    def get_task_list(self, status: Optional[str] = None, priority: Optional[str] = None, 
                      tag: Optional[str] = None, assigned_to: Optional[str] = None,
                      page: int = 1, page_size: int = 100) -> Dict[str, Any]:
        """
        获取任务列表，支持各种筛选条件
        
        Args:
            多种筛选条件和分页参数
            
        Returns:
            Dict: 包含任务列表的分页响应
        """
        # 实现任务列表查询和分页
    
    def get_next_executable_task(self, limit: int = 5) -> Dict[str, Any]:
        """
        获取下一个可执行任务
        
        逻辑顺序：
        1. 首先查找状态为"in_progress"的任务
        2. 如果没有进行中的任务，查找"todo"状态且依赖已满足的任务
        3. 按优先级排序(critical > high > medium > low)
        4. 同等优先级下，被更多任务依赖的排前面
        5. 同等条件下，创建时间早的排前面
        
        Args:
            limit: 内部排序时考虑的任务数量限制
            
        Returns:
            Dict: 包含下一个可执行任务的响应
        """
        # 实现获取下一个任务的复杂逻辑
    
    async def expand_task(self, task_id: str, num_subtasks: int = 5,
                          project_context: str = "") -> Dict[str, Any]:
        """
        为指定任务生成子任务
        
        Args:
            task_id: 要展开的任务ID
            num_subtasks: 希望生成的子任务数量
            project_context: 项目相关上下文
            
        Returns:
            Dict: 包含生成的子任务信息的响应
        """
        # 调用LLM生成子任务
        # 处理子任务层级标识与依赖关系
```

### 3.2 PRD解析服务 (src/services/prd_parser.py)

PRD解析服务负责智能解析产品需求文档，提取任务和依赖关系：

```python
import re
import os
import json
import google.generativeai as genai
from typing import List, Dict, Optional, Any, Tuple
import logging

from ..models.task import Task, TaskStatus, TaskPriority
from ..storage.task_storage import TaskStorage
from ..llm.base import LLMInterface

class PrdParser:
    """PRD文档解析器，使用注入的LLM客户端（如果提供）"""
    
    def __init__(self, storage: TaskStorage, llm_client: Optional[LLMInterface] = None):
        """
        初始化PRD解析器。
        
        Args:
            storage: 任务存储后端实例。
            llm_client: 一个实现了LLMInterface的可选客户端实例。
                        如果提供，将用于解析PRD；否则，将回退到基本解析。
        """
        self.storage = storage
        self.llm_client = llm_client
    
    async def parse(self, content: str) -> Tuple[List[Task], Optional[str]]:
        """
        解析PRD文档内容，提取任务和依赖关系
        
        Args:
            content: PRD文档内容
            
        Returns:
            Tuple[List[Task], Optional[str]]: 提取的任务列表和LLM解析错误信息
        """
        # 优先使用LLM进行解析
        # 发生错误时回退到基础解析方法
    
    async def parse_with_llm(self, prd_content: str) -> List[Task]:
        """
        使用LLM客户端解析PRD文档
        
        Args:
            prd_content: PRD文档内容
            
        Returns:
            List[Task]: 提取并转换为Task对象的任务列表
        """
        # 第一次LLM调用提取任务
        # 第二次LLM调用分析依赖关系
        # 创建任务对象并建立依赖关系
```

### 3.3 LLM接口实现 (src/llm)

LLM集成模块提供了与大语言模型交互的抽象接口和具体实现：

#### 3.3.1 LLM接口基类 (src/llm/base.py)

```python
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, List
import logging

class LLMInterface(ABC):
    """大语言模型调用的抽象基类接口"""

    @abstractmethod
    async def generate_text_async(
        self,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs: Any
    ) -> str:
        """生成文本内容 (异步)"""
        pass

    @abstractmethod
    async def generate_structured_content_async(
        self,
        prompt: str,
        schema: Dict[str, Any],
        temperature: float = 0.1,
        **kwargs: Any
    ) -> Any:
        """根据提供的Schema生成结构化内容 (异步)"""
        pass

    @abstractmethod
    async def parse_prd_to_tasks_async(
        self,
        prd_content: str,
        **kwargs: Any
    ) -> List[Dict[str, Any]]:
        """解析PRD文档内容，提取结构化的任务列表 (异步)"""
        pass

    @abstractmethod
    async def generate_subtasks_for_task_async(
        self,
        task_info: Dict[str, Any],
        num_subtasks: int = 5,
        temperature: float = 0.2,
        **kwargs: Any
    ) -> List[Dict[str, Any]]:
        """为指定的任务生成子任务列表 (异步)"""
        pass
```

#### 3.3.2 Gemini实现 (src/llm/gemini.py)

```python
import os
import json
import logging
from typing import Any, Dict, Optional, List

import google.generativeai as genai
from google.generativeai.types import GenerationConfig
from google.api_core.exceptions import GoogleAPIError

from .base import LLMInterface

class GeminiLLM(LLMInterface):
    """Google Gemini LLM implementation using the google-generativeai SDK."""

    def __init__(self, api_key: Optional[str] = None, config: Optional[Dict[str, Any]] = None):
        """初始化Gemini LLM客户端"""
        # 配置Gemini SDK和模型
    
    async def generate_text_async(self, prompt: str, temperature: float = 0.7,
                                 max_tokens: Optional[int] = None, **kwargs: Any) -> str:
        """生成文本内容"""
        # 实现文本生成
    
    async def generate_structured_content_async(self, prompt: str, schema: Dict[str, Any],
                                              temperature: float = 0.1, **kwargs: Any) -> Any:
        """生成结构化内容"""
        # 实现结构化内容生成
    
    async def parse_prd_to_tasks_async(self, prd_content: str, **kwargs: Any) -> List[Dict[str, Any]]:
        """解析PRD文档为任务列表"""
        # 构建PRD解析的提示词
        # 定义输出模式
        # 调用结构化内容生成
    
    async def generate_subtasks_for_task_async(self, task_info: Dict[str, Any],
                                             num_subtasks: int = 5, **kwargs: Any) -> List[Dict[str, Any]]:
        """为任务生成子任务"""
        # 实现子任务生成
```

## 4. 测试策略

### 4.1 单元测试

为核心功能编写单元测试，特别是：
- 任务依赖关系检查和循环依赖检测
- 任务状态转换和状态同步
- get_next_executable_task 优先级排序逻辑

```python
# tests/test_task_service.py 示例
import unittest
from unittest.mock import MagicMock, patch
from src.storage.task_storage import TaskStorage
from src.services.task_service import TaskService
from src.models.task import Task, TaskStatus, TaskPriority

class TestTaskService(unittest.TestCase):
    
    def setUp(self):
        """测试前准备"""
        self.storage = TaskStorage()
        self.service = TaskService(storage=self.storage)
    
    def test_get_next_executable_task(self):
        """测试获取下一个可执行任务的逻辑"""
        # 创建测试任务
        task1 = self.storage.create_task(id="1", name="Task 1", priority=TaskPriority.HIGH)
        task2 = self.storage.create_task(id="2", name="Task 2", priority=TaskPriority.MEDIUM)
        task3 = self.storage.create_task(id="3", name="Task 3", priority=TaskPriority.HIGH)
        
        # 设置依赖关系
        self.storage.set_task_dependency("2", "1")  # Task 2 依赖于 Task 1
        
        # 测试返回优先级高的没有依赖的任务
        result = self.service.get_next_executable_task()
        self.assertEqual(result["task"]["id"], "3")  # Task 3 优先级高且无依赖
        
        # 将任务3标记为进行中
        self.storage.update_task("3", status=TaskStatus.IN_PROGRESS)
        
        # 测试返回进行中的任务
        result = self.service.get_next_executable_task()
        self.assertEqual(result["task"]["id"], "3")  # 进行中的任务优先
        
        # 将任务3标记为完成
        self.storage.update_task("3", status=TaskStatus.DONE)
        
        # 测试返回无依赖且优先级高的任务
        result = self.service.get_next_executable_task()
        self.assertEqual(result["task"]["id"], "1")  # Task 1 无依赖可执行
        
        # 将任务1标记为完成
        self.storage.update_task("1", status=TaskStatus.DONE)
        
        # 测试依赖已满足的任务
        result = self.service.get_next_executable_task()
        self.assertEqual(result["task"]["id"], "2")  # Task 2 依赖已满足
```

### 4.2 集成测试

集成测试主要测试PRD解析和LLM集成的端到端流程：

```python
# tests/test_prd_parser_integration.py 示例
import asyncio
import unittest
from unittest.mock import MagicMock, patch
from src.storage.task_storage import TaskStorage
from src.services.prd_parser import PrdParser
from src.llm.gemini import GeminiLLM

class TestPrdParserIntegration(unittest.TestCase):
    
    def setUp(self):
        """测试前准备"""
        self.storage = TaskStorage()
        self.mock_llm = MagicMock(spec=GeminiLLM)
        self.parser = PrdParser(storage=self.storage, llm_client=self.mock_llm)
    
    def test_prd_parsing_with_llm(self):
        """测试使用LLM解析PRD"""
        # 模拟LLM返回的任务数据
        mock_tasks = [
            {"id": "1", "name": "任务1", "description": "描述1", "priority": "high"},
            {"id": "2", "name": "任务2", "description": "描述2", "priority": "medium"}
        ]
        
        # 模拟依赖分析结果
        mock_dependencies = [
            {"task_id": "2", "depends_on_id": "1"}
        ]
        
        # 设置模拟函数的返回值
        async def mock_parse_prd(*args, **kwargs):
            return mock_tasks
            
        async def mock_generate_structured(*args, **kwargs):
            return mock_dependencies
        
        self.mock_llm.parse_prd_to_tasks_async.side_effect = mock_parse_prd
        self.mock_llm.generate_structured_content_async.side_effect = mock_generate_structured
        
        # 执行测试
        sample_prd = "# 标题1\n## 子标题1\n# 标题2"
        tasks, error = asyncio.run(self.parser.parse(sample_prd))
        
        # 验证结果
        self.assertEqual(len(tasks), 2)
        self.assertIsNone(error)
        self.assertEqual(tasks[0].id, "1")
        self.assertEqual(tasks[0].name, "任务1")
        self.assertEqual(tasks[1].id, "2")
        
        # 验证依赖关系
        task2 = self.storage.get_task("2")
        self.assertEqual(task2.dependencies, {"1"})
```

## 5. 部署指南

### 5.1 环境变量配置

服务运行需要以下环境变量:

```bash
# LLM配置
export GEMINI_API_KEY="your-api-key"       # Gemini API密钥
export MODEL_NAME="gemini-1.5-flash"        # 使用的模型
export LLM_PROVIDER="gemini"                # LLM提供商 (gemini 或 openai)

# 代理设置(可选)
export HTTP_PROXY="http://127.0.0.1:7890"   # HTTP代理
export HTTPS_PROXY="http://127.0.0.1:7890"  # HTTPS代理

# 输出目录(可选)
export MCP_OUTPUT_DIR="/path/to/output"     # 输出文件保存路径
```

### 5.2 使用 uv 运行

推荐使用 uv 运行服务，支持基于 PEP 735 的子解释器隔离:

```bash
# 安装依赖
pip install uv

# 运行服务
uv run --with fastmcp fastmcp run /path/to/server.py
```

### 5.3 Docker部署

```dockerfile
FROM python:3.10-slim

WORKDIR /app

# 安装UV
RUN pip install uv

# 拷贝项目文件
COPY requirements.txt .
COPY src/ src/
COPY docs/ docs/

# 创建输出目录
RUN mkdir -p /app/output/tasks /app/output/md /app/output/logs

# 设置环境变量
ENV PYTHONPATH=/app
ENV MCP_OUTPUT_DIR=/app/output

# 暴露端口
EXPOSE 8000

# 使用UV运行服务
CMD ["uv", "run", "--with", "fastmcp", "fastmcp", "run", "/app/src/server.py"]
```

### 5.4 运行命令

```bash
# 构建镜像
docker build -t task-manager-mcp .

# 运行容器
docker run -d \
  -p 8000:8000 \
  -e GEMINI_API_KEY=your-api-key \
  -e MODEL_NAME=gemini-1.5-flash \
  -e LLM_PROVIDER=gemini \
  --name task-manager-mcp \
  task-manager-mcp
``` 