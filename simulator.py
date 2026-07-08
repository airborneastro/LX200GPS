# simulator.py
#
# Telescope motion simulation engine.
#

from __future__ import annotations

import math
import threading
import time

from telescope import (
    TelescopeState, 
    MountState,
    TrackingMode,
)

from coordinates import (
    angular_separation,
    move_ra_towards,
    move_towards,
    shortest_ra_delta_deg,
    normalize_ra_hours,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SIM_RATE_HZ = 10.0
SIM_DT = 1.0 / SIM_RATE_HZ

# ---------------------------------------------------------------------------
# Tracking rates
# ---------------------------------------------------------------------------

SIDEREAL_DAY_SEC = 86164.0905
SOLAR_DAY_SEC = 86400.0

# Normal star tracking
SIDEREAL_RA_HOURS_PER_SEC = 24.0 / SIDEREAL_DAY_SEC

# Solar tracking
SOLAR_RA_HOURS_PER_SEC = 24.0 / SOLAR_DAY_SEC

# Approximate lunar tracking
LUNAR_RATE_FACTOR = 0.965

LUNAR_RA_HOURS_PER_SEC = (
    SIDEREAL_RA_HOURS_PER_SEC * LUNAR_RATE_FACTOR
)


# Slew considered complete
SLEW_TOLERANCE_DEG = 30.0 / 3600.0  # 30 arcsec

# Manual motion speed
MANUAL_RATE_DEG_SEC = 1.0


class TelescopeSimulator(threading.Thread):

    def __init__(self, state: TelescopeState):

        super().__init__(daemon=True)

        self.state = state

        self.running = True

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------

    def run(self):

        last = time.monotonic()

        while self.running:

            now = time.monotonic()

            dt = now - last
            last = now

            try:
                self.update(dt)

            except Exception as ex:
                print(f"SIM ERROR: {ex}")

            time.sleep(SIM_DT)

    # ------------------------------------------------------------------
    # Update
    # ------------------------------------------------------------------

    def update(self, dt: float):

        with self.state.lock:
            self.update_lst(dt)
            if self.state.is_parked():
                self.update_park_finalize()
                return

            if self.state.slewing:
                self.update_slew(dt)

            else:

                if self.state.tracking:
                    self.update_tracking(dt)

                self.update_manual_motion(dt)
              # normal motion update happens above this
        self.update_park_finalize()


    # ------------------------------------------------------------------
    # Tracking
    # ------------------------------------------------------------------

    def get_tracking_rate(self) -> float:

        mode = self.state.tracking_mode

        if mode == TrackingMode.SIDEREAL:
            return SIDEREAL_RA_HOURS_PER_SEC

        if mode == TrackingMode.LUNAR:
            return LUNAR_RA_HOURS_PER_SEC

        if mode == TrackingMode.SOLAR:
            return SOLAR_RA_HOURS_PER_SEC

        return 0.0
    
    def update_tracking(self, dt: float):

    
        # Lunar tracking adds slow eastward RA drift
        if self.state.tracking_mode == TrackingMode.LUNAR:

            lunar_offset = (
                SIDEREAL_RA_HOURS_PER_SEC
                - LUNAR_RA_HOURS_PER_SEC
            ) * dt

            self.state.current_ra_hours = (
                self.state.current_ra_hours
                + lunar_offset
            ) % 24.0

        # Solar tracking adds tiny solar correction
        elif self.state.tracking_mode == TrackingMode.SOLAR:

            solar_offset = (
                SIDEREAL_RA_HOURS_PER_SEC
                - SOLAR_RA_HOURS_PER_SEC
            ) * dt

            self.state.current_ra_hours = (
                self.state.current_ra_hours
                + solar_offset
            ) % 24.0

    def update_lst(self, dt):

        self.state.local_sidereal_hours = (
            self.state.local_sidereal_hours
            + SIDEREAL_RA_HOURS_PER_SEC * dt
        ) % 24.0




        
    # ------------------------------------------------------------------
    # Slewing
    # ------------------------------------------------------------------

    def update_slew(self, dt: float):

        sep = angular_separation(
            self.state.current_ra_hours,
            self.state.current_dec_deg,
            self.state.target_ra_hours,
            self.state.target_dec_deg
        )

        # ----------------------------
        # Reached target
        # ----------------------------

        if sep <= SLEW_TOLERANCE_DEG:

            self.state.current_ra_hours = (
                self.state.target_ra_hours
            )

            self.state.current_dec_deg = (
                self.state.target_dec_deg
            )

            self.state.slewing = False
            self.state.slew_velocity_deg_sec = 0.0


            # if this was a park move, finalize PARKED state
            if self.state.pending_park:
                # enter a "settling" phase instead of PARKED immediately
                self.state.state_mode = MountState.NORMAL   # still responsive
                self.state.tracking = False                 # stop tracking motion
                self.state._park_finalize_pending = True    # NEW FLAG
                self.state._park_finalize_time = time.monotonic() + 2.0  # 20000ms buffer
            else:
                self.state.state_mode = MountState.NORMAL
                self.state.tracking = True

            return

        # ----------------------------
        # Acceleration model   
        # ----------------------------

        accel = self.state.slew_acceleration_deg_sec2

        vmax = self.state.max_slew_rate_deg_sec

        v = self.state.slew_velocity_deg_sec

        # accelerate

        v += accel * dt

        if v > vmax:
            v = vmax

        # stopping distance

        stopping_distance = (v * v) / (2.0 * accel)

        # decelerate if required

        if stopping_distance >= sep:

            v -= accel * dt

            if v < 0.1:
                v = 0.1

        self.state.slew_velocity_deg_sec = v

        step = v * dt

        # ----------------------------
        # Move RA
        # ----------------------------

        self.state.current_ra_hours = move_ra_towards(
            self.state.current_ra_hours,
            self.state.target_ra_hours,
            step
        )

        # ----------------------------
        # Move DEC
        # ----------------------------

        self.state.current_dec_deg = move_towards(
            self.state.current_dec_deg,
            self.state.target_dec_deg,
            step
        )

        #------------------------------------------------------
        # Parking finalize
        #-------------------------------------------------------
        
    def update_park_finalize(self):

        with self.state.lock:

            if not self.state._park_finalize_pending:
                return

            if time.monotonic() < self.state._park_finalize_time:
                return

            # finalize park ONLY after last motion update has been visible
            self.state.state_mode = MountState.PARKED
            self.state.pending_park = False
            self.state._park_finalize_pending = False
            self.state.tracking = False
            



    # ------------------------------------------------------------------
    # Manual motion
    # ------------------------------------------------------------------

    def update_manual_motion(self, dt: float):

        step = MANUAL_RATE_DEG_SEC * dt

        # ---------------------------------
        # DEC motion
        # ---------------------------------

        if self.state.move_north:

            self.state.current_dec_deg += step

        if self.state.move_south:

            self.state.current_dec_deg -= step

        # ---------------------------------
        # RA motion
        # ---------------------------------

        ra_step_hours = step / 15.0

        if self.state.move_east:

            self.state.current_ra_hours += ra_step_hours

        if self.state.move_west:

            self.state.current_ra_hours -= ra_step_hours

        self.state.current_ra_hours = normalize_ra_hours(
            self.state.current_ra_hours
        )

        # clamp DEC

        if self.state.current_dec_deg > 90.0:
            self.state.current_dec_deg = 90.0

        if self.state.current_dec_deg < -90.0:
            self.state.current_dec_deg = -90.0

    # ------------------------------------------------------------------
    # Shutdown
    # ------------------------------------------------------------------

    def stop(self):

        self.running = False

