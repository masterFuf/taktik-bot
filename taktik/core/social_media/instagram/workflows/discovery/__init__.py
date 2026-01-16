"""
Discovery Workflow Module

Intelligent prospect discovery based on hashtags, competitor accounts,
and engagement analysis with AI-powered scoring and persona generation.

V2 Architecture:
- DiscoveryWorkflowV2: Orchestrateur principal avec système de reprise
- Ordre d'exécution: profil → posts → likers → commentaires → post suivant
- Tracking de progression pour reprendre si interrompu
"""

from .discovery_workflow import DiscoveryWorkflow
from .discovery_workflow_v2 import DiscoveryWorkflowV2

__all__ = ['DiscoveryWorkflow', 'DiscoveryWorkflowV2']
