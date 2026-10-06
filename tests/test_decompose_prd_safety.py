"""Offline regression tests: real service/storage, synthetic temporary files only."""

import asyncio
import copy
import importlib.util
import json
import logging
import os
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

from src.services.task_service import TaskService
from src.storage.task_storage import TaskStorage
from src.utils.file_operations import replace_text_files


ROOT = Path(__file__).resolve().parents[1]


class FailingLLM:
    async def parse_prd_to_tasks_async(self, content):
        raise RuntimeError("synthetic provider failure")


class SuccessfulLLM:
    async def parse_prd_to_tasks_async(self, content):
        return [{"id": "1", "name": "New task"}]

    async def generate_structured_content_async(self, **kwargs):
        return []


class SafetyFixture:
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="prd-regression-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.tasks_dir = self.root / "tasks"
        self.md_dir = self.root / "md"
        self.md_dir.mkdir()
        self.storage = TaskStorage(str(self.tasks_dir))
        self.storage.create_task(id="1", name="Previous task")
        self.storage.create_task(id="2", name="Previous dependent")
        self.storage.set_task_dependency("2", "1")
        self.service = TaskService(storage=self.storage)
        self.markdown = self.md_dir / "prd_main_tasks.md"
        self.markdown.write_text("# Previous result", encoding="utf-8")
        (self.tasks_dir / "task_1.json").write_text("previous export", encoding="utf-8")
        (self.tasks_dir / "notes.txt").write_text("unrelated task notes", encoding="utf-8")
        (self.md_dir / "notes.md").write_text("unrelated markdown", encoding="utf-8")
        (self.md_dir / "nested").mkdir()
        (self.md_dir / "nested" / "keep.txt").write_text("nested file", encoding="utf-8")
        self.before_files = self.files()
        self.before_tasks = copy.deepcopy(self.storage.tasks)
        self.before_graph = copy.deepcopy(self.storage.dependency_graph)
        # Silence intentional fault-injection logs, without hiding assertions.
        self.log_patch = patch.object(logging.getLogger("src.services.task_service"), "error")
        self.log_patch.start()
        self.addCleanup(self.log_patch.stop)

    def files(self):
        return {
            str(path.relative_to(self.root)): path.read_bytes()
            for directory in (self.tasks_dir, self.md_dir)
            for path in directory.rglob("*") if path.is_file()
        }

    def assert_preserved(self):
        self.assertEqual(self.before_files, self.files())
        self.assertEqual(self.before_tasks, self.storage.tasks)
        self.assertEqual(self.before_graph, self.storage.dependency_graph)
        self.assertIs(self.service.prd_parser.storage, self.storage)

    def prepare_outputs(self, result):
        return {str(self.markdown): "# New result"}


