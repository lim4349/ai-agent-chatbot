"""Supervisor agent for routing user queries to specialist agents."""

import re
from typing import Literal, override

from dependency_injector.wiring import Provide, inject
from langchain_core.messages import BaseMessage
from pydantic import BaseModel, Field

from src.agents.base import BaseAgent
from src.core.di_container import DIContainer
from src.core.logging import get_logger
from src.core.protocols import LLMProvider, MemoryStore, MemoryTool
from src.graph.state import AgentState
from src.observability import extract_token_usage_from_response, record_agent_metrics

logger = get_logger(__name__)


def message_to_dict(msg) -> dict:
    """Convert LangChain message to dict format."""
    if isinstance(msg, dict):
        return msg
    if isinstance(msg, BaseMessage):
        return {"role": msg.type, "content": msg.content}
    return {"role": "user", "content": str(msg)}


# Agent descriptions for dynamic prompt generation
AGENT_DESCRIPTIONS = {
    "rag": "For questions about uploaded documents, knowledge bases, or when the user needs information from stored documents. Use when the query might be answered by internal knowledge.",
    "web_search": "For real-time information, current events, weather, news, latest technology updates, or anything requiring up-to-date information from the internet.",
    "code": "For code writing, debugging, code explanation, algorithm implementation, programming questions, code execution, running Python scripts, executing code and showing results, or any task involving programming languages.",
    "chat": "For general conversation, greetings, casual questions, opinions, creative writing, or any query that doesn't fit the other categories.",
    "report": "For comprehensive research reports that synthesize information from multiple sources (web search, documents, and code execution). Creates structured reports with sections, citations, and executive summaries.",
}

# Workflow pattern hints for multi-step tasks
WORKFLOW_PATTERNS = """
## Multi-Step Workflow Detection

When a user request involves multiple sequential steps, break it down and route to agents one by one.

Common patterns:
1. "Search web → Summarize in code → Write report with RAG"
   - Step 1: web_search (get information)
   - Step 2: code (summarize/transform data)
   - Step 3: rag (combine with documents) or chat (final report)
   - Step 4: done

2. "Analyze this code → Search for similar solutions → Explain"
   - Step 1: code (analyze)
   - Step 2: web_search (find similar)
   - Step 3: chat (explain)

3. "Find documents about X → Write code to process them"
   - Step 1: rag (retrieve documents)
   - Step 2: code (write processing code)

4. "Research report on topic X"
   - Step 1: web_search (get latest information from web)
   - Step 2: rag (retrieve relevant documents if available)
   - Step 3: report (synthesize findings into structured report)
   - Step 4: done

Always set remaining_tasks to track what's left to do.
Return 'done' when all tasks are complete.
"""


def create_route_decision_model(available_agents: set[str]):
    """Create a RouteDecision model with dynamic agent choices."""
    # Include "done" as a valid option for workflow completion
    agent_or_done = Literal[tuple(available_agents | {"done"})]  # type: ignore

    class SupervisorRoutingDecision(BaseModel):
        """Supervisor's decision for routing user queries to specialist agents."""

        selected_agent: agent_or_done = Field(
            description="The name of the agent to route the query to, or 'done' if workflow is complete"
        )
        reasoning: str = Field(description="Brief explanation of why this agent was selected")
        remaining_tasks: list[str] = Field(
            default_factory=list,
            description="List of remaining tasks after this step (e.g., ['code_summarize', 'rag_report'])",
        )

    return SupervisorRoutingDecision


