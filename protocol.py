# protocol.py
#
# LX200GPS protocol implementation (BYTES VERSION)
#

from __future__ import annotations

from datetime import datetime, timezone
import time

from telescope import TelescopeState, MountState, TrackingMode

from coordinates import (
    parse_ra,
    parse_dec,
    format_ra,
    format_dec,
)


class LX200Protocol:

    def __init__(self, state: TelescopeState):
        self.state = state

    # ------------------------------------------------------------------
    # Main dispatcher
    # ------------------------------------------------------------------

    def process(self, command: bytes) -> bytes:
#        print("PROCESS ENTRY:", repr(command))
        print(
#            f"CMD={repr(command)} "
            f"STATE={self.state.state_mode} "
            f"SLEWING={self.state.slewing} "
            f"TRACKING={self.state.tracking} "
            f"TRACKING_MODE={self.state.tracking_mode} "
            f"PARK_PENDING={self.state.pending_park} "
            f"PARKED={self.state.is_parked()}"
        )

        try:
            # ----------------------------------------------------------
            # BOOT / PARK STATE
            # ----------------------------------------------------------
            
             # ----------------------------------------------------------
            # ALWAYS UPDATE BOOT STATE FIRST
            # ----------------------------------------------------------
            self.state.update_boot_state()

            # ==========================================================
            # HARD GLOBAL GATE: BOOTING OR PARKED
            # ==========================================================
            if (
                self.state.state_mode == MountState.BOOTING
                or self.state.is_parked()
            ):

#                print(f"STATE BLOCKED: {repr(command)}")

                # ONLY allow boot trigger (optional rule)
                if command == b":I#":
                    print("BOOT TRIGGER :I# RECEIVED")
                    self.state.start_boot()
                    return b""

                # EVERYTHING ELSE IS IGNORED (INCLUDING ACK)
                return None
            

            # ----------------------------------------------------------
            # UNPARK / INIT
            # ----------------------------------------------------------

#            if command == b":I#":
#                with self.state.lock:
#                    self.state.unpark()
#                    self.state.pending_park = False
#                    self.state.slewing = False
#                    self.state.tracking = True
#                return b"1"

            # ----------------------------------------------------------
            # ACK
            # ----------------------------------------------------------

            if command == b"\x06":
                return b"A"

            # ----------------------------------------------------------
            # POSITION QUERIES
            # ----------------------------------------------------------

            if command == b":GR#":
                return self.get_ra().encode("ascii")

            if command == b":GD#":
                print(
                    f"LST = {format_ra(self.state.local_sidereal_hours)}"
                )
                return self.get_dec().encode("ascii")

            if command == b":Gr#":
                return self.get_target_ra().encode("ascii")

            if command == b":Gd#":
                return self.get_target_dec().encode("ascii")

            # ----------------------------------------------------------
            # SET TARGET COORDINATES
            # ----------------------------------------------------------

            if command.startswith(b":Sr"):
                value = command[3:-1]  # includes trailing #
                return self.set_target_ra(value).encode("ascii")

            if command.startswith(b":Sd"):
                value = command[3:-1]
                return self.set_target_dec(value).encode("ascii")

            # ----------------------------------------------------------
            # SLEW COMMANDS (start)
            # ----------------------------------------------------------

            if command == b":MS#":
                return self.start_slew().encode("ascii")

            if command == b":CM#":
                return self.sync().encode("ascii")

            if command == b":Q#":
                return self.abort().encode("ascii")

            if command == b":D#":
                return self.slew_status().encode("ascii")

            # ----------------------------------------------------------
            # MOTION CONTROL
            # ----------------------------------------------------------

            if command == b":Mn#":
                self.state.start_north()
                return b""

            if command == b":Ms#":
                self.state.start_south()
                return b""

            if command == b":Me#":
                self.state.start_east()
                return b""

            if command == b":Mw#":
                self.state.start_west()
                return b"":S

            if command == b":Qn#":
                self.state.stop_north()
                return b""

            if command == b":Qs#":
                self.state.stop_south()
                return b""

            if command == b":Qe#":
                self.state.stop_east()
                return b""

            if command == b":Qw#":
                self.state.stop_west()
                return b""

            # ----------------------------------------------------------
            # SLEW RATE
            # ----------------------------------------------------------

            if command == b":RG#":
                self.state.set_guide_rate()
                return b""

            if command == b":RC#":
                self.state.set_center_rate()
                return b""

            if command == b":RM#":
                self.state.set_find_rate()
                return b""

            if command == b":RS#":
                self.state.set_max_rate()
                return b""

            # ----------------------------------------------------------
            # TIME / DATE
            # ----------------------------------------------------------

            if command == b":GL#":
                return self.get_local_time().encode("ascii")

            if command == b":GC#":
                return self.get_local_date().encode("ascii")

            if command == b":Ga#":
                return self.get_utc_time().encode("ascii")

            if command == b":Gc#":
                return b"24#"
                        # ----------------------------------------------------------
            # SITE
            # ----------------------------------------------------------

            if command == b":Gt#":
                return self.get_latitude().encode("ascii")

            if command == b":Gg#":
                return self.get_longitude().encode("ascii")

            if command == b":GM#":
                return b"LX200GPS Simulator#"

            if command == b":GG#":
                utc_offset = time.localtime().tm_gmtoff/7200
                return ('{:+05.1f}#'.format(utc_offset) ).encode("ascii")