class DecomposeSafetyTests(SafetyFixture, unittest.IsolatedAsyncioTestCase):
    async def test_missing_file_preserves_everything(self):
        result = await self.service.decompose_prd(f"file://{self.root / 'missing.md'}")
        self.assertEqual("file_read_error", result["error_code"])
        self.assert_preserved()

    async def test_directory_input_preserves_everything(self):
        result = await self.service.decompose_prd(f"file://{self.root}")
        self.assertEqual("file_read_error", result["error_code"])
        self.assert_preserved()

    async def test_unreadable_file_preserves_everything(self):
        with patch("builtins.open", side_effect=PermissionError("synthetic unreadable file")):
            result = await self.service.decompose_prd(f"file://{self.root / 'blocked.md'}")
        self.assertEqual("file_read_error", result["error_code"])
        self.assert_preserved()

    async def test_invalid_utf8_preserves_everything(self):
        source = self.root / "invalid.md"
        source.write_bytes(b"\xff\xfe")
        result = await self.service.decompose_prd(f"file://{source}")
        self.assertEqual("file_read_error", result["error_code"])
        self.assert_preserved()

    async def test_empty_and_invalid_inputs_preserve_everything(self):
        for content in ("", " \n\t", None, 42):
            with self.subTest(content=content):
                result = await self.service.decompose_prd(content)
                self.assertEqual("invalid_prd_content", result["error_code"])
                self.assert_preserved()

    async def test_empty_file_preserves_everything(self):
        source = self.root / "empty.md"
        source.write_text(" \n", encoding="utf-8")
        result = await self.service.decompose_prd(f"file://{source}")
        self.assertEqual("invalid_prd_content", result["error_code"])
        self.assert_preserved()

    async def test_no_extractable_tasks_preserves_everything(self):
        result = await self.service.decompose_prd("plain text without any headings")
        self.assertEqual("no_tasks_extracted", result["error_code"])
        self.assert_preserved()

    async def test_provider_failure_without_fallback_preserves_everything(self):
        self.service.prd_parser.llm_client = FailingLLM()
        result = await self.service.decompose_prd("plain text without any headings")
        self.assertEqual("no_tasks_extracted", result["error_code"])
        self.assert_preserved()

    async def test_exception_after_partial_parse_preserves_everything(self):
        class PartialParser:
            async def parse(inner, content):
                inner.storage.create_task(id="new", name="Partial task")
                raise RuntimeError("synthetic failure after writing staged task")

        self.service.prd_parser = PartialParser()
        self.service.prd_parser.storage = self.storage
        result = await self.service.decompose_prd("# New")
        self.assertFalse(result["success"])
        self.assert_preserved()

    async def test_export_render_failure_preserves_everything(self):
        def broken_export(result):
            raise ValueError("synthetic render failure")

        result = await self.service.decompose_prd("# New", prepare_outputs=broken_export)
        self.assertFalse(result["success"])
        self.assert_preserved()

    async def test_output_preparation_failure_preserves_everything(self):
        with patch("src.utils.file_operations.tempfile.NamedTemporaryFile",
                   side_effect=PermissionError("synthetic output error")):
            result = await self.service.decompose_prd("# New", self.prepare_outputs)
        self.assertFalse(result["success"])
        self.assert_preserved()

    async def test_later_replacement_failure_rolls_back_markdown(self):
        real_replace = os.replace
        calls = 0

        def fail_second_replace(source, destination):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise OSError("synthetic JSON replacement failure")
            return real_replace(source, destination)

        with patch("src.utils.file_operations.os.replace", side_effect=fail_second_replace):
            result = await self.service.decompose_prd("# New", self.prepare_outputs)
        self.assertFalse(result["success"])
        self.assertEqual(3, calls)  # Markdown publish, JSON failure, Markdown restore.
        self.assert_preserved()

    async def test_serialization_failure_preserves_everything(self):
        class InvalidParser:
            async def parse(inner, content):
                task = inner.storage.create_task(id="1", name="New")
                task.description = object()
                return [task], None

        self.service.prd_parser = InvalidParser()
        self.service.prd_parser.storage = self.storage
        result = await self.service.decompose_prd("# New")
        self.assertFalse(result["success"])
        self.assert_preserved()

    async def test_success_replaces_results_but_retains_unrelated_files(self):
        result = await self.service.decompose_prd("# New", self.prepare_outputs)
        self.assertTrue(result["success"])
        self.assertEqual(["1"], list(self.storage.tasks))
        self.assertEqual("New", self.storage.tasks["1"].name)
        self.assertEqual("# New result", self.markdown.read_text(encoding="utf-8"))
        stored = json.loads(Path(self.storage.master_file_path).read_text(encoding="utf-8"))
        self.assertEqual("New", stored[0]["name"])
        for path, content in self.before_files.items():
            if path not in ("tasks/all_tasks.json", "md/prd_main_tasks.md"):
                self.assertEqual(content, self.files()[path])
        self.assertEqual(set(self.before_files), set(self.files()))
        self.assertIs(self.service.prd_parser.storage, self.storage)
        reloaded = TaskStorage(str(self.tasks_dir))
        self.assertEqual(self.storage.tasks, reloaded.tasks)

    async def test_successful_llm_and_repeated_calls(self):
        self.service.prd_parser.llm_client = SuccessfulLLM()
        for _ in range(2):
            result = await self.service.decompose_prd("Product requirements", self.prepare_outputs)
            self.assertTrue(result["success"])
            self.assertEqual(["1"], list(self.storage.tasks))
            self.assertEqual("New task", self.storage.tasks["1"].name)

    async def test_invalid_root_hierarchy_preserves_everything(self):
        class InvalidHierarchyLLM(SuccessfulLLM):
            def __init__(inner, tasks):
                inner.tasks = tasks

            async def parse_prd_to_tasks_async(inner, content):
                return inner.tasks

        cases = [
            [{"id": "1.1", "name": "Orphan"}],
            [{"id": "1", "name": "Main"}, {"id": "2.1", "name": "Orphan"}],
            [{"id": "1.1", "name": "Child first"}, {"id": "1", "name": "Parent later"}],
            [{"id": "", "name": "Empty root ID"}],
        ]
        for tasks in cases:
            with self.subTest(tasks=tasks):
                self.service.prd_parser.llm_client = InvalidHierarchyLLM(tasks)
                result = await self.service.decompose_prd("PRD", self.prepare_outputs)
                self.assertEqual("invalid_task_hierarchy", result["error_code"])
                self.assert_preserved()

    async def test_valid_parent_and_subtask_survive_reload(self):
        class HierarchicalLLM(SuccessfulLLM):
            async def parse_prd_to_tasks_async(inner, content):
                return [{"id": "1", "name": "Parent"}, {"id": "1.1", "name": "Child"}]

        self.service.prd_parser.llm_client = HierarchicalLLM()
        result = await self.service.decompose_prd("PRD", self.prepare_outputs)
        self.assertTrue(result["success"])
        reloaded = TaskStorage(str(self.tasks_dir))
        self.assertEqual("Parent", reloaded.get_task("1").name)
        self.assertEqual("Child", reloaded.get_task("1.1").name)

    async def test_provider_failure_can_successfully_fall_back(self):
        self.service.prd_parser.llm_client = FailingLLM()
        result = await self.service.decompose_prd("# Fallback", self.prepare_outputs)
        self.assertTrue(result["success"])
        self.assertIn("llm_parsing_warning", result)
        self.assertEqual("Fallback", self.storage.tasks["1"].name)

    async def test_partial_llm_attempt_is_discarded_before_fallback(self):
        class PartiallyInvalidLLM(SuccessfulLLM):
            async def parse_prd_to_tasks_async(inner, content):
                return [{"id": "1", "name": "Partial"}, {"id": "2", "name": 42}]

        self.service.prd_parser.llm_client = PartiallyInvalidLLM()
        result = await self.service.decompose_prd("# Fallback", self.prepare_outputs)
        self.assertTrue(result["success"])
        self.assertIn("llm_parsing_warning", result)
        self.assertEqual(["1"], list(self.storage.tasks))
        self.assertEqual("Fallback", self.storage.tasks["1"].name)

    async def test_cancelled_parse_preserves_everything(self):
        entered = asyncio.Event()

        class WaitingLLM:
            async def parse_prd_to_tasks_async(inner, content):
                entered.set()
                await asyncio.Future()

        self.service.prd_parser.llm_client = WaitingLLM()
        request = asyncio.create_task(self.service.decompose_prd("# New"))
        await entered.wait()
        self.assert_preserved()  # No live clearing while the provider is pending.
        request.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await request
        self.assert_preserved()

    async def test_concurrent_edit_is_not_overwritten(self):
        entered = asyncio.Event()
        release = asyncio.Event()

        class WaitingLLM(SuccessfulLLM):
            async def parse_prd_to_tasks_async(inner, content):
                entered.set()
                await release.wait()
                return await super().parse_prd_to_tasks_async(content)

        self.service.prd_parser.llm_client = WaitingLLM()
        request = asyncio.create_task(self.service.decompose_prd("# New"))
        await entered.wait()
        self.storage.create_task(name="Concurrent edit", id="3")
        edited_files = self.files()
        release.set()
        result = await request
        self.assertEqual("tasks_changed", result["error_code"])
        self.assertEqual(edited_files, self.files())
        self.assertEqual("Concurrent edit", self.storage.tasks["3"].name)


