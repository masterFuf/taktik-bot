"""Data models for Taktik Instagram using pure API, no direct database connection."""

import logging

logger = logging.getLogger(__name__)

class Column:
    def __init__(self, name):
        self.name = name
        
    def __eq__(self, other):
        return (self.name, other)

class InstagramProfile:
    
    username = Column("username")
    followers_count = Column("followers_count")
    following_count = Column("following_count")
    posts_count = Column("posts_count")
    is_private = Column("is_private")
    full_name = Column("full_name")
    id = Column("id")
    
    def __init__(self, username=None, full_name=None, followers_count=0, 
                 following_count=0, posts_count=0, is_private=False, 
                 biography=None, notes=None, profile_pic_path=None, id=None, **kwargs):
        self.username = username
        self.full_name = full_name or ""
        self.followers_count = followers_count or 0
        self.following_count = following_count or 0
        self.posts_count = posts_count or 0
        self.is_private = is_private or False
        self.biography = biography or ""
        self.notes = notes or ""
        self.profile_pic_path = profile_pic_path or ""
        self.id = id
        
        for key, value in kwargs.items():
            setattr(self, key, value)
    
    @property
    def followers(self):
        return self.followers_count
    
    @followers.setter
    def followers(self, value):
        self.followers_count = value
    
    @property
    def following(self):
        return self.following_count
    
    @following.setter
    def following(self, value):
        self.following_count = value
    
    @property
    def posts(self):
        return self.posts_count
    
    @posts.setter
    def posts(self, value):
        self.posts_count = value
    
    def to_dict(self):
        return {
            'username': self.username,
            'full_name': self.full_name,
            'followers_count': self.followers_count,
            'following_count': self.following_count,
            'posts_count': self.posts_count,
            'is_private': self.is_private,
            'biography': self.biography,
            'notes': self.notes,
            'profile_pic_path': self.profile_pic_path
        }

class DatabaseSession:
    
    def __init__(self, api_service):
        self.api_service = api_service
        self.logger = logger
        self.pending_instances = []
        
    def query(self, model_class):
        return DatabaseQuery(self, model_class)
        
    def add(self, instance):
        self.pending_instances.append(instance)
        return self
        
    def commit(self):
        for instance in self.pending_instances:
            if isinstance(instance, InstagramProfile):
                try:
                    result = self.api_service.save_profile_via_api(instance)
                    if result and 'profile_id' in result:
                        instance.id = result['profile_id']
                        self.logger.info(f"Profile {instance.username} saved via API with ID: {result['profile_id']}")
                except Exception as e:
                    self.logger.error(f"Error saving via API: {e}")
        self.pending_instances.clear()

class DatabaseQuery:
    
    def __init__(self, session, model_class):
        self.session = session
        self.model_class = model_class
        self.filters = []
        
    def filter(self, *args):
        self.filters.extend(args)
        return self
        
    def first(self):
        username = None
        for f in self.filters:
            if isinstance(f, tuple) and f[0] == 'username':
                username = f[1]
                break
        
        if username and self.model_class == InstagramProfile:
            try:
                profile_data = self.session.api_service.get_profile_via_api(username)
                if profile_data:
                    return InstagramProfile(
                        id=profile_data.get('profile_id'),
                        username=profile_data.get('username'),
                        full_name=profile_data.get('full_name', ''),
                        followers_count=profile_data.get('followers_count', 0),
                        following_count=profile_data.get('following_count', 0),
                        posts_count=profile_data.get('posts_count', 0),
                        is_private=profile_data.get('is_private', False),
                        biography=profile_data.get('biography', ''),
                        notes=profile_data.get('notes', '')
                    )
            except Exception as e:
                self.session.logger.error(f"Error retrieving via API: {e}")
        return None
