"""
依赖检查工具

提供检查任务依赖关系的功能，包括循环依赖检测
"""

from typing import Dict, List, Set


class DependencyChecker:
    """依赖关系检查器"""
    
    @staticmethod
    def detect_cycle(graph: Dict[str, Set[str]], start_node: str, end_node: str) -> bool:
        """
        检测添加新依赖是否会导致循环依赖
        
        Args:
            graph: 依赖关系图，键为节点ID，值为依赖该节点的节点ID集合
            start_node: 起始节点ID
            end_node: 目标节点ID
            
        Returns:
            bool: 如果添加依赖会导致循环，返回True，否则返回False
        """
        # 如果被依赖的节点已经直接或间接依赖于起始节点，则会形成循环
        visited = set()
        queue = [end_node]
        
        while queue:
            current = queue.pop(0)
            if current == start_node:
                return True
            
            if current in visited:
                continue
                
            visited.add(current)
            if current in graph:
                queue.extend([dep for dep in graph[current] if dep not in visited])
        
        return False
    
    @staticmethod
    def find_all_cycles(graph: Dict[str, Set[str]]) -> List[List[str]]:
        """
        查找图中的所有循环
        
        Args:
            graph: 依赖关系图，键为节点ID，值为该节点依赖的节点ID集合
            
        Returns:
            List[List[str]]: 包含所有循环的列表
        """
        result = []
        visited = set()
        
        def dfs(node: str, path: List[str], start_node: str) -> None:
            """深度优先搜索查找循环"""
            if node in path:
                # 找到循环
                cycle_start_index = path.index(node)
                cycle = path[cycle_start_index:] + [node]
                if set(cycle) not in [set(c) for c in result]:
                    result.append(cycle)
                return
            
            path.append(node)
            visited.add(node)
            
            if node in graph:
                for neighbor in graph[node]:
                    if neighbor not in visited or neighbor == start_node:
                        dfs(neighbor, path[:], start_node)
            
            visited.remove(node)
        
        # 对每个节点进行DFS
        for node in graph:
            if node not in visited:
                dfs(node, [], node)
        
        return result
    
    @staticmethod
    def get_dependency_chain(graph: Dict[str, Set[str]], start_node: str) -> List[List[str]]:
        """
        获取从起始节点到所有叶子节点的依赖链
        
        Args:
            graph: 依赖关系图，键为节点ID，值为该节点依赖的节点ID集合
            start_node: 起始节点ID
            
        Returns:
            List[List[str]]: 包含所有依赖链的列表
        """
        result = []
        visited = set()
        
        def dfs(node: str, path: List[str]) -> None:
            """深度优先搜索查找依赖链"""
            path.append(node)
            
            # 如果是叶子节点（没有依赖）或所有依赖都已访问
            if node not in graph or not graph[node] or all(dep in visited for dep in graph[node]):
                result.append(path[:])
                return
            
            visited.add(node)
            
            if node in graph:
                for dep in graph[node]:
                    if dep not in path:  # 避免循环
                        dfs(dep, path[:])
            
            visited.remove(node)
        
        dfs(start_node, [])
        return result
    
    @staticmethod
    def get_blocked_tasks(graph: Dict[str, Set[str]], done_tasks: Set[str]) -> Set[str]:
        """
        获取被阻塞的任务
        
        Args:
            graph: 依赖关系图，键为节点ID，值为依赖该节点的节点ID集合
            done_tasks: 已完成的任务ID集合
            
        Returns:
            Set[str]: 被阻塞的任务ID集合
        """
        blocked_tasks = set()
        
        # 对于每个已完成的任务，移除它对其他任务的阻塞
        for done_task in done_tasks:
            if done_task in graph:
                # 该任务已完成，不再阻塞其他任务
                for blocked in graph[done_task]:
                    blocked_tasks.discard(blocked)
        
        # 对于每个未完成的任务，它阻塞依赖它的任务
        for node, blocked in graph.items():
            if node not in done_tasks:
                blocked_tasks.update(blocked)
        
        return blocked_tasks 