#                return b"+02.0#"

            if command.startswith(b":Sg"):
                value = command[3:-1]  # includes #
                return self.set_longitude(value).encode("ascii")

            if command.startswith(b":SG"):
                value = command[3:-1]  # includes #
                return b"1"
            
            if command.startswith(b":St"):
                value = command[3:-1]
                return self.set_latitude(value).encode("ascii")
                
            if command.startswith(b":SC"):
                value = command[3:-1]
                return b"1Updating Planetary Data#"
                
            if command.startswith(b":SL"):
                return b"1"

            # ----------------------------------------------------------
            # AUX / HOME / INIT FLAGS
            # ----------------------------------------------------------

            if command.startswith(b":hI"):
                return b"1"

            if command == b":I#":
                with self.state.lock:
                    self.state.state_mode = MountState.NORMAL
                    self.state.tracking = True
                    self.state.slewing = False
                    self.state.pending_park = False
                return b"1"

            # ----------------------------------------------------------
            # FIRMWARE
            # ----------------------------------------------------------

            if command == b":GVP#":
                return (self.state.product_name + "#").encode("ascii")

            if (command == b":GVN#") or (command == b":GVF#"):
                return (self.state.firmware_version + "#").encode("ascii")

            if command == b":GVD#":
                return (self.state.firmware_date + "#").encode("ascii")

            if command == b":GVT#":
                return (self.state.firmware_time + "#").encode("ascii")

            # ----------------------------------------------------------
            # TRACKING FREQUENCY
            # ----------------------------------------------------------

            if command == b":GT#":
                return b"60.1#"

            # ----------------------------------------------------------
            # TRACKING MODE
            # ----------------------------------------------------------

            if command == b":TL#":
                self.state.tracking_mode = TrackingMode.LUNAR
                return b"1"

            if command == b":TQ#":
                self.state.tracking_mode = TrackingMode.SIDEREAL
                return b"1"

            if command == b":TS#":
                self.state.tracking_mode = TrackingMode.SOLAR
                return b"1"

            # ----------------------------------------------------------
            # PARK / UNPARK
            # ----------------------------------------------------------

            if command == b":hP#":

                self.state.set_target_ra(
                    self.state.ha_to_ra(self.state.park_ha_hours)
                )

                print(
                    f"LST = {format_ra(self.state.local_sidereal_hours)}"
                )
                print(
                    f"PARK_RA = {format_ra(self.state.ha_to_ra(self.state.park_ha_hours))}"
                )

                self.state.set_target_dec(self.state.park_dec_deg)

                self.state.start_slew()
                self.state.state_mode = MountState.SLEWING
                self.state.pending_park = True

                return b""

            if command == b":hS#":
                self.state.set_park_position(
                    self.state.current_ra_hours,
                    self.state.current_dec_deg
                )
                return b""

            # ----------------------------------------------------------
            # UNKNOWN COMMAND
            # ----------------------------------------------------------

            print(f"UNKNOWN COMMAND: {repr(command)}")
            return b""

        except Exception as ex:
            print(
                f"PROTOCOL ERROR command={repr(command)} error={ex}"
            )
            return b""
            # ------------------------------------------------------------------
    # POSITION HELPERS
    # ------------------------------------------------------------------

    def get_ra(self) -> str:
        with self.state.lock:
            return format_ra(self.state.current_ra_hours) + "#"

    def get_dec(self) -> str:
        with self.state.lock:
            return format_dec(self.state.current_dec_deg) + "#"

    def get_target_ra(self) -> str:
        with self.state.lock:
            return format_ra(self.state.target_ra_hours) + "#"

    def get_target_dec(self) -> str:
        with self.state.lock:
            return format_dec(self.state.target_dec_deg) + "#"

    # ------------------------------------------------------------------
    # SET TARGET COORDINATES
    # ------------------------------------------------------------------

    def set_target_ra(self, value: bytes) -> str:
        try:
            ra = parse_ra(value.decode("ascii", errors="ignore"))
            self.state.set_target_ra(ra)
            return "1"
        except Exception:
            return "0"

    def set_target_dec(self, value: bytes) -> str:
        try:
            dec = parse_dec(value.decode("ascii", errors="ignore"))
            self.state.set_target_dec(dec)
            return "1"
        except Exception:
            return "0"

    # ------------------------------------------------------------------
    # SLEW CONTROL
    # ------------------------------------------------------------------

    def start_slew(self) -> str:
        self.state.start_slew()
        return "0"

    def sync(self) -> str:
        self.state.sync()
        return "Coordinates matched.#"

    def abort(self) -> str:
        self.state.abort()
        return ""

    def slew_status(self) -> str:
        with self.state.lock:
            if self.state.slewing:
                return "|#"
            return "#"

    # ------------------------------------------------------------------
    # TIME
    # ------------------------------------------------------------------

    def get_local_time(self) -> str:
        return datetime.now().strftime("%H:%M:%S") + "#"

    def get_local_date(self) -> str:
        return datetime.now().strftime("%m/%d/%y") + "#"

    def get_utc_time(self) -> str:
        return datetime.now(timezone.utc).strftime("%H:%M:%S") + "#"

    # ------------------------------------------------------------------
    # SITE
    # ------------------------------------------------------------------

    def get_latitude(self) -> str:
        lat = self.state.latitude_deg
        sign = "+" if lat >= 0 else "-"
        lat = abs(lat)

        deg = int(lat)
        minutes = int((lat - deg) * 60.0)

        return f"{sign}{deg:02d}*{minutes:02d}#"

    def get_longitude(self) -> str:
        lon = self.state.longitude_deg
        deg = int(lon)
        minutes = int((lon - deg) * 60.0)

        return f"{deg:03d}*{minutes:02d}#"

    def set_longitude(self, value: bytes) -> str:
        try:
            text = value.decode("ascii", errors="ignore")
            deg_str, min_str = text.split("*")
            deg = int(deg_str)
            minutes = int(min_str)
            self.state.longitude_deg = deg + minutes / 60.0
            return "1"
        except Exception:
            return "0"

    def set_latitude(self, value: bytes) -> str:
        try:
            text = value.decode("ascii", errors="ignore")

            sign = 1
            if text.startswith("-"):
                sign = -1
                text = text[1:]

            deg_str, min_str = text.split("*")
            deg = int(deg_str)
            minutes = int(min_str)

            self.state.latitude_deg = sign * (deg + minutes / 60.0)
            return "1"

        except Exception:
            return "0"       