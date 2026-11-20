from .telegram import TelegramProvider
from .vk import VKProvider
from ..enums import NotificationProvider


class ProviderRegistry:
    _providers = {
        NotificationProvider.TELEGRAM: TelegramProvider(),
        NotificationProvider.VK: VKProvider(),
    }

    @classmethod
    def get(cls, provider: str):
        return cls._providers[provider]
