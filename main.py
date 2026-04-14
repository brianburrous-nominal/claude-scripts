"""Simulated aircraft data generator.

Streams live telemetry and log messages to a Nominal dataset every second.
"""

import math
import random
import time
from datetime import datetime

from nominal.core import NominalClient

# ---- Configuration ----
DATASET_RID = "ri.catalog.cerulean-staging.dataset.61aa6048-4ae6-4e4b-8a34-40df8b112fab"
PROFILE_NAME = "default"
LOG_CHANNEL_NAME = "logs"


# ---------------------------------------------------------------------------
# Aircraft simulation
# ---------------------------------------------------------------------------

class AircraftState:
    """Simulates a single-engine aircraft flying a holding pattern."""

    def __init__(self) -> None:
        # Position (starting near Edwards AFB)
        self.latitude = 34.905
        self.longitude = -117.884
        self.altitude_ft = 5_000.0  # feet MSL

        # Attitude & motion
        self.heading_deg = 90.0  # east
        self.airspeed_kts = 120.0  # knots
        self.vertical_speed_fpm = 0.0  # feet per minute
        self.pitch_deg = 0.0
        self.roll_deg = 0.0
        self.yaw_deg = 0.0

        # Engine
        self.engine_rpm = 2_400.0
        self.engine_temp_c = 180.0  # cylinder head temp
        self.oil_pressure_psi = 60.0
        self.oil_temp_c = 95.0
        self.fuel_qty_gal = 48.0
        self.fuel_flow_gph = 9.5

        # Electrical / environment
        self.battery_voltage = 28.0
        self.outside_air_temp_c = -5.0

        # Flight phase tracking
        self._phase = "climb"  # climb -> cruise -> turn -> cruise -> descend -> climb ...
        self._phase_timer = 0
        self._turn_direction = 1  # 1 = right, -1 = left
        self._target_altitude = 15_000.0

    def step(self, dt: float = 1.0) -> dict[str, float]:
        """Advance the simulation by dt seconds and return all channels."""
        self._phase_timer += dt
        self._update_flight_phase(dt)
        self._update_engine(dt)
        self._update_position(dt)
        self._add_sensor_noise()

        return {
            "aircraft.position.latitude_deg": self.latitude,
            "aircraft.position.longitude_deg": self.longitude,
            "aircraft.position.altitude_ft": self.altitude_ft,
            "aircraft.attitude.heading_deg": self.heading_deg % 360,
            "aircraft.attitude.pitch_deg": self.pitch_deg,
            "aircraft.attitude.roll_deg": self.roll_deg,
            "aircraft.attitude.yaw_deg": self.yaw_deg,
            "aircraft.motion.airspeed_kts": self.airspeed_kts,
            "aircraft.motion.vertical_speed_fpm": self.vertical_speed_fpm,
            "aircraft.engine.rpm": self.engine_rpm,
            "aircraft.engine.cylinder_head_temp_c": self.engine_temp_c,
            "aircraft.engine.oil_pressure_psi": self.oil_pressure_psi,
            "aircraft.engine.oil_temp_c": self.oil_temp_c,
            "aircraft.fuel.quantity_gal": self.fuel_qty_gal,
            "aircraft.fuel.flow_gph": self.fuel_flow_gph,
            "aircraft.electrical.battery_voltage": self.battery_voltage,
            "aircraft.environment.outside_air_temp_c": self.outside_air_temp_c,
        }

    # -- private helpers --

    def _update_flight_phase(self, dt: float) -> None:
        if self._phase == "climb":
            self.vertical_speed_fpm = 500.0
            self.pitch_deg = 5.0
            self.roll_deg *= 0.9  # level wings
            self.airspeed_kts = max(100.0, self.airspeed_kts - 0.05 * dt)
            if self.altitude_ft >= self._target_altitude:
                self._phase = "cruise"
                self._phase_timer = 0
        elif self._phase == "cruise":
            self.vertical_speed_fpm *= 0.8  # settle to zero
            self.pitch_deg *= 0.9
            self.roll_deg *= 0.9
            self.airspeed_kts += (150.0 - self.airspeed_kts) * 0.02
            if self._phase_timer > 30:
                self._phase = "turn"
                self._phase_timer = 0
                self._turn_direction = random.choice([-1, 1])
        elif self._phase == "turn":
            target_roll = 25.0 * self._turn_direction
            self.roll_deg += (target_roll - self.roll_deg) * 0.1
            self.heading_deg += self._turn_direction * 3.0 * dt
            self.pitch_deg = 2.0
            self.vertical_speed_fpm = -50.0
            if self._phase_timer > 30:  # ~90 degree turn
                self._phase = "straight"
                self._phase_timer = 0
        elif self._phase == "straight":
            self.roll_deg *= 0.9
            self.pitch_deg *= 0.95
            self.vertical_speed_fpm *= 0.9
            self.airspeed_kts += (150.0 - self.airspeed_kts) * 0.02
            if self._phase_timer > 20:
                if self.altitude_ft > 12_000:
                    self._phase = "descend"
                    self._target_altitude = random.uniform(5_000, 8_000)
                else:
                    self._phase = "climb"
                    self._target_altitude = random.uniform(12_000, 18_000)
                self._phase_timer = 0
        elif self._phase == "descend":
            self.vertical_speed_fpm = -700.0
            self.pitch_deg = -3.0
            self.roll_deg *= 0.9
            self.airspeed_kts += (160.0 - self.airspeed_kts) * 0.02
            if self.altitude_ft <= self._target_altitude:
                self._phase = "cruise"
                self._phase_timer = 0

    def _update_engine(self, dt: float) -> None:
        # RPM responds to pitch/power
        target_rpm = 2400.0 if self._phase in ("climb",) else 2200.0
        self.engine_rpm += (target_rpm - self.engine_rpm) * 0.05
        # Temperatures correlate with RPM
        self.engine_temp_c += (160.0 + self.engine_rpm / 40.0 - self.engine_temp_c) * 0.02
        self.oil_temp_c += (80.0 + self.engine_rpm / 60.0 - self.oil_temp_c) * 0.01
        self.oil_pressure_psi += (55.0 + self.engine_rpm / 200.0 - self.oil_pressure_psi) * 0.03
        # Fuel burn
        self.fuel_flow_gph = 7.0 + (self.engine_rpm - 2000) / 200.0
        self.fuel_qty_gal = max(0.0, self.fuel_qty_gal - self.fuel_flow_gph / 3600.0 * dt)
        # Battery
        self.battery_voltage += (28.0 - self.battery_voltage) * 0.05
        # OAT decreases ~2C per 1000ft
        self.outside_air_temp_c = 15.0 - 2.0 * (self.altitude_ft / 1000.0)

    def _update_position(self, dt: float) -> None:
        self.altitude_ft += self.vertical_speed_fpm / 60.0 * dt
        self.altitude_ft = max(0.0, self.altitude_ft)
        # Horizontal movement (rough lat/lon update)
        heading_rad = math.radians(self.heading_deg)
        speed_deg_per_sec = self.airspeed_kts / 3600.0 / 60.0  # ~1 knot = 1 arcmin
        self.latitude += math.cos(heading_rad) * speed_deg_per_sec * dt
        self.longitude += math.sin(heading_rad) * speed_deg_per_sec * dt / math.cos(math.radians(self.latitude))

    def _add_sensor_noise(self) -> None:
        self.airspeed_kts += random.gauss(0, 0.3)
        self.altitude_ft += random.gauss(0, 2.0)
        self.engine_rpm += random.gauss(0, 5.0)
        self.engine_temp_c += random.gauss(0, 0.5)
        self.oil_pressure_psi += random.gauss(0, 0.2)
        self.oil_temp_c += random.gauss(0, 0.3)
        self.battery_voltage += random.gauss(0, 0.05)
        self.pitch_deg += random.gauss(0, 0.1)
        self.roll_deg += random.gauss(0, 0.2)
        self.yaw_deg = self.heading_deg + random.gauss(0, 0.5)


