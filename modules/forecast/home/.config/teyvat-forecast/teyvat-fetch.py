#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
teyvat-fetch.py — Teyvat Forecast data layer.

Fetches weather + air quality from Open-Meteo (no API key), merges everything
into ONE JSON file written atomically to:
    ~/.cache/teyvat-forecast/weather.json

That single file is shared by:
  * the Quickshell popup (read-only, file-watched)
  * the Waybar module shim (waybar/weather.sh, precomputed `waybar` object)

Location resolution order:
  1. ~/.config/teyvat-forecast/config.json   (lat / lon / city)
  2. legacy ~/.config/waybar-genshin/weather.conf  (LAT / LON / [CITY] / UNIT)
  3. legacy location cache ~/.cache/genshin-weather/loc (if < 7 days old)
  4. own location cache ~/.cache/teyvat-forecast/loc (if < 7 days old)
  5. IP geolocation via https://ipwho.is/  (cached for 7 days)

Commands:
    fetch                     fetch real data, write cache (default)
    preview <scene> [--stale] write synthetic data for a preview scene
                              scenes: clear rain snow storm fog hot windy night
    demo-stale                mark data stale (uses real cache if present)
    restore                   restore the pre-preview cache backup
    status                    print cache state (for humans)
    search <query>            city lookup (Open-Meteo geocoding) -> JSON on stdout
    set-city <lat> <lon> <name>   save the chosen city to config.json, then fetch
    locate                    set the city from IP geolocation, then fetch

Exit codes: 0 ok / 1 network or io failure / 2 bad usage.