class FileReplacementTests(unittest.TestCase):
    def test_new_file_removed_if_later_publish_fails(self):
        with tempfile.TemporaryDirectory(prefix="prd-publish-") as directory:
            first = Path(directory) / "first.txt"
            second = Path(directory) / "second.txt"
            second.write_text("previous", encoding="utf-8")
            real_replace = os.replace

            def fail_second(source, destination):
                if destination == str(second):
                    raise OSError("synthetic second publish failure")
                return real_replace(source, destination)

            with patch("src.utils.file_operations.os.replace", side_effect=fail_second):
                with self.assertRaises(OSError):
                    replace_text_files({str(first): "new", str(second): "new"})
            self.assertFalse(first.exists())
            self.assertEqual("previous", second.read_text(encoding="utf-8"))
            self.assertEqual([second], list(Path(directory).iterdir()))

    def test_recovery_backup_retained_if_rollback_fails(self):
        with tempfile.TemporaryDirectory(prefix="prd-recovery-") as directory:
            first = Path(directory) / "first.txt"
            second = Path(directory) / "second.txt"
            first.write_text("previous first", encoding="utf-8")
            second.write_text("previous second", encoding="utf-8")
            real_replace = os.replace
            calls = 0

            def fail_commit_and_rollback(source, destination):
                nonlocal calls
                calls += 1
                if calls >= 2:
                    raise OSError("synthetic persistent disk failure")
                return real_replace(source, destination)

            with patch("src.utils.file_operations.os.replace",
                       side_effect=fail_commit_and_rollback):
                with self.assertLogs("src.utils.file_operations", level="ERROR") as logs:
                    with self.assertRaises(OSError):
                        replace_text_files({str(first): "new", str(second): "new"})
            backups = list(Path(directory).glob(".prd-backup-*"))
            self.assertEqual(1, len(backups))
            self.assertEqual("previous first", backups[0].read_text(encoding="utf-8"))
            self.assertIn(str(backups[0]), logs.output[0])
            self.assertEqual("previous second", second.read_text(encoding="utf-8"))

    def test_symlink_target_is_not_overwritten(self):
        with tempfile.TemporaryDirectory(prefix="prd-symlink-") as directory:
            target = Path(directory) / "target.txt"
            alias = Path(directory) / "alias.txt"
            target.write_text("unrelated", encoding="utf-8")
            alias.symlink_to(target)
            with self.assertRaises(ValueError):
                replace_text_files({str(alias): "new"})
            self.assertEqual("unrelated", target.read_text(encoding="utf-8"))
            self.assertTrue(alias.is_symlink())


