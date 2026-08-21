import matplotlib.pyplot as plt


def plot_routes(routes, depot=(0, 0)):
    """Visualize vehicle routes.

    routes: list of routes, each route is a list of (x, y) coordinates.
    """
    plt.figure(figsize=(8, 6))

    plt.scatter(
        depot[0],
        depot[1],
        marker="*",
        s=120,
        label="Depot",
    )

    for idx, route in enumerate(routes):
        xs = [point[0] for point in route]
        ys = [point[1] for point in route]
        plt.plot(xs, ys, marker="o", label=f"Vehicle {idx}")

    plt.xlabel("X")
    plt.ylabel("Y")
    plt.title("Vehicle Routing Solution")
    plt.legend()
    plt.grid(True)
    plt.show()
