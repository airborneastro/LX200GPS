# telescope.py
#
# Thread-safe telescope state model.
#

from __future__ import annotations

from dataclasses import dataclass, field
from threading import RLock
from typing import Dict
from enum import Enum
import time
from coordinates import calculate_lst

# ---------------------------------------------------------------------------
# Slew rate definitions
# ---------------------------------------------------------------------------

GUIDE_RATE = 0.02      # deg/sec
CENTER_RATE = 0.20     # deg/sec
FIND_RATE = 2.00       # deg/sec
MAX_RATE = 8.00        # deg/sec


# ---------------------------------------------------------------------------
# Mount state machine
# ---------------------------------------------------------------------------

class MountState(Enum):
    NORMAL = 0
    SLEWING = 1
    PARKED = 2
    BOOTING = 3

# ---------------------------------------------------------------------------
# Tracking modes
# ---------------------------------------------------------------------------

class TrackingMode(Enum):
    SIDEREAL = 0
    LUNAR = 1
    SOLAR = 2


# ---------------------------------------------------------------------------
# Telescope state
# ---------------------------------------------------------------------------

@dataclass
class TelescopeState:
    # --------------------------------------------------------------------
    # boot wait
    #---------------------------------------------------------------------
    
    boot_complete_time: float = 0.0
    boot_duration_sec: float = 30.0

    # ------------------------------------------------------------------
    # Current position
    # ------------------------------------------------------------------

    current_ra_hours: float = 5.5880556
    current_dec_deg: float = 22.014444

    pending_park: bool = False
    # ------------------------------------------------------------------
    # Target position
    # ------------------------------------------------------------------

    target_ra_hours: float = 5.5880556
    target_dec_deg: float = 22.014444
    local_sidereal_hours: float = 0.0
    # ------------------------------------------------------------------
    # Mount state
    # ------------------------------------------------------------------

    state_mode: MountState = MountState.NORMAL

    tracking: bool = True
    slewing: bool = False
    tracking_mode: TrackingMode = TrackingMode.SIDEREAL

    # ------------------------------------------------------------------
    # Park position (HA/DEC model ready)
    # preset to South, Celestial equator at 51deg latitude
    # ------------------------------------------------------------------
    
    park_ha_hours: float = 0.0 
    park_dec_deg: float = 0.0
    # NEW: park finalize handshake flag
    _park_finalize_pending: bool = False
    _park_finalize_time: float = 0.0
    # ------------------------------------------------------------------
    # Manual motion
    # ------------------------------------------------------------------

    move_north: bool = False
    move_south: bool = False
    move_east: bool = False
    move_west: bool = False

    # ------------------------------------------------------------------
    # Slew configuration
    # ------------------------------------------------------------------

    selected_rate_name: str = "MAX"
    selected_rate_deg_sec: float = MAX_RATE

    slew_velocity_deg_sec: float = 0.0
    max_slew_rate_deg_sec: float = MAX_RATE
    slew_acceleration_deg_sec2: float = 4.0

    # ------------------------------------------------------------------
    # Site information
    # ------------------------------------------------------------------

    latitude_deg: float = 50.625
    longitude_deg: float = -7.233

    # ------------------------------------------------------------------
    # Firmware
    # ------------------------------------------------------------------

    product_name: str = "LX200GPS"
    firmware_version: str = "4.2g"
    firmware_date: str = "Jan 01 2024"
    firmware_time: str = "00:00:00"

    # ------------------------------------------------------------------
    # Thread lock
    # ------------------------------------------------------------------

    lock: RLock = field(default_factory=RLock)

    # ------------------------------------------------------------------
    # State helpers
    # ------------------------------------------------------------------
    def __post_init__(self):

        self.local_sidereal_hours = calculate_lst(
            abs(self.longitude_deg)
        )
        # Startup position on meridian + equator (like park position)
        self.current_ra_hours = self.local_sidereal_hours
        self.target_ra_hours = self.local_sidereal_hours
        self.current_dec_deg = 0.0
        self.target_dec_deg = 0.0

    # PARK -------------------------------------------------------------

    def park(self):
        with self.lock:

            self.target_ra_hours = self.ha_to_ra(self.park_ha_hours)
            self.target_dec_deg = self.park_dec_deg

            self.state_mode = MountState.SLEWING
            self.slewing = True
            self.tracking = False

            self.pending_park = True   # IMPORTANT
    
      
    def unpark(self) -> None:
        with self.lock:
            self.state_mode = MountState.NORMAL
            self.tracking = True

    def is_parked(self) -> bool:
        with self.lock:
            if self.state_mode == MountState.BOOTING:
                return True
            return self.state_mode == MountState.PARKED

    # ------------------------------------------------------------------
    # Slew control
    # ------------------------------------------------------------------

    def start_slew(self) -> None:
        with self.lock:
            self.state_mode = MountState.SLEWING
            self.slewing = True
            self.tracking = False
            self.slew_velocity_deg_sec = 0.0

    def stop_slew(self) -> None:
        with self.lock:
            self.slewing = False
            self.tracking = True
            self.slew_velocity_deg_sec = 0.0

            if self.state_mode == MountState.SLEWING:
                self.state_mode = MountState.NORMAL

    def abort(self) -> None:
        with self.lock:
            self.stop_slew()

            self.move_north = False
            self.move_south = False
            self.move_east = False
            self.move_west = False

    # ------------------------------------------------------------------
    # Sync
    # ------------------------------------------------------------------

    def sync(self) -> None:
        with self.lock:
            self.current_ra_hours = self.target_ra_hours
            self.current_dec_deg = self.target_dec_deg

    # ------------------------------------------------------------------
    # Target updates
    # ------------------------------------------------------------------

    def set_target_ra(self, hours: float) -> None:
        with self.lock:
            self.target_ra_hours = hours

    def set_target_dec(self, deg: float) -> None:
        with self.lock:
            self.target_dec_deg = deg

    # ------------------------------------------------------------------
    # Manual motion
    # ------------------------------------------------------------------

    def start_north(self) -> None:
        with self.lock:
            self.move_north = True

    def stop_north(self) -> None:
        with self.lock:
            self.move_north = False

    def start_south(self) -> None:
        with self.lock:
            self.move_south = True

    def stop_south(self) -> None:
        with self.lock:
            self.move_south = False

    def start_east(self) -> None:
        with self.lock:
            self.move_east = True

    def stop_east(self) -> None:
        with self.lock:
            self.move_east = False

    def start_west(self) -> None:
        with self.lock:
            self.move_west = True

    def stop_west(self) -> None:
        with self.lock:
            self.move_west = False

    # ------------------------------------------------------------------
    # Slew rate selection
    # ------------------------------------------------------------------

    def set_guide_rate(self) -> None:
        with self.lock:
            self.selected_rate_name = "GUIDE"
            self.selected_rate_deg_sec = GUIDE_RATE

    def set_center_rate(self) -> None:
        with self.lock:
            self.selected_rate_name = "CENTER"
            self.selected_rate_deg_sec = CENTER_RATE

    def set_find_rate(self) -> None:
        with self.lock:
            self.selected_rate_name = "FIND"
            self.selected_rate_deg_sec = FIND_RATE

    def set_max_rate(self) -> None:
        with self.lock:
            self.selected_rate_name = "MAX"
            self.selected_rate_deg_sec = MAX_RATE

    # ------------------------------------------------------------------
    # Snapshot
    # ------------------------------------------------------------------

    def snapshot(self) -> Dict:
        with self.lock:
            return {
                "ra": self.current_ra_hours,
                "dec": self.current_dec_deg,
                "target_ra": self.target_ra_hours,
                "target_dec": self.target_dec_deg,
                "tracking": self.tracking,
                "slewing": self.slewing,
                "state": self.state_mode.name,
                "rate_name": self.selected_rate_name,
                "rate_deg_sec": self.selected_rate_deg_sec,
                "move_north": self.move_north,
                "move_south": self.move_south,
                "move_east": self.move_east,
                "move_west": self.move_west,
            }

    # ------------------------------------------------------------------
    # Firmware info
    # ------------------------------------------------------------------

    def get_product_name(self) -> str:
        return self.product_name

    def get_firmware_version(self) -> str:
        return self.firmware_version

    def get_firmware_date(self) -> str:
        return self.firmware_date

    def get_firmware_time(self) -> str:
        return self.firmware_time

    # ------------------------------------------------------------------
    # Site info
    # ------------------------------------------------------------------

    def get_latitude(self) -> float:
        return self.latitude_deg

    def get_longitude(self) -> float:
        return self.longitude_deg
        
    def set_park_position(self, ha_hours: float, dec_deg: float):
        with self.lock:
            self.park_ha_hours = ha_hours
            self.park_dec_deg = dec_deg
            
    def at_target(self, tolerance_deg: float = 0.01) -> bool:
        from coordinates import angular_separation

        return angular_separation(
            self.current_ra_hours,
            self.current_dec_deg,
            self.target_ra_hours,
            self.target_dec_deg
        ) <= tolerance_deg
     # ------------------------------------------------------------------
    # HA/RA conversions
    # ------------------------------------------------------------------

    def ha_to_ra(self, ha_hours: float) -> float:
        """
        Convert Hour Angle to Right Ascension.
        RA = LST - HA
        """
        ra = self.local_sidereal_hours - ha_hours
        return ra % 24.0


    def ra_to_ha(self, ra_hours: float) -> float:
        """
        Convert Right Ascension to Hour Angle.
        HA = LST - RA
        """
        ha = self.local_sidereal_hours - ra_hours

        # normalize to [-12, +12]
        while ha > 12:
            ha -= 24

        while ha < -12:
            ha += 24

        return ha
        
        # ------------------------------------------------------------------
        # Boot handling
        # ------------------------------------------------------------------

    def start_boot(self):
        with self.lock:
            self.state_mode = MountState.BOOTING

            self.boot_complete_time = (
                time.monotonic() + self.boot_duration_sec
            )

            self.pending_park = False
            self.slewing = False
            self.tracking = False


    def update_boot_state(self):
        with self.lock:

            if self.state_mode != MountState.BOOTING:
                return

            if time.monotonic() >= self.boot_complete_time:

                self.unpark()
                self.pending_park = False
                self.slewing = False