# ---------------------------------------------------------------------------
# Aircraft-specific log messages
# ---------------------------------------------------------------------------

FLIGHT_LOG_TEMPLATES: dict[str, list[str]] = {
    "INFO": [
        "Autopilot engaged: mode={mode}",
        "Altitude check passed: {alt_ft} ft MSL",
        "Nav waypoint reached: {waypoint}",
        "Fuel state nominal: {fuel_gal} gal remaining",
        "Transponder squawking {squawk}",
        "ATIS received for {airport}",
        "Flaps set to {flap_deg} degrees",
        "Landing gear status: {gear_status}",
    ],
    "DEBUG": [
        "ADC sample: pitot={pitot_hpa} hPa, static={static_hpa} hPa",
        "GPS fix: {lat:.4f}, {lon:.4f} HDOP={hdop}",
        "IMU accel: x={ax:.2f} y={ay:.2f} z={az:.2f} g",
        "EGT probe {probe}: {egt_c} C",
        "Bus voltage: main={main_v:.1f}V aux={aux_v:.1f}V",
    ],
    "WARN": [
        "Airspeed low: {airspeed_kts} kts (min {min_kts} kts)",
        "Engine CHT elevated: {cht_c} C (limit {limit_c} C)",
        "Oil pressure below normal: {oil_psi} psi",
        "Fuel imbalance: L={fuel_l} gal R={fuel_r} gal",
        "Turbulence detected: severity {severity}",
        "TCAS advisory: traffic {dist_nm} nm, {alt_delta} ft",
    ],
    "ERROR": [
        "Engine roughness detected: RPM variance {rpm_var}",
        "Pitot heat failure: icing likely",
        "GPS signal lost: reverting to dead reckoning",
        "Generator offline: battery only",
        "Stall warning activated at {airspeed_kts} kts",
    ],
}

