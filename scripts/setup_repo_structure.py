"""
DESCRIPTION
Creates full enhanced repository structure with artifacts folders, ML, analytics,
ingestion, raw, and .gitkeep placeholders.

Run from project root.
"""

import os

# All folders to create
FOLDERS = [
    # Artifacts medallion layers
    "artifacts/bronze/_checks",
    "artifacts/bronze/_meta",
    "artifacts/bronze/tables",
    "artifacts/silver/_checks",
    "artifacts/silver/_meta",
    "artifacts/silver/tables",
    "artifacts/gold/_checks",
    "artifacts/gold/_meta",
    "artifacts/gold/marts",
    "artifacts/reports",
    "artifacts/tmp",

    # Source and SQL areas
    "configs",
    "sql/bronze",
    "sql/silver",
    "sql/gold",

    # Ingestion
    "ingestion",

    # Raw files
    "raw",

    # Analytics / BI
    "analytics/tableau",

    # Machine Learning
    "ml",

    # Scripts and source
    "scripts",
    "src",

    # Tests
    "tests",

    # Documentation
    "docs"
]

# Static files to generate if missing
FILE_TEMPLATES = {
    # Root governance & project files
    ".gitignore": (
        "# Python env\n"
        ".venv/\n"
        "__pycache__/\n"
        "*.pyc\n"
        "# artifact tmp\n"
        "artifacts/tmp/\n"
        "# local secrets\n"
        ".env\n"
    ),
    "README.md": "# MySQL Data Warehouse\n\nProject repository structure.\n",
    "LICENSE": "MIT License Placeholder\n",

    # Config templates
    "configs/.env.example": (
        "# Example environment variables (never commit real secrets)\n"
        "MYSQL_HOST=localhost\n"
        "MYSQL_PORT=3306\n"
        "MYSQL_USER=your_user\n"
        "MYSQL_PASSWORD=your_password\n"
        "MYSQL_DB=your_db\n"
    ),

    # Documentation templates
    "docs/architecture.md": "# Architecture Overview\n",
    "docs/standards.md": "# Naming and Coding Standards\n",
    "docs/metadata_dictionary.md": "# Metadata Dictionary\n",
    "docs/lineage_overview.md": "# Data Lineage Overview\n",

    # Ingestion template
    "ingestion/README.md": "# Ingestion Scripts\n",

    # Analytics / BI placeholder
    "analytics/tableau/README.md": "# Tableau Public Analytics\n",

    # Raw placeholder
    "raw/README.md": "# Raw Data Files\n",

    # Tests placeholder
    "tests/README.md": "# Tests\n",

    # Scripts placeholder
    "scripts/README.md": "# Utility Scripts\n",

    # Src placeholder
    "src/README.md": "# Source Code\n"
}


def create_folder(path: str):
    """Create folder if absent."""
    if not os.path.exists(path):
        os.makedirs(path)
        print(f"[+] Created folder: {path}")


def create_gitkeep(folder: str):
    """Place .gitkeep in empty folder."""
    gitkeep = os.path.join(folder, ".gitkeep")
    if not os.listdir(folder) and not os.path.exists(gitkeep):
        with open(gitkeep, "w"):
            pass
        print(f"[+] Created .gitkeep in: {folder}")


def create_file(path: str, content: str):
    """Create file with content if it doesn't exist."""
    if not os.path.exists(path):
        parent = os.path.dirname(path)
        if parent and not os.path.exists(parent):
            os.makedirs(parent)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"[+] Created file: {path}")


def main():
    print("Setting up project structure...")

    # Create all folders
    for folder in FOLDERS:
        create_folder(folder)

    # Place .gitkeep in any empty folder
    for folder in FOLDERS:
        create_gitkeep(folder)

    # Create static files
    for file_path, content in FILE_TEMPLATES.items():
        create_file(file_path, content)

    print("Repository structure generation complete.")


if __name__ == "__main__":
    main()
