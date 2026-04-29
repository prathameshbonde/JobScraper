import importlib
import logging
from pathlib import Path

import yaml

from portals.base import PortalBase

logger = logging.getLogger(__name__)


def load_portal(portal_name: str, portal_config: dict, global_config: dict) -> PortalBase:
    """
    Dynamically load a portal plugin by name.

    Looks for a module at portals/<portal_name>/__init__.py that exports
    a class inheriting from PortalBase.

    Args:
        portal_name: Name of the portal (must match folder name under portals/).
        portal_config: Portal-specific configuration from global config.yaml.
        global_config: The full global configuration dict.

    Returns:
        An instance of the portal plugin.
    """
    module_path = f"portals.{portal_name}"

    try:
        module = importlib.import_module(module_path)
    except ModuleNotFoundError:
        raise ValueError(
            f"Portal plugin '{portal_name}' not found. "
            f"Expected module at portals/{portal_name}/__init__.py"
        )

    # Look for the Portal class
    if not hasattr(module, "Portal"):
        raise ValueError(
            f"Portal plugin '{portal_name}' must export a 'Portal' class "
            f"that inherits from PortalBase."
        )

    portal_class = module.Portal

    if not issubclass(portal_class, PortalBase):
        raise ValueError(
            f"Portal class in '{portal_name}' must inherit from PortalBase."
        )

    # Load portal-specific config.yaml if it exists
    portal_dir = Path(__file__).parent / portal_name
    portal_config_path = portal_dir / "config.yaml"

    portal_specific_config = {}
    if portal_config_path.exists():
        with open(portal_config_path, "r") as f:
            portal_specific_config = yaml.safe_load(f) or {}
        logger.info(f"Loaded portal-specific config from {portal_config_path}")

    # Merge portal-specific config into the portal_config
    merged_config = {**portal_specific_config, **portal_config}

    instance = portal_class(
        name=portal_name,
        portal_config=merged_config,
        global_config=global_config,
    )

    logger.info(f"Loaded portal plugin: {portal_name}")
    return instance


def list_available_portals() -> list[str]:
    """List all available portal plugins (directories with __init__.py)."""
    portals_dir = Path(__file__).parent
    available = []

    for child in portals_dir.iterdir():
        if child.is_dir() and (child / "__init__.py").exists() and child.name != "__pycache__":
            available.append(child.name)

    return sorted(available)
