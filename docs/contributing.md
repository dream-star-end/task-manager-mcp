# 贡献指南

感谢您对任务管理MCP服务项目的关注！本文档将指导您如何为项目做出贡献。

## 目录

- [行为准则](#行为准则)
- [如何贡献](#如何贡献)
  - [报告Bug](#报告bug)
  - [功能请求](#功能请求)
  - [代码贡献](#代码贡献)
- [开发流程](#开发流程)
  - [环境设置](#环境设置)
  - [代码风格](#代码风格)
  - [测试](#测试)
  - [提交规范](#提交规范)
- [分支策略](#分支策略)
- [发布流程](#发布流程)
- [审核流程](#审核流程)
- [社区](#社区)

## 行为准则

参与本项目的所有贡献者都必须遵守我们的行为准则：

- 尊重所有贡献者，无论他们的经验水平、性别、种族、宗教信仰或其他个人特征
- 提供建设性的反馈，避免不必要的批评
- 专注于项目目标和技术讨论，避免无关话题
- 在沟通中保持专业和友好的态度

## 如何贡献

### 报告Bug

1. 确保该Bug尚未在[Issues](https://github.com/yourusername/task-manager-mcp/issues)中报告
2. 使用Bug报告模板创建新Issue
3. 包含以下信息：
   - 问题的简明描述
   - 复现步骤
   - 预期行为与实际行为
   - 环境信息（操作系统、Python版本等）
   - 可能的截图或日志

### 功能请求

1. 检查现有[Issues](https://github.com/yourusername/task-manager-mcp/issues)确保功能尚未被请求
2. 使用功能请求模板创建新Issue
3. 清晰描述该功能的用例和价值
4. 如可能，提供功能的实现建议

### 代码贡献

1. Fork项目仓库
2. 创建特性分支：`git checkout -b feature/your-feature-name`
3. 实现您的更改
4. 编写测试并确保测试通过
5. 提交更改：`git commit -m 'Add some feature'`
6. 推送到分支：`git push origin feature/your-feature-name`
7. 提交Pull Request

## 开发流程

### 环境设置

1. 克隆项目
   ```bash
   git clone https://github.com/yourusername/task-manager-mcp.git
   cd task-manager-mcp
   ```

2. 创建虚拟环境
   ```bash
   python -m venv venv
   source venv/bin/activate  # Linux/macOS
   venv\Scripts\activate     # Windows
   ```

3. 安装开发依赖
   ```bash
   pip install -r requirements-dev.txt
   ```

4. 安装pre-commit钩子
   ```bash
   pre-commit install
   ```

### 代码风格

我们使用以下工具确保代码质量和一致性：

- **Black**: Python代码格式化
- **isort**: 导入排序
- **flake8**: 代码风格检查
- **mypy**: 类型检查

提交代码前请运行：

```bash
# 格式化代码
black .
isort .

# 代码检查
flake8
mypy .
```

### 测试

提交前请确保所有测试通过：

```bash
# 运行所有测试
pytest

# 运行特定测试
pytest tests/test_specific.py

# 带覆盖率报告
pytest --cov=src
```

添加新功能时，请编写相应的测试。我们使用pytest框架。

### 提交规范

提交消息应遵循[约定式提交](https://www.conventionalcommits.org/)规范：

```
<类型>[可选作用域]: <描述>

[可选正文]

[可选脚注]
```

类型包括：
- `feat`: 新功能
- `fix`: 错误修复
- `docs`: 文档更改
- `style`: 不影响代码含义的格式更改
- `refactor`: 代码重构
- `perf`: 性能改进
- `test`: 添加或修正测试
- `build`: 影响构建系统或外部依赖的更改
- `ci`: CI配置或脚本的更改
- `chore`: 其他不修改src或测试文件的更改

示例：
```
feat(task): 添加任务依赖关系校验功能

添加了在创建或更新任务时校验依赖关系的功能，防止出现循环依赖。

解决 #123
```

## 分支策略

- `main`: 稳定分支，包含已发布的代码
- `develop`: 开发分支，包含下一个版本的代码
- `feature/*`: 特性分支，用于开发新功能
- `bugfix/*`: 错误修复分支，用于修复错误
- `release/*`: 发布准备分支，用于版本发布前的最终测试和准备
- `hotfix/*`: 热修复分支，用于紧急修复生产环境中的问题

## 发布流程

1. 从`develop`分支创建`release`分支：`release/vX.Y.Z`
2. 在`release`分支上进行最终测试和准备
3. 更新版本号和CHANGELOG.md
4. 将`release`分支合并到`main`和`develop`
5. 在`main`分支上创建标签：`vX.Y.Z`
6. 发布新版本

## 审核流程

所有Pull Request都需要通过以下审核步骤：

1. 代码风格检查（自动通过CI运行）
2. 测试通过（自动通过CI运行）
3. 至少一位维护者的代码审核
4. 解决所有审核评论
5. 最终维护者批准

## 社区

- **问题讨论**: 使用[GitHub Issues](https://github.com/yourusername/task-manager-mcp/issues)
- **特性讨论**: [GitHub Discussions](https://github.com/yourusername/task-manager-mcp/discussions)
- **实时聊天**: [Gitter](https://gitter.im/task-manager-mcp)

---

再次感谢您的贡献！如有任何问题，请随时联系项目维护者。 