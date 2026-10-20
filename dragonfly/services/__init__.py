"""
dragonfly/services - Capa de lógica de negocio y ataques ofensivos.
Exporta todos los servicios independientes y un contenedor centralizado.
"""

from dragonfly.services.recon_service import ReconService
from dragonfly.services.mac_service import MacService
from dragonfly.services.wifi_service import WiFiService, MultiDeauthAttack
from dragonfly.services.wifi_audit_service import WiFiAuditService
from dragonfly.services.evil_twin_service import EvilTwinService
from dragonfly.services.jammer_service import JammerService
from dragonfly.services.sub1ghz_service import Sub1GHzService
from dragonfly.services.ducky_service import DuckyService
from dragonfly.services.poison_service import PoisonService
from dragonfly.services.cracking_service import CrackingService
from dragonfly.services.system_service import SystemService
from dragonfly.core.executor import CommandExecutor
from dragonfly.core.process_manager import ProcessManager


class ServiceContainer:
    """
    Contenedor unificado para acceder a todos los servicios de DragonFly
    compartiendo el mismo ejecutor de comandos y gestor de procesos.
    """

    def __init__(self, executor: CommandExecutor = None, process_manager: ProcessManager = None):
        self.executor = executor or CommandExecutor()
        self.pm = process_manager or ProcessManager()

        self.recon = ReconService(executor=self.executor)
        self.mac = MacService(executor=self.executor)
        self.wifi = WiFiService(executor=self.executor, process_manager=self.pm)
        self.wifi_audit = WiFiAuditService(wifi_service=self.wifi)
        self.evil_twin = EvilTwinService(process_manager=self.pm)
        self.jammer = JammerService()
        self.sub1ghz = Sub1GHzService()
        self.ducky = DuckyService()
        self.poison = PoisonService()
        self.cracking = CrackingService(executor=self.executor)
        self.system = SystemService(executor=self.executor)


__all__ = [
    "ReconService",
    "MacService",
    "WiFiService",
    "WiFiAuditService",
    "MultiDeauthAttack",
    "EvilTwinService",
    "JammerService",
    "Sub1GHzService",
    "DuckyService",
    "PoisonService",
    "CrackingService",
    "SystemService",
    "ServiceContainer"
]
