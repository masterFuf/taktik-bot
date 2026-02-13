"""LLM integration: context building, API calls, response cleaning, message filtering."""

import httpx
from typing import Optional
from .auto_reply_models import DMAutoReplyConfig


class DMLLMIntegrationMixin:
    """Mixin: LLM context building, fal.ai API call, response cleaning, message filtering."""

    def _message_matches_filters(self, message: str, config: DMAutoReplyConfig) -> bool:
        """Vérifier si le message passe les filtres."""
        message_lower = message.lower()
        
        # Ignorer si contient des mots-clés à ignorer
        for keyword in config.ignore_keywords:
            if keyword.lower() in message_lower:
                return False
        
        # Si des mots-clés de réponse sont définis, vérifier leur présence
        if config.respond_only_keywords:
            for keyword in config.respond_only_keywords:
                if keyword.lower() in message_lower:
                    return True
            return False
        
        return True

    def _build_conversation_context(self, username: str, config: DMAutoReplyConfig) -> str:
        """Construire le contexte de conversation pour le LLM."""
        context_parts = []
        
        # Ajouter le contexte business
        if config.business_context:
            context_parts.append(f"Business context: {config.business_context}")
        
        # Ajouter la persona
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
        Générer une réponse via fal.ai LLM.
        
        Args:
            message: Message reçu
            context: Contexte de la conversation
            config: Configuration
            
        Returns:
            Réponse générée ou None
        """
        try:
            self.logger.debug(f"Generating reply with LLM for: {message[:50]}...")
            
            # Construire le prompt
            full_prompt = f"""{config.system_prompt}

{context}

User message: {message}

Your reply (keep it natural and concise):"""
            
            # Appel à fal.ai
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    "https://fal.run/fal-ai/lora",
                    headers={
                        "Authorization": f"Key {config.fal_api_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model_name": config.llm_model,
                        "prompt": full_prompt,
                        "max_tokens": 150,
                        "temperature": 0.7
                    }
                )
                
                if response.status_code == 200:
                    result = response.json()
                    reply = result.get("output", "").strip()
                    
                    # Nettoyer la réponse
                    reply = self._clean_llm_response(reply)
                    
                    self.logger.debug(f"LLM generated: {reply[:50]}...")
                    return reply
                else:
                    self.logger.error(f"fal.ai API error: {response.status_code} - {response.text}")
                    return None
                    
        except Exception as e:
            self.logger.error(f"Error calling LLM: {e}")
            return None

    def _clean_llm_response(self, response: str) -> str:
        """Nettoyer la réponse du LLM."""
        # Supprimer les préfixes courants
        prefixes_to_remove = [
            "Your reply:",
            "Reply:",
            "Response:",
            "Assistant:",
        ]
        
        for prefix in prefixes_to_remove:
            if response.startswith(prefix):
                response = response[len(prefix):].strip()
        
        # Supprimer les guillemets encadrants
        if response.startswith('"') and response.endswith('"'):
            response = response[1:-1]
        
        return response.strip()
