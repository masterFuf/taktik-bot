"""Business logic for Instagram profile filtering."""

from typing import Optional, Dict, Any, List, Tuple, Callable
from loguru import logger
import re
from datetime import datetime, timedelta

from ...core.base_business_action import BaseBusinessAction
from .profile import ProfileBusiness


class FilteringBusiness(BaseBusinessAction):
    
    def __init__(self, device, session_manager=None):
        super().__init__(device, session_manager, automation=None, module_name="filtering")
        self.profile_business = ProfileBusiness(device, session_manager)
    
    def create_profile_filter(self, criteria: Dict[str, Any]) -> Callable[[Dict[str, Any]], Dict[str, Any]]:
        def profile_filter(profile_info: Dict[str, Any]) -> Dict[str, Any]:
            return self.apply_comprehensive_filter(profile_info, criteria)
        return profile_filter
    
    def apply_comprehensive_filter(self, profile_info: Dict[str, Any], 
                                 criteria: Dict[str, Any]) -> Dict[str, Any]:
        result = {
            'suitable': True,
            'score': 100,
            'reasons': [],
            'category': 'suitable',
            'filter_details': {},
            'username': profile_info.get('username', 'unknown')
        }
        
        try:
            basic_result = self._apply_basic_filters(profile_info, criteria)
            result.update(basic_result)
            
            if not result['suitable']:
                return result
            
            advanced_result = self._apply_advanced_filters(profile_info, criteria)
            result['score'] = min(result['score'], advanced_result['score'])
            result['reasons'].extend(advanced_result['reasons'])
            result['filter_details'].update(advanced_result['details'])
            
            content_result = self._apply_content_filters(profile_info, criteria)
            result['score'] = min(result['score'], content_result['score'])
            result['reasons'].extend(content_result['reasons'])
            result['filter_details'].update(content_result['details'])
            
            behavior_result = self._apply_behavior_filters(profile_info, criteria)
            result['score'] = min(result['score'], behavior_result['score'])
            result['reasons'].extend(behavior_result['reasons'])
            result['filter_details'].update(behavior_result['details'])
            
            result['category'] = self._determine_final_category(result)
            
            min_score = criteria.get('min_score', 50)
            if result['score'] < min_score:
                result['suitable'] = False
                result['reasons'].append(f'Score too low ({result["score"]} < {min_score})')
            
        except Exception as e:
            self.logger.error(f"Error filtering profile: {e}")
            result.update({
                'suitable': False,
                'score': 0,
                'reasons': [f'Filter error: {str(e)}'],
                'category': 'error'
            })
        
        return result
    
    def _apply_basic_filters(self, profile_info: Dict[str, Any], 
                           criteria: Dict[str, Any]) -> Dict[str, Any]:
        result = {
            'suitable': True,
            'score': 100,
            'reasons': [],
            'filter_details': {'basic_filters': {}}
        }
        
        if profile_info.get('is_private', False):
            if not criteria.get('allow_private', False):
                result.update({
                    'suitable': False,
                    'reasons': ['Private account'],
                    'category': 'private',
                    'score': 0
                })
                return result
        
        followers = profile_info.get('followers_count', 0)
        if followers is None:
            followers = 0
        min_followers = criteria.get('min_followers', 0)
        if followers < min_followers:
            result.update({
                'suitable': False,
                'reasons': [f'Too few followers ({followers} < {min_followers})'],
                'category': 'low_followers',
                'score': 0
            })
            return result
        
        max_followers = criteria.get('max_followers', float('inf'))
        if followers > max_followers:
            result.update({
                'suitable': False,
                'reasons': [f'Too many followers ({followers} > {max_followers})'],
                'category': 'high_followers',
                'score': 0
            })
            return result
        
        posts = profile_info.get('posts_count', 0)
        min_posts = criteria.get('min_posts', 0)
        if posts < min_posts:
            result.update({
                'suitable': False,
                'reasons': [f'Too few posts ({posts} < {min_posts})'],
                'category': 'inactive',
                'score': 0
            })
            return result
        
        # DISABLED: Bot username detection - too many false positives
        # username = profile_info.get('username', '')
        # if self.utils.is_likely_bot_username(username):
        #     if not criteria.get('allow_bots', False):
        #         result.update({
        #             'suitable': False,
        #             'reasons': ['Likely bot username'],
        #             'category': 'bot',
        #             'score': 0
        #         })
        #         return result
        
        result['filter_details']['basic_filters'] = {
            'private_check': 'passed',
            'followers_range': 'passed',
            'posts_minimum': 'passed',
            'bot_detection': 'passed'
        }
        
        return result
    
    def _apply_advanced_filters(self, profile_info: Dict[str, Any], 
                              criteria: Dict[str, Any]) -> Dict[str, Any]:
        result = {
            'score': 100,
            'reasons': [],
            'details': {'advanced_filters': {}}
        }
        
        followers = profile_info.get('followers_count', 0)
        following = profile_info.get('following_count', 0)
        posts = profile_info.get('posts_count', 0)
        
        if following > 0:
            ratio = followers / following
            max_ratio = criteria.get('max_following_ratio', 10.0)
            
            if ratio > max_ratio:
                penalty = min(30, (ratio - max_ratio) * 5)
                result['score'] -= penalty
                result['reasons'].append(f'High follower ratio ({ratio:.1f})')
                result['details']['advanced_filters']['follower_ratio'] = 'penalty'
            else:
                result['details']['advanced_filters']['follower_ratio'] = 'good'
        
        if followers > 0:
            posts_ratio = posts / followers
            
            if posts_ratio < 0.001:
                result['score'] -= 20
                result['reasons'].append('Very low posting activity')
                result['details']['advanced_filters']['activity_level'] = 'low'
            elif posts_ratio > 0.1:
                result['score'] -= 10
                result['reasons'].append('Very high posting activity')
                result['details']['advanced_filters']['activity_level'] = 'high'
            else:
                result['details']['advanced_filters']['activity_level'] = 'normal'
        
        if profile_info.get('is_verified', False):
            if criteria.get('verified_penalty', 0) > 0:
                result['score'] -= criteria['verified_penalty']
                result['reasons'].append('Verified account')
                result['details']['advanced_filters']['verified'] = 'penalty'
            else:
                result['details']['advanced_filters']['verified'] = 'bonus'
        
        if profile_info.get('is_business', False):
            business_penalty = criteria.get('business_penalty', 0)
            if business_penalty > 0:
                result['score'] -= business_penalty
                result['reasons'].append('Business account')
                result['details']['advanced_filters']['business'] = 'penalty'
            else:
                result['details']['advanced_filters']['business'] = 'neutral'
        
        return result
    
    def _apply_content_filters(self, profile_info: Dict[str, Any], 
                             criteria: Dict[str, Any]) -> Dict[str, Any]:
        result = {
            'score': 100,
            'reasons': [],
            'details': {'content_filters': {}}
        }
        
        bio = profile_info.get('biography', '')
        if bio:
            forbidden_keywords = criteria.get('forbidden_bio_keywords', [])
            for keyword in forbidden_keywords:
                if keyword.lower() in bio.lower():
                    result['score'] -= 25
                    result['reasons'].append(f'Forbidden keyword in bio: {keyword}')
                    result['details']['content_filters']['bio_keywords'] = 'violation'
                    break
            else:
                result['details']['content_filters']['bio_keywords'] = 'clean'
            
            required_keywords = criteria.get('required_bio_keywords', [])
            if required_keywords:
                found_keywords = []
                for keyword in required_keywords:
                    if keyword.lower() in bio.lower():
                        found_keywords.append(keyword)
                
                if not found_keywords:
                    result['score'] -= 15
                    result['reasons'].append('No required keywords in bio')
                    result['details']['content_filters']['required_keywords'] = 'missing'
                else:
                    result['details']['content_filters']['required_keywords'] = 'found'
        else:
            if criteria.get('require_bio', False):
                result['score'] -= 10
                result['reasons'].append('No biography')
                result['details']['content_filters']['bio_presence'] = 'missing'
            else:
                result['details']['content_filters']['bio_presence'] = 'optional'
        
        full_name = profile_info.get('full_name', '')
        if not full_name and criteria.get('require_full_name', False):
            result['score'] -= 5
            result['reasons'].append('No full name')
            result['details']['content_filters']['full_name'] = 'missing'
        else:
            result['details']['content_filters']['full_name'] = 'present'
        
        return result
    
    def _apply_behavior_filters(self, profile_info: Dict[str, Any], 
                              criteria: Dict[str, Any]) -> Dict[str, Any]:
        result = {
            'score': 100,
            'reasons': [],
            'details': {'behavior_filters': {}}
        }
        
        follow_state = profile_info.get('follow_button_state', 'unknown')
        
        if follow_state == 'unfollow':
            if criteria.get('skip_already_following', True):
                result['score'] -= 50
                result['reasons'].append('Already following')
                result['details']['behavior_filters']['follow_state'] = 'already_following'
            else:
                result['details']['behavior_filters']['follow_state'] = 'following_allowed'
        elif follow_state == 'message':
            result['score'] -= 30
            result['reasons'].append('Own profile or special relationship')
            result['details']['behavior_filters']['follow_state'] = 'special_relationship'
        else:
            result['details']['behavior_filters']['follow_state'] = 'available'
        
        stories_count = profile_info.get('visible_stories_count', 0)
        if stories_count > 0:
            result['score'] += 5
            result['details']['behavior_filters']['recent_activity'] = 'active'
        else:
            result['details']['behavior_filters']['recent_activity'] = 'inactive'
        
        visible_posts = profile_info.get('visible_posts_count', 0)
        if visible_posts == 0 and not profile_info.get('is_private', False):
            result['score'] -= 15
            result['reasons'].append('No visible posts')
            result['details']['behavior_filters']['content_visibility'] = 'no_posts'
        else:
            result['details']['behavior_filters']['content_visibility'] = 'has_content'
        
        return result
    
    def _determine_final_category(self, result: Dict[str, Any]) -> str:
        if not result['suitable']:
            return result.get('category', 'filtered')
        
        score = result['score']
        reasons = result['reasons']
        
        if score >= 90:
            return 'excellent'
        elif score >= 80:
            return 'very_good'
        elif score >= 70:
            return 'good'
        elif score >= 60:
            return 'acceptable'
        elif score >= 50:
            return 'marginal'
        else:
            return 'poor'
    
    def batch_filter_profiles(self, profiles: List[Dict[str, Any]], 
                            criteria: Dict[str, Any]) -> Dict[str, Any]:
        results = {
            'total_profiles': len(profiles),
            'suitable_profiles': [],
            'filtered_profiles': [],
            'categories': {},
            'filter_summary': {
                'suitable_count': 0,
                'filtered_count': 0,
                'average_score': 0.0,
                'top_filter_reasons': {}
            }
        }
        
        total_score = 0
        reason_counts = {}
        
        self.logger.info(f"Batch filtering {len(profiles)} profiles")
        
        for i, profile in enumerate(profiles):
            try:
                filter_result = self.apply_comprehensive_filter(profile, criteria)
                
                if filter_result['suitable']:
                    results['suitable_profiles'].append({
                        'profile': profile,
                        'filter_result': filter_result
                    })
                    results['filter_summary']['suitable_count'] += 1
                else:
                    results['filtered_profiles'].append({
                        'profile': profile,
                        'filter_result': filter_result
                    })
                    results['filter_summary']['filtered_count'] += 1
                
                category = filter_result['category']
                results['categories'][category] = results['categories'].get(category, 0) + 1
                
                for reason in filter_result['reasons']:
                    reason_counts[reason] = reason_counts.get(reason, 0) + 1
                
                total_score += filter_result['score']
                
                if (i + 1) % 50 == 0:
                    self.logger.debug(f"Filtering: {i + 1}/{len(profiles)} profiles processed")
                
            except Exception as e:
                self.logger.error(f"Error filtering profile {i}: {e}")
                results['filtered_profiles'].append({
                    'profile': profile,
                    'filter_result': {
                        'suitable': False,
                        'score': 0,
                        'reasons': [f'Filter error: {str(e)}'],
                        'category': 'error'
                    }
                })
                results['filter_summary']['filtered_count'] += 1
        
        if len(profiles) > 0:
            results['filter_summary']['average_score'] = total_score / len(profiles)
        
        sorted_reasons = sorted(reason_counts.items(), key=lambda x: x[1], reverse=True)
        results['filter_summary']['top_filter_reasons'] = dict(sorted_reasons[:5])
        
        success_rate = results['filter_summary']['suitable_count'] / len(profiles) * 100
        self.logger.info(f"Filtering completed: {results['filter_summary']['suitable_count']}/{len(profiles)} "
                        f"profiles accepted ({success_rate:.1f}%)")
        
        return results
    
    def get_default_criteria(self, profile_type: str = "general") -> Dict[str, Any]:
        base_criteria = {
            'allow_private': False,
            'allow_bots': False,
            'skip_already_following': True,
            'min_score': 50
        }
        
        if profile_type == "general":
            return {
                **base_criteria,
                'min_followers': 50,
                'max_followers': 10000,
                'min_posts': 5,
                'max_following_ratio': 5.0,
                'require_bio': False,
                'verified_penalty': 20,
                'business_penalty': 10
            }
        
        elif profile_type == "influencer":
            return {
                **base_criteria,
                'min_followers': 1000,
                'max_followers': 100000,
                'min_posts': 20,
                'max_following_ratio': 10.0,
                'require_bio': True,
                'verified_penalty': 0,
                'business_penalty': 0
            }
        
        elif profile_type == "micro":
            return {
                **base_criteria,
                'min_followers': 10,
                'max_followers': 1000,
                'min_posts': 3,
                'max_following_ratio': 3.0,
                'require_bio': False,
                'verified_penalty': 30,
                'business_penalty': 20
            }
        
        elif profile_type == "business":
            return {
                **base_criteria,
                'min_followers': 100,
                'max_followers': 50000,
                'min_posts': 10,
                'max_following_ratio': 8.0,
                'require_bio': True,
                'verified_penalty': 0,
                'business_penalty': 0,
                'required_bio_keywords': ['business', 'service', 'shop', 'store']
            }
        
        else:
            return base_criteria
    
    # ─── Methods absorbed from ProfileBusiness (pure logic, no device I/O) ────
    
    def is_profile_suitable_for_interaction(self, profile_info: Dict[str, Any], 
                                          criteria: Dict[str, Any] = None) -> Dict[str, Any]:
        if not criteria:
            criteria = self._get_simple_default_criteria()
        
        result = {
            'suitable': True,
            'reasons': [],
            'score': 100,
            'category': 'suitable'
        }
        
        if not profile_info:
            result.update({'suitable': False, 'reasons': ['Profile info unavailable'], 'score': 0})
            return result
        
        if profile_info.get('is_private', False):
            if not criteria.get('allow_private', False):
                result.update({
                    'suitable': False,
                    'reasons': ['Private account'],
                    'category': 'private',
                    'score': 0
                })
                return result
        
        # Vérifications des compteurs
        followers = profile_info.get('followers_count', 0)
        following = profile_info.get('following_count', 0)
        posts = profile_info.get('posts_count', 0)
        
        # Nombre minimum de followers
        min_followers = criteria.get('min_followers', 0)
        if followers < min_followers:
            result['suitable'] = False
            result['reasons'].append(f'Too few followers ({followers} < {min_followers})')
            result['score'] -= 30
        
        # Nombre maximum de followers
        max_followers = criteria.get('max_followers', float('inf'))
        if followers > max_followers:
            result['suitable'] = False
            result['reasons'].append(f'Too many followers ({followers} > {max_followers})')
            result['score'] -= 20
        
        # Nombre minimum de posts
        min_posts = criteria.get('min_posts', 3)
        if posts < min_posts:
            result['suitable'] = False
            result['reasons'].append(f'Too few posts ({posts} < {min_posts})')
            result['score'] -= 25
        
        # Ratio followers/following
        max_following_ratio = criteria.get('max_following_ratio', 10.0)
        if following > 0:
            ratio = followers / following
            if ratio > max_following_ratio:
                result['reasons'].append(f'High follower ratio ({ratio:.1f})')
                result['score'] -= 10
        
        # Comptes vérifiés
        if profile_info.get('is_verified', False):
            if not criteria.get('allow_verified', True):
                result['suitable'] = False
                result['reasons'].append('Verified account')
                result['score'] -= 40
        
        # Comptes business
        if profile_info.get('is_business', False):
            if not criteria.get('allow_business', True):
                result['reasons'].append('Business account')
                result['score'] -= 15
        
        # DISABLED: Bot username detection - too many false positives
        # username = profile_info.get('username', '')
        # if self.utils.is_likely_bot_username(username):
        #     result['suitable'] = False
        #     result['reasons'].append('Likely bot username')
        #     result['category'] = 'bot'
        #     result['score'] -= 50
        
        # Déterminer la catégorie finale
        if result['suitable']:
            if result['score'] >= 90:
                result['category'] = 'excellent'
            elif result['score'] >= 70:
                result['category'] = 'good'
            else:
                result['category'] = 'acceptable'
        else:
            if 'Private account' in result['reasons']:
                result['category'] = 'private'
            elif 'bot' in result['category']:
                result['category'] = 'bot'
            else:
                result['category'] = 'filtered'
        
        return result
    
    def extract_profile_metrics(self, profile_info: Dict[str, Any]) -> Dict[str, Any]:
        metrics = {}
        
        followers = profile_info.get('followers_count', 0)
        following = profile_info.get('following_count', 0)
        posts = profile_info.get('posts_count', 0)
        
        # Ratios de base
        metrics['followers_following_ratio'] = followers / following if following > 0 else float('inf')
        metrics['posts_followers_ratio'] = posts / followers if followers > 0 else 0
        metrics['avg_followers_per_post'] = followers / posts if posts > 0 else 0
        
        # Score d'engagement estimé (basé sur les ratios)
        engagement_score = 0
        if followers > 0 and posts > 0:
            # Plus de posts par rapport aux followers = plus actif
            if metrics['posts_followers_ratio'] > 0.01:  # Plus de 1 post pour 100 followers
                engagement_score += 30
            
            # Ratio followers/following équilibré
            if 0.5 <= metrics['followers_following_ratio'] <= 5:
                engagement_score += 40
            
            # Compte avec activité récente (basé sur la présence de stories)
            if profile_info.get('visible_stories_count', 0) > 0:
                engagement_score += 30
        
        metrics['estimated_engagement_score'] = min(engagement_score, 100)
        
        # Catégorie de compte
        if followers < 100:
            metrics['account_category'] = 'micro'
        elif followers < 1000:
            metrics['account_category'] = 'small'
        elif followers < 10000:
            metrics['account_category'] = 'medium'
        elif followers < 100000:
            metrics['account_category'] = 'large'
        else:
            metrics['account_category'] = 'mega'
        
        # Score de qualité global
        quality_score = 50  # Base
        
        # Bonus pour profil complet
        if profile_info.get('full_name'):
            quality_score += 10
        if profile_info.get('biography'):
            quality_score += 15
        if profile_info.get('is_verified'):
            quality_score += 20
        
        # Malus pour signaux négatifs
        if profile_info.get('is_private'):
            quality_score -= 20
        # DISABLED: Bot username detection - too many false positives
        # if self.utils.is_likely_bot_username(profile_info.get('username', '')):
        #     quality_score -= 40
        
        metrics['quality_score'] = max(0, min(100, quality_score))
        
        return metrics
    
    def _get_simple_default_criteria(self) -> Dict[str, Any]:
        """Simple default criteria used by is_profile_suitable_for_interaction."""
        return {
            'min_followers': 10,
            'max_followers': 50000,
            'min_posts': 3,
            'max_following_ratio': 10.0,
            'allow_private': False,
            'allow_verified': True,
            'allow_business': True
        }
