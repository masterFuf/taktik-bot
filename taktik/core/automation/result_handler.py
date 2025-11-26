"""
Result Handler
==============

Gestion et formatage des résultats de session.
"""

from typing import Dict, Any, Optional
from datetime import datetime
from dataclasses import dataclass, field, asdict
from enum import Enum


class SessionStatus(Enum):
    """Statut de la session"""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class SessionStats:
    """Statistiques d'une session"""
    likes: int = 0
    follows: int = 0
    unfollows: int = 0
    comments: int = 0
    watches: int = 0
    dms_sent: int = 0
    errors: int = 0
    skipped: int = 0
    
    def to_dict(self) -> Dict[str, int]:
        """Convertit en dictionnaire"""
        return asdict(self)
    
    def total_actions(self) -> int:
        """Nombre total d'actions"""
        return (
            self.likes + self.follows + self.unfollows + 
            self.comments + self.watches + self.dms_sent
        )


@dataclass
class SessionResult:
    """Résultat d'une session d'automatisation"""
    
    # Métadonnées
    session_id: str
    client_id: Optional[str] = None
    platform: str = "instagram"
    username: str = ""
    device_id: str = ""
    
    # Statut
    status: SessionStatus = SessionStatus.PENDING
    
    # Timestamps
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    # Statistiques
    stats: SessionStats = field(default_factory=SessionStats)
    
    # Détails
    workflow_type: str = ""
    target_type: Optional[str] = None
    target_value: Optional[str] = None
    
    # Erreurs
    error_message: Optional[str] = None
    error_details: Optional[Dict[str, Any]] = None
    
    # Logs
    logs: list = field(default_factory=list)
    
    def mark_started(self) -> None:
        """Marque la session comme démarrée"""
        self.status = SessionStatus.RUNNING
        self.started_at = datetime.now()
    
    def mark_success(self) -> None:
        """Marque la session comme réussie"""
        self.status = SessionStatus.SUCCESS
        self.completed_at = datetime.now()
    
    def mark_failed(self, error: str, details: Optional[Dict] = None) -> None:
        """Marque la session comme échouée"""
        self.status = SessionStatus.FAILED
        self.completed_at = datetime.now()
        self.error_message = error
        self.error_details = details
    
    def mark_cancelled(self) -> None:
        """Marque la session comme annulée"""
        self.status = SessionStatus.CANCELLED
        self.completed_at = datetime.now()
    
    def add_log(self, message: str, level: str = "info") -> None:
        """Ajoute un log"""
        self.logs.append({
            "timestamp": datetime.now().isoformat(),
            "level": level,
            "message": message
        })
    
    def duration_seconds(self) -> Optional[float]:
        """Durée de la session en secondes"""
        if not self.started_at or not self.completed_at:
            return None
        return (self.completed_at - self.started_at).total_seconds()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire"""
        return {
            "session_id": self.session_id,
            "client_id": self.client_id,
            "platform": self.platform,
            "username": self.username,
            "device_id": self.device_id,
            "status": self.status.value,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "duration_seconds": self.duration_seconds(),
            "stats": self.stats.to_dict(),
            "workflow_type": self.workflow_type,
            "target_type": self.target_type,
            "target_value": self.target_value,
            "error_message": self.error_message,
            "error_details": self.error_details,
            "logs": self.logs[-50:]  # Derniers 50 logs seulement
        }
    
    def summary(self) -> str:
        """Résumé textuel de la session"""
        duration = self.duration_seconds()
        duration_str = f"{duration:.1f}s" if duration else "N/A"
        
        return f"""
╭─────────── Session Summary ────────────╮
│ Status: {self.status.value.upper()}
│ Platform: {self.platform}
│ Username: {self.username}
│ Device: {self.device_id}
│ Duration: {duration_str}
│
│ 📊 Stats:
│   • Likes: {self.stats.likes}
│   • Follows: {self.stats.follows}
│   • Unfollows: {self.stats.unfollows}
│   • Comments: {self.stats.comments}
│   • DMs: {self.stats.dms_sent}
│   • Errors: {self.stats.errors}
│   • Total: {self.stats.total_actions()}
╰────────────────────────────────────────╯
        """.strip()
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SessionResult':
        """Crée depuis un dictionnaire"""
        # Convertir les timestamps
        started_at = None
        if data.get('started_at'):
            started_at = datetime.fromisoformat(data['started_at'])
        
        completed_at = None
        if data.get('completed_at'):
            completed_at = datetime.fromisoformat(data['completed_at'])
        
        # Convertir le statut
        status = SessionStatus(data.get('status', 'pending'))
        
        # Convertir les stats
        stats_data = data.get('stats', {})
        stats = SessionStats(**stats_data)
        
        return cls(
            session_id=data['session_id'],
            client_id=data.get('client_id'),
            platform=data.get('platform', 'instagram'),
            username=data.get('username', ''),
            device_id=data.get('device_id', ''),
            status=status,
            started_at=started_at,
            completed_at=completed_at,
            stats=stats,
            workflow_type=data.get('workflow_type', ''),
            target_type=data.get('target_type'),
            target_value=data.get('target_value'),
            error_message=data.get('error_message'),
            error_details=data.get('error_details'),
            logs=data.get('logs', [])
        )
