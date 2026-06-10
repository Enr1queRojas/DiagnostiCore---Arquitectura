"""
teams_bot/config.py
====================
Lee variables de entorno desde .env.teams y expone la configuración
del bot como un dataclass singleton.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

# Carga .env.teams si existe (local dev). En Azure App Service las vars
# ya están en el entorno, por lo que load_dotenv es no-op.
_env_file = Path(__file__).parent.parent / ".env.teams"
load_dotenv(_env_file)


@dataclass
class BotConfig:
    app_id: str = field(default_factory=lambda: os.environ.get("MicrosoftAppId", ""))
    app_password: str = field(default_factory=lambda: os.environ.get("MicrosoftAppPassword", ""))
    tenant_id: str = field(default_factory=lambda: os.environ.get("MicrosoftTenantId", ""))
    diagnosticore_api_url: str = field(
        default_factory=lambda: os.environ.get("DIAGNOSTICORE_API_URL", "http://localhost:8000")
    )
    port: int = field(default_factory=lambda: int(os.environ.get("BOT_PORT", "3978")))

    def validate(self) -> None:
        if not self.app_id:
            raise ValueError("MicrosoftAppId no está configurado.")
        if not self.app_password:
            raise ValueError("MicrosoftAppPassword no está configurado.")
        if not self.tenant_id:
            raise ValueError("MicrosoftTenantId no está configurado (requerido para Single Tenant).")


CONFIG = BotConfig()
