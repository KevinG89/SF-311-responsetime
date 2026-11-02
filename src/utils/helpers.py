# Small helper functions used in several places.

import matplotlib.pyplot as plt

from src.utils import config


def make_folders():
    """Create the output folders if they do not exist yet."""
    for folder in [config.PROCESSED, config.LOGS, config.VISUALIZATIONS, config.TABLES]:
        folder.mkdir(parents=True, exist_ok=True)


def save_figure(fig, filename, source=config.SOURCE):
    """Add the data source under a figure, save it to visualizations/ and close it."""
    if source:
        fig.text(0.01, -0.04, source, fontsize=7, color="#555555")
    path = config.VISUALIZATIONS / filename
    fig.savefig(path, dpi=200, bbox_inches="tight")
    plt.close(fig)
    print("saved", path.relative_to(config.ROOT))
