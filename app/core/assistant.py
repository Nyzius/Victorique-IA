import asyncio
import json
import logging
from typing import AsyncGenerator, Dict, Any, Optional

from app.memory.conversation_store import conversation_store
from app.core.context_builder import context_builder
from app.models.ollama_client import ollama_client
from app.config import settings

logger = logging.getLogger("assistant")

CANCELLED_MARKER = "\n\n_[Geração interrompida pelo usuário.]_"


class AssistantEngine:
    def _save_assistant_message(
        self,
        conversation_id: str,
        content: str,
        sources: Optional[list],
    ) -> Optional[Dict[str, Any]]:
        try:
            return conversation_store.add_message(
                conversation_id=conversation_id,
                role="assistant",
                content=content,
                sources=sources or None,
            )
        except Exception as e:
            logger.error(f"Failed to save assistant message: {e}")
            return None

    async def chat_stream(
        self,
        conversation_id: str,
        user_message: str,
        model: Optional[str] = None,
        project_id: Optional[str] = None,
        personality_id: Optional[str] = None,
        enable_rag: bool = True
    ) -> AsyncGenerator[str, None]:
        """
        Orchestrates one conversation turn and yields SSE JSON events:
        - {"type": "meta", "conversation_id": "...", "model": "..."}
        - {"type": "sources", "data": [...]}
        - {"type": "token", "content": "..."}
        - {"type": "error", "message": "..."} (also emitted as token for compatibility)
        - {"type": "done", "conversation_id": "...", "message_id": "...", "content": "..."}

        If the client disconnects, the underlying Ollama stream is closed and
        the partial answer is persisted with an explicit cancellation marker.
        """
        # Save user message immediately
        conversation_store.add_message(
            conversation_id=conversation_id,
            role="user",
            content=user_message
        )

        selected_model = model or settings.default_model
        full_response_parts: list[str] = []
        sources: list = []
        saved_id: Optional[str] = None
        finished = False

        try:
            yield f"data: {json.dumps({'type': 'meta', 'conversation_id': conversation_id, 'model': selected_model}, ensure_ascii=False)}\n\n"

            history = conversation_store.get_messages(conversation_id)

            ctx = await context_builder.build_context(
                user_query=user_message,
                conversation_history=history,
                project_id=project_id,
                personality_id=personality_id,
                enable_rag=enable_rag
            )

            sources = ctx["sources"]
            if sources:
                yield f"data: {json.dumps({'type': 'sources', 'data': sources}, ensure_ascii=False)}\n\n"

            try:
                async for token in ollama_client.chat_stream(
                    messages=ctx["messages"],
                    model=selected_model,
                    system_prompt=ctx["system_prompt"],
                    max_tokens=settings.max_output_tokens,
                ):
                    full_response_parts.append(token)
                    yield f"data: {json.dumps({'type': 'token', 'content': token}, ensure_ascii=False)}\n\n"
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.error(f"Chat stream generation error: {e}")
                err_msg = f"\n[Erro ao processar resposta do modelo local: {str(e)}]"
                full_response_parts.append(err_msg)
                yield f"data: {json.dumps({'type': 'error', 'message': str(e)}, ensure_ascii=False)}\n\n"
                yield f"data: {json.dumps({'type': 'token', 'content': err_msg}, ensure_ascii=False)}\n\n"

            full_content = "".join(full_response_parts)
            saved = self._save_assistant_message(conversation_id, full_content, sources)
            saved_id = saved["id"] if saved else None
            finished = True

            yield f"data: {json.dumps({'type': 'done', 'conversation_id': conversation_id, 'message_id': saved_id, 'content': full_content}, ensure_ascii=False)}\n\n"

        except (GeneratorExit, asyncio.CancelledError):
            # Client disconnected / generation aborted. Persist partial content.
            partial = "".join(full_response_parts).strip()
            if not finished and partial:
                self._save_assistant_message(
                    conversation_id,
                    partial + CANCELLED_MARKER,
                    sources,
                )
            logger.info(f"Generation cancelled for conversation {conversation_id}")
            raise
        finally:
            # Defensive: if the generator is closed before the done event but no
            # partial content exists, nothing is persisted (user message remains).
            pass


assistant_engine = AssistantEngine()
