"""LLM integration: context building, API calls, response cleaning, message filtering."""

import json
import urllib.request
import urllib.error
from typing import Optional
from .auto_reply_models import DMAutoReplyConfig

OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"


class DMLLMIntegrationMixin:
    """Mixin: LLM context building, OpenRouter API call, response cleaning, message filtering."""

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
        Générer une réponse via OpenRouter LLM.
        
        Args:
            message: Message reçu
            context: Contexte de la conversation
            config: Configuration
            
        Returns:
            Réponse générée ou None
        """
        try:
            self.logger.debug(f"Generating reply with LLM for: {message[:50]}...")
            
            # Construire les messages pour l'API OpenRouter
            messages = [
                {"role": "system", "content": config.system_prompt},
                {"role": "user", "content": f"{context}\n\nUser message: {message}\n\nYour reply (keep it natural and concise):"}
            ]
            
            headers = {
                "Authorization": f"Bearer {config.openrouter_api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://taktik-bot.com",
                "X-Title": "TAKTIK Bot",
            }
            body = json.dumps({
                "model": config.llm_model,
                "messages": messages,
                "max_tokens": 150,
                "temperature": 0.7,
            }).encode("utf-8")
            
            req = urllib.request.Request(OPENROUTER_API_URL, data=body, headers=headers, method="POST")
            
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                choice = data.get("choices", [{}])[0]
                reply = choice.get("message", {}).get("content", "").strip()
                
                # Nettoyer la réponse
                reply = self._clean_llm_response(reply)
                
                self.logger.debug(f"LLM generated: {reply[:50]}...")
                return reply
                    
        except urllib.error.HTTPError as e:
            error_body = ""
            try:
                error_body = e.read().decode("utf-8")
            except Exception:
                pass
            self.logger.error(f"OpenRouter API error: {e.code} - {error_body[:300]}")
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