Python 3.8+, standard library only. HTTP via `curl` (checked by install.sh).
"""

import fcntl
import json
import math
import os
import subprocess
import sys
import time
import urllib.parse
from datetime import datetime, timedelta, timezone
from pathlib import Path

# --------------------------------------------------------------------------- #
# paths (overridable for testing)
# --------------------------------------------------------------------------- #

HOME = os.environ.get("HOME", str(Path.home()))
XDG_CONFIG = os.environ.get("XDG_CONFIG_HOME", os.path.join(HOME, ".config"))
XDG_CACHE = os.environ.get("XDG_CACHE_HOME", os.path.join(HOME, ".cache"))

CONF_DIR = Path(os.environ.get("TEYVAT_CONFIG", os.path.join(XDG_CONFIG, "teyvat-forecast")))
CACHE_DIR = Path(os.environ.get("TEYVAT_CACHE", os.path.join(XDG_CACHE, "teyvat-forecast")))

CONF_FILE = CONF_DIR / "config.json"
CACHE_JSON = CACHE_DIR / "weather.json"
CACHE_BAK = CACHE_DIR / "weather.json.bak"
LOCK_FILE = CACHE_DIR / ".fetch.lock"
LOC_CACHE = CACHE_DIR / "loc"

LEGACY_CONF = Path(os.environ.get("TEYVAT_LEGACY_CONF",
                                  os.path.join(XDG_CONFIG, "waybar-genshin", "weather.conf")))
LEGACY_LOC = Path(os.path.join(XDG_CACHE, "genshin-weather", "loc"))

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
AIR_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"
IP_URL = "https://ipwho.is/"
GEO_URL = "https://geocoding-api.open-meteo.com/v1/search"
CURL_TIMEOUT = 10

SCHEMA = 1

# --------------------------------------------------------------------------- #
# small helpers
# --------------------------------------------------------------------------- #


def log(msg: str) -> None:
    print(f"teyvat-fetch: {msg}", file=sys.stderr)


def curl_json(url: str):
    """GET a URL with curl, return parsed JSON or None."""
    try:
        out = subprocess.run(
            ["curl", "-fsS", "--max-time", str(CURL_TIMEOUT), "-H", "Accept: application/json", url],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=CURL_TIMEOUT + 5,
        )
        if out.returncode != 0:
            return None
        return json.loads(out.stdout.decode("utf-8", "replace"))
    except (subprocess.SubprocessError, ValueError, OSError):
        return None


def jq_round(x):
    """Round half away from zero (matches jq's round())."""
    if x is None:
        return None
    x = float(x)
    return int(math.floor(x + 0.5)) if x >= 0 else int(math.ceil(x - 0.5))


def atomic_write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    os.replace(str(tmp), str(path))


def compass(deg):
    dirs = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
    if deg is None:
        return ""
    return dirs[int(((float(deg) % 360) + 22.5) // 45) % 8]


# ---- weather code tables (identical wording to the original weather.sh) ---- #

CONDITIONS = {
    0: "Clear", 1: "Mostly clear", 2: "Partly cloudy", 3: "Overcast",
    45: "Fog", 48: "Fog",
    51: "Drizzle", 53: "Drizzle", 55: "Drizzle", 56: "Drizzle", 57: "Drizzle",
    61: "Rain", 63: "Rain", 65: "Rain", 66: "Rain", 67: "Rain",
    71: "Snow", 73: "Snow", 75: "Snow", 77: "Snow",
    80: "Rain", 81: "Rain", 82: "Rain",
    85: "Snow", 86: "Snow",
    95: "Thunderstorm", 96: "Thunderstorm", 99: "Thunderstorm",
}

WAYBAR_CLASS = {
    0: "clear", 1: "clear", 2: "cloud", 3: "cloud", 45: "fog", 48: "fog",
    51: "rain", 53: "rain", 55: "rain", 56: "rain", 57: "rain",
    61: "rain", 63: "rain", 65: "rain", 66: "rain", 67: "rain",
    71: "snow", 73: "snow", 75: "snow", 77: "snow",
    80: "rain", 81: "rain", 82: "rain",
    85: "snow", 86: "snow",
    95: "storm", 96: "storm", 99: "storm",
}

# ---- moon phase (computed locally; Open-Meteo has no moon endpoint) -------- #
# Full implementation based on Jean Meeus, "Astronomical Algorithms" 2nd ed.
#   Ch. 7   - Julian Day
#   Ch. 13  - Sidereal time & hour angle
#   Ch. 22  - Nutation & obliquity
#   Ch. 25  - Solar coordinates (low-accuracy, sufficient for phase/limb angle)
#   Ch. 47  - Moon position (longitude, latitude, distance) - full periodic table
#   Ch. 48  - Illuminated fraction & position angle of the bright limb
# Additionally: parallactic angle q from spherical astronomy (Meeus Ch. 14)
# to obtain the topocentric bright-limb tilt as seen by the observer.

MOON_NAMES = [
    (0.033, "New Moon"), (0.216, "Waxing Crescent"), (0.283, "First Quarter"),
    (0.466, "Waxing Gibbous"), (0.533, "Full Moon"), (0.716, "Waning Gibbous"),
    (0.783, "Last Quarter"), (0.966, "Waning Crescent"), (1.01, "New Moon"),
]

SYNODIC_MONTH = 29.530588861   # mean synodic month in days


def _julian_day(u):
    """Julian day of an aware/naive-UTC datetime (Meeus, ch. 7)."""
    y, m = u.year, u.month
    d = u.day + (u.hour + u.minute / 60.0 + u.second / 3600.0) / 24.0
    if m <= 2:
        y -= 1
        m += 12
    a = y // 100
    b = 2 - a + a // 4
    return int(365.25 * (y + 4716)) + int(30.6001 * (m + 1)) + d + b - 1524.5


def _rad(deg):
    return math.radians(deg % 360.0)


def _norm360(deg):
    return deg % 360.0


def _norm180(deg):
    """Normalize to -180..+180."""
    d = deg % 360.0
    return d - 360.0 if d > 180 else d


# -- Nutation in longitude and obliquity of ecliptic (Meeus ch. 22) --------- #

def _nutation_obliquity(t):
    """Returns (delta_psi_deg, epsilon_deg) - nutation in longitude and true
    obliquity of the ecliptic, both in degrees.  Uses the four largest terms
    of the 1980 IAU nutation series (accurate to ~0.5 arcsec in delta-psi)."""
    omega = 125.04452 - 1934.136261 * t
    ls = 280.4665 + 36000.7698 * t        # mean longitude of the Sun
    lm = 218.3165 + 481267.8813 * t        # mean longitude of the Moon
    dp = (-17.20 * math.sin(_rad(omega))
          - 1.32 * math.sin(_rad(2 * ls))
          - 0.23 * math.sin(_rad(2 * lm))
          + 0.21 * math.sin(_rad(2 * omega))) / 3600.0   # arcsec -> degrees
    de = (9.20 * math.cos(_rad(omega))
          + 0.57 * math.cos(_rad(2 * ls))
          + 0.10 * math.cos(_rad(2 * lm))
          - 0.09 * math.cos(_rad(2 * omega))) / 3600.0
    e0 = (23.0 + 26.0 / 60 + 21.448 / 3600
          - (46.8150 * t + 0.00059 * t * t - 0.001813 * t * t * t) / 3600.0)
    return dp, e0 + de


# -- Sun position (Meeus ch. 25, low accuracy) ------------------------------ #

def _sun_ra_dec(t, epsilon):
    """Geocentric apparent RA (deg) and Dec (deg) of the Sun."""
    l0 = _norm360(280.46646 + 36000.76983 * t + 0.0003032 * t * t)
    m = _norm360(357.52911 + 35999.05029 * t - 0.0001537 * t * t)
    mr = _rad(m)
    c = ((1.914602 - 0.004817 * t - 0.000014 * t * t) * math.sin(mr)
         + (0.019993 - 0.000101 * t) * math.sin(2 * mr)
         + 0.000289 * math.sin(3 * mr))
    sun_lon = math.radians(l0 + c)
    er = math.radians(epsilon)
    ra = math.degrees(math.atan2(math.cos(er) * math.sin(sun_lon), math.cos(sun_lon)))
    dec = math.degrees(math.asin(math.sin(er) * math.sin(sun_lon)))
    return _norm360(ra), dec


# -- Moon position (Meeus ch. 47) - full periodic series -------------------- #
# Largest terms for longitude (Sl), latitude (Sb) and distance (Sr).

_MOON_LR = [
    # (D, M, M', F, Sl_coeff [1e-6 deg], Sr_coeff [km * 1000])
    (0,0,1,0,  6288774, -20905355),
    (2,0,-1,0, 1274027,  -3699111),
    (2,0,0,0,   658314,  -2955968),
    (0,0,2,0,   213618,   -569925),
    (0,1,0,0,  -185116,     48888),
    (0,0,0,2,  -114332,     -3149),
    (2,0,-2,0,   58793,    246158),
    (2,-1,-1,0,  57066,   -152138),
    (2,0,1,0,    53322,   -170733),
    (2,-1,0,0,   45758,   -204586),
    (0,1,-1,0,  -40923,   -129620),
    (1,0,0,0,   -34720,    108743),
    (0,1,1,0,   -30383,    104755),
    (2,0,0,-2,   15327,     10321),
    (0,0,1,2,   -12528,         0),
    (0,0,1,-2,   10980,     79661),
    (4,0,-1,0,   10675,    -34782),
    (0,0,3,0,    10034,    -23210),
    (4,0,-2,0,    8548,    -21636),
    (2,1,-1,0,   -7888,     24208),
    (2,1,0,0,    -6766,     30824),
    (1,0,-1,0,   -5163,     -8379),
    (1,1,0,0,    4987,    -16675),
    (2,-1,1,0,    4036,    -12831),
    (2,0,2,0,    3994,    -10445),
    (4,0,0,0,    3861,    -11650),
    (2,0,-3,0,   3665,     14403),
    (0,1,-2,0,  -2689,     -7003),
    (2,0,-1,2,  -2602,         0),
    (2,-1,-2,0,  2390,     10056),
    (1,0,1,0,   -2348,      6322),
    (2,-2,0,0,   2236,     -9884),
    (0,1,2,0,   -2120,      5751),
    (0,2,0,0,   -2069,         0),
    (2,-2,-1,0,  2048,     -4950),
    (2,0,1,-2,  -1773,      4130),
    (2,0,0,2,   -1595,         0),
    (4,-1,-1,0,  1215,     -3958),
    (0,0,2,2,   -1110,         0),
    (3,0,-1,0,   -892,      3258),
    (2,1,1,0,    -810,      2616),
    (4,-1,-2,0,   759,     -1897),
    (0,2,-1,0,   -713,     -2117),
    (2,2,-1,0,   -700,      2354),
    (2,1,-2,0,    691,         0),
    (2,-1,0,-2,   596,         0),
    (4,0,1,0,    549,     -1423),
    (0,0,4,0,    537,     -1117),
    (4,-1,0,0,   520,     -1571),
    (1,0,-2,0,  -487,     -1739),
    (2,1,0,-2,  -399,         0),
    (0,0,2,-2,  -381,     -4421),
    (1,1,1,0,    351,         0),
    (3,0,-2,0,   -340,         0),
    (4,0,-3,0,    330,         0),
    (2,-1,2,0,    327,         0),
    (0,2,1,0,    -323,      1165),
    (1,1,-1,0,    299,         0),
    (2,0,3,0,    294,         0),
    (2,0,-1,-2,   0,       8752),
]

_MOON_B = [
    # (D, M, M', F, Sb_coeff [1e-6 deg])
    (0,0,0,1,  5128122),
    (0,0,1,1,   280602),
    (0,0,1,-1,  277693),
    (2,0,0,-1,  173237),
    (2,0,-1,1,   55413),
    (2,0,-1,-1,  46271),
    (2,0,0,1,    32573),
    (0,0,2,1,    17198),
    (2,0,1,-1,    9266),
    (0,0,2,-1,    8822),
    (2,-1,0,-1,   8216),
    (2,0,-2,-1,   4324),
    (2,0,1,1,     4200),
    (2,1,0,-1,   -3359),
    (2,-1,-1,1,   2463),
    (2,-1,0,1,    2211),
    (2,-1,-1,-1,  2065),
    (0,1,-1,-1,  -1870),
    (4,0,-1,-1,   1828),
    (0,1,0,1,    -1794),
    (0,0,0,3,    -1749),
    (0,1,-1,1,   -1565),
    (1,0,0,1,    -1491),
    (0,1,1,1,    -1475),
    (0,1,1,-1,   -1410),
    (0,1,0,-1,   -1344),
    (1,0,0,-1,   -1335),
    (0,0,3,1,     1107),
    (4,0,0,-1,    1021),
    (4,0,-1,1,     833),
    (0,0,1,-3,     777),
    (4,0,-2,1,     671),
    (2,0,0,-3,     607),
    (2,0,2,-1,     596),
    (2,-1,1,-1,    491),
    (2,0,-2,1,    -451),
    (0,0,3,-1,     439),
    (2,0,2,1,      422),
    (2,0,-3,-1,    421),
    (2,1,-1,1,    -366),
    (2,1,0,1,     -351),
    (4,0,0,1,      331),
    (2,-1,1,1,     315),
    (2,-2,0,-1,    302),
    (0,0,1,3,     -283),
    (2,1,1,-1,    -229),
    (1,1,0,-1,     223),
    (1,1,0,1,      223),
    (0,1,-2,-1,   -220),
    (2,1,-1,-1,   -220),
    (1,0,1,1,     -185),
    (2,-1,-2,-1,   181),
    (0,1,2,1,     -177),
    (4,0,-2,-1,    176),
    (4,-1,-1,-1,   166),
    (1,0,1,-1,    -164),
    (4,0,1,-1,     132),
    (1,0,-1,-1,   -119),
    (4,-1,0,-1,    115),
    (2,-2,0,1,     107),
]


def _moon_position(t):
    """Geocentric ecliptic longitude (deg), latitude (deg) and distance (km)
    of the Moon.  Full periodic series from Meeus ch. 47, Table 47.A/47.B."""
    # Fundamental arguments (degrees)
    Lp = _norm360(218.3164477 + 481267.88123421 * t
                  - 0.0015786 * t * t + t * t * t / 538841.0
                  - t ** 4 / 65194000.0)
    D  = _norm360(297.8501921 + 445267.1114034  * t
                  - 0.0018819 * t * t + t * t * t / 545868.0
                  - t ** 4 / 113065000.0)
    M  = _norm360(357.5291092 + 35999.0502909   * t
                  - 0.0001536 * t * t + t * t * t / 24490000.0)
    Mp = _norm360(134.9633964 + 477198.8675055  * t
                  + 0.0087414 * t * t + t * t * t / 69699.0
                  - t ** 4 / 14712000.0)
    F  = _norm360(93.2720950  + 483202.0175233  * t
                  - 0.0036539 * t * t - t * t * t / 3526000.0
                  + t ** 4 / 863310000.0)

    # Eccentricity correction for terms involving M of the Sun
    E  = 1.0 - 0.002516 * t - 0.0000074 * t * t
    E2 = E * E

    # Sl and Sr
    sum_l = 0.0
    sum_r = 0.0
    for d_c, m_c, mp_c, f_c, sl, sr in _MOON_LR:
        arg = _rad(d_c * D + m_c * M + mp_c * Mp + f_c * F)
        e_fac = E2 if abs(m_c) == 2 else (E if abs(m_c) == 1 else 1.0)
        sum_l += sl * e_fac * math.sin(arg)
        sum_r += sr * e_fac * math.cos(arg)

    # Sb
    sum_b = 0.0
    for d_c, m_c, mp_c, f_c, sb in _MOON_B:
        arg = _rad(d_c * D + m_c * M + mp_c * Mp + f_c * F)
        e_fac = E2 if abs(m_c) == 2 else (E if abs(m_c) == 1 else 1.0)
        sum_b += sb * e_fac * math.sin(arg)

    # Additional additive terms (Venus A1, Jupiter A2, flat-Earth A3)
    A1 = _norm360(119.75 + 131.849 * t)
    A2 = _norm360(53.09  + 479264.290 * t)
    A3 = _norm360(313.45 + 481266.484 * t)

    sum_l += (3958 * math.sin(_rad(A1))
              + 1962 * math.sin(_rad(Lp - F))
              + 318 * math.sin(_rad(A2)))
    sum_b += (-2235 * math.sin(_rad(Lp))
              + 382  * math.sin(_rad(A3))
              + 175  * math.sin(_rad(A1 - F))
              + 175  * math.sin(_rad(A1 + F))
              + 127  * math.sin(_rad(Lp - Mp))
              - 115  * math.sin(_rad(Lp + Mp)))

    lam = Lp + sum_l / 1e6       # ecliptic longitude (degrees)
    beta = sum_b / 1e6            # ecliptic latitude  (degrees)
    dist = 385000.56 + sum_r / 1000.0  # distance (km)

    return lam, beta, dist


def _ecliptic_to_equatorial(lam_deg, beta_deg, epsilon_deg):
    """Convert ecliptic (lam, beta) to equatorial (RA, Dec), all in degrees."""
    lam = math.radians(lam_deg)
    beta = math.radians(beta_deg)
    eps = math.radians(epsilon_deg)
    sin_lam = math.sin(lam)
    cos_lam = math.cos(lam)
    sin_beta = math.sin(beta)
    cos_beta = math.cos(beta)
    sin_eps = math.sin(eps)
    cos_eps = math.cos(eps)

    ra = math.atan2(sin_lam * cos_eps - math.tan(beta) * sin_eps, cos_lam)
    dec = math.asin(sin_beta * cos_eps + cos_beta * sin_eps * sin_lam)
    return _norm360(math.degrees(ra)), math.degrees(dec)


def _gmst(jd):
    """Greenwich Mean Sidereal Time in degrees (Meeus ch. 12)."""
    t = (jd - 2451545.0) / 36525.0
    theta = (280.46061837 + 360.98564736629 * (jd - 2451545.0)
             + 0.000387933 * t * t - t * t * t / 38710000.0)
    return _norm360(theta)


def _parallactic_angle(lat_deg, dec_deg, ha_deg):
    """Parallactic angle q (degrees) - Meeus ch. 14, eq. 14.1.
    This is the angle between the great circle through the celestial pole
    and the zenith, measured at the Moon's position."""
    lat = math.radians(lat_deg)
    dec = math.radians(dec_deg)
    ha = math.radians(ha_deg)
    q = math.atan2(math.sin(ha),
                   math.tan(lat) * math.cos(dec) - math.sin(dec) * math.cos(ha))
    return math.degrees(q)


def _position_angle_bright_limb(ra_sun, dec_sun, ra_moon, dec_moon):
    """Position angle chi of the midpoint of the bright limb (Meeus ch. 48).
    Measured from north celestial pole, eastward (CCW)."""
    d_ra = math.radians(ra_sun - ra_moon)
    ds = math.radians(dec_sun)
    dm = math.radians(dec_moon)
    chi = math.atan2(math.cos(ds) * math.sin(d_ra),
                     math.sin(ds) * math.cos(dm)
                     - math.cos(ds) * math.sin(dm) * math.cos(d_ra))
    return math.degrees(chi)


def _moon_age(D_deg):
    """Moon age in days from mean elongation D (degrees).
    Age 0 = new moon, ~14.77 = full moon, ~29.53 = next new."""
    return (D_deg % 360.0) / 360.0 * SYNODIC_MONTH


def moon_phase(now, lat=None, lon=None):
    """Compute detailed lunar phase information.

    Returns a dict with keys:
        phase       - 0..1 cycle fraction (0 new, 0.5 full) [QML terminator]
        name        - English phase name
        illum       - illuminated fraction in percent (0..100)
        tilt        - bright-limb tilt for observer (degrees, 0=up, CW positive)
                      None if lat/lon not provided
        age         - moon age in days (0..29.53)
        distance_km - geocentric distance in km
        is_supermoon - True if distance < 360000 km AND illum >= 98%

    Astronomical illumination (Meeus ch. 47/48) with full periodic series
    for longitude, latitude and distance.

    `phase` is the fraction the QML terminator formula expects:
        lit fraction = (1 - cos(2*pi*phase)) / 2
        phase < 0.5  -> waxing,  phase > 0.5 -> waning
    so the drawn shape and the printed % always agree."""
    u = now.astimezone(timezone.utc) if now.tzinfo else now.astimezone().astimezone(timezone.utc)
    jd = _julian_day(u)
    t = (jd - 2451545.0) / 36525.0

    # Nutation + true obliquity
    delta_psi, epsilon = _nutation_obliquity(t)

    # Moon geocentric position (ecliptic)
    moon_lam, moon_beta, moon_dist = _moon_position(t)
    moon_lam += delta_psi  # apparent longitude

    # Moon equatorial RA/Dec
    moon_ra, moon_dec = _ecliptic_to_equatorial(moon_lam, moon_beta, epsilon)

    # Sun equatorial RA/Dec
    sun_ra, sun_dec = _sun_ra_dec(t, epsilon)

    # Phase angle i (Meeus ch. 48) - accurate version using actual elongation
    d_ra = math.radians(moon_ra - sun_ra)
    cos_psi = (math.sin(math.radians(sun_dec)) * math.sin(math.radians(moon_dec))
               + math.cos(math.radians(sun_dec)) * math.cos(math.radians(moon_dec))
               * math.cos(d_ra))
    cos_psi = max(-1.0, min(1.0, cos_psi))
    psi = math.acos(cos_psi)  # geocentric elongation

    # i = atan2(R * sin(psi), delta - R * cos(psi))  (Meeus eq. 48.3)
    R_sun_au = 1.0  # sufficient accuracy; Sun distance varies +/-1.7%
    delta_au = moon_dist / 149597870.7
    i_rad = math.atan2(R_sun_au * math.sin(psi),
                       delta_au - R_sun_au * cos_psi)

    k = max(0.0, min(1.0, (1.0 + math.cos(i_rad)) / 2.0))  # illuminated fraction

    # Determine waxing/waning from the mean elongation D
    D_mean = _norm360(297.8501921 + 445267.1114034 * t - 0.0018819 * t * t)
    waxing = (D_mean % 360.0) < 180.0

    # Phase fraction for QML (0 new -> 0.5 full -> 1 new)
    base = math.acos(max(-1.0, min(1.0, 1.0 - 2.0 * k))) / (2.0 * math.pi)
    phase = base if waxing else 1.0 - base

    name = "New Moon"
    for limit, n in MOON_NAMES:
        if phase <= limit:
            name = n
            break

    # Moon age (days since new moon)
    age = _moon_age(D_mean)

    # Supermoon: near perigee AND near full
    is_supermoon = moon_dist < 360000 and k >= 0.98

    # Bright-limb tilt for observer (topocentric)
    tilt = None
    if lat is not None and lon is not None:
        try:
            lat_f = float(lat)
            lon_f = float(lon)
            # Hour angle of the Moon
            gast = _gmst(jd) + delta_psi * math.cos(math.radians(epsilon))
            local_sidereal = _norm360(gast + lon_f)
            ha = _norm180(local_sidereal - moon_ra)
            # Position angle of the bright limb (geocentric)
            chi = _position_angle_bright_limb(sun_ra, sun_dec, moon_ra, moon_dec)
            # Parallactic angle
            q = _parallactic_angle(lat_f, moon_dec, ha)
            # Topocentric bright limb angle (rotation for the observer)
            tilt = round(_norm180(chi - q), 2)
        except (TypeError, ValueError):
            tilt = None

    return {
        "phase": round(phase, 4),
        "name": name,
        "illum": round(k * 100),
        "tilt": tilt,
        "age": round(age, 2),
        "distance_km": round(moon_dist),
        "is_supermoon": is_supermoon,
    }



# --------------------------------------------------------------------------- #
# config / location
# --------------------------------------------------------------------------- #


def load_config():
    cfg = {"city": "", "lat": None, "lon": None, "units": "metric",
           "refresh_minutes": 12, "quality": "medium"}
    if CONF_FILE.is_file():
        try:
            data = json.loads(CONF_FILE.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                for key in ("city", "lat", "lon", "units"):
                    if data.get(key) is not None:
                        cfg[key] = data[key]
                if str(data.get("units", "")).lower() == "imperial":
                    cfg["units"] = "imperial"
        except (ValueError, OSError):
            pass
    return cfg


def load_legacy_conf():
    """Reuse the original weather.sh override file (KEY=VALUE)."""
    vals = {}
    if LEGACY_CONF.is_file():
        try:
            for line in LEGACY_CONF.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                vals[k.strip().upper()] = v.strip()
        except OSError:
            pass
    return vals


def read_loc_cache(path: Path, max_age_days: int = 7):
    try:
        age_days = (time.time() - path.stat().st_mtime) / 86400.0
        if age_days > max_age_days:
            return None
        parts = path.read_text(encoding="utf-8").split()
        if len(parts) >= 2:
            return float(parts[0]), float(parts[1]), (parts[2] if len(parts) > 2 else "")
    except (OSError, ValueError):
        return None
    return None


def write_loc_cache(lat, lon, city):
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        LOC_CACHE.write_text(f"{lat} {lon} {city}\n", encoding="utf-8")
    except OSError:
        pass


def ip_locate():
    data = curl_json(IP_URL)
    if not data or data.get("success") is False:
        return None
    try:
        lat = float(data["latitude"])
        lon = float(data["longitude"])
    except (KeyError, TypeError, ValueError):
        return None
    city = str(data.get("city") or data.get("region") or "")
    return lat, lon, city


def resolve_location(cfg):
    """Returns (lat, lon, city, source)."""
    if cfg.get("lat") is not None and cfg.get("lon") is not None:
        return float(cfg["lat"]), float(cfg["lon"]), str(cfg.get("city") or ""), "config"

    legacy = load_legacy_conf()
    if legacy.get("LAT") and legacy.get("LON"):
        return float(legacy["LAT"]), float(legacy["LON"]), str(legacy.get("CITY", "")), "legacy weather.conf"

    for path, source in ((LEGACY_LOC, "legacy cache"), (LOC_CACHE, "cache")):
        got = read_loc_cache(path)
        if got:
            return got[0], got[1], got[2], source

    got = ip_locate()
    if got:
        write_loc_cache(*got)
        return got[0], got[1], got[2], "ip lookup"

    # dead last: reuse even a stale cache rather than nothing
    for path in (LEGACY_LOC, LOC_CACHE):
        got = read_loc_cache(path, max_age_days=3650)
        if got:
            return got[0], got[1], got[2], "stale cache"
    return None, None, "", "unavailable"


# --------------------------------------------------------------------------- #
# fetching
# --------------------------------------------------------------------------- #

CURRENT_VARS = ("temperature_2m,apparent_temperature,relative_humidity_2m,is_day,"
                "precipitation,weather_code,cloud_cover,pressure_msl,wind_speed_10m,"
                "wind_direction_10m,wind_gusts_10m")
HOURLY_VARS = "temperature_2m,precipitation_probability,weather_code,visibility,uv_index,is_day"
DAILY_VARS = ("weather_code,temperature_2m_max,temperature_2m_min,sunrise,sunset,"
              "uv_index_max,precipitation_probability_max")
AIR_VARS = "european_aqi,us_aqi,pm10,pm2_5,ozone,nitrogen_dioxide"


def fetch_forecast(lat, lon, units):
    params = {
        "latitude": lat, "longitude": lon,
        "current": CURRENT_VARS, "hourly": HOURLY_VARS, "daily": DAILY_VARS,
        "timezone": "auto", "forecast_days": 7,
    }
    if units == "imperial":
        params["temperature_unit"] = "fahrenheit"
        params["wind_speed_unit"] = "mph"
    else:
        params["temperature_unit"] = "celsius"
        params["wind_speed_unit"] = "kmh"
    url = FORECAST_URL + "?" + "&".join(f"{k}={v}" for k, v in params.items())
    return curl_json(url)


def fetch_air(lat, lon):
    url = (f"{AIR_URL}?latitude={lat}&longitude={lon}&current={AIR_VARS}&timezone=auto")
    return curl_json(url)


# --------------------------------------------------------------------------- #
# building the unified JSON
# --------------------------------------------------------------------------- #


def build_weather_json(forecast, air, loc, units, now=None):
    now = now or datetime.now()
    cur = forecast.get("current") or {}
    hourly = forecast.get("hourly") or {}
    daily = forecast.get("daily") or {}

    temp_unit = "fahrenheit" if units == "imperial" else "celsius"
    temp_sym = "°F" if units == "imperial" else "°C"
    wind_unit = "mph" if units == "imperial" else "km/h"
    kmh_factor = 1.609344 if units == "imperial" else 1.0

    def fnum(d, k, default=None):
        v = d.get(k) if isinstance(d, dict) else None
        try:
            if v is None:
                return default
            return float(v)
        except (TypeError, ValueError):
            return default

    def fint(d, k, default=0):
        """int coercion with an EXPLICIT None check — never `x or default`,
        because 0 / 0.0 is a valid value (is_day=0 is night!)."""
        v = fnum(d, k, None)
        return default if v is None else int(v)

    # array-field coercions with the same explicit-None rule (a 0 in the data
    # stays a 0; only a missing value falls back to the default)
    def a_int(d, k, i, default=0):
        v = _arr(d, k, i)
        return default if v is None else int(v)

    def a_float(d, k, i, default=0.0):
        v = _arr(d, k, i)
        return default if v is None else float(v)

    code = fint(cur, "weather_code", 0)
    is_day = fint(cur, "is_day", 1)
    wind_kmh = fnum(cur, "wind_speed_10m", 0.0) * kmh_factor

    # --- next 24 h slice, anchored on the API's own current time ----------- #
    h_times = hourly.get("time") or []
    start = 0
    cur_time = cur.get("time")
    if cur_time:
        for i, t in enumerate(h_times):
            if t >= cur_time:
                start = i
                break
    h_idx = list(range(start, min(start + 24, len(h_times))))
    if len(h_idx) < 24 and h_times:                       # pad by clamping
        while len(h_idx) < 24:
            h_idx.append(min(h_idx[-1] + 1, len(h_times) - 1))

    hourly_out = []
    for i in h_idx:
        t = h_times[i]
        hour_label = t[11:13] if len(t) >= 13 else ""
        hourly_out.append({
            "time": t, "label": hour_label,
            "temp": _arr(hourly, "temperature_2m", i),
            "precip_prob": a_int(hourly, "precipitation_probability", i, 0),
            "code": a_int(hourly, "weather_code", i, 0),
            "is_day": a_int(hourly, "is_day", i, 1),
            "uv": _arr(hourly, "uv_index", i),
            "visibility_km": round(a_float(hourly, "visibility", i, 0.0) / 1000.0, 1),
        })

    # --- daily ------------------------------------------------------------- #
    d_times = daily.get("time") or []
    daily_out = []
    for i, d in enumerate(d_times[:7]):
        try:
            label = datetime.strptime(d, "%Y-%m-%d").strftime("%a %d")
        except ValueError:
            label = d
        daily_out.append({
            "date": d, "label": label, "is_today": i == 0,
            "code": a_int(daily, "weather_code", i, 0),
            "t_max": _arr(daily, "temperature_2m_max", i),
            "t_min": _arr(daily, "temperature_2m_min", i),
            "precip_prob": a_int(daily, "precipitation_probability_max", i, 0),
            "sunrise": _arr(daily, "sunrise", i), "sunset": _arr(daily, "sunset", i),
            "uv_max": _arr(daily, "uv_index_max", i),
        })

    # --- today ------------------------------------------------------------- #
    moon = moon_phase(now, lat=loc[0], lon=loc[1])
    today = {
        "sunrise": _arr(daily, "sunrise", 0),
        "sunset": _arr(daily, "sunset", 0),
        "uv_max": _arr(daily, "uv_index_max", 0),
        "precip_prob_max": a_int(daily, "precipitation_probability_max", 0, 0),
        "temp_max": _arr(daily, "temperature_2m_max", 0),
        "temp_min": _arr(daily, "temperature_2m_min", 0),
        "moon_phase": moon["phase"], "moon_name": moon["name"],
        "moon_illum": moon["illum"], "moon_tilt": moon["tilt"],
        "moon_age": moon["age"], "moon_distance_km": moon["distance_km"],
        "is_supermoon": moon["is_supermoon"],
    }

    # --- air --------------------------------------------------------------- #
    air_out = {"available": False, "reason": "air quality service unreachable"}
    if air and isinstance(air.get("current"), dict):
        ac = air["current"]
        if ac.get("european_aqi") is not None or ac.get("us_aqi") is not None:
            air_out = {
                "available": True,
                "eu_aqi": fnum(ac, "european_aqi"), "us_aqi": fnum(ac, "us_aqi"),
                "pm2_5": fnum(ac, "pm2_5"), "pm10": fnum(ac, "pm10"),
                "o3": fnum(ac, "ozone"), "no2": fnum(ac, "nitrogen_dioxide"),
                "updated": ac.get("time", ""),
            }
        else:
            air_out = {"available": False, "reason": "no air quality data for this region"}

    # --- current ----------------------------------------------------------- #
    current_out = {
        "temperature": fnum(cur, "temperature_2m"),
        "feels_like": fnum(cur, "apparent_temperature"),
        "humidity": fint(cur, "relative_humidity_2m", 0),
        "pressure": fnum(cur, "pressure_msl"),
        "wind_speed": fnum(cur, "wind_speed_10m"),
        "wind_kmh": round(wind_kmh, 1),
        "wind_gusts": fnum(cur, "wind_gusts_10m"),
        "wind_direction": fnum(cur, "wind_direction_10m"),
        "wind_dir_text": compass(fnum(cur, "wind_direction_10m")),
        "uv_index": fnum(cur, "uv_index"),
        "visibility_m": fnum(cur, "visibility") if cur.get("visibility") is not None else None,
        "cloud_cover": fint(cur, "cloud_cover", 0),
        "is_day": is_day, "code": code,
        "precipitation": fnum(cur, "precipitation", 0.0),
        "time": cur.get("time", ""),
    }
    if current_out["visibility_m"] is None:
        current_out["visibility_m"] = _arr(hourly, "visibility", start)
    if current_out["uv_index"] is None:
        current_out["uv_index"] = _arr(hourly, "uv_index", start)

    # --- precomputed Waybar payload (format-identical to the old script) --- #
    cond = CONDITIONS.get(code, "Unknown")
    t_r = jq_round(current_out["temperature"])
    feel_r = jq_round(current_out["feels_like"])
    wind_r = jq_round(current_out["wind_speed"])
    tip_lines = []
    if loc[2]:
        tip_lines.append(loc[2])
    tip_lines += [cond, f"Feels like {feel_r}°", f"Humidity {current_out['humidity']}%",
                  f"Wind {wind_r} {wind_unit}"]
    waybar = {
        "text": f"{t_r}°",
        "tooltip": "\n".join(tip_lines),
        "classes": ["day" if is_day == 1 else "night", WAYBAR_CLASS.get(code, "cloud")],
    }

    return {
        "schema": SCHEMA, "preview": False, "preview_scene": None, "stale": False,
        "fetched_at": int(now.timestamp()),
        "fetched_at_iso": now.strftime("%Y-%m-%dT%H:%M:%S"),
        "source": "open-meteo",
        "location": {"lat": loc[0], "lon": loc[1], "city": loc[2], "source": loc[3],
                     # seconds east of UTC for THIS city (Open-Meteo timezone=auto);
                     # the popup uses it so the sun/moon arc follows the city's clock
                     "utc_offset_seconds": forecast.get("utc_offset_seconds")},
        "units": {"temperature": temp_unit, "temperature_symbol": temp_sym, "wind": wind_unit},
        "current": current_out, "today": today,
        "hourly": hourly_out, "daily": daily_out, "air": air_out,
        "waybar": waybar,
    }


def _arr(d, key, i):
    """Index into an Open-Meteo array field, tolerating missing data.
    Numeric values come back as floats; strings (times) pass through."""
    arr = d.get(key)
    if isinstance(arr, list) and 0 <= i < len(arr):
        v = arr[i]
        if v is None:
            return None
        try:
            return float(v)
        except (TypeError, ValueError):
            return v
    return None


def mark_stale(obj):
    obj["stale"] = True
    obj["stale_since"] = int(time.time())
    return obj


# --------------------------------------------------------------------------- #
# preview data
# --------------------------------------------------------------------------- #

PREVIEW_SCENES = {
    #            code day  temp feel hum  wind gust uv   vis_m  city          air
    "clear":  dict(code=0,  day=1, temp=24, feel=25, hum=45, wind=8,  gust=14, uv=5.6,  vis=24000, city="Mondstadt",   air=24),
    "rain":   dict(code=63, day=1, temp=14, feel=12, hum=88, wind=14, gust=30, uv=1.2,  vis=6000,  city="Liyue Harbor", air=18),
    "snow":   dict(code=73, day=1, temp=-3, feel=-7, hum=78, wind=10, gust=22, uv=1.5,  vis=3000,  city="Dragonspine",  air=31),
    "storm":  dict(code=95, day=1, temp=18, feel=17, hum=84, wind=26, gust=62, uv=0.6,  vis=4000,  city="Inazuma City", air=42),
    "fog":    dict(code=45, day=1, temp=9,  feel=8,  hum=96, wind=4,  gust=8,  uv=0.8,  vis=600,   city="Sumeru City",  air=88),
    "hot":    dict(code=0,  day=1, temp=37, feel=40, hum=74, wind=6,  gust=12, uv=10.4, vis=20000, city="Natlan",       air=96),
    "windy":  dict(code=1,  day=1, temp=21, feel=20, hum=50, wind=46, gust=72, uv=4.0,  vis=18000, city="Stormbearer Point", air=35),
    "night":  dict(code=1,  day=0, temp=16, feel=15, hum=60, wind=6,  gust=10, uv=0.0,  vis=20000, city="Falcon Coast",  air=21),
}


def build_preview(scene, stale=False, now=None):
    now = now or datetime.now()
    p = PREVIEW_SCENES[scene]
    code, day = p["code"], p["day"]

    hourly_out = []
    for i in range(24):
        t = now + timedelta(hours=i)
        h = t.hour
        day_factor = math.cos((h - 14) / 24.0 * 2 * math.pi) if day == 1 or h in range(6, 20) else -0.6
        temp = p["temp"] + (2.5 * day_factor if day == 1 else 1.2 * day_factor)
        uv = max(0.0, p["uv"] * max(0.0, math.cos((h - 13) / 12.0 * math.pi))) if day == 1 else 0.0
        precip_base = {"rain": 85, "storm": 92, "snow": 78, "fog": 22, "clear": 5,
                       "hot": 4, "windy": 10, "night": 6}[scene]
        prob = max(0, min(100, int(precip_base + 10 * math.sin(i / 3.0))))
        hourly_out.append({
            "time": t.strftime("%Y-%m-%dT%H:%M"), "label": t.strftime("%H"),
            "temp": round(temp, 1), "precip_prob": prob, "code": code, "is_day": day,
            "uv": round(uv, 1),
            "visibility_km": round(p["vis"] / 1000.0, 1),
        })

    # Fake sun times for the arc. The preview forces is_day, but the arc runs on
    # the real clock — so at 05:40 a "clear day" preview showed a MOON on the arc.
    # Use the classic 06:41 / 18:52 when they agree with the forced flag; when
    # they don't, shift them so the arc matches the scene being previewed.
    sr0 = now.replace(hour=6, minute=41, second=0, microsecond=0)
    ss0 = now.replace(hour=18, minute=52, second=0, microsecond=0)
    real_day = sr0 <= now <= ss0
    if (day == 1) != real_day:
        if day == 1:
            sr0, ss0 = now - timedelta(hours=5), now + timedelta(hours=7)
        else:
            ss0 = now - timedelta(hours=2)
            sr0 = ss0 - timedelta(hours=12)
            # tomorrow's sunrise (daily[1]) = sr0 + 24 h = ss0 + 12 h  → still ahead

    daily_codes = {"clear": [0, 1, 2, 0, 3, 1, 0], "rain": [63, 61, 80, 3, 65, 51, 2],
                   "snow": [73, 75, 71, 3, 77, 73, 2], "storm": [95, 96, 63, 3, 95, 61, 2],
                   "fog": [45, 3, 45, 48, 2, 3, 1], "hot": [0, 0, 1, 0, 2, 0, 1],
                   "windy": [1, 2, 1, 3, 1, 0, 2], "night": [1, 0, 2, 1, 3, 0, 1]}[scene]
    daily_out = []
    for i in range(7):
        d = now + timedelta(days=i)
        c = daily_codes[i]
        daily_out.append({
            "date": d.strftime("%Y-%m-%d"), "label": d.strftime("%a %d"), "is_today": i == 0,
            "code": c,
            "t_max": round(p["temp"] + 3 - i * 0.3, 1), "t_min": round(p["temp"] - 4 - i * 0.2, 1),
            "precip_prob": hourly_out[i * 3]["precip_prob"],
            "sunrise": (sr0 + timedelta(days=i)).strftime("%Y-%m-%dT%H:%M"),
            "sunset": (ss0 + timedelta(days=i)).strftime("%Y-%m-%dT%H:%M"),
            "uv_max": round(p["uv"] + 0.5, 1),
        })

    moon = moon_phase(now, lat=0.0, lon=0.0)
    cond = CONDITIONS.get(code, "Unknown")
    wind_unit = "km/h"  # preview data is always metric

    fake = {
        "schema": SCHEMA, "preview": True, "preview_scene": scene,
        "stale": bool(stale),
        "fetched_at": int(now.timestamp()) - (7200 if stale else 0),
        "fetched_at_iso": (now - timedelta(hours=2 if stale else 0)).strftime("%Y-%m-%dT%H:%M:%S"),
        "source": "preview",
        "location": {"lat": 0.0, "lon": 0.0, "city": p["city"], "source": "preview"},
        "units": {"temperature": "celsius", "temperature_symbol": "°C", "wind": wind_unit},
        "current": {
            "temperature": float(p["temp"]), "feels_like": float(p["feel"]),
            "humidity": p["hum"], "pressure": 1014.0,
            "wind_speed": float(p["wind"]), "wind_kmh": float(p["wind"]),
            "wind_gusts": float(p["gust"]),
            "wind_direction": 225.0, "wind_dir_text": "SW",
            "uv_index": float(p["uv"]), "visibility_m": float(p["vis"]),
            "cloud_cover": 90 if scene in ("rain", "storm", "snow", "fog") else (30 if scene == "windy" else 10),
            "is_day": day, "code": code, "precipitation": 0.6 if scene in ("rain", "storm") else 0.0,
            "time": now.strftime("%Y-%m-%dT%H:%M"),
        },
        "today": {
            "sunrise": daily_out[0]["sunrise"], "sunset": daily_out[0]["sunset"],
            "uv_max": round(p["uv"] + 0.5, 1),
            "precip_prob_max": max(h["precip_prob"] for h in hourly_out),
            "temp_max": daily_out[0]["t_max"], "temp_min": daily_out[0]["t_min"],
            "moon_phase": moon["phase"], "moon_name": moon["name"],
            "moon_illum": moon["illum"], "moon_tilt": moon["tilt"],
            "moon_age": moon["age"], "moon_distance_km": moon["distance_km"],
            "is_supermoon": moon["is_supermoon"],
        },
        "hourly": hourly_out, "daily": daily_out,
        "air": {"available": True, "eu_aqi": p["air"], "us_aqi": round(p["air"] * 1.4),
                "pm2_5": round(p["air"] * 0.28, 1), "pm10": round(p["air"] * 0.52, 1),
                "o3": round(p["air"] * 1.3, 1), "no2": round(p["air"] * 0.4, 1),
                "updated": now.strftime("%Y-%m-%dT%H:%M")},
        "waybar": {
            "text": f"{jq_round(p['temp'])}°",
            "tooltip": "\n".join([p["city"], cond, f"Feels like {jq_round(p['feel'])}°",
                                  f"Humidity {p['hum']}%", f"Wind {jq_round(p['wind'])} km/h"]),
            "classes": ["day" if day == 1 else "night", WAYBAR_CLASS.get(code, "cloud")],
        },
    }
    return fake


# --------------------------------------------------------------------------- #
# locking (prevents timer + manual + waybar-fallback fetches from stampeding)
# --------------------------------------------------------------------------- #


class CacheLock:
    def __init__(self, wait_seconds: float = 0.0):
        self.wait = wait_seconds
        self.fd = None

    def __enter__(self):
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        self.fd = open(LOCK_FILE, "w")
        if self.wait <= 0:
            got = False
            try:
                fcntl.flock(self.fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                got = True
            except OSError:
                pass
            if not got:
                self._cleanup()
                raise RuntimeError("another fetch is running")
        else:
            deadline = time.time() + self.wait
            while True:
                try:
                    fcntl.flock(self.fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    return self
                except OSError:
                    if time.time() >= deadline:
                        self._cleanup()
                        raise RuntimeError("timed out waiting for fetch lock")
                    time.sleep(0.25)
        return self

    def _cleanup(self):
        if self.fd:
            try:
                self.fd.close()
            except OSError:
                pass
            self.fd = None

    def __exit__(self, *exc):
        try:
            if self.fd:
                fcntl.flock(self.fd, fcntl.LOCK_UN)
        except OSError:
            pass
        self._cleanup()
        return False


# --------------------------------------------------------------------------- #
# commands
# --------------------------------------------------------------------------- #


def cmd_fetch(wait_lock=0.0):
    cfg = load_config()
    lat, lon, city, source = resolve_location(cfg)
    if lat is None or lon is None:
        log("could not determine location (config, cache and IP lookup all failed)")
        return 1

    try:
        with CacheLock(wait_lock):
            return _do_fetch(cfg, lat, lon, city, source)
    except RuntimeError as e:
        log(str(e))
        return 0  # another instance is already fetching; not an error


def _do_fetch(cfg, lat, lon, city, source):
    loc = (lat, lon, city, source)
    forecast = fetch_forecast(lat, lon, cfg["units"])
    if not forecast or not forecast.get("current"):
        # network down: keep last JSON, flag it stale
        if CACHE_JSON.is_file():
            try:
                obj = json.loads(CACHE_JSON.read_text(encoding="utf-8"))
                mark_stale(obj)
                atomic_write_json(CACHE_JSON, obj)
                log("network down — kept last data, marked stale")
                return 1
            except (ValueError, OSError):
                pass
        log("forecast fetch failed and no cache to fall back on")
        return 1

    air = fetch_air(lat, lon)
    obj = build_weather_json(forecast, air, loc, cfg["units"])
    atomic_write_json(CACHE_JSON, obj)
    return 0


def backup_cache():
    """Preserve the ORIGINAL data before the first preview of a session.
    Never overwrite an existing backup, so preview → preview → restore
    always comes back to real data."""
    if CACHE_JSON.is_file() and not CACHE_BAK.is_file():
        try:
            CACHE_BAK.write_bytes(CACHE_JSON.read_bytes())
        except OSError:
            pass


def cmd_preview(scene, stale=False):
    if scene not in PREVIEW_SCENES:
        log(f"unknown preview scene '{scene}' (try: {' '.join(PREVIEW_SCENES)})")
        return 2
    try:
        with CacheLock(0):
            backup_cache()
            atomic_write_json(CACHE_JSON, build_preview(scene, stale=stale))
        return 0
    except RuntimeError:
        log("another fetch is running — try again in a moment")
        return 1


def cmd_demo_stale():
    try:
        with CacheLock(0):
            backup_cache()
            if CACHE_JSON.is_file():
                try:
                    obj = json.loads(CACHE_JSON.read_text(encoding="utf-8"))
                    obj["stale"] = True
                    obj["preview"] = True      # marks it as a demo → nothing self-heals it
                    obj["preview_scene"] = "stale-demo"
                    obj["fetched_at"] = int(time.time()) - 7200
                    obj["fetched_at_iso"] = (datetime.now() - timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:%S")
                    atomic_write_json(CACHE_JSON, obj)
                    return 0
                except (ValueError, OSError):
                    pass
            atomic_write_json(CACHE_JSON, build_preview("rain", stale=True))
            return 0
    except RuntimeError:
        log("another fetch is running — try again in a moment")
        return 1


def cmd_restore():
    if CACHE_BAK.is_file():
        try:
            with CacheLock(0):
                os.replace(str(CACHE_BAK), str(CACHE_JSON))
        except RuntimeError:
            log("another fetch is running — try again in a moment")
            return 1
        print("restored pre-preview data")
        return 0
    print("nothing to restore")
    return 1


def cmd_status():
    if not CACHE_JSON.is_file():
        print("cache: MISSING (run: teyvat-forecast fetch)")
        return 1
    try:
        obj = json.loads(CACHE_JSON.read_text(encoding="utf-8"))
    except ValueError:
        print("cache: MALFORMED JSON")
        return 1
    age = int(time.time()) - int(obj.get("fetched_at") or 0)
    preview = " [PREVIEW:" + str(obj.get("preview_scene")) + "]" if obj.get("preview") else ""
    stale = " STALE" if obj.get("stale") else ""
    city = (obj.get("location") or {}).get("city", "?")
    cur = obj.get("current") or {}
    air = obj.get("air") or {}
    air_txt = f"aqi {air.get('eu_aqi')}" if air.get("available") else "unavailable"
    print(f"cache: OK{preview}{stale}")
    print(f"  city:       {city} (via {(obj.get('location') or {}).get('source', '?')})")
    print(f"  now:        {cur.get('temperature')}°  code {cur.get('code')}  "
          f"wind {cur.get('wind_kmh')} km/h  air: {air_txt}")
    print(f"  fetched:    {age // 60} min ago ({obj.get('fetched_at_iso')})")
    print(f"  file:       {CACHE_JSON}")
    return 0


def cmd_search(query):
    """City lookup for the popup's search box. Prints ONE JSON object:
         {"ok": true,  "results": [{name, admin1, country, lat, lon}, ...]}
         {"ok": false, "error": "network" | "empty-query"}
    Open-Meteo geocoding matches names in any language (Karaj, کرج, Köln...)."""
    query = (query or "").strip()
    if len(query) < 2:
        print(json.dumps({"ok": False, "error": "empty-query"}))
        return 2
    url = GEO_URL + "?" + urllib.parse.urlencode(
        {"name": query, "count": 8, "language": "en", "format": "json"})
    data = curl_json(url)
    if data is None:
        print(json.dumps({"ok": False, "error": "network"}))
        return 1
    out, seen = [], set()
    for r in (data.get("results") or []):
        try:
            lat, lon = float(r["latitude"]), float(r["longitude"])
        except (KeyError, TypeError, ValueError):
            continue
        name = str(r.get("name") or "").strip()
        if not name:
            continue
        key = (name.lower(), str(r.get("admin1") or ""), round(lat, 1), round(lon, 1))
        if key in seen:
            continue
        seen.add(key)
        out.append({"name": name, "admin1": str(r.get("admin1") or ""),
                    "country": str(r.get("country") or r.get("country_code") or ""),
                    "lat": round(lat, 4), "lon": round(lon, 4)})
    print(json.dumps({"ok": True, "results": out}, ensure_ascii=False))
    return 0


def save_location(lat, lon, city):
    """Write city/lat/lon into config.json, keeping every other key.
    config.json has the highest priority in resolve_location(), so this
    overrides the legacy weather.conf / location caches."""
    data = {}
    if CONF_FILE.is_file():
        try:
            loaded = json.loads(CONF_FILE.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                data = loaded
        except (ValueError, OSError):
            pass
    data["city"] = city
    data["lat"] = round(float(lat), 4)
    data["lon"] = round(float(lon), 4)
    CONF_DIR.mkdir(parents=True, exist_ok=True)
    tmp = CONF_FILE.with_name(CONF_FILE.name + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(str(tmp), str(CONF_FILE))


def cmd_set_city(args):
    if len(args) < 3:
        log("usage: set-city <lat> <lon> <name>")
        return 2
    try:
        lat, lon = float(args[0]), float(args[1])
    except ValueError:
        log("set-city: lat/lon must be numbers")
        return 2
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        log("set-city: coordinates out of range")
        return 2
    city = " ".join(args[2:]).strip()
    save_location(lat, lon, city)
    log(f"city set to {city} ({lat}, {lon})")
    return cmd_fetch(wait_lock=8.0)


def cmd_locate():
    got = ip_locate()
    if not got:
        log("IP geolocation failed")
        return 1
    save_location(got[0], got[1], got[2])
    log(f"city set from IP: {got[2]} ({got[0]}, {got[1]})")
    return cmd_fetch(wait_lock=8.0)


USAGE = """teyvat-fetch — Teyvat Forecast data layer

usage:
  teyvat-fetch fetch [--wait-lock SECONDS]   fetch real data (default)
  teyvat-fetch preview <scene> [--stale]     write fake data
       scenes: clear rain snow storm fog hot windy night
  teyvat-fetch demo-stale                    mark current data stale
  teyvat-fetch restore                       undo preview, restore backup
  teyvat-fetch status                        human-readable cache state
  teyvat-fetch search <query>                find cities (JSON on stdout)
  teyvat-fetch set-city <lat> <lon> <name>   choose the city, then refetch
  teyvat-fetch locate                        choose the city by IP, then refetch

environment overrides: TEYVAT_CONFIG, TEYVAT_CACHE, TEYVAT_LEGACY_CONF
"""


def main(argv):
    if not argv or argv[0] in ("-h", "--help", "help"):
        print(USAGE, end="")
        return 0
    cmd = argv[0]

    if cmd == "fetch":
        wait = 0.0
        if "--wait-lock" in argv:
            i = argv.index("--wait-lock")
            try:
                wait = float(argv[i + 1])
            except (IndexError, ValueError):
                pass
        return cmd_fetch(wait)

    if cmd == "preview":
        scene = argv[1] if len(argv) > 1 else ""
        stale = "--stale" in argv
        return cmd_preview(scene, stale)

    if cmd == "demo-stale":
        return cmd_demo_stale()

    if cmd == "restore":
        return cmd_restore()

    if cmd == "status":
        return cmd_status()

    if cmd == "search":
        return cmd_search(" ".join(argv[1:]))

    if cmd == "set-city":
        return cmd_set_city(argv[1:])

    if cmd == "locate":
        return cmd_locate()

    log(f"unknown command '{cmd}'")
    print(USAGE, end="", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
