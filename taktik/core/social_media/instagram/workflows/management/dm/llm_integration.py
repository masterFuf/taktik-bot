"""LLM integration: context building, API calls, response cleaning, message filtering.

The call goes through the shared provider (`build_ai_service(...).text_completion`, then
`_call_openrouter`), the single point every paid call passes through: rate-limit retry, cost log,
and `ai_spend` when the workflow was given an `ipc`. This module is core: it never imports a bridge, so the notifier
is injected (`self.ipc`), and the CLI runs without one.
"""

from typing import Optional

from taktik.core.app.ai.factory import build_ai_service
from taktik.core.app.ai.spend import AI_SPEND_DM

from .auto_reply_models import DMAutoReplyConfig


class DMLLMIntegrationMixin:
    """Mixin: LLM context building, OpenRouter API call, response cleaning, message filtering."""

    def _message_matches_filters(self, message: str, config: DMAutoReplyConfig) -> bool:
        """Does the message pass the filters?"""
        message_lower = message.lower()
        
        # Skip when it carries an ignore keyword
        for keyword in config.ignore_keywords:
            if keyword.lower() in message_lower:
                return False
        
        # When reply keywords are configured, require one of them
        if config.respond_only_keywords:
            for keyword in config.respond_only_keywords:
                if keyword.lower() in message_lower:
                    return True
            return False
        
        return True

    def _build_conversation_context(self, username: str, config: DMAutoReplyConfig) -> str:
        """Build the conversation context for the LLM."""
        context_parts = []
        
        # Add the business context
        if config.business_context:
            context_parts.append(f"Business context: {config.business_context}")
        
        # Add the persona
        if config.persona_name:
            context_parts.append(f"You are responding as: {config.persona_name}")
        if config.persona_description:
            context_parts.append(f"Persona: {config.persona_description}")
        
        # Ajouter l'historique de conversation
        if username in self.conversation_history:
            history = self.conversation_history[username][-config.context_messages_count:]
            if history:
                context_parts.append("Previous messages in this conversation:")
                for msg in history:
                    sender = "You" if msg.sender == "me" else msg.sender
                    context_parts.append(f"  {sender}: {msg.content}")
        
        return "\n".join(context_parts)

    async def _generate_reply_with_llm(
        self,
        message: str,
        context: str,
        config: DMAutoReplyConfig
    ) -> Optional[str]:
        """
        Generate a reply through the LLM provider.
        
        Args:
            message: Message reçu
                context: conversation context
            config: Configuration
            
        Returns:
            Réponse générée ou None
        """
        try:
            self.logger.debug(f"Generating reply with LLM ({len(message)} chars incoming)...")
            
            # Build the messages for the OpenRouter API
            messages = [
                {"role": "system", "content": config.system_prompt},
                {"role": "user", "content": f"{context}\n\nUser message: {message}\n\nYour reply (keep it natural and concise):"}
            ]
            
            service = build_ai_service(api_key=config.openrouter_api_key, ipc=getattr(self, "ipc", None))
            result = service.text_completion(
                messages[0]["content"], messages[1]["content"],
                temperature=0.7, max_tokens=150, model=config.llm_model,
                label="dm_auto_reply", kind=AI_SPEND_DM,
            )
        except Exception as e:
            self.logger.error(f"Error calling LLM: {e}")
            return None

        if not result.get("success"):
            self.logger.error(f"OpenRouter API error: {result.get('error')}")
            return None
        reply = self._clean_llm_response(result.get("text", ""))
        self.logger.debug(f"LLM generated ({len(reply)} chars)...")
        return reply

    def _clean_llm_response(self, response: str) -> str:
        """Clean the LLM reply."""
        # Drop the common prefixes
        prefixes_to_remove = [
            "Your reply:",
            "Reply:",
            "Response:",
            "Assistant:",
        ]
        
        for prefix in prefixes_to_remove:
            if response.startswith(prefix):
                response = response[len(prefix):].strip()
        
        # Drop the surrounding quotes
        if response.startswith('"') and response.endswith('"'):
            response = response[1:-1]
        
        return response.strip()
