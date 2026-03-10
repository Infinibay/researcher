"""Communication service layer for INFINIBAY.

Centralizes inter-agent messaging, thread management, notification delivery,
pre-ticket check-in protocol enforcement, and brainstorming coordination.
"""

from backend.communication.brainstorm_coordinator import BrainstormingCoordinator
from backend.communication.notifications import NotificationService
from backend.communication.protocol import TicketProtocol
from backend.communication.service import CommunicationService
from backend.communication.thread_manager import ThreadManager

__all__ = [
    "CommunicationService",
    "NotificationService",
    "TicketProtocol",
    "ThreadManager",
    "BrainstormingCoordinator",
]
