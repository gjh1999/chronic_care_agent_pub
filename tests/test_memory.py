import shutil
import pytest
from pathlib import Path

from app.memory.service import memory_service

_TEST_USER = "test_memory_user"
_USER_DIR = Path("data/memory/users") / _TEST_USER


@pytest.fixture(autouse=True)
def clean_user_dir():
    """每个测试前后清理测试用户目录，保证隔离。"""
    if _USER_DIR.exists():
        shutil.rmtree(_USER_DIR)
    yield
    if _USER_DIR.exists():
        shutil.rmtree(_USER_DIR)


def test_load_returns_default_when_no_files():
    ctx = memory_service.load_user_memory(_TEST_USER)
    assert isinstance(ctx, str)
    assert len(ctx) > 0


def test_add_memory_note_and_reload():
    memory_service.add_memory_note(_TEST_USER, "preferences", "用户喜欢饭后散步")
    ctx = memory_service.load_user_memory(_TEST_USER)
    assert "饭后散步" in ctx


def test_get_task_preferences_only_returns_preferences():
    memory_service.add_memory_note(_TEST_USER, "preferences", "用户不喜欢早上运动")
    memory_service.add_memory_note(_TEST_USER, "profile", "用户关注血压管理")

    prefs = memory_service.get_task_preferences(_TEST_USER)
    assert "不喜欢早上运动" in prefs
    assert "血压管理" not in prefs


def test_policy_blocks_one_time_data():
    result = memory_service.update_from_session_summary(
        _TEST_USER, "今天血压145/92"
    )
    assert result.skipped >= 1
    assert result.added == 0


def test_policy_allows_long_term_preference():
    result = memory_service.update_from_session_summary(
        _TEST_USER, "用户通常喜欢晚饭后散步"
    )
    assert result.added >= 1


def test_policy_blocks_reminder_note():
    result = memory_service.update_from_session_summary(
        _TEST_USER, "提醒我明天早上测血糖"
    )
    assert result.added == 0


def test_update_writes_to_correct_category():
    memory_service.update_from_session_summary(
        _TEST_USER, "用户喜欢简短的建议风格"
    )
    prefs = memory_service.get_task_preferences(_TEST_USER)
    assert "简短" in prefs