class SupervisorAgent(BaseAgent):
    """Supervisor agent that routes queries to specialist agents."""

    _system_prompt: str = ""  # Instance attribute for dynamic prompt

    @property
    @override
    def name(self) -> str:
        """Agent identifier."""
        return "supervisor"

    # Korean reference patterns for memory-aware routing
    REFERENCE_PATTERNS = [
        r"이전에",
        r"그것",
        r"그거",
        r"그 코드",
        r"그 함수",
        r"그 파일",
        r"방금",
        r"아까",
        r"전에",
        r"위에서",
        r"앞에서",
        r"말한",
        r"얘기한",
        r"질문한",
    ]

    # Simple query patterns for fast-path routing (no LLM call needed)
    SIMPLE_PATTERNS = {
        "greeting": [
            r"^안녕[\s!?.]*$",
            r"^안녕하세요[\s!?.]*$",
            r"^반가워[\s!?.]*$",
            r"^반갑습니다[\s!?.]*$",
            r"^헬로[\s!?.]*$",
            r"^하이[\s!?.]*$",
            r"^hello[\s!?.]*$",
            r"^hi[\s!?.]*$",
            r"^hey[\s!?.]*$",
        ],
        "thanks": [
            r"^고마워[\s!?.]*$",
            r"^감사[\s!?.]*$",
            r"^감사합니다[\s!?.]*$",
            r"^땡큐[\s!?.]*$",
            r"^thanks[\s!?.]*$",
            r"^thank you[\s!?.]*$",
        ],
        "farewell": [
            r"^잘가[\s!?.]*$",
            r"^잘가요[\s!?.]*$",
            r"^바이[\s!?.]*$",
            r"^bye[\s!?.]*$",
            r"^再见[\s!?.]*$",
        ],
    }

    @inject
    def __init__(
        self,
        llm: LLMProvider = Provide[DIContainer.llm],
        available_agents: set[str] | None = None,
        memory: MemoryStore = Provide[DIContainer.memory],
        memory_tool: MemoryTool | None = Provide[DIContainer.memory_tool],
        metrics_store=Provide[DIContainer.metrics_store],
    ):
        """Initialize supervisor with LLM and available agents.

        Args:
            llm: The LLM to use for routing decisions
            available_agents: Set of available agent names (e.g., {'chat', 'code', 'rag'})
            memory: Optional memory store for conversation history
            memory_tool: Optional memory tool for semantic search
            metrics_store: Optional metrics store for observability
        """
        super().__init__(llm=llm, memory=memory)
        # Default to all agents if not specified
        self.available_agents = available_agents or {"chat", "code", "rag", "web_search"}
        # Ensure 'chat' is always available as fallback
        self.available_agents.add("chat")
        self.memory_tool = memory_tool
        self.metrics_store = metrics_store
        self._build_system_prompt()

    @property
    @override
    def system_prompt(self) -> str:
        """System prompt for this agent."""
        return self._system_prompt

    def _build_system_prompt(self):
        """Build system prompt based on available agents."""
        agent_list = []
        for agent in sorted(self.available_agents):
            if agent in AGENT_DESCRIPTIONS:
                agent_list.append(f"- {agent}: {AGENT_DESCRIPTIONS[agent]}")

        self._system_prompt = f"""You are a supervisor that analyzes user queries and routes them to the most appropriate specialist agent.

Available agents:
{chr(10).join(agent_list)}

{WORKFLOW_PATTERNS}

## Routing Rules

Analyze the user's intent and select the SINGLE most appropriate agent.

CRITICAL: Do NOT return 'done' unless the user query is a simple greeting/farewell or the workflow is truly complete.

Examples:
- "코드 실행해서 결과 알려줘" → select "code" agent
- "파이썬으로 2+2 계산해줘" → select "code" agent
- "검색해서 정리해줘" → select "web_search" agent
- "안녕" → select "chat" agent
- "고마워" → select "done"

Consider the context of the conversation when making your decision.

IMPORTANT: If previous steps have been completed (check completed_steps and workflow_context),
continue with the next logical step. Return 'done' only when the entire workflow is complete."""

    def _is_simple_query(self, content: str) -> tuple[str | None, str | None]:
        """Check if query is simple enough to skip LLM routing.

        Args:
            content: The user query content

        Returns:
            Tuple of (agent_name, reasoning) if simple query, (None, None) otherwise
        """
        content_lower = content.lower().strip()

        for pattern_type, patterns in self.SIMPLE_PATTERNS.items():
            for pattern in patterns:
                if re.match(pattern, content_lower, re.IGNORECASE):
                    if pattern_type == "greeting":
                        return ("chat", "Simple greeting detected via pattern matching")
                    else:  # thanks, farewell
                        return ("done", f"Simple {pattern_type} detected via pattern matching")

        return (None, None)

    def _contains_reference_to_previous(self, content: str) -> bool:
        """Check if query contains references to previous conversation.

        Args:
            content: The user query content

        Returns:
            True if query refers to previous conversation
        """
        content_lower = content.lower()

        for pattern in self.REFERENCE_PATTERNS:
            if re.search(pattern, content_lower):
                logger.debug("reference_pattern_matched", pattern=pattern, content=content[:50])
                return True

        return False

    async def _resolve_ambiguous_reference(
        self, session_id: str, content: str
    ) -> list[dict] | None:
        """Resolve ambiguous references using memory search.

        Args:
            session_id: The session identifier
            content: The user query with ambiguous reference

        Returns:
            List of relevant context messages or None
        """
        if not self.memory_tool:
            return None

        try:
            # Search for relevant context
            results = await self.memory_tool.search_memory(
                query=content, session_id=session_id, top_k=3
            )

            if results:
                logger.info(
                    "resolved_reference",
                    session_id=session_id,
                    results_count=len(results),
                )
                return [r["message"] for r in results]

        except Exception as e:
            logger.error("reference_resolution_failed", error=str(e), session_id=session_id)

        return None

    async def _get_memory_enriched_context(
        self, session_id: str, messages: list[dict]
    ) -> list[dict]:
        """Get conversation context enriched with relevant memories.

        Args:
            session_id: The session identifier
            messages: Current messages

        Returns:
            Enriched context messages
        """
        if not messages:
            return []

        # Get the last user message
        last_message = messages[-1]
        content = last_message.get("content", "")

        # Check if it contains ambiguous references
        if not self._contains_reference_to_previous(content):
            return []

        # Try to resolve the reference
        context = await self._resolve_ambiguous_reference(session_id, content)

        if context:
            # Add context marker
            context.insert(
                0,
                {
                    "role": "system",
                    "content": "[Relevant context from previous conversation]",
                },
            )
            return context

        return []

    @override
    async def process(self, state: AgentState) -> AgentState:
        """Analyze query and determine routing.

        Supports multi-step workflows by tracking completed_steps and remaining_tasks.
        """
        session_id = state.get("metadata", {}).get("session_id", "default")
        user_id = state.get("metadata", {}).get("user_id", "anonymous")

        # Get workflow state
        completed_steps = state.get("completed_steps", [])
        remaining_tasks = state.get("remaining_tasks", [])
        workflow_context = state.get("workflow_context", "")

        # If workflow_context is empty but memory has history,
        # extract previous agent responses for context continuity
        if not workflow_context and self.memory:
            history = await self.memory.get_messages(session_id)
            logger.info(
                "restoring_workflow_context",
                session_id=session_id,
                history_count=len(history),
            )
            # Extract recent assistant/ai responses as workflow context
            context_parts = []
            for msg in reversed(history[-10:]):  # Last 10 messages
                role = msg.get("role", "")
                content = msg.get("content", "")
                # Check both "assistant" and "ai" roles (LangChain uses "ai")
                # Skip routing messages
                if (
                    role in ("assistant", "ai")
                    and content
                    and not content.startswith("Routing to:")
                ):
                    # Try to identify which agent produced this
                    agent_hint = "previous"
                    if "web_search" in content.lower() or "검색" in content:
                        agent_hint = "web_search"
                    elif "rag" in content.lower() or "문서" in content:
                        agent_hint = "rag"
                    elif "```python" in content.lower() or "코드" in content:
                        agent_hint = "code"
                    context_parts.append(f"[{agent_hint}]: {content[:1500]}")
                    if len(context_parts) >= 3:  # Max 3 previous responses
                        break
            if context_parts:
                workflow_context = "\n".join(reversed(context_parts))
                logger.info(
                    "restored_workflow_context_from_memory",
                    session_id=session_id,
                    context_length=len(workflow_context),
                    parts_count=len(context_parts),
                )

        # Fast path: Check for simple queries that don't need LLM routing
        # Only apply if this is the first step (no completed_steps yet)
        logger.info(
            "supervisor_process_start",
            session_id=session_id,
            completed_steps=completed_steps,
            messages_count=len(state.get("messages", [])),
        )
        if not completed_steps:
            last_msg = state["messages"][-1] if state["messages"] else None
            if last_msg:
                # Extract content from dict, LangChain message, or string
                if isinstance(last_msg, dict):
                    content = last_msg.get("content", "")
                elif hasattr(last_msg, "content"):
                    content = last_msg.content  # LangChain message
                else:
                    content = str(last_msg)
                logger.info("fast_path_check", session_id=session_id, content=content[:50])
                simple_agent, simple_reasoning = self._is_simple_query(content)
                logger.info(
                    "fast_path_result",
                    session_id=session_id,
                    agent=simple_agent,
                    reasoning=simple_reasoning,
                )
                if simple_agent:
                    logger.info(
                        "simple_query_fast_path",
                        session_id=session_id,
                        agent=simple_agent,
                        reasoning=simple_reasoning,
                    )
                    # Record metrics for fast path
                    if self.metrics_store:
                        await self.metrics_store.record_request(
                            session_id=session_id,
                            agent_name=simple_agent,
                            duration_ms=0,  # Fast path has negligible duration
                            model_name=self.llm.config.model,
                            input_tokens=0,
                            output_tokens=0,
                            status="success",
                            user_id=user_id,
                            metadata={"fast_path": True, "reasoning": simple_reasoning},
                        )
                    if simple_agent == "done":
                        # Simple thanks/farewell - respond directly
                        final_response = await self._generate_final_response(
                            state, simple_reasoning, session_id, user_id
                        )
                        return {
                            **state,
                            "next_agent": "done",
                            "remaining_tasks": [],
                            "messages": [
                                *state["messages"],
                                {"role": "assistant", "content": final_response},
                            ],
                            "metadata": {
                                **state.get("metadata", {}),
                                "route_reasoning": simple_reasoning,
                            },
                        }
                    else:
                        # Simple greeting - route directly to chat
                        return {
                            **state,
                            "next_agent": simple_agent,
                            "remaining_tasks": [],
                            "metadata": {
                                **state.get("metadata", {}),
                                "route_reasoning": simple_reasoning,
                            },
                        }

        # Inject document context into system prompt for better routing
        has_documents = state.get("has_documents", False)
        doc_context = (
            "\n\nIMPORTANT: The user HAS uploaded documents in this session. "
            "Route to 'rag' if the question might be answered by those documents."
            if has_documents
            else "\n\nIMPORTANT: The user has NOT uploaded any documents in this session. "
            "Do NOT route to 'rag' unless the user explicitly asks about uploading or using documents. "
            "Prefer 'chat' or 'web_search' for informational queries."
        )

        # Build workflow context message for multi-step scenarios
        workflow_info = ""
        if completed_steps:
            workflow_info = f"""

## Current Workflow Status
- Completed steps: {completed_steps}
- Remaining tasks: {remaining_tasks if remaining_tasks else "None - ready to complete"}
- Context from previous steps: {workflow_context[:500] if workflow_context else "None"}

Continue with the next logical step or return 'done' if all tasks are complete."""

        messages = [{"role": "system", "content": self.system_prompt + doc_context + workflow_info}]

        # Include conversation history if memory is available
        if self.memory:
            history = await self.memory.get_messages(session_id)
            messages.extend(history)

        # Check for ambiguous references and enrich context
        current_messages = [message_to_dict(msg) for msg in state["messages"]]
        enriched_context = await self._get_memory_enriched_context(session_id, current_messages)
        if enriched_context:
            messages.extend(enriched_context)
            logger.info(
                "enriched_context_added",
                session_id=session_id,
                context_messages=len(enriched_context),
            )

        # Convert LangChain messages to dict format
        for msg in state["messages"]:
            messages.append(message_to_dict(msg))

        # Get user_id from state metadata
        user_id = state.get("metadata", {}).get("user_id", "anonymous")

        # Get structured routing decision with dynamic model
        route_decision = create_route_decision_model(self.available_agents)

        # Wrap LLM call with metrics recording
        try:
            if self.metrics_store:
                async with record_agent_metrics(
                    metrics_store=self.metrics_store,
                    session_id=session_id,
                    agent_name=self.name,
                    model_name=self.llm.config.model,
                    user_id=user_id,
                ) as metrics:
                    decision = await self.llm.generate_structured(
                        messages=messages,
                        output_schema=route_decision,
                    )
                    input_tokens, output_tokens = extract_token_usage_from_response(decision)
                    metrics.set_token_count(input_tokens, output_tokens)
            else:
                decision = await self.llm.generate_structured(
                    messages=messages,
                    output_schema=route_decision,
                )
        except Exception as e:
            logger.error("supervisor_generate_structured_failed", error=str(e), session_id=session_id)
            raise

        # Handle None response from LLM (fallback to chat or done)
        if not decision:
            logger.warning("supervisor_llm_returned_none", session_id=session_id)
            # If we have completed steps, consider workflow done
            if completed_steps:
                decision = {
                    "selected_agent": "done",
                    "reasoning": "LLM response was empty, but steps were completed",
                    "remaining_tasks": [],
                }
            else:
                decision = {
                    "selected_agent": "chat",
                    "reasoning": "LLM response was empty, defaulting to chat",
                    "remaining_tasks": [],
                }

        # Safe access with defaults
        selected_agent = decision.get("selected_agent", "chat")
        reasoning = decision.get("reasoning", "No reasoning provided")
        new_remaining_tasks = decision.get("remaining_tasks", [])

        # Store the routing exchange in memory if available
        if self.memory:
            last_msg = state["messages"][-1]
            await self.memory.add_message(session_id, message_to_dict(last_msg))
            await self.memory.add_message(
                session_id,
                {
                    "role": "assistant",
                    "content": f"Routing to: {selected_agent} (reasoning: {reasoning})",
                },
            )

        # If selected_agent is 'done', decide whether supervisor needs to respond directly
        if selected_agent == "done":
            if not completed_steps:
                # No specialist agent ran — supervisor must respond directly (e.g., greetings/farewells)
                final_response = await self._generate_final_response(
                    state, reasoning, session_id, user_id
                )
                return {
                    **state,
                    "next_agent": "done",
                    "remaining_tasks": [],
                    "messages": [
                        *state["messages"],
                        {"role": "assistant", "content": final_response},
                    ],
                    "metadata": {
                        **state.get("metadata", {}),
                        "route_reasoning": reasoning,
                    },
                }
            else:
                # Specialist agent(s) already responded — skip redundant LLM call
                logger.info(
                    "supervisor_done",
                    session_id=session_id,
                    completed_steps=completed_steps,
                )
                return {
                    **state,
                    "next_agent": "done",
                    "remaining_tasks": [],
                    "metadata": {
                        **state.get("metadata", {}),
                        "route_reasoning": reasoning,
                    },
                }

        logger.info(
            "supervisor_routing",
            session_id=session_id,
            selected_agent=selected_agent,
            completed_steps=completed_steps,
            remaining_tasks=new_remaining_tasks,
        )

        return {
            **state,
            "next_agent": selected_agent,
            "remaining_tasks": new_remaining_tasks,
            "workflow_context": workflow_context,  # Include restored context
            "metadata": {
                **state.get("metadata", {}),
                "route_reasoning": reasoning,
            },
        }

    async def _generate_final_response(
        self, state: AgentState, reasoning: str, session_id: str, user_id: str
    ) -> str:
        """Generate a final response when workflow is complete.

        Args:
            state: Current agent state
            reasoning: Routing reasoning
            session_id: Session identifier
            user_id: User identifier

        Returns:
            Final response string
        """
        workflow_context = state.get("workflow_context", "")
        messages = state.get("messages", [])

        # If there's workflow context, summarize it
        if workflow_context:
            prompt = f"""Based on the following workflow results, provide a concise summary response:

Workflow Context:
{workflow_context[:2000]}

Provide a helpful response summarizing the results."""

            try:
                # Wrap LLM call with metrics recording
                messages = [
                    {
                        "role": "system",
                        "content": "You are a helpful assistant summarizing workflow results.",
                    },
                    {"role": "user", "content": prompt},
                ]

                if self.metrics_store:
                    async with record_agent_metrics(
                        metrics_store=self.metrics_store,
                        session_id=session_id,
                        agent_name=self.name,
                        model_name=self.llm.config.model,
                        user_id=user_id,
                    ) as metrics:
                        response, usage = await self.llm.generate_with_usage(messages)
                        metrics.set_token_count(
                            usage.get("input_tokens", 0), usage.get("output_tokens", 0)
                        )
                        return response

                response, _ = await self.llm.generate_with_usage(messages)
                return response
            except Exception as e:
                logger.error("final_response_generation_failed", error=str(e))
                return "작업이 완료되었습니다. 추가로 도움이 필요하시면 말씀해 주세요."

        # If no context but has messages, provide generic completion message
        if messages and len(messages) > 1:
            return "도움이 되셨나요? 추가로 궁금하신 점이 있으면 말씀해 주세요."

        # Default fallback
        return "안녕하세요! 무엇을 도와드릴까요?"
