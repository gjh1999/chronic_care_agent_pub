from app.memory import store, updater
from app.memory.schemas import MemoryUpdateResult


class MemoryService:

    def load_user_memory(self, user_id: str) -> str:
        """返回可直接放入 prompt 的完整用户上下文文本。"""
        ctx = store.read_all(user_id)
        return ctx.to_prompt_text()

    def get_task_preferences(self, user_id: str) -> str:
        """只返回 preferences 部分，供 plan/reminder 子图使用。"""
        ctx = store.read_all(user_id)
        return ctx.to_task_preferences_text()

    def update_from_session_summary(
        self,
        user_id: str,
        session_summary: str,
    ) -> MemoryUpdateResult:
        """对话结束后，从摘要里提取候选记忆并写入文档。"""
        candidates = updater.extract_candidates(session_summary)
        return updater.update_from_candidates(user_id, candidates)

    def add_memory_note(
        self,
        user_id: str,
        category: str,
        note: str,
        source: str | None = None,
    ) -> None:
        """业务模块主动写入一条记忆（category: profile/preferences/care_context）。"""
        store.append_to(user_id, category, note)


memory_service = MemoryService()
