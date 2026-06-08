"""
Chat service — manages conversation state and Claude streaming.
Handles tool execution loop for HR chatbot.
"""
import json
import uuid
from typing import AsyncGenerator, Optional
import anthropic
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.config import settings
from app.models.chat import ChatSession
from app.agents.tools import TOOLS
from app.agents.tool_executor import ToolExecutor

client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)

SYSTEM_PROMPT = """You are TalentOS Assistant, an AI recruitment coordinator for Webknot Technologies.
You help HR professionals create job postings, check internal bench availability, and manage the hiring pipeline.

Your capabilities:
- Generate complete job descriptions from role details
- Check if internal employees are available on bench for a role
- Post confirmed jobs to the careers page
- Show current job posting status and shortlisted candidates

Always be professional, concise, and action-oriented.
When generating a JD, show it clearly and ask for confirmation before posting.
When checking bench, present results clearly and ask HR what they'd like to do.
Never post a job without explicit HR confirmation.
"""


class ChatService:
    @staticmethod
    async def stream(
        db: AsyncSession,
        hr_email: str,
        message: str,
        session_id: Optional[uuid.UUID] = None,
        job_posting_id: Optional[uuid.UUID] = None,
    ) -> AsyncGenerator[str, None]:

        # Load or create session
        session = await ChatService._get_or_create_session(
            db, hr_email, session_id, job_posting_id
        )

        # Append user message
        session.messages.append({
            "role": "user",
            "content": message,
        })

        messages = [
            {"role": m["role"], "content": m["content"]}
            for m in session.messages
        ]

        yield f"data: {json.dumps({'type': 'session_id', 'session_id': str(session.id)})}\n\n"

        # Agentic loop — handles tool calls
        while True:
            response = client.messages.create(
                model="claude-sonnet-4-5",
                max_tokens=2048,
                system=SYSTEM_PROMPT,
                tools=TOOLS,
                messages=messages,
            )

            assistant_content = []

            for block in response.content:
                if block.type == "text":
                    assistant_content.append({"type": "text", "text": block.text})
                    # Stream text chunks
                    for chunk in block.text.split(" "):
                        yield f"data: {json.dumps({'type': 'text', 'content': chunk + ' '})}\n\n"

                elif block.type == "tool_use":
                    assistant_content.append({
                        "type": "tool_use",
                        "id": block.id,
                        "name": block.name,
                        "input": block.input,
                    })

                    yield f"data: {json.dumps({'type': 'tool_call', 'tool': block.name})}\n\n"

                    # Execute tool
                    tool_result = await ToolExecutor.execute(
                        tool_name=block.name,
                        tool_input=block.input,
                        db=db,
                        hr_email=hr_email,
                        session=session,
                    )

                    messages.append({"role": "assistant", "content": assistant_content})
                    messages.append({
                        "role": "user",
                        "content": [{
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": json.dumps(tool_result),
                        }],
                    })
                    assistant_content = []

            if response.stop_reason == "end_turn":
                # Save final assistant message
                session.messages.append({
                    "role": "assistant",
                    "content": " ".join(
                        b["text"] for b in assistant_content if b.get("type") == "text"
                    ),
                })
                await db.commit()
                break

            if response.stop_reason != "tool_use":
                break

        yield f"data: {json.dumps({'type': 'done'})}\n\n"

    @staticmethod
    async def _get_or_create_session(
        db: AsyncSession,
        hr_email: str,
        session_id: Optional[uuid.UUID],
        job_posting_id: Optional[uuid.UUID],
    ) -> ChatSession:
        if session_id:
            result = await db.execute(
                select(ChatSession).where(ChatSession.id == session_id)
            )
            session = result.scalar_one_or_none()
            if session:
                return session

        session = ChatSession(
            hr_email=hr_email,
            job_posting_id=job_posting_id,
            messages=[],
        )
        db.add(session)
        await db.flush()
        return session
