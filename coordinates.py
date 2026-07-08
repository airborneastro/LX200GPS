# coordinates.py
#
# LX200 coordinate conversion utilities
#
# Internal representation:
#   RA  = decimal hours
#   DEC = decimal degrees
#
# LX200 formats:
#   RA  = HH:MM:SS
#   DEC = +DD*MM:SS
#

from __future__ import annotations

import math

ARCSEC_PER_DEG = 3600.0
DEG_PER_HOUR = 15.0


# ---------------------------------------------------------------------------
# RA parsing / formatting
# ---------------------------------------------------------------------------

def parse_ra(value: str) -> float:
    """
    Convert LX200 RA string to decimal hours.

    Example:
        05:35:17 -> 5.5880556
    """

    value = value.strip()

    parts = value.split(":")
    if len(parts) != 3:
        raise ValueError(f"Invalid RA format: {value}")

    h = int(parts[0])
    m = int(parts[1])
    s = int(parts[2])

    return h + m / 60.0 + s / 3600.0


def format_ra(hours: float) -> str:
    """
    Convert decimal hours to LX200 RA string.

    Example:
        5.588055 -> 05:35:17
    """

    hours %= 24.0

    h = int(hours)

    rem = (hours - h) * 60.0
    m = int(rem)

    rem = (rem - m) * 60.0
    s = int(round(rem))

    if s >= 60:
        s = 0
        m += 1

    if m >= 60:
        m = 0
        h += 1

    h %= 24

    return f"{h:02d}:{m:02d}:{s:02d}"


# ---------------------------------------------------------------------------
# DEC parsing / formatting
# ---------------------------------------------------------------------------

def parse_dec(value: str) -> float:
    """
    Convert LX200 DEC string to decimal degrees.

    Example:
        +22*00:52 -> 22.014444
        -10*30:00 -> -10.500000
    """

    value = value.strip()

    sign = 1

    if value.startswith("-"):
        sign = -1

    value = value[1:]

    d_part, rest = value.split("*")
    m_part, s_part = rest.split(":")

    deg = int(d_part)
    minutes = int(m_part)
    seconds = int(s_part)

    result = deg + minutes / 60.0 + seconds / 3600.0

    return sign * result


def format_dec(deg: float) -> str:
    """
    Convert decimal degrees to LX200 DEC string.

    Example:
        22.014444 -> +22*00:52
    """

    sign = "+" if deg >= 0 else "-"

    deg = abs(deg)

    d = int(deg)

    rem = (deg - d) * 60.0
    m = int(rem)

    rem = (rem - m) * 60.0
    s = int(round(rem))

    if s >= 60:
        s = 0
        m += 1

    if m >= 60:
        m = 0
        d += 1

    return f"{sign}{d:02d}*{m:02d}:{s:02d}"


# ---------------------------------------------------------------------------
# Angular helpers
# ---------------------------------------------------------------------------

def ra_hours_to_deg(hours: float) -> float:
    return hours * DEG_PER_HOUR


def deg_to_ra_hours(deg: float) -> float:
    return deg / DEG_PER_HOUR


def normalize_ra_hours(hours: float) -> float:
    return hours % 24.0


def normalize_degrees(deg: float) -> float:
    return deg % 360.0


def shortest_ra_delta_hours(current: float, target: float) -> float:
    """
    Return shortest RA delta in hours.

    Handles wraparound across 0h.
    """

    delta = target - current

    while delta > 12.0:
        delta -= 24.0

    while delta < -12.0:
        delta += 24.0

    return delta


def shortest_ra_delta_deg(current_hours: float,
                          target_hours: float) -> float:

    return shortest_ra_delta_hours(
        current_hours,
        target_hours
    ) * DEG_PER_HOUR


# ---------------------------------------------------------------------------
# Spherical geometry
# ---------------------------------------------------------------------------

def angular_separation(
        ra1_hours: float,
        dec1_deg: float,
        ra2_hours: float,
        dec2_deg: float
) -> float:
    """
    Great-circle distance in degrees.
    """

    ra1 = math.radians(ra_hours_to_deg(ra1_hours))
    dec1 = math.radians(dec1_deg)

    ra2 = math.radians(ra_hours_to_deg(ra2_hours))
    dec2 = math.radians(dec2_deg)

    cos_sep = (
        math.sin(dec1) * math.sin(dec2)
        + math.cos(dec1)
        * math.cos(dec2)
        * math.cos(ra1 - ra2)
    )

    cos_sep = max(-1.0, min(1.0, cos_sep))

    return math.degrees(math.acos(cos_sep))


# ---------------------------------------------------------------------------
# Slew helpers
# ---------------------------------------------------------------------------

def move_towards(
        current: float,
        target: float,
        max_step: float
) -> float:
    """
    Move a scalar toward target by max_step.
    """

    delta = target - current

    if abs(delta) <= max_step:
        return target

    if delta > 0:
        return current + max_step

    return current - max_step


def move_ra_towards(
        current_hours: float,
        target_hours: float,
        max_step_deg: float
) -> float:
    """
    Move RA along shortest path.
    """

    delta_deg = shortest_ra_delta_deg(
        current_hours,
        target_hours
    )

    if abs(delta_deg) <= max_step_deg:
        return normalize_ra_hours(target_hours)

    direction = 1.0 if delta_deg > 0 else -1.0

    current_deg = ra_hours_to_deg(current_hours)

    current_deg += direction * max_step_deg

    return normalize_ra_hours(
        deg_to_ra_hours(current_deg)
    )
def hour_angle(state):
    ha = state.local_sidereal_hours - state.current_ra_hours
    if ha < 0:
        ha += 24.0
    return ha
    
from datetime import datetime, timezone
import math


def calculate_lst(longitude_deg: float) -> float:
    """
    Returns Local Sidereal Time in decimal hours.
    East longitude positive.
    """

    now = datetime.now(timezone.utc)

    # Julian Date
    unix_days = now.timestamp() / 86400.0
    jd = unix_days + 2440587.5

    # Days since J2000
    d = jd - 2451545.0

    # GMST in hours
    gmst = (
        18.697374558
        + 24.06570982441908 * d
    ) % 24.0

    # Convert longitude to hours
    longitude_hours = longitude_deg / 15.0

    # Local Sidereal Time
    lst = (gmst + longitude_hours) % 24.0

    return lst


# ---------------------------------------------------------------------------
# Simple tests
# ---------------------------------------------------------------------------

if __name__ == "__main__":

    ra = parse_ra("05:35:17")
    print("RA:", ra)
    print(format_ra(ra))

    dec = parse_dec("+22*00:52")
    print("DEC:", dec)
    print(format_dec(dec))

    print(
        angular_separation(
            5.0,
            20.0,
            5.5,
            20.0
        )
    )
    
