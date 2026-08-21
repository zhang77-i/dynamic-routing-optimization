#include <stdlib.h>

#ifdef _WIN32
#define LADE_EXPORT extern "C" __declspec(dllexport)
#else
#define LADE_EXPORT extern "C"
#endif

namespace {

double route_distance_impl(
    const double* start_distance,
    const double* order_distance,
    int order_count,
    int vehicle,
    const int* route,
    int route_length
) {
    if (route_length <= 0) {
        return 0.0;
    }
    double total = start_distance[vehicle * order_count + route[0]];
    for (int position = 1; position < route_length; ++position) {
        const int previous = route[position - 1];
        const int current = route[position];
        total += order_distance[previous * order_count + current];
    }
    return total;
}

double insertion_delta_impl(
    const double* start_distance,
    const double* order_distance,
    int order_count,
    int vehicle,
    const int* route,
    int route_length,
    int order,
    int position
) {
    if (route_length <= 0) {
        return start_distance[vehicle * order_count + order];
    }
    if (position == 0) {
        const int following = route[0];
        return start_distance[vehicle * order_count + order]
            + order_distance[order * order_count + following]
            - start_distance[vehicle * order_count + following];
    }
    const int previous = route[position - 1];
    if (position == route_length) {
        return order_distance[previous * order_count + order];
    }
    const int following = route[position];
    return order_distance[previous * order_count + order]
        + order_distance[order * order_count + following]
        - order_distance[previous * order_count + following];
}

}  // namespace

LADE_EXPORT double lade_route_distance(
    const double* start_distance,
    const double* order_distance,
    int order_count,
    int vehicle,
    const int* route,
    int route_length
) {
    if (
        start_distance == 0
        || order_distance == 0
        || route == 0
        || order_count <= 0
        || vehicle < 0
        || route_length < 0
    ) {
        return -1.0;
    }
    return route_distance_impl(
        start_distance,
        order_distance,
        order_count,
        vehicle,
        route,
        route_length
    );
}

LADE_EXPORT int lade_insertion_deltas(
    const double* start_distance,
    const double* order_distance,
    int order_count,
    int vehicle,
    const int* route,
    int route_length,
    int order,
    double* output
) {
    if (
        start_distance == 0
        || order_distance == 0
        || output == 0
        || order_count <= 0
        || vehicle < 0
        || route_length < 0
        || order < 0
        || order >= order_count
    ) {
        return -1;
    }
    if (route_length > 0 && route == 0) {
        return -2;
    }
    for (int position = 0; position <= route_length; ++position) {
        output[position] = insertion_delta_impl(
            start_distance,
            order_distance,
            order_count,
            vehicle,
            route,
            route_length,
            order,
            position
        );
    }
    return route_length + 1;
}

LADE_EXPORT int lade_all_insertion_deltas(
    const double* start_distance,
    const double* order_distance,
    int order_count,
    const int* routes,
    const int* offsets,
    int vehicle_count,
    int capacity,
    int order,
    int max_options,
    double* deltas,
    int* vehicles,
    int* positions
) {
    if (
        start_distance == 0
        || order_distance == 0
        || offsets == 0
        || deltas == 0
        || vehicles == 0
        || positions == 0
        || order_count <= 0
        || vehicle_count <= 0
        || capacity <= 0
        || order < 0
        || order >= order_count
        || max_options <= 0
    ) {
        return -1;
    }
    int written = 0;
    for (int vehicle = 0; vehicle < vehicle_count; ++vehicle) {
        const int begin = offsets[vehicle];
        const int end = offsets[vehicle + 1];
        const int length = end - begin;
        if (length < 0 || length >= capacity) {
            continue;
        }
        const int* route = length > 0 ? routes + begin : 0;
        for (int position = 0; position <= length; ++position) {
            const double delta = insertion_delta_impl(
                start_distance,
                order_distance,
                order_count,
                vehicle,
                route,
                length,
                order,
                position
            );
            int insertion = written;
            for (int index = 0; index < written; ++index) {
                const bool smaller_delta = delta < deltas[index];
                const bool equal_delta = delta == deltas[index];
                const bool smaller_vehicle = vehicle < vehicles[index];
                const bool equal_vehicle = vehicle == vehicles[index];
                if (
                    smaller_delta
                    || (
                        equal_delta
                        && (
                            smaller_vehicle
                            || (equal_vehicle && position < positions[index])
                        )
                    )
                ) {
                    insertion = index;
                    break;
                }
            }
            if (written < max_options) {
                ++written;
            } else if (insertion >= max_options) {
                continue;
            }
            for (int index = written - 1; index > insertion; --index) {
                deltas[index] = deltas[index - 1];
                vehicles[index] = vehicles[index - 1];
                positions[index] = positions[index - 1];
            }
            deltas[insertion] = delta;
            vehicles[insertion] = vehicle;
            positions[insertion] = position;
        }
    }
    return written;
}

LADE_EXPORT int lade_two_opt(
    const double* start_distance,
    const double* order_distance,
    int order_count,
    int vehicle,
    int* route,
    int route_length
) {
    if (
        start_distance == 0
        || order_distance == 0
        || route == 0
        || order_count <= 0
        || vehicle < 0
        || route_length < 0
    ) {
        return -1;
    }
    if (route_length < 4) {
        return 0;
    }

    int* candidate = static_cast<int*>(
        malloc(sizeof(int) * static_cast<size_t>(route_length))
    );
    if (candidate == 0) {
        return -2;
    }
    double current_cost = route_distance_impl(
        start_distance,
        order_distance,
        order_count,
        vehicle,
        route,
        route_length
    );
    int accepted_moves = 0;
    bool changed = true;

    while (changed) {
        changed = false;
        for (int left = 0; left < route_length - 2 && !changed; ++left) {
            for (int right = left + 2; right <= route_length; ++right) {
                for (int position = 0; position < route_length; ++position) {
                    candidate[position] = route[position];
                }
                int low = left;
                int high = right - 1;
                while (low < high) {
                    const int temporary = candidate[low];
                    candidate[low] = candidate[high];
                    candidate[high] = temporary;
                    ++low;
                    --high;
                }
                const double candidate_cost = route_distance_impl(
                    start_distance,
                    order_distance,
                    order_count,
                    vehicle,
                    candidate,
                    route_length
                );
                if (candidate_cost + 1e-9 < current_cost) {
                    for (int position = 0; position < route_length; ++position) {
                        route[position] = candidate[position];
                    }
                    current_cost = candidate_cost;
                    ++accepted_moves;
                    changed = true;
                    break;
                }
            }
        }
    }
    free(candidate);
    return accepted_moves;
}
