"""User profiler for extracting and storing user information."""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from src.core.logging import get_logger

if TYPE_CHECKING:
    from src.memory.long_term_memory import LongTermMemory

logger = get_logger(__name__)


@dataclass
class UserProfile:
    """Structured user profile data."""

    user_id: str
    interests: list[str] = field(default_factory=list)
    preferred_response_style: str = "balanced"  # concise, detailed, balanced
    technical_level: str = "intermediate"  # beginner, intermediate, advanced
    expertise_areas: list[str] = field(default_factory=list)
    communication_preferences: dict[str, Any] = field(default_factory=dict)
    goals: list[str] = field(default_factory=list)
    pain_points: list[str] = field(default_factory=list)
    last_updated: str | None = None


class UserProfiler:
    """Extract and manage user profiles from conversations.

    Uses LLM analysis to extract user information and preferences,
    storing them in long-term memory for personalization.
    """

    def __init__(
        self,
        llm,
        long_term_memory: "LongTermMemory | None" = None,
    ):
        """Initialize user profiler.

        Args:
            llm: LLM provider for analysis
            long_term_memory: Long-term memory store for persistence
        """
        self.llm = llm
        self.memory = long_term_memory

    _PROFILE_EXTRACTION_PROMPT = """Analyze the following conversation and extract user profile information.

Conversation:
{conversation}

Extract the following information about the user (respond in JSON format):
{{
    "interests": ["list of topics the user is interested in"],
    "technical_level": "beginner|intermediate|advanced",
    "preferred_response_style": "concise|detailed|balanced",
    "expertise_areas": ["areas where user shows expertise"],
    "communication_preferences": {{
        "formality": "casual|formal|professional",
        "detail_level": "high-level|detailed|step-by-step"
    }},
    "goals": ["user's apparent goals or objectives"],
    "pain_points": ["challenges or frustrations mentioned"]
}}

Only include fields where you have clear evidence from the conversation.
Respond with valid JSON only."""

    _FACT_EXTRACTION_PROMPT = """Analyze the following conversation and extract facts about the user.

Conversation:
{conversation}

Extract specific facts about the user that would be useful for future conversations.
Focus on:
- Personal preferences (communication style, format preferences)
- Technical background and skills
- Domain knowledge and expertise
- Work context (role, industry, team size)
- Tools and technologies they use
- Goals and objectives

Respond in JSON format:
{{
    "facts": [
        {{
            "fact": "the specific fact",
            "category": "preferences|technical|domain|work|tools|goals",
            "confidence": 0.0-1.0
        }}
    ]
}}

Only include facts with high confidence (>= 0.7).
Respond with valid JSON only."""

    async def analyze_conversation(
        self,
        user_id: str,
        messages: list[dict],
    ) -> UserProfile | None:
        """Analyze conversation and extract/update user profile.

        Args:
            user_id: User identifier
            messages: List of conversation messages

        Returns:
            Updated user profile or None if analysis failed
        """
        if not messages:
            return None

        # Format conversation for analysis
        conversation = self._format_conversation(messages)

        try:
            # Extract profile information
            profile_data = await self.llm.generate_structured(
                messages=[
                    {
                        "role": "user",
                        "content": self._PROFILE_EXTRACTION_PROMPT.format(
                            conversation=conversation
                        ),
                    }
                ],
                output_schema=dict,
            )

            # Extract specific facts
            facts_data = await self.llm.generate_structured(
                messages=[
                    {
                        "role": "user",
                        "content": self._FACT_EXTRACTION_PROMPT.format(conversation=conversation),
                    }
                ],
                output_schema=dict,
            )

            # Build profile
            profile = UserProfile(user_id=user_id)

            if profile_data:
                profile.interests = profile_data.get("interests", [])
                profile.technical_level = profile_data.get("technical_level", "intermediate")
                profile.preferred_response_style = profile_data.get(
                    "preferred_response_style", "balanced"
                )
                profile.expertise_areas = profile_data.get("expertise_areas", [])
                profile.communication_preferences = profile_data.get(
                    "communication_preferences", {}
                )
                profile.goals = profile_data.get("goals", [])
                profile.pain_points = profile_data.get("pain_points", [])

            # Store facts in long-term memory
            if self.memory and facts_data:
                for fact_item in facts_data.get("facts", []):
                    await self.memory.store_user_fact(
                        user_id=user_id,
                        fact=fact_item["fact"],
                        category=fact_item.get("category", "general"),
                        confidence=fact_item.get("confidence", 0.8),
                    )

            # Store profile in long-term memory
            if self.memory:
                await self._store_profile(user_id, profile)

            logger.debug(
                "conversation_analyzed",
                user_id=user_id,
                interests_count=len(profile.interests),
                facts_count=len(facts_data.get("facts", [])),
            )

            return profile

        except Exception as e:
            logger.error("profile_analysis_failed", error=str(e), user_id=user_id)
            return None

    async def get_profile(self, user_id: str) -> UserProfile | None:
        """Get user profile from long-term memory.

        Args:
            user_id: User identifier

        Returns:
            User profile or None if not found
        """
        if not self.memory:
            return None

        try:
            profile_data = await self.memory.get_user_profile(user_id)

            if not profile_data or not profile_data.get("facts"):
                return None

            # Build profile from stored data
            profile = UserProfile(user_id=user_id)

            # Extract interests from facts
            interests_facts = profile_data.get("facts", {}).get("interests", [])
            profile.interests = [f["fact"] for f in interests_facts]

            # Get technical level from preferences
            prefs = profile_data.get("facts", {}).get("preferences", [])
            for pref in prefs:
                if "technical" in pref["fact"].lower():
                    if "beginner" in pref["fact"].lower():
                        profile.technical_level = "beginner"
                    elif "advanced" in pref["fact"].lower():
                        profile.technical_level = "advanced"

            # Get response style
            for pref in prefs:
                if "style" in pref["fact"].lower():
                    if "concise" in pref["fact"].lower():
                        profile.preferred_response_style = "concise"
                    elif "detailed" in pref["fact"].lower():
                        profile.preferred_response_style = "detailed"

            # Get expertise areas
            expertise_facts = profile_data.get("facts", {}).get("domain", [])
            profile.expertise_areas = [f["fact"] for f in expertise_facts]

            return profile

        except Exception as e:
            logger.error("profile_retrieval_failed", error=str(e), user_id=user_id)
            return None

    async def update_from_message(
        self,
        user_id: str,
        message: dict,
        context_messages: list[dict] | None = None,
    ) -> None:
        """Incrementally update profile from a single message.

        Args:
            user_id: User identifier
            message: The new message to analyze
            context_messages: Optional recent context messages
        """
        messages = context_messages or []
        messages.append(message)

        # Only analyze if we have enough context
        if len(messages) < 3:
            return

        # Analyze every N messages to avoid excessive LLM calls
        if len(messages) % 5 != 0:
            return

        await self.analyze_conversation(user_id, messages)

    def _format_conversation(self, messages: list[dict]) -> str:
        """Format messages for analysis.

        Args:
            messages: List of conversation messages

        Returns:
            Formatted conversation string
        """
        lines = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if content:
                lines.append(f"{role}: {content}")
        return "\n".join(lines)

    async def _store_profile(self, user_id: str, profile: UserProfile) -> None:
        """Store profile in long-term memory.

        Args:
            user_id: User identifier
            profile: User profile to store
        """
        if not self.memory:
            return

        from datetime import datetime

        updates = {
            "interests": profile.interests,
            "technical_level": profile.technical_level,
            "preferred_response_style": profile.preferred_response_style,
            "expertise_areas": profile.expertise_areas,
            "communication_preferences": profile.communication_preferences,
            "goals": profile.goals,
            "pain_points": profile.pain_points,
            "updated_at": datetime.utcnow().isoformat(),
        }

        await self.memory.update_user_profile(user_id, updates)

    def get_personalization_context(self, profile: UserProfile | None) -> str:
        """Generate personalization context for LLM prompts.

        Args:
            profile: User profile

        Returns:
            Context string for personalization
        """
        if not profile:
            return ""

        context_parts = []

        if profile.technical_level != "intermediate":
            context_parts.append(f"User technical level: {profile.technical_level}")

        if profile.preferred_response_style != "balanced":
            context_parts.append(f"Preferred response style: {profile.preferred_response_style}")

        if profile.interests:
            context_parts.append(f"User interests: {', '.join(profile.interests[:5])}")

        if profile.expertise_areas:
            context_parts.append(f"Expertise areas: {', '.join(profile.expertise_areas[:3])}")

        if not context_parts:
            return ""

        return "\nUser Context:\n" + "\n".join(f"- {p}" for p in context_parts)
