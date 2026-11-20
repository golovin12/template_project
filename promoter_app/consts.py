from dataclasses import dataclass


@dataclass
class Version:
    """Класс для работы с версиями"""
    major: int = 0
    minor: int = 0
    patch: int = 0

    def __str__(self):
        return f'{self.major}.{self.minor}.{self.patch}'

    def __lt__(self, other: 'Version') -> bool:
        if self.major != other.major:
            return self.major < other.major
        if self.minor != other.minor:
            return self.minor < other.minor
        return self.patch < other.patch

    def __le__(self, other: 'Version') -> bool:
        return self < other or self == other

    def __gt__(self, other: 'Version') -> bool:
        return other < self

    def __ge__(self, other: 'Version') -> bool:
        return self > other or self == other

    def __eq__(self, other: 'Version') -> bool:
        if not isinstance(other, Version):
            return False
        return self.major == other.major and self.minor == other.minor and self.patch == other.patch

    @classmethod
    def from_string(cls, version_str: str) -> 'Version':
        parts = version_str.split('.')
        return cls(
            int(parts[0]),
            int(parts[1]),
            int(parts[2]),
        )

    @classmethod
    def try_parse(cls, version_str: str) -> 'Version':
        try:
            return cls.from_string(version_str)
        except (ValueError, TypeError, IndexError):
            return cls()


APP_VERSIONS_CACHE_KEY = 'app_versions'

DEFAULT_APP_VERSIONS = {
    'android': {
        'minimum': '1.0.8',
        'latest': '1.0.8',
    },
    'ios': {
        'minimum': '1.0.4',
        'latest': '1.0.4',
    },
}
