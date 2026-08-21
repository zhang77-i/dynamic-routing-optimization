"""Optional C++ acceleration for the routing neighborhood operations."""

from __future__ import annotations

import ctypes
from pathlib import Path

import numpy as np


class CppRouteCore:
    """Load the Dev-C++/MinGW DLL and expose NumPy-friendly operations."""

    def __init__(self) -> None:
        self.dll_path = (
            Path(__file__).resolve().parents[2]
            / "cpp"
            / "build"
            / "lade_route_core.dll"
        )
        self._library: ctypes.CDLL | None = None
        self.load_error: str | None = None
        self.enabled = False
        self._load()

    @property
    def available(self) -> bool:
        return self._library is not None

    def _load(self) -> None:
        if not self.dll_path.exists():
            self.load_error = f"DLL not found: {self.dll_path}"
            return
        try:
            library = ctypes.CDLL(str(self.dll_path))
            double_pointer = ctypes.POINTER(ctypes.c_double)
            int_pointer = ctypes.POINTER(ctypes.c_int)

            library.lade_route_distance.argtypes = [
                double_pointer,
                double_pointer,
                ctypes.c_int,
                ctypes.c_int,
                int_pointer,
                ctypes.c_int,
            ]
            library.lade_route_distance.restype = ctypes.c_double

            library.lade_insertion_deltas.argtypes = [
                double_pointer,
                double_pointer,
                ctypes.c_int,
                ctypes.c_int,
                int_pointer,
                ctypes.c_int,
                ctypes.c_int,
                double_pointer,
            ]
            library.lade_insertion_deltas.restype = ctypes.c_int

            library.lade_all_insertion_deltas.argtypes = [
                double_pointer,
                double_pointer,
                ctypes.c_int,
                int_pointer,
                int_pointer,
                ctypes.c_int,
                ctypes.c_int,
                ctypes.c_int,
                ctypes.c_int,
                double_pointer,
                int_pointer,
                int_pointer,
            ]
            library.lade_all_insertion_deltas.restype = ctypes.c_int

            library.lade_two_opt.argtypes = [
                double_pointer,
                double_pointer,
                ctypes.c_int,
                ctypes.c_int,
                int_pointer,
                ctypes.c_int,
            ]
            library.lade_two_opt.restype = ctypes.c_int
            self._library = library
            self.enabled = True
        except OSError as exc:
            self.load_error = str(exc)

    @staticmethod
    def _double_matrix(values: np.ndarray) -> np.ndarray:
        return np.ascontiguousarray(values, dtype=np.float64)

    @staticmethod
    def _route(values: list[int]) -> np.ndarray:
        return np.ascontiguousarray(values, dtype=np.int32)

    @staticmethod
    def _double_pointer(values: np.ndarray):
        return values.ctypes.data_as(ctypes.POINTER(ctypes.c_double))

    @staticmethod
    def _int_pointer(values: np.ndarray):
        return values.ctypes.data_as(ctypes.POINTER(ctypes.c_int))

    def _require_library(self) -> ctypes.CDLL:
        if self._library is None:
            raise RuntimeError(self.load_error or "C++ route core is unavailable")
        return self._library

    def route_distance(
        self,
        start_distance: np.ndarray,
        order_distance: np.ndarray,
        vehicle: int,
        route: list[int],
    ) -> float:
        if not route:
            return 0.0
        library = self._require_library()
        starts = self._double_matrix(start_distance)
        distances = self._double_matrix(order_distance)
        route_array = self._route(route)
        value = library.lade_route_distance(
            self._double_pointer(starts),
            self._double_pointer(distances),
            distances.shape[0],
            vehicle,
            self._int_pointer(route_array),
            len(route),
        )
        if value < 0:
            raise RuntimeError("C++ route-distance calculation failed")
        return float(value)

    def insertion_deltas(
        self,
        start_distance: np.ndarray,
        order_distance: np.ndarray,
        vehicle: int,
        route: list[int],
        order: int,
    ) -> np.ndarray:
        library = self._require_library()
        starts = self._double_matrix(start_distance)
        distances = self._double_matrix(order_distance)
        route_array = self._route(route)
        output = np.empty(len(route) + 1, dtype=np.float64)
        route_pointer = (
            self._int_pointer(route_array)
            if route_array.size
            else ctypes.POINTER(ctypes.c_int)()
        )
        written = library.lade_insertion_deltas(
            self._double_pointer(starts),
            self._double_pointer(distances),
            distances.shape[0],
            vehicle,
            route_pointer,
            len(route),
            order,
            self._double_pointer(output),
        )
        if written != len(route) + 1:
            raise RuntimeError(f"C++ insertion calculation failed: {written}")
        return output

    def two_opt(
        self,
        start_distance: np.ndarray,
        order_distance: np.ndarray,
        vehicle: int,
        route: list[int],
    ) -> tuple[list[int], int]:
        if len(route) < 4:
            return list(route), 0
        library = self._require_library()
        starts = self._double_matrix(start_distance)
        distances = self._double_matrix(order_distance)
        route_array = self._route(route)
        accepted_moves = library.lade_two_opt(
            self._double_pointer(starts),
            self._double_pointer(distances),
            distances.shape[0],
            vehicle,
            self._int_pointer(route_array),
            len(route),
        )
        if accepted_moves < 0:
            raise RuntimeError("C++ 2-opt calculation failed")
        return route_array.tolist(), int(accepted_moves)

    def all_insertion_options(
        self,
        start_distance: np.ndarray,
        order_distance: np.ndarray,
        routes: list[list[int]],
        capacity: int,
        order: int,
    ) -> list[tuple[float, int, int]]:
        """Calculate every capacity-feasible insertion in one DLL call."""
        library = self._require_library()
        starts = self._double_matrix(start_distance)
        distances = self._double_matrix(order_distance)
        offsets = np.zeros(len(routes) + 1, dtype=np.int32)
        for index, route in enumerate(routes):
            offsets[index + 1] = offsets[index] + len(route)
        flattened = np.ascontiguousarray(
            [value for route in routes for value in route],
            dtype=np.int32,
        )
        feasible_options = sum(
            len(route) + 1
            for route in routes
            if len(route) < capacity
        )
        maximum = min(3, feasible_options)
        deltas = np.empty(maximum, dtype=np.float64)
        vehicles = np.empty(maximum, dtype=np.int32)
        positions = np.empty(maximum, dtype=np.int32)
        route_pointer = (
            self._int_pointer(flattened)
            if flattened.size
            else ctypes.POINTER(ctypes.c_int)()
        )
        written = library.lade_all_insertion_deltas(
            self._double_pointer(starts),
            self._double_pointer(distances),
            distances.shape[0],
            route_pointer,
            self._int_pointer(offsets),
            len(routes),
            capacity,
            order,
            maximum,
            self._double_pointer(deltas),
            self._int_pointer(vehicles),
            self._int_pointer(positions),
        )
        if written < 0 or written > maximum:
            raise RuntimeError(f"C++ all-insertion calculation failed: {written}")
        return [
            (float(deltas[index]), int(vehicles[index]), int(positions[index]))
            for index in range(written)
        ]


CPP_CORE = CppRouteCore()
