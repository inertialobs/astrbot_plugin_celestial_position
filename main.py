# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Inertialobs

import asyncio
import json
import re
import unicodedata
from datetime import timezone as dt_timezone
from functools import lru_cache
from pathlib import Path
from zoneinfo import ZoneInfo

import astropy.units as u
from astropy.coordinates import AltAz, EarthLocation, SkyCoord, get_body
from astropy.time import Time
from astropy.utils import iers
from pydantic import Field
from pydantic.dataclasses import dataclass

from astrbot.api import AstrBotConfig, logger
from astrbot.api.star import Context, Star
from astrbot.core.agent.run_context import ContextWrapper
from astrbot.core.agent.tool import FunctionTool, ToolExecResult
from astrbot.core.astr_agent_context import AstrAgentContext

SOLAR_SYSTEM_BODIES = frozenset(
    {
        "sun",
        "moon",
        "mercury",
        "venus",
        "mars",
        "jupiter",
        "saturn",
        "uranus",
        "neptune",
    }
)
"""Object names resolvable with ``astropy.coordinates.get_body``."""

_COMPASS_POINTS = ("N", "NE", "E", "SE", "S", "SW", "W", "NW")

_GREEK_NAMES = {
    "Alp": ("alpha", "α"),
    "Bet": ("beta", "β"),
    "Gam": ("gamma", "γ"),
    "Del": ("delta", "δ"),
    "Eps": ("epsilon", "ε"),
    "Zet": ("zeta", "ζ"),
    "Eta": ("eta", "η"),
    "The": ("theta", "θ"),
    "Iot": ("iota", "ι"),
    "Kap": ("kappa", "κ"),
    "Lam": ("lambda", "λ"),
    "Mu": ("mu", "μ"),
    "Nu": ("nu", "ν"),
    "Xi": ("xi", "ξ"),
    "Omi": ("omicron", "ο"),
    "Pi": ("pi", "π"),
    "Rho": ("rho", "ρ"),
    "Sig": ("sigma", "σ"),
    "Tau": ("tau", "τ"),
    "Ups": ("upsilon", "υ"),
    "Phi": ("phi", "φ"),
    "Chi": ("chi", "χ"),
    "Psi": ("psi", "ψ"),
    "Ome": ("omega", "ω"),
}
_BAYER_RE = re.compile(r"^([A-Za-z]+)-?(\d*)$")
_STAR_CATALOG_PATH = Path(__file__).with_name("star_catalog.json")
_DSO_CATALOG_PATH = Path(__file__).with_name("dso_catalog.json")


def _normalize_name(value: str) -> str:
    """Normalize an object name for case- and punctuation-insensitive lookup."""
    value = unicodedata.normalize("NFKD", value)
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    return "".join(ch for ch in value.lower() if ch.isalnum())


