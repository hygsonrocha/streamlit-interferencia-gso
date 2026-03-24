import numpy as np


def geodetic_to_ecef(lat_deg: float, lon_deg: float, h_m: float) -> np.ndarray:
    a = 6378137.0
    f = 1.0 / 298.257223563
    e2 = f * (2.0 - f)

    lat = np.deg2rad(lat_deg)
    lon = np.deg2rad(lon_deg)

    sin_lat = np.sin(lat)
    cos_lat = np.cos(lat)
    sin_lon = np.sin(lon)
    cos_lon = np.cos(lon)

    N = a / np.sqrt(1.0 - e2 * sin_lat**2)

    x = (N + h_m) * cos_lat * cos_lon
    y = (N + h_m) * cos_lat * sin_lon
    z = (N * (1.0 - e2) + h_m) * sin_lat

    return np.array([x, y, z], dtype=float)


def gso_to_ecef(gso_lon_deg: float) -> np.ndarray:
    a = 6378137.0
    h_geo_m = 35786000.0
    r_geo = a + h_geo_m

    lon_sat = np.deg2rad(gso_lon_deg)

    x_sat = r_geo * np.cos(lon_sat)
    y_sat = r_geo * np.sin(lon_sat)
    z_sat = 0.0

    return np.array([x_sat, y_sat, z_sat], dtype=float)


def ecef_to_enu_matrix(lat_deg: float, lon_deg: float) -> np.ndarray:
    lat = np.deg2rad(lat_deg)
    lon = np.deg2rad(lon_deg)

    sin_lat = np.sin(lat)
    cos_lat = np.cos(lat)
    sin_lon = np.sin(lon)
    cos_lon = np.cos(lon)

    return np.array(
        [
            [-sin_lon, cos_lon, 0.0],
            [-sin_lat * cos_lon, -sin_lat * sin_lon, cos_lat],
            [cos_lat * cos_lon, cos_lat * sin_lon, sin_lat],
        ],
        dtype=float,
    )


def unit_vector(v: np.ndarray) -> np.ndarray:
    norm_v = np.linalg.norm(v)
    if norm_v == 0.0:
        raise ValueError("Não é possível normalizar um vetor nulo.")
    return v / norm_v


def angle_between_vectors_deg(u: np.ndarray, v: np.ndarray) -> float:
    cosang = np.clip(np.dot(unit_vector(u), unit_vector(v)), -1.0, 1.0)
    return float(np.rad2deg(np.arccos(cosang)))
