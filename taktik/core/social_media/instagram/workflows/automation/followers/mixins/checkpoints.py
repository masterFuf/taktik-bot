"""Checkpoint persistence for resumable follower sessions."""

import json
import os
import time
from typing import Dict, Any, List


class FollowerCheckpointsMixin:
    """Mixin: create/load/update/cleanup checkpoints for session resume."""
    
    def _create_checkpoint(self, session_id: str, target_username: str, followers: List[Dict[str, Any]], current_index: int = 0) -> str:
        try:
            checkpoint_data = {
                'session_id': session_id,
                'target_username': target_username,
                'followers': followers,
                'current_index': current_index,
                'total_followers': len(followers),
                'created_at': time.time(),
                'status': 'active'
            }
            
            checkpoint_filename = f"checkpoint_{session_id}_{target_username}.json"
            checkpoint_path = self.checkpoint_dir / checkpoint_filename
            
            with open(checkpoint_path, 'w', encoding='utf-8') as f:
                json.dump(checkpoint_data, f, indent=2, ensure_ascii=False)
            
            self.current_checkpoint_file = str(checkpoint_path)
            self.current_followers_list = followers
            self.current_index = current_index
            
            self.logger.info(f"Checkpoint created: {checkpoint_filename} (index: {current_index}/{len(followers)})")
            return str(checkpoint_path)
            
        except Exception as e:
            self.logger.error(f"Error creating checkpoint: {e}")
            return None
    
    def _load_checkpoint(self, session_id: str, target_username: str) -> Dict[str, Any]:
        try:
            checkpoint_filename = f"checkpoint_{session_id}_{target_username}.json"
            checkpoint_path = self.checkpoint_dir / checkpoint_filename
            
            if not checkpoint_path.exists():
                return None
            
            with open(checkpoint_path, 'r', encoding='utf-8') as f:
                checkpoint_data = json.load(f)
            
            self.current_checkpoint_file = str(checkpoint_path)
            self.current_followers_list = checkpoint_data.get('followers', [])
            self.current_index = checkpoint_data.get('current_index', 0)
            
            self.logger.info(f"Checkpoint loaded: {checkpoint_filename} (index: {self.current_index}/{len(self.current_followers_list)})")
            return checkpoint_data
            
        except Exception as e:
            self.logger.error(f"Error loading checkpoint: {e}")
            return None
    
    def _update_checkpoint_index(self, new_index: int):
        try:
            if not self.current_checkpoint_file or not os.path.exists(self.current_checkpoint_file):
                return
            
            with open(self.current_checkpoint_file, 'r', encoding='utf-8') as f:
                checkpoint_data = json.load(f)
            
            checkpoint_data['current_index'] = new_index
            checkpoint_data['updated_at'] = time.time()
            
            with open(self.current_checkpoint_file, 'w', encoding='utf-8') as f:
                json.dump(checkpoint_data, f, indent=2, ensure_ascii=False)
            
            self.current_index = new_index
            self.logger.debug(f"Checkpoint updated: index {new_index}/{len(self.current_followers_list)}")
            
        except Exception as e:
            self.logger.error(f"Error updating checkpoint: {e}")
    
    def _cleanup_checkpoint(self):
        try:
            if self.current_checkpoint_file and os.path.exists(self.current_checkpoint_file):
                os.remove(self.current_checkpoint_file)
                self.logger.info(f"Checkpoint cleaned: {os.path.basename(self.current_checkpoint_file)}")
            
            self.current_checkpoint_file = None
            self.current_followers_list = []
            self.current_index = 0
            
        except Exception as e:
            self.logger.error(f"Error cleaning checkpoint: {e}")