@lru_cache(maxsize=1)
def _load_star_catalog() -> dict[str, tuple[float, float]]:
    """Build an alias index over the bundled HYG star catalog.

    Returns:
        A mapping from normalized alias to ``(ra_deg, dec_deg)`` in ICRS.
    """
    if not _STAR_CATALOG_PATH.exists():
        logger.warning("Local star catalog not found: %s", _STAR_CATALOG_PATH)
        return {}
    try:
        payload = json.loads(_STAR_CATALOG_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        logger.warning("Failed to load local star catalog: %s", e)
        return {}

    catalog: dict[str, tuple[float, float]] = {}
    for proper, bayer, flam, con, ra_deg, dec_deg, _mag in payload.get("stars", []):
        coords = (float(ra_deg), float(dec_deg))
        aliases: set[str] = set()
        if proper:
            aliases.add(proper)
        if bayer:
            match = _BAYER_RE.match(bayer)
            if match:
                base, number = match.groups()
                greek = _GREEK_NAMES.get(base)
                if greek:
                    full, symbol = greek
                    aliases.update(
                        {
                            f"{full}{number} {con}",
                            f"{full} {number} {con}",
                            f"{full}{number}{con}",
                            f"{base}{number} {con}",
                            f"{symbol}{number} {con}",
                        }
                    )
        if flam:
            aliases.update({f"{flam} {con}", f"{flam}{con}"})
        for alias in aliases:
            catalog.setdefault(_normalize_name(alias), coords)
    return catalog


@lru_cache(maxsize=1)
def _load_dso_catalog() -> dict[str, tuple[float, float]]:
    """Build an alias index over the bundled Messier/NGC/IC catalog.

    Returns:
        A mapping from normalized alias to ``(ra_deg, dec_deg)`` in ICRS.
    """
    if not _DSO_CATALOG_PATH.exists():
        logger.warning("Local DSO catalog not found: %s", _DSO_CATALOG_PATH)
        return {}
    try:
        payload = json.loads(_DSO_CATALOG_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        logger.warning("Failed to load local DSO catalog: %s", e)
        return {}

    catalog: dict[str, tuple[float, float]] = {}
    for cat, oid, cat2, oid2, name, ra_deg, dec_deg, _type, _mag in payload.get(
        "objects", []
    ):
        coords = (float(ra_deg), float(dec_deg))
        aliases: set[str] = set()
        for catalog_name, catalog_id in ((cat, oid), (cat2, oid2)):
            if not catalog_name or not catalog_id:
                continue
            aliases.add(f"{catalog_name} {catalog_id}")
            aliases.add(f"{catalog_name}{catalog_id}")
            if catalog_name == "M":
                aliases.add(f"Messier {catalog_id}")
        if name:
            aliases.add(name)
        for alias in aliases:
            catalog.setdefault(_normalize_name(alias), coords)
    return catalog


@dataclass
class CelestialPositionTool(FunctionTool[AstrAgentContext]):
    """Report the altitude and azimuth of a celestial object for an observer."""

    name: str = "get_celestial_position"
    description: str = (
        "Get the current horizontal position (altitude and azimuth) of a "
        "celestial object as seen from the configured observing location.\n"
        "Accepted 'object_name' values:\n"
        "- Solar system bodies by English name: Sun, Moon, Mercury, Venus, Mars, "
        "Jupiter, Saturn, Uranus, Neptune.\n"
        "- Stars resolved offline from a bundled catalog: common names "
        "('Sirius', 'Vega', 'Betelgeuse'), Bayer designations ('alpha And', "
        "'eps Eri', 'alpha Centauri') and Flamsteed numbers.\n"
        "- Messier, NGC and IC objects resolved offline from a bundled catalog, "
        "e.g. 'M31', 'M42', 'NGC 224', 'IC 434', or common names such as "
        "'Horsehead Nebula'.\n"
        "Other designations (e.g. 'PGC 2557', 'UGC 1') fall back to the online "
        "Sesame resolver and need network access. If a name cannot be resolved, "
        "retry with an alternative designation.\n"
        "Returns altitude in degrees (negative means below the horizon), "
        "azimuth in degrees (0=N, 90=E, 180=S, 270=W), a compass direction, and "
        "whether the object is above the horizon."
    )
    parameters: dict = Field(
        default_factory=lambda: {
            "type": "object",
            "properties": {
                "object_name": {
                    "type": "string",
                    "description": (
                        "Name of the celestial object. Solar system bodies: "
                        "'Moon', 'Mars', 'Jupiter'. Stars: 'Sirius', 'alpha And', "
                        "'eps Eri'. Deep-sky objects: 'M31', 'Horsehead Nebula', "
                        "'NGC 224', 'IC 434'. Use English/Latin designations."
                    ),
                }
            },
            "required": ["object_name"],
        }
    )

    latitude: float = 31.3
    longitude: float = 120.5
    elevation: float = 15
    timezone: str = "Asia/Shanghai"

    async def call(
        self, context: ContextWrapper[AstrAgentContext], **kwargs
    ) -> ToolExecResult:
        logger.debug("celestial plugin activated")
        object_name = str(kwargs.get("object_name", "")).strip()
        if not object_name:
            return "Error: the 'object_name' parameter is required."

        try:
            ZoneInfo(self.timezone)
        except Exception:
            logger.warning(
                "Invalid timezone '%s', falling back to UTC.", self.timezone
            )
            self.timezone = "UTC"

        obstime = Time.now()
        location = EarthLocation(
            lat=self.latitude * u.deg,
            lon=self.longitude * u.deg,
            height=self.elevation * u.m,
        )

        normalized_name = _normalize_name(object_name)
        local_coords = _load_star_catalog().get(normalized_name)
        if local_coords is None:
            local_coords = _load_dso_catalog().get(normalized_name)

        try:
            target: SkyCoord
            if object_name.lower() in SOLAR_SYSTEM_BODIES:
                target = get_body(object_name.lower(), obstime, location)
            elif local_coords is not None:
                target = SkyCoord(
                    ra=local_coords[0] * u.deg,
                    dec=local_coords[1] * u.deg,
                    frame="icrs",
                )
            else:
                target = await asyncio.to_thread(SkyCoord.from_name, object_name)
        except Exception as e:
            logger.warning(
                "Failed to resolve celestial object '%s': %s", object_name, e
            )
            return (
                f"Error: could not resolve celestial object '{object_name}'. "
                "Use a solar system body name (e.g. 'Moon', 'Mars'), a star name "
                "from the bundled catalog (e.g. 'Sirius', 'alpha And'), or a "
                "catalog designation resolvable online (e.g. 'M31', 'NGC 224')."
            )

        with (
            iers.conf.set_temp("auto_download", False),
            iers.conf.set_temp("auto_max_age", None),
        ):
            altaz = target.transform_to(AltAz(obstime=obstime, location=location))
        altitude = float(altaz.alt.deg)
        azimuth = float(altaz.az.deg)
        compass = _COMPASS_POINTS[int((azimuth + 22.5) % 360 // 45)]

        utc_time = obstime.to_datetime(timezone=dt_timezone.utc)
        local_time = utc_time.astimezone(ZoneInfo(self.timezone))
        visibility = (
            "above the horizon (visible)"
            if altitude > 0
            else "below the horizon (not visible)"
        )

        return (
            f"Object: {object_name}\n"
            f"Observer: latitude {self.latitude:.4f} deg, "
            f"longitude {self.longitude:.4f} deg, "
            f"elevation {self.elevation:.1f} m\n"
            f"Time (UTC): {utc_time:%Y-%m-%d %H:%M:%S}\n"
            f"Time ({self.timezone}): {local_time:%Y-%m-%d %H:%M:%S}\n"
            f"Altitude: {altitude:.2f} deg\n"
            f"Azimuth: {azimuth:.2f} deg ({compass})\n"
            f"Status: {visibility}"
        )


class CelestialPositionPlugin(Star):
    """AstrBot plugin exposing a celestial position tool to the LLM."""

    def __init__(self, context: Context, config: AstrBotConfig) -> None:
        super().__init__(context)
        self.config = config
        self.context.add_llm_tools(
            CelestialPositionTool(
                latitude=float(config.get("latitude", 0.0)),
                longitude=float(config.get("longitude", 0.0)),
                elevation=float(config.get("elevation", 0.0)),
                timezone=str(config.get("timezone", "UTC")),
            )
        )
        logger.info("Celestial position tool registered.")
