"""Tests for file tools."""

import os

import pytest

from backend.tools.file import ListDirectoryTool, ReadFileTool, WriteFileTool


class TestReadFileTool:
    def test_read_existing_file(self, sandbox_dir, agent_context):
        # Create a test file
        test_file = os.path.join(sandbox_dir, "test.txt")
        with open(test_file, "w") as f:
            f.write("hello world")

        tool = ReadFileTool()
        result = tool._run(path=test_file)
        assert result == "hello world"

    def test_read_nonexistent_file(self, sandbox_dir, agent_context):
        tool = ReadFileTool()
        result = tool._run(path=os.path.join(sandbox_dir, "missing.txt"))
        assert "error" in result
        assert "not found" in result.lower()

    def test_read_outside_sandbox(self, sandbox_dir, agent_context):
        tool = ReadFileTool()
        result = tool._run(path="/etc/passwd")
        assert "error" in result
        assert "denied" in result.lower() or "outside" in result.lower()

    def test_read_directory_fails(self, sandbox_dir, agent_context):
        tool = ReadFileTool()
        result = tool._run(path=sandbox_dir)
        assert "error" in result
        assert "not a file" in result.lower()


class TestWriteFileTool:
    def test_write_new_file(self, sandbox_dir, agent_context):
        tool = WriteFileTool()
        test_file = os.path.join(sandbox_dir, "output.txt")
        result = tool._run(path=test_file, content="hello")

        assert os.path.exists(test_file)
        with open(test_file) as f:
            assert f.read() == "hello"
        assert "created" in result

    def test_write_creates_dirs(self, sandbox_dir, agent_context):
        tool = WriteFileTool()
        test_file = os.path.join(sandbox_dir, "subdir", "deep", "file.txt")
        tool._run(path=test_file, content="nested")

        assert os.path.exists(test_file)

    def test_append_mode(self, sandbox_dir, agent_context):
        tool = WriteFileTool()
        test_file = os.path.join(sandbox_dir, "append.txt")
        with open(test_file, "w") as f:
            f.write("first ")

        tool._run(path=test_file, content="second", mode="a")
        with open(test_file) as f:
            assert f.read() == "first second"

    def test_write_outside_sandbox(self, sandbox_dir, agent_context):
        tool = WriteFileTool()
        result = tool._run(path="/tmp/evil.txt", content="hack")
        assert "error" in result

    def test_write_exceeds_max_size(self, sandbox_dir, agent_context):
        from backend.config.settings import settings
        original = settings.MAX_FILE_SIZE_BYTES
        settings.MAX_FILE_SIZE_BYTES = 100  # 100 bytes limit for test

        tool = WriteFileTool()
        test_file = os.path.join(sandbox_dir, "big.txt")
        result = tool._run(path=test_file, content="x" * 200)
        assert "error" in result
        assert "too large" in result.lower()
        assert not os.path.exists(test_file)  # file should NOT have been created

        settings.MAX_FILE_SIZE_BYTES = original

    def test_write_within_max_size(self, sandbox_dir, agent_context):
        from backend.config.settings import settings
        original = settings.MAX_FILE_SIZE_BYTES
        settings.MAX_FILE_SIZE_BYTES = 1000

        tool = WriteFileTool()
        test_file = os.path.join(sandbox_dir, "ok.txt")
        result = tool._run(path=test_file, content="small content")
        assert "error" not in result
        assert os.path.exists(test_file)

        settings.MAX_FILE_SIZE_BYTES = original


class TestListDirectoryTool:
    def test_list_files(self, sandbox_dir, agent_context):
        # Create some files
        for name in ["a.py", "b.txt", "c.md"]:
            with open(os.path.join(sandbox_dir, name), "w") as f:
                f.write("")

        tool = ListDirectoryTool()
        result = tool._run(path=sandbox_dir)
        assert "a.py" in result
        assert "b.txt" in result

    def test_list_with_pattern(self, sandbox_dir, agent_context):
        for name in ["a.py", "b.txt", "c.py"]:
            with open(os.path.join(sandbox_dir, name), "w") as f:
                f.write("")

        tool = ListDirectoryTool()
        result = tool._run(path=sandbox_dir, pattern="*.py")
        assert "a.py" in result
        assert "c.py" in result
        assert "b.txt" not in result

    def test_list_nonexistent_dir(self, sandbox_dir, agent_context):
        tool = ListDirectoryTool()
        result = tool._run(path=os.path.join(sandbox_dir, "missing"))
        assert "error" in result
