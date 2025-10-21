import re
import time
import random
from typing import Optional, List, Dict, Any, Union
from loguru import logger


class ActionUtils:
    @staticmethod
    def parse_number_from_text(text: str) -> Optional[int]:
        if not text:
            return None
        
        text = text.strip().replace(',', '.').replace(' ', '')
        
        patterns = [
            r'(\d+(?:\.\d+)?)\s*([KkMmBb]?)',  # 1.2K, 500, 2.5M
            r'(\d+(?:,\d+)*)',  # 1,234,567
            r'(\d+)'  # Simple number
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                try:
                    number_str = match.group(1)
                    suffix = match.group(2) if len(match.groups()) > 1 else ''
                    
                    number = float(number_str.replace(',', ''))
                    
                    multipliers = {
                        'K': 1000, 'k': 1000,
                        'M': 1000000, 'm': 1000000,
                        'B': 1000000000, 'b': 1000000000
                    }
                    
                    if suffix in multipliers:
                        number *= multipliers[suffix]
                    
                    return int(number)
                    
                except (ValueError, IndexError):
                    continue
        
        return None
    
    @staticmethod
    def clean_username(username: str) -> str:
        if not username:
            return ""
        
        username = username.strip()
        username = username.lstrip('@')
        username = re.sub(r'[^\w._]', '', username)
        
        return username.lower()
    
    @staticmethod
    def is_valid_username(username: str) -> bool:
        if not username:
            return False
        
        clean_name = ActionUtils.clean_username(username)
        
        if len(clean_name) < 1 or len(clean_name) > 30:
            return False
        
        pattern = r'^[a-zA-Z0-9._]+$'
        if not re.match(pattern, clean_name):
            return False
        
        if clean_name.startswith('.') or clean_name.endswith('.'):
            return False
        
        if '..' in clean_name:
            return False
        
        return True
    
    @staticmethod
    def format_duration(seconds: int) -> str:
        if seconds < 60:
            return f"{seconds}s"
        
        minutes = seconds // 60
        remaining_seconds = seconds % 60
        
        if minutes < 60:
            return f"{minutes}m {remaining_seconds}s"
        
        hours = minutes // 60
        remaining_minutes = minutes % 60
        
        if remaining_minutes == 0 and remaining_seconds == 0:
            return f"{hours}h"
        elif remaining_seconds == 0:
            return f"{hours}h {remaining_minutes}m"
        else:
            return f"{hours}h {remaining_minutes}m {remaining_seconds}s"
    
    @staticmethod
    def calculate_rate_per_hour(count: int, duration_seconds: int) -> float:
        if duration_seconds <= 0:
            return 0.0
        
        hours = duration_seconds / 3600
        return count / hours if hours > 0 else 0.0
    
    @staticmethod
    def generate_human_like_delay(min_seconds: float = 1.0, max_seconds: float = 3.0) -> float:
        mean = (min_seconds + max_seconds) / 2
        std_dev = (max_seconds - min_seconds) / 6
        
        delay = random.normalvariate(mean, std_dev)
        
        delay = max(min_seconds, min(max_seconds, delay))
        
        return delay
    
    @staticmethod
    def extract_hashtags_from_text(text: str) -> List[str]:
        if not text:
            return []
        
        pattern = r'#(\w+)'
        hashtags = re.findall(pattern, text)
        return [tag.lower() for tag in hashtags]
    
    @staticmethod
    def extract_mentions_from_text(text: str) -> List[str]:
        if not text:
            return []
        
        pattern = r'@(\w+(?:\.\w+)*)'
        mentions = re.findall(pattern, text)
        return [ActionUtils.clean_username(mention) for mention in mentions]
    
    @staticmethod
    def is_likely_bot_username(username: str) -> bool:
        if not username:
            return True
        
        username = username.lower()
        
        bot_patterns = [
            r'^[a-z]+\d{4,}$',  # lettres suivies de beaucoup de chiffres
            r'^\w+_\w+_\w+_',   # beaucoup d'underscores
            r'^\d+[a-z]+\d+$',  # chiffres-lettres-chiffres
            r'^(bot|fake|spam)',  # mots suspects
            r'(bot|fake|spam)$',
        ]
        
        for pattern in bot_patterns:
            if re.match(pattern, username):
                return True
        
        digit_ratio = sum(c.isdigit() for c in username) / len(username)
        if digit_ratio > 0.5:
            return True
        
        return False
    
    @staticmethod
    def sanitize_filename(filename: str) -> str:
        if not filename:
            return "unnamed"
        
        invalid_chars = r'[<>:"/\\|?*]'
        filename = re.sub(invalid_chars, '_', filename)
        
        filename = filename.strip()
        
        if len(filename) > 200:
            filename = filename[:200]
        
        return filename or "unnamed"
    
    @staticmethod
    def chunk_list(items: List[Any], chunk_size: int) -> List[List[Any]]:
        if chunk_size <= 0:
            return [items]
        
        return [items[i:i + chunk_size] for i in range(0, len(items), chunk_size)]
    
    @staticmethod
    def merge_dicts(*dicts: Dict[str, Any]) -> Dict[str, Any]:
        result = {}
        for d in dicts:
            if isinstance(d, dict):
                result.update(d)
        return result
    
    @staticmethod
    def safe_get(data: Dict[str, Any], key: str, default: Any = None) -> Any:
        if not isinstance(data, dict):
            return default
        
        keys = key.split('.')
        current = data
        
        for k in keys:
            if isinstance(current, dict) and k in current:
                current = current[k]
            else:
                return default
        
        return current
