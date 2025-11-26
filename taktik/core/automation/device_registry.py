"""
Device Registry
===============

Gestion de l'assignation device ↔ client ↔ compte.
"""

import json
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict
from loguru import logger


@dataclass
class DeviceAssignment:
    """Assignation d'un device à un client/compte"""
    device_id: str
    client_id: Optional[str] = None
    platform: str = "instagram"
    username: Optional[str] = None
    assigned_at: Optional[str] = None
    last_used: Optional[str] = None
    is_active: bool = True
    notes: str = ""
    
    def to_dict(self) -> Dict:
        """Convertit en dictionnaire"""
        return asdict(self)


class DeviceRegistry:
    """
    Registre des devices et leurs assignations.
    
    Permet de gérer:
    - Assignation device ↔ client
    - Assignation device ↔ compte Instagram/TikTok
    - Disponibilité des devices
    - Historique d'utilisation
    """
    
    def __init__(self, registry_path: Optional[str] = None):
        """
        Initialise le registre.
        
        Args:
            registry_path: Chemin du fichier de registre (défaut: ~/.taktik/device_registry.json)
        """
        if registry_path:
            self.registry_path = Path(registry_path)
        else:
            self.registry_path = Path.home() / ".taktik" / "device_registry.json"
        
        self.registry_path.parent.mkdir(parents=True, exist_ok=True)
        self.assignments: Dict[str, DeviceAssignment] = {}
        self._load()
    
    def _load(self) -> None:
        """Charge le registre depuis le fichier"""
        if not self.registry_path.exists():
            logger.info("📱 Creating new device registry")
            self._save()
            return
        
        try:
            with open(self.registry_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            self.assignments = {
                device_id: DeviceAssignment(**assignment_data)
                for device_id, assignment_data in data.items()
            }
            
            logger.info(f"📱 Loaded {len(self.assignments)} device assignments")
            
        except Exception as e:
            logger.error(f"❌ Failed to load device registry: {e}")
            self.assignments = {}
    
    def _save(self) -> None:
        """Sauvegarde le registre dans le fichier"""
        try:
            data = {
                device_id: assignment.to_dict()
                for device_id, assignment in self.assignments.items()
            }
            
            with open(self.registry_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            logger.debug(f"💾 Device registry saved: {len(self.assignments)} assignments")
            
        except Exception as e:
            logger.error(f"❌ Failed to save device registry: {e}")
    
    def assign_device(
        self,
        device_id: str,
        client_id: Optional[str] = None,
        platform: str = "instagram",
        username: Optional[str] = None,
        notes: str = ""
    ) -> DeviceAssignment:
        """
        Assigne un device à un client/compte.
        
        Args:
            device_id: ID du device
            client_id: ID du client (optionnel)
            platform: Platform (instagram/tiktok)
            username: Username du compte
            notes: Notes additionnelles
            
        Returns:
            DeviceAssignment créée
        """
        from datetime import datetime
        
        assignment = DeviceAssignment(
            device_id=device_id,
            client_id=client_id,
            platform=platform,
            username=username,
            assigned_at=datetime.now().isoformat(),
            is_active=True,
            notes=notes
        )
        
        self.assignments[device_id] = assignment
        self._save()
        
        logger.success(f"✅ Device assigned: {device_id} → {username or client_id}")
        return assignment
    
    def unassign_device(self, device_id: str) -> bool:
        """
        Désassigne un device.
        
        Args:
            device_id: ID du device
            
        Returns:
            True si désassigné, False si non trouvé
        """
        if device_id in self.assignments:
            del self.assignments[device_id]
            self._save()
            logger.info(f"📱 Device unassigned: {device_id}")
            return True
        
        logger.warning(f"⚠️ Device not found: {device_id}")
        return False
    
    def get_assignment(self, device_id: str) -> Optional[DeviceAssignment]:
        """
        Récupère l'assignation d'un device.
        
        Args:
            device_id: ID du device
            
        Returns:
            DeviceAssignment ou None
        """
        return self.assignments.get(device_id)
    
    def get_device_for_client(self, client_id: str) -> Optional[str]:
        """
        Récupère le device assigné à un client.
        
        Args:
            client_id: ID du client
            
        Returns:
            Device ID ou None
        """
        for device_id, assignment in self.assignments.items():
            if assignment.client_id == client_id and assignment.is_active:
                return device_id
        return None
    
    def get_device_for_account(self, username: str, platform: str = "instagram") -> Optional[str]:
        """
        Récupère le device assigné à un compte.
        
        Args:
            username: Username du compte
            platform: Platform
            
        Returns:
            Device ID ou None
        """
        for device_id, assignment in self.assignments.items():
            if (assignment.username == username and 
                assignment.platform == platform and 
                assignment.is_active):
                return device_id
        return None
    
    def get_available_devices(self) -> List[str]:
        """
        Récupère les devices disponibles (non assignés ou inactifs).
        
        Returns:
            Liste des device IDs disponibles
        """
        import subprocess
        
        # Récupérer tous les devices connectés via ADB
        try:
            result = subprocess.run(
                ['adb', 'devices'],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            lines = result.stdout.strip().split('\n')[1:]  # Skip header
            all_devices = [
                line.split()[0] 
                for line in lines 
                if line.strip() and 'device' in line
            ]
            
        except Exception as e:
            logger.error(f"❌ Failed to get ADB devices: {e}")
            all_devices = []
        
        # Filtrer les devices non assignés
        assigned_devices = {
            device_id 
            for device_id, assignment in self.assignments.items() 
            if assignment.is_active
        }
        
        available = [d for d in all_devices if d not in assigned_devices]
        
        logger.info(f"📱 Available devices: {len(available)}/{len(all_devices)}")
        return available
    
    def update_last_used(self, device_id: str) -> None:
        """
        Met à jour la dernière utilisation d'un device.
        
        Args:
            device_id: ID du device
        """
        from datetime import datetime
        
        if device_id in self.assignments:
            self.assignments[device_id].last_used = datetime.now().isoformat()
            self._save()
    
    def set_device_active(self, device_id: str, is_active: bool) -> bool:
        """
        Active/désactive un device.
        
        Args:
            device_id: ID du device
            is_active: Actif ou non
            
        Returns:
            True si modifié, False si non trouvé
        """
        if device_id in self.assignments:
            self.assignments[device_id].is_active = is_active
            self._save()
            status = "activated" if is_active else "deactivated"
            logger.info(f"📱 Device {status}: {device_id}")
            return True
        
        logger.warning(f"⚠️ Device not found: {device_id}")
        return False
    
    def list_assignments(self) -> List[DeviceAssignment]:
        """
        Liste toutes les assignations.
        
        Returns:
            Liste des DeviceAssignment
        """
        return list(self.assignments.values())
    
    def export_to_json(self, output_path: str) -> None:
        """
        Exporte le registre vers un fichier JSON.
        
        Args:
            output_path: Chemin du fichier de sortie
        """
        data = {
            device_id: assignment.to_dict()
            for device_id, assignment in self.assignments.items()
        }
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        logger.success(f"✅ Registry exported: {output_path}")
