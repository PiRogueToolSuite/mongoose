import subprocess
from pathlib import Path

from hatchling.metadata.plugin.interface import MetadataHookInterface
import re

from typing import List, Dict, Optional

def get_authors(changelog_path: str) -> List[Dict[str, str]]:
    """
    Extract all unique authors from a Debian changelog file.

    Each author is represented as a dict with keys 'name' and 'email'.
    Authors are identified by lines starting with ' -- ' followed by
    'Name <email>'.

    Args:
        changelog_path: Path to the debian/changelog file.

    Returns:
        List of dicts, e.g. [{"name": "John Doe", "email": "john@example.com"}]
    """
    author_pattern = re.compile(r'^ -- (.*?) <([^>]+)>')
    authors = []
    seen = set()

    with open(changelog_path, 'r', encoding='utf-8') as f:
        for line in f:
            match = author_pattern.match(line)
            if match:
                name = match.group(1).strip()
                email = match.group(2).strip()
                key = (name, email)
                if key not in seen:
                    seen.add(key)
                    authors.append({"name": name, "email": email})

    return authors

def get_latest_version(changelog_path: str) -> Optional[str]:
    """
    Extract the latest version from a Debian changelog file.

    Args:
        changelog_path: Path to the debian/changelog file.

    Returns:
        Version string (e.g., "1.0.2") or None if not found.
    """
    version_pattern = re.compile(r'^[^\s]+\s+\(([^)]+)\)')
    
    with open(changelog_path, 'r', encoding='utf-8') as f:
        for line in f:
            match = version_pattern.match(line)
            if match:
                return match.group(1)
    return None

def get_latest_xxversion(changelog_path):
    version_pattern = re.compile(r'^[^\s]+\s+\(([^)]+)\)')

    with open(changelog_path, 'r', encoding='utf-8') as f:
        for line in f:
            match = version_pattern.match(line)
            if match:
                return match.group(1)   # captured version
    return None


class DebianChangelogHook(MetadataHookInterface):
    def update(self, metadata):
        # Only run for the 'metadata' phase
        changelog_path = Path(self.root) / "debian" / "changelog"
        if not changelog_path.exists():
            return

        version = get_latest_version(changelog_path)
        authors = get_authors(changelog_path)

        if not version:
            raise Exception("Not version found")

        if authors:
            metadata["authors"] = authors 

        metadata["version"] = version
        print(metadata)


#class JSONMetaDataHook(MetadataHookInterface):
#    def update(self, meta data):
#        version = subprocess.check_output(["dpkg-parsechangelog", "--show-field", "Version"])
#        metadata["version"] = version
#        print(metadata)

