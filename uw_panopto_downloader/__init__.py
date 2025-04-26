"""UW Panopto Downloader - A tool for downloading videos from UW Panopto."""

__version__ = "1.0.6"

# Check for required dependencies
def _check_dependencies():
    """Check if all required dependencies are installed."""
    required_packages = [
        "requests", "bs4", "selenium", "webdriver_manager.chrome",
        "rich", "typer", "click"
    ]

    missing = []

    for package in required_packages:
        try:
            __import__(package)
        except ImportError:
            missing.append(package)

    if missing:
        print(f"Warning: Missing required dependencies: {', '.join(missing)}")
        print("Please install them using: pip install " + " ".join(missing))

# Run dependency check
_check_dependencies()
