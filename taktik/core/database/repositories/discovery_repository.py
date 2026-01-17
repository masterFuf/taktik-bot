"""
Discovery Repository - Manages discovery_campaigns, scraped_profiles, discovery_progress tables
"""

import json
from typing import Dict, List, Optional, Any, Tuple
from .base_repository import BaseRepository


class DiscoveryRepository(BaseRepository):
    """Repository for discovery campaigns and scraped profiles"""
    
    # ============================================
    # DISCOVERY CAMPAIGNS
    # ============================================
    
    def create_campaign(
        self,
        account_id: int,
        name: str,
        description: Optional[str] = None,
        niche_keywords: Optional[List[str]] = None,
        target_hashtags: Optional[List[str]] = None,
        target_accounts: Optional[List[str]] = None,
        target_post_urls: Optional[List[str]] = None,
        min_score_threshold: int = 60
    ) -> Optional[int]:
        """Create a new discovery campaign"""
        try:
            cursor = self.execute(
                """INSERT INTO discovery_campaigns (
                    account_id, name, description, niche_keywords, target_hashtags,
                    target_accounts, target_post_urls, min_score_threshold
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    account_id,
                    name,
                    description,
                    json.dumps(niche_keywords or []),
                    json.dumps(target_hashtags or []),
                    json.dumps(target_accounts or []),
                    json.dumps(target_post_urls or []),
                    min_score_threshold
                )
            )
            return cursor.lastrowid
        except Exception as e:
            print(f"Error creating discovery campaign: {e}")
            return None
    
    def find_campaign_by_id(self, campaign_id: int) -> Optional[Dict[str, Any]]:
        """Find campaign by ID"""
        row = self.query_one(
            "SELECT * FROM discovery_campaigns WHERE campaign_id = ?",
            (campaign_id,)
        )
        return self._map_campaign_row(row)
    
    def find_campaigns_by_account(self, account_id: int) -> List[Dict[str, Any]]:
        """Get campaigns by account"""
        rows = self.query(
            "SELECT * FROM discovery_campaigns WHERE account_id = ? ORDER BY updated_at DESC",
            (account_id,)
        )
        return [self._map_campaign_row(row) for row in rows]
    
    def update_campaign_stats(
        self,
        campaign_id: int,
        total_discovered: Optional[int] = None,
        total_qualified: Optional[int] = None,
        total_contacted: Optional[int] = None,
        total_converted: Optional[int] = None
    ) -> bool:
        """Update campaign stats"""
        updates = ["updated_at = datetime('now')"]
        values = []
        
        if total_discovered is not None:
            updates.append('total_discovered = ?')
            values.append(total_discovered)
        if total_qualified is not None:
            updates.append('total_qualified = ?')
            values.append(total_qualified)
        if total_contacted is not None:
            updates.append('total_contacted = ?')
            values.append(total_contacted)
        if total_converted is not None:
            updates.append('total_converted = ?')
            values.append(total_converted)
        
        values.append(campaign_id)
        cursor = self.execute(
            f"UPDATE discovery_campaigns SET {', '.join(updates)} WHERE campaign_id = ?",
            tuple(values)
        )
        return cursor.rowcount > 0
    
    # ============================================
    # SCRAPED PROFILES (Junction table with AI scores)
    # ============================================
    
    def link_profile_to_session(self, scraping_id: int, profile_id: int) -> bool:
        """Link a profile to a scraping session"""
        try:
            self.execute(
                "INSERT OR IGNORE INTO scraped_profiles (scraping_id, profile_id) VALUES (?, ?)",
                (scraping_id, profile_id)
            )
            return True
        except Exception as e:
            print(f"Error linking profile to session: {e}")
            return False
    
    def link_profiles_to_session(self, scraping_id: int, profile_ids: List[int]) -> int:
        """Link multiple profiles to a scraping session (batch)"""
        if not profile_ids:
            return 0
        
        linked = 0
        for profile_id in profile_ids:
            try:
                self.execute(
                    "INSERT OR IGNORE INTO scraped_profiles (scraping_id, profile_id) VALUES (?, ?)",
                    (scraping_id, profile_id)
                )
                linked += 1
            except:
                pass
        
        return linked
    
    def get_scraped_profiles(self, scraping_id: int) -> List[Dict[str, Any]]:
        """Get profiles for a scraping session with details"""
        rows = self.query(
            """SELECT 
                sp.id, sp.scraping_id, sp.profile_id, sp.scraped_at,
                sp.ai_score, sp.ai_qualified, sp.ai_analysis,
                sp.qualification_criteria, sp.scored_at,
                ip.username, ip.full_name, ip.biography,
                ip.followers_count, ip.following_count, ip.posts_count,
                ip.is_private, ip.is_verified, ip.is_business, ip.business_category
            FROM scraped_profiles sp
            JOIN instagram_profiles ip ON sp.profile_id = ip.profile_id
            WHERE sp.scraping_id = ?
            ORDER BY sp.ai_score DESC NULLS LAST, sp.scraped_at DESC""",
            (scraping_id,)
        )
        return [self._map_scraped_profile_row(row) for row in rows]
    
    def update_ai_scores(
        self,
        scraping_id: int,
        scores: List[Dict[str, Any]],
        qualification_criteria: str
    ) -> int:
        """Update AI scores for scraped profiles (batch)"""
        updated = 0
        
        for score in scores:
            cursor = self.execute(
                """UPDATE scraped_profiles 
                   SET ai_score = ?, ai_qualified = ?, ai_analysis = ?,
                       qualification_criteria = ?, scored_at = datetime('now')
                   WHERE scraping_id = ? AND profile_id = ?""",
                (
                    score.get('ai_score') or score.get('aiScore'),
                    1 if (score.get('ai_qualified') or score.get('aiQualified')) else 0,
                    score.get('ai_analysis') or score.get('aiAnalysis'),
                    qualification_criteria,
                    scraping_id,
                    score.get('profile_id') or score.get('profileId')
                )
            )
            if cursor.rowcount > 0:
                updated += 1
        
        print(f"[DiscoveryRepository] Updated AI scores for {updated} profiles")
        return updated
    
    def get_qualified_profiles(self, scraping_id: int, min_score: int = 60) -> List[Dict[str, Any]]:
        """Get qualified profiles for a scraping session"""
        rows = self.query(
            """SELECT sp.*, ip.username, ip.full_name, ip.biography,
                ip.followers_count, ip.following_count, ip.posts_count,
                ip.is_private, ip.is_verified, ip.is_business, ip.business_category
            FROM scraped_profiles sp
            JOIN instagram_profiles ip ON sp.profile_id = ip.profile_id
            WHERE sp.scraping_id = ? AND sp.ai_qualified = 1 AND sp.ai_score >= ?
            ORDER BY sp.ai_score DESC""",
            (scraping_id, min_score)
        )
        return [self._map_scraped_profile_row(row) for row in rows]
    
    def count_by_qualification(self, scraping_id: int) -> Dict[str, int]:
        """Count profiles by qualification status"""
        row = self.query_one(
            """SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN ai_qualified = 1 THEN 1 ELSE 0 END) as qualified,
                SUM(CASE WHEN ai_qualified = 0 AND ai_score IS NOT NULL THEN 1 ELSE 0 END) as not_qualified,
                SUM(CASE WHEN ai_score IS NULL THEN 1 ELSE 0 END) as not_scored
            FROM scraped_profiles
            WHERE scraping_id = ?""",
            (scraping_id,)
        )
        
        return {
            'total': row['total'] if row else 0,
            'qualified': row['qualified'] if row else 0,
            'not_qualified': row['not_qualified'] if row else 0,
            'not_scored': row['not_scored'] if row else 0
        }
    
    # ============================================
    # DISCOVERY PROGRESS
    # ============================================
    
    def get_or_create_progress(
        self,
        campaign_id: int,
        source_type: str,
        source_value: str
    ) -> Tuple[int, bool]:
        """Get or create discovery progress record"""
        row = self.query_one(
            """SELECT progress_id FROM discovery_progress 
               WHERE campaign_id = ? AND source_type = ? AND source_value = ?""",
            (campaign_id, source_type, source_value)
        )
        
        if row:
            return row['progress_id'], False
        
        cursor = self.execute(
            """INSERT INTO discovery_progress (campaign_id, source_type, source_value)
               VALUES (?, ?, ?)""",
            (campaign_id, source_type, source_value)
        )
        return cursor.lastrowid, True
    
    def update_progress(
        self,
        progress_id: int,
        current_post_index: Optional[int] = None,
        total_posts: Optional[int] = None,
        current_phase: Optional[str] = None,
        likers_scraped: Optional[int] = None,
        likers_total: Optional[int] = None,
        comments_scraped: Optional[int] = None,
        comments_total: Optional[int] = None,
        status: Optional[str] = None
    ) -> bool:
        """Update discovery progress"""
        updates = ["updated_at = datetime('now')"]
        values = []
        
        fields = {
            'current_post_index': current_post_index,
            'total_posts': total_posts,
            'current_phase': current_phase,
            'likers_scraped': likers_scraped,
            'likers_total': likers_total,
            'comments_scraped': comments_scraped,
            'comments_total': comments_total,
            'status': status
        }
        
        for field, value in fields.items():
            if value is not None:
                updates.append(f'{field} = ?')
                values.append(value)
        
        values.append(progress_id)
        cursor = self.execute(
            f"UPDATE discovery_progress SET {', '.join(updates)} WHERE progress_id = ?",
            tuple(values)
        )
        return cursor.rowcount > 0
    
    # ============================================
    # MAPPERS
    # ============================================
    
    def _map_campaign_row(self, row) -> Optional[Dict[str, Any]]:
        """Map database row to dict"""
        if row is None:
            return None
        result = dict(row)
        result['niche_keywords'] = json.loads(result.get('niche_keywords') or '[]')
        result['target_hashtags'] = json.loads(result.get('target_hashtags') or '[]')
        result['target_accounts'] = json.loads(result.get('target_accounts') or '[]')
        result['target_post_urls'] = json.loads(result.get('target_post_urls') or '[]')
        if result.get('scoring_weights'):
            result['scoring_weights'] = json.loads(result['scoring_weights'])
        return result
    
    def _map_scraped_profile_row(self, row) -> Dict[str, Any]:
        """Map database row to dict"""
        row_dict = dict(row)
        return {
            **row_dict,
            'ai_qualified': bool(row_dict.get('ai_qualified', 0)),
            'is_private': bool(row_dict.get('is_private', 0)),
            'is_verified': bool(row_dict.get('is_verified', 0)),
            'is_business': bool(row_dict.get('is_business', 0))
        }
