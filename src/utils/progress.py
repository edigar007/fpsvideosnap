from tqdm import tqdm
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeRemainingColumn
from typing import Optional, Iterable, Any

def get_progress_bar():
    """
    Returns a Rich Progress object configured for the project.
    """
    return Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TimeRemainingColumn(),
    )

def create_progress_bar(iterable: Optional[Iterable[Any]] = None, desc: str = "Processing", total: Optional[int] = None):
    """
    Creates a tqdm progress bar.
    If iterable is provided, it returns a tqdm object wrapping the iterable.
    If total is provided, it returns a manual tqdm object.
    """
    return tqdm(
        iterable,
        desc=desc,
        total=total,
        unit="frame",
        ncols=100,
        bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}{postfix}]"
    )