LOG_LEVELS = ["INFO", "DEBUG", "WARN", "ERROR"]
LOG_LEVEL_WEIGHTS = [50, 25, 15, 10]

FLIGHT_PLACEHOLDER_VALUES: dict[str, object] = {
    "mode": lambda: random.choice(["ALT_HOLD", "NAV", "APPROACH", "HEADING"]),
    "alt_ft": lambda: str(random.randint(3000, 18000)),
    "waypoint": lambda: random.choice(["KLAX", "KEDW", "KPMD", "FIXXX", "RNAV1", "VOR_DAG"]),
    "fuel_gal": lambda: f"{random.uniform(10, 48):.1f}",
    "squawk": lambda: str(random.randint(1000, 7777)),
    "airport": lambda: random.choice(["KLAX", "KEDW", "KONT", "KPMD"]),
    "flap_deg": lambda: str(random.choice([0, 10, 20, 30, 40])),
    "gear_status": lambda: random.choice(["UP_AND_LOCKED", "DOWN_AND_LOCKED", "IN_TRANSIT"]),
    "pitot_hpa": lambda: f"{random.uniform(950, 1050):.1f}",
    "static_hpa": lambda: f"{random.uniform(950, 1050):.1f}",
    "lat": lambda: 34.905 + random.gauss(0, 0.01),
    "lon": lambda: -117.884 + random.gauss(0, 0.01),
    "hdop": lambda: f"{random.uniform(0.8, 3.0):.1f}",
    "ax": lambda: random.gauss(0, 0.1),
    "ay": lambda: random.gauss(0, 0.1),
    "az": lambda: -1.0 + random.gauss(0, 0.05),
    "probe": lambda: str(random.randint(1, 4)),
    "egt_c": lambda: str(random.randint(700, 900)),
    "main_v": lambda: 27.5 + random.gauss(0, 0.3),
    "aux_v": lambda: 27.0 + random.gauss(0, 0.5),
    "airspeed_kts": lambda: str(random.randint(60, 180)),
    "min_kts": lambda: "75",
    "cht_c": lambda: str(random.randint(200, 260)),
    "limit_c": lambda: "240",
    "oil_psi": lambda: str(random.randint(25, 45)),
    "fuel_l": lambda: f"{random.uniform(10, 25):.1f}",
    "fuel_r": lambda: f"{random.uniform(10, 25):.1f}",
    "severity": lambda: random.choice(["light", "moderate", "severe"]),
    "dist_nm": lambda: f"{random.uniform(1, 10):.1f}",
    "alt_delta": lambda: str(random.choice([-500, -200, 0, 200, 500])),
    "rpm_var": lambda: str(random.randint(50, 300)),
}


def _fill_flight_placeholders(template: str) -> str:
    result = template
    for key, gen in FLIGHT_PLACEHOLDER_VALUES.items():
        token = "{" + key + "}"
        if token in result:
            value = gen() if callable(gen) else gen
            # Handle format specs (e.g. {lat:.4f}) by also checking plain token
            result = result.replace(token, str(value))
    return result


def generate_flight_log() -> str:
    level = random.choices(LOG_LEVELS, weights=LOG_LEVEL_WEIGHTS, k=1)[0]
    template = random.choice(FLIGHT_LOG_TEMPLATES[level])
    message = _fill_flight_placeholders(template)
    return f"[{level}] [flight-computer] {message}"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    print(f"Connecting to Nominal using profile '{PROFILE_NAME}'...")
    client = NominalClient.from_profile(PROFILE_NAME)

    print(f"Fetching dataset {DATASET_RID}...")
    dataset = client.get_dataset(DATASET_RID)

    aircraft = AircraftState()

    print(f"Streaming aircraft telemetry + logs to dataset (Ctrl+C to stop)")
    print("-" * 60)

    with dataset.get_write_stream() as data_stream, dataset.get_log_stream() as log_stream:
        count = 0
        try:
            while True:
                now = datetime.now()
                count += 1

                # -- telemetry --
                channels = aircraft.step(dt=1.0)
                data_stream.enqueue_from_dict(timestamp=now, channel_values=channels)

                # -- log message --
                log_msg = generate_flight_log()
                log_stream.enqueue(
                    channel_name=LOG_CHANNEL_NAME,
                    timestamp=now,
                    value=log_msg,
                )

                phase = aircraft._phase
                alt = channels["aircraft.position.altitude_ft"]
                hdg = channels["aircraft.attitude.heading_deg"]
                spd = channels["aircraft.motion.airspeed_kts"]
                print(
                    f"[{now.isoformat()}] #{count}  "
                    f"phase={phase:<8s} alt={alt:>8.0f}ft  hdg={hdg:>5.0f}°  "
                    f"spd={spd:>5.0f}kts  | {log_msg}"
                )

                time.sleep(1)
        except KeyboardInterrupt:
            print(f"\nStopping. Sent {count} telemetry frames + log messages.")


if __name__ == "__main__":
    main()