class ServerSafetyTests(SafetyFixture, unittest.IsolatedAsyncioTestCase):
    """Exercise the registered server function without provider initialization."""

    def load_server(self):
        fake_config = types.ModuleType("config")
        fake_config.get_llm_client = lambda: None
        spec = importlib.util.spec_from_file_location("prd_test_server", ROOT / "src/server.py")
        server = importlib.util.module_from_spec(spec)
        # Restore only the injected config, keeping normal dependency imports.
        original_config = sys.modules.get("config")
        sys.modules["config"] = fake_config
        handlers = set(logging.getLogger().handlers)
        def restore_imports_and_logs():
            if original_config is None:
                sys.modules.pop("config", None)
            else:
                sys.modules["config"] = original_config
            for handler in set(logging.getLogger().handlers) - handlers:
                logging.getLogger().removeHandler(handler)
                handler.close()
        self.addCleanup(restore_imports_and_logs)
        with patch.dict(os.environ, {
            "MCP_OUTPUT_DIR": str(self.root),
            "MCP_TASKS_DIR": str(self.tasks_dir),
            "MCP_MD_DIR": str(self.md_dir),
            "MCP_LOGS_DIR": str(self.root / "logs"),
        }), patch.object(
            sys, "path", [str(ROOT / "src")] + sys.path
        ):
            spec.loader.exec_module(server)
        server.task_service = self.service
        server.PROJECT_PRD_CONTENT = "# Previous PRD"
        return server

    async def test_server_invalid_path_preserves_files_and_prd(self):
        server = self.load_server()
        result = await server.decompose_prd(f"file://{self.root / 'missing.md'}")
        self.assertEqual("file_read_error", json.loads(result[0].text)["error_code"])
        self.assertEqual("# Previous PRD", server.PROJECT_PRD_CONTENT)
        self.assert_preserved()

    async def test_server_success_publishes_json_markdown_and_prd(self):
        server = self.load_server()
        result = await server.decompose_prd("# New")
        self.assertIn("New", result[0].text)
        self.assertEqual("# New", server.PROJECT_PRD_CONTENT)
        self.assertIn("### New", self.markdown.read_text(encoding="utf-8"))
        self.assertEqual("New", self.storage.tasks["1"].name)
        self.assertEqual(set(self.before_files), set(self.files()))

    async def test_server_orphan_subtask_preserves_files_and_prd(self):
        class OrphanLLM(SuccessfulLLM):
            async def parse_prd_to_tasks_async(inner, content):
                return [{"id": "1.1", "name": "Orphan"}]

        server = self.load_server()
        self.service.prd_parser.llm_client = OrphanLLM()
        result = await server.decompose_prd("New PRD")
        self.assertEqual("invalid_task_hierarchy", json.loads(result[0].text)["error_code"])
        self.assertEqual("# Previous PRD", server.PROJECT_PRD_CONTENT)
        self.assert_preserved()

    async def test_server_export_failure_preserves_files_and_prd(self):
        server = self.load_server()
        with patch("src.utils.file_operations.os.replace", side_effect=OSError("synthetic failure")):
            result = await server.decompose_prd("# New")
        self.assertFalse(json.loads(result[0].text)["success"])
        self.assertEqual("# Previous PRD", server.PROJECT_PRD_CONTENT)
        self.assert_preserved()


if __name__ == "__main__":
    unittest.main()
