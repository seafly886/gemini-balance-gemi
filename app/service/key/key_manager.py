import asyncio
import random
from itertools import cycle
from typing import Dict, Union

from app.config.config import settings
from app.log.logger import get_key_manager_logger
from app.utils.helpers import redact_key_for_logging

logger = get_key_manager_logger()


class KeyManager:
    def __init__(self, api_keys: list, vertex_api_keys: list):
        self.api_keys = api_keys
        self.vertex_api_keys = vertex_api_keys
        self.key_cycle = cycle(api_keys)
        self.vertex_key_cycle = cycle(vertex_api_keys)
        self.key_cycle_lock = asyncio.Lock()
        self.vertex_key_cycle_lock = asyncio.Lock()
        self.failure_count_lock = asyncio.Lock()
        self.vertex_failure_count_lock = asyncio.Lock()
        self.key_failure_counts: Dict[str, int] = {key: 0 for key in api_keys}
        self.vertex_key_failure_counts: Dict[str, int] = {
            key: 0 for key in vertex_api_keys
        }
        self.MAX_FAILURES = settings.MAX_FAILURES
        self.paid_key = settings.PAID_KEY

        # Key usage mode and counting
        self.usage_mode = settings.KEY_USAGE_MODE  # "polling" or "fixed"
        self.usage_threshold = settings.KEY_USAGE_THRESHOLD
        self.key_usage_counts: Dict[str, int] = {key: 0 for key in api_keys}
        self.vertex_key_usage_counts: Dict[str, int] = {key: 0 for key in vertex_api_keys}
        self.usage_count_lock = asyncio.Lock()
        self.vertex_usage_count_lock = asyncio.Lock()

        # Current fixed key tracking
        self.current_fixed_key_index = 0
        self.current_vertex_fixed_key_index = 0
        self.fixed_key_lock = asyncio.Lock()
        self.vertex_fixed_key_lock = asyncio.Lock()

    async def get_paid_key(self) -> str:
        return self.paid_key

    async def set_usage_mode(self, mode: str) -> bool:
        """设置key使用模式"""
        if mode not in ["polling", "fixed"]:
            return False
        self.usage_mode = mode
        logger.info(f"Key usage mode changed to: {mode}")
        return True

    async def get_usage_mode(self) -> str:
        """获取当前key使用模式"""
        return self.usage_mode

    async def set_usage_threshold(self, threshold: int) -> bool:
        """设置使用阈值"""
        if threshold < 1:
            return False
        self.usage_threshold = threshold
        logger.info(f"Key usage threshold changed to: {threshold}")
        return True

    async def get_usage_threshold(self) -> int:
        """获取当前使用阈值"""
        return self.usage_threshold

    async def reset_usage_counts(self):
        """重置所有key的使用计数"""
        async with self.usage_count_lock:
            for key in self.key_usage_counts:
                self.key_usage_counts[key] = 0
        async with self.vertex_usage_count_lock:
            for key in self.vertex_key_usage_counts:
                self.vertex_key_usage_counts[key] = 0
        logger.info("All key usage counts have been reset")

    async def get_key_usage_count(self, key: str) -> int:
        """获取指定key的使用次数"""
        async with self.usage_count_lock:
            return self.key_usage_counts.get(key, 0)

    async def get_vertex_key_usage_count(self, key: str) -> int:
        """获取指定vertex key的使用次数"""
        async with self.vertex_usage_count_lock:
            return self.vertex_key_usage_counts.get(key, 0)

    async def get_next_key(self) -> str:
        """获取下一个API key"""
        if self.usage_mode == "fixed":
            return await self._get_fixed_key()
        else:
            async with self.key_cycle_lock:
                key = next(self.key_cycle)
                # 在轮询模式下也记录使用次数
                async with self.usage_count_lock:
                    self.key_usage_counts[key] = self.key_usage_counts.get(key, 0) + 1
                return key

    async def _get_fixed_key(self) -> str:
        """获取固定模式下的key"""
        if not self.api_keys:
            return ""

        async with self.fixed_key_lock:
            current_key = self.api_keys[self.current_fixed_key_index]

            # 检查当前key是否需要切换
            async with self.usage_count_lock:
                usage_count = self.key_usage_counts.get(current_key, 0)

                if usage_count >= self.usage_threshold:
                    # 切换到下一个key
                    self.current_fixed_key_index = (self.current_fixed_key_index + 1) % len(self.api_keys)
                    current_key = self.api_keys[self.current_fixed_key_index]
                    logger.info(f"Switched to next key due to usage threshold. New key index: {self.current_fixed_key_index}")

                # 增加使用计数
                self.key_usage_counts[current_key] = self.key_usage_counts.get(current_key, 0) + 1

            return current_key

    async def get_next_vertex_key(self) -> str:
        """获取下一个 Vertex Express API key"""
        if self.usage_mode == "fixed":
            return await self._get_fixed_vertex_key()
        else:
            async with self.vertex_key_cycle_lock:
                key = next(self.vertex_key_cycle)
                # 在轮询模式下也记录使用次数
                async with self.vertex_usage_count_lock:
                    self.vertex_key_usage_counts[key] = self.vertex_key_usage_counts.get(key, 0) + 1
                return key

    async def _get_fixed_vertex_key(self) -> str:
        """获取固定模式下的vertex key"""
        if not self.vertex_api_keys:
            return ""

        async with self.vertex_fixed_key_lock:
            current_key = self.vertex_api_keys[self.current_vertex_fixed_key_index]

            # 检查当前key是否需要切换
            async with self.vertex_usage_count_lock:
                usage_count = self.vertex_key_usage_counts.get(current_key, 0)

                if usage_count >= self.usage_threshold:
                    # 切换到下一个key
                    self.current_vertex_fixed_key_index = (self.current_vertex_fixed_key_index + 1) % len(self.vertex_api_keys)
                    current_key = self.vertex_api_keys[self.current_vertex_fixed_key_index]
                    logger.info(f"Switched to next vertex key due to usage threshold. New key index: {self.current_vertex_fixed_key_index}")

                # 增加使用计数
                self.vertex_key_usage_counts[current_key] = self.vertex_key_usage_counts.get(current_key, 0) + 1

            return current_key

    async def is_key_valid(self, key: str) -> bool:
        """检查key是否有效"""
        async with self.failure_count_lock:
            return self.key_failure_counts[key] < self.MAX_FAILURES

    async def is_vertex_key_valid(self, key: str) -> bool:
        """检查 Vertex key 是否有效"""
        async with self.vertex_failure_count_lock:
            return self.vertex_key_failure_counts[key] < self.MAX_FAILURES

    async def reset_failure_counts(self):
        """重置所有key的失败计数"""
        async with self.failure_count_lock:
            for key in self.key_failure_counts:
                self.key_failure_counts[key] = 0

    async def reset_vertex_failure_counts(self):
        """重置所有 Vertex key 的失败计数"""
        async with self.vertex_failure_count_lock:
            for key in self.vertex_key_failure_counts:
                self.vertex_key_failure_counts[key] = 0

    async def reset_key_failure_count(self, key: str) -> bool:
        """重置指定key的失败计数"""
        async with self.failure_count_lock:
            if key in self.key_failure_counts:
                self.key_failure_counts[key] = 0
                logger.info(f"Reset failure count for key: {redact_key_for_logging(key)}")
                return True
            logger.warning(
                f"Attempt to reset failure count for non-existent key: {key}"
            )
            return False

    async def reset_vertex_key_failure_count(self, key: str) -> bool:
        """重置指定 Vertex key 的失败计数"""
        async with self.vertex_failure_count_lock:
            if key in self.vertex_key_failure_counts:
                self.vertex_key_failure_counts[key] = 0
                logger.info(f"Reset failure count for Vertex key: {redact_key_for_logging(key)}")
                return True
            logger.warning(
                f"Attempt to reset failure count for non-existent Vertex key: {key}"
            )
            return False

    async def get_next_working_key(self) -> str:
        """获取下一可用的API key"""
        initial_key = await self.get_next_key()
        current_key = initial_key

        while True:
            if await self.is_key_valid(current_key):
                return current_key

            current_key = await self.get_next_key()
            if current_key == initial_key:
                return current_key

    async def get_next_working_vertex_key(self) -> str:
        """获取下一可用的 Vertex Express API key"""
        initial_key = await self.get_next_vertex_key()
        current_key = initial_key

        while True:
            if await self.is_vertex_key_valid(current_key):
                return current_key

            current_key = await self.get_next_vertex_key()
            if current_key == initial_key:
                return current_key

    async def handle_api_failure(self, api_key: str, retries: int) -> str:
        """处理API调用失败"""
        async with self.failure_count_lock:
            self.key_failure_counts[api_key] += 1
            if self.key_failure_counts[api_key] >= self.MAX_FAILURES:
                logger.warning(
                    f"API key {redact_key_for_logging(api_key)} has failed {self.MAX_FAILURES} times"
                )
        if retries < settings.MAX_RETRIES:
            return await self.get_next_working_key()
        else:
            return ""

    async def handle_vertex_api_failure(self, api_key: str, retries: int) -> str:
        """处理 Vertex Express API 调用失败"""
        async with self.vertex_failure_count_lock:
            self.vertex_key_failure_counts[api_key] += 1
            if self.vertex_key_failure_counts[api_key] >= self.MAX_FAILURES:
                logger.warning(
                    f"Vertex Express API key {redact_key_for_logging(api_key)} has failed {self.MAX_FAILURES} times"
                )

    def get_fail_count(self, key: str) -> int:
        """获取指定密钥的失败次数"""
        return self.key_failure_counts.get(key, 0)

    def get_vertex_fail_count(self, key: str) -> int:
        """获取指定 Vertex 密钥的失败次数"""
        return self.vertex_key_failure_counts.get(key, 0)

    async def get_all_keys_with_fail_count(self) -> dict:
        """获取所有API key及其失败次数"""
        all_keys = {}
        async with self.failure_count_lock:
            for key in self.api_keys:
                all_keys[key] = self.key_failure_counts.get(key, 0)
        
        valid_keys = {k: v for k, v in all_keys.items() if v < self.MAX_FAILURES}
        invalid_keys = {k: v for k, v in all_keys.items() if v >= self.MAX_FAILURES}
        
        return {"valid_keys": valid_keys, "invalid_keys": invalid_keys, "all_keys": all_keys}

    async def get_keys_by_status(self) -> dict:
        """获取分类后的API key列表，包括失败次数和使用次数"""
        valid_keys = {}
        invalid_keys = {}

        async with self.failure_count_lock:
            async with self.usage_count_lock:
                for key in self.api_keys:
                    fail_count = self.key_failure_counts[key]
                    usage_count = self.key_usage_counts.get(key, 0)
                    key_info = {
                        "fail_count": fail_count,
                        "usage_count": usage_count
                    }
                    if fail_count < self.MAX_FAILURES:
                        valid_keys[key] = key_info
                    else:
                        invalid_keys[key] = key_info

        return {"valid_keys": valid_keys, "invalid_keys": invalid_keys}

    async def get_usage_mode_status(self) -> dict:
        """获取key使用模式状态信息"""
        current_key = ""
        current_vertex_key = ""

        if self.usage_mode == "fixed":
            if self.api_keys:
                current_key = self.api_keys[self.current_fixed_key_index]
            if self.vertex_api_keys:
                current_vertex_key = self.vertex_api_keys[self.current_vertex_fixed_key_index]

        async with self.usage_count_lock:
            async with self.vertex_usage_count_lock:
                return {
                    "usage_mode": self.usage_mode,
                    "usage_threshold": self.usage_threshold,
                    "current_fixed_key": current_key,
                    "current_vertex_fixed_key": current_vertex_key,
                    "current_key_usage": self.key_usage_counts.get(current_key, 0) if current_key else 0,
                    "current_vertex_key_usage": self.vertex_key_usage_counts.get(current_vertex_key, 0) if current_vertex_key else 0,
                    "total_usage_counts": dict(self.key_usage_counts),
                    "total_vertex_usage_counts": dict(self.vertex_key_usage_counts)
                }

    async def get_vertex_keys_by_status(self) -> dict:
        """获取分类后的 Vertex Express API key 列表，包括失败次数和使用次数"""
        valid_keys = {}
        invalid_keys = {}

        async with self.vertex_failure_count_lock:
            async with self.vertex_usage_count_lock:
                for key in self.vertex_api_keys:
                    fail_count = self.vertex_key_failure_counts[key]
                    usage_count = self.vertex_key_usage_counts.get(key, 0)
                    key_info = {
                        "fail_count": fail_count,
                        "usage_count": usage_count
                    }
                    if fail_count < self.MAX_FAILURES:
                        valid_keys[key] = key_info
                    else:
                        invalid_keys[key] = key_info
        return {"valid_keys": valid_keys, "invalid_keys": invalid_keys}

    async def get_first_valid_key(self) -> str:
        """获取第一个有效的API key"""
        async with self.failure_count_lock:
            for key in self.key_failure_counts:
                if self.key_failure_counts[key] < self.MAX_FAILURES:
                    return key
        if self.api_keys:
            return self.api_keys[0]
        if not self.api_keys:
            logger.warning("API key list is empty, cannot get first valid key.")
            return ""
        return self.api_keys[0]

    async def get_random_valid_key(self) -> str:
        """获取随机的有效API key"""
        valid_keys = []
        async with self.failure_count_lock:
            for key in self.key_failure_counts:
                if self.key_failure_counts[key] < self.MAX_FAILURES:
                    valid_keys.append(key)
        
        if valid_keys:
            return random.choice(valid_keys)
        
        # 如果没有有效的key，返回第一个key作为fallback
        if self.api_keys:
            logger.warning("No valid keys available, returning first key as fallback.")
            return self.api_keys[0]
        
        logger.warning("API key list is empty, cannot get random valid key.")
        return ""


_singleton_instance = None
_singleton_lock = asyncio.Lock()
_preserved_failure_counts: Union[Dict[str, int], None] = None
_preserved_vertex_failure_counts: Union[Dict[str, int], None] = None
_preserved_old_api_keys_for_reset: Union[list, None] = None
_preserved_vertex_old_api_keys_for_reset: Union[list, None] = None
_preserved_next_key_in_cycle: Union[str, None] = None
_preserved_vertex_next_key_in_cycle: Union[str, None] = None
# New preserved state for usage counts and fixed key mode
_preserved_usage_counts: Union[Dict[str, int], None] = None
_preserved_vertex_usage_counts: Union[Dict[str, int], None] = None
_preserved_fixed_key_index: Union[int, None] = None
_preserved_vertex_fixed_key_index: Union[int, None] = None


async def get_key_manager_instance(
    api_keys: list = None, vertex_api_keys: list = None
) -> KeyManager:
    """
    获取 KeyManager 单例实例。

    如果尚未创建实例，将使用提供的 api_keys,vertex_api_keys 初始化 KeyManager。
    如果已创建实例，则忽略 api_keys 参数，返回现有单例。
    如果在重置后调用，会尝试恢复之前的状态（失败计数、循环位置）。
    """
    global _singleton_instance, _preserved_failure_counts, _preserved_vertex_failure_counts, _preserved_old_api_keys_for_reset, _preserved_vertex_old_api_keys_for_reset, _preserved_next_key_in_cycle, _preserved_vertex_next_key_in_cycle, _preserved_usage_counts, _preserved_vertex_usage_counts, _preserved_fixed_key_index, _preserved_vertex_fixed_key_index

    async with _singleton_lock:
        if _singleton_instance is None:
            if api_keys is None:
                raise ValueError(
                    "API keys are required to initialize or re-initialize the KeyManager instance."
                )
            if vertex_api_keys is None:
                raise ValueError(
                    "Vertex Express API keys are required to initialize or re-initialize the KeyManager instance."
                )

            if not api_keys:
                logger.warning(
                    "Initializing KeyManager with an empty list of API keys."
                )
            if not vertex_api_keys:
                logger.warning(
                    "Initializing KeyManager with an empty list of Vertex Express API keys."
                )

            _singleton_instance = KeyManager(api_keys, vertex_api_keys)
            logger.info(
                f"KeyManager instance created/re-created with {len(api_keys)} API keys and {len(vertex_api_keys)} Vertex Express API keys."
            )

            # 1. 恢复失败计数
            if _preserved_failure_counts:
                current_failure_counts = {
                    key: 0 for key in _singleton_instance.api_keys
                }
                for key, count in _preserved_failure_counts.items():
                    if key in current_failure_counts:
                        current_failure_counts[key] = count
                _singleton_instance.key_failure_counts = current_failure_counts
                logger.info("Inherited failure counts for applicable keys.")
            _preserved_failure_counts = None

            if _preserved_vertex_failure_counts:
                current_vertex_failure_counts = {
                    key: 0 for key in _singleton_instance.vertex_api_keys
                }
                for key, count in _preserved_vertex_failure_counts.items():
                    if key in current_vertex_failure_counts:
                        current_vertex_failure_counts[key] = count
                _singleton_instance.vertex_key_failure_counts = (
                    current_vertex_failure_counts
                )
                logger.info("Inherited failure counts for applicable Vertex keys.")
            _preserved_vertex_failure_counts = None

            # 1.5. 恢复使用计数
            if _preserved_usage_counts:
                current_usage_counts = {
                    key: 0 for key in _singleton_instance.api_keys
                }
                for key, count in _preserved_usage_counts.items():
                    if key in current_usage_counts:
                        current_usage_counts[key] = count
                _singleton_instance.key_usage_counts = current_usage_counts
                logger.info("Inherited usage counts for applicable keys.")
            _preserved_usage_counts = None

            if _preserved_vertex_usage_counts:
                current_vertex_usage_counts = {
                    key: 0 for key in _singleton_instance.vertex_api_keys
                }
                for key, count in _preserved_vertex_usage_counts.items():
                    if key in current_vertex_usage_counts:
                        current_vertex_usage_counts[key] = count
                _singleton_instance.vertex_key_usage_counts = current_vertex_usage_counts
                logger.info("Inherited usage counts for applicable Vertex keys.")
            _preserved_vertex_usage_counts = None

            # 1.6. 恢复固定key索引
            if _preserved_fixed_key_index is not None and _singleton_instance.api_keys:
                _singleton_instance.current_fixed_key_index = min(
                    _preserved_fixed_key_index, len(_singleton_instance.api_keys) - 1
                )
                logger.info(f"Inherited fixed key index: {_singleton_instance.current_fixed_key_index}")
            _preserved_fixed_key_index = None

            if _preserved_vertex_fixed_key_index is not None and _singleton_instance.vertex_api_keys:
                _singleton_instance.current_vertex_fixed_key_index = min(
                    _preserved_vertex_fixed_key_index, len(_singleton_instance.vertex_api_keys) - 1
                )
                logger.info(f"Inherited vertex fixed key index: {_singleton_instance.current_vertex_fixed_key_index}")
            _preserved_vertex_fixed_key_index = None

            # 2. 调整 key_cycle 的起始点
            start_key_for_new_cycle = None
            if (
                _preserved_old_api_keys_for_reset
                and _preserved_next_key_in_cycle
                and _singleton_instance.api_keys
            ):
                try:
                    start_idx_in_old = _preserved_old_api_keys_for_reset.index(
                        _preserved_next_key_in_cycle
                    )

                    for i in range(len(_preserved_old_api_keys_for_reset)):
                        current_old_key_idx = (start_idx_in_old + i) % len(
                            _preserved_old_api_keys_for_reset
                        )
                        key_candidate = _preserved_old_api_keys_for_reset[
                            current_old_key_idx
                        ]
                        if key_candidate in _singleton_instance.api_keys:
                            start_key_for_new_cycle = key_candidate
                            break
                except ValueError:
                    logger.warning(
                        f"Preserved next key '{_preserved_next_key_in_cycle}' not found in preserved old API keys. "
                        "New cycle will start from the beginning of the new list."
                    )
                except Exception as e:
                    logger.error(
                        f"Error determining start key for new cycle from preserved state: {e}. "
                        "New cycle will start from the beginning."
                    )

            if start_key_for_new_cycle and _singleton_instance.api_keys:
                try:
                    target_idx = _singleton_instance.api_keys.index(
                        start_key_for_new_cycle
                    )
                    for _ in range(target_idx):
                        next(_singleton_instance.key_cycle)
                    logger.info(
                        f"Key cycle in new instance advanced. Next call to get_next_key() will yield: {start_key_for_new_cycle}"
                    )
                except ValueError:
                    logger.warning(
                        f"Determined start key '{start_key_for_new_cycle}' not found in new API keys during cycle advancement. "
                        "New cycle will start from the beginning."
                    )
                except StopIteration:
                    logger.error(
                        "StopIteration while advancing key cycle, implies empty new API key list previously missed."
                    )
                except Exception as e:
                    logger.error(
                        f"Error advancing new key cycle: {e}. Cycle will start from beginning."
                    )
            else:
                if _singleton_instance.api_keys:
                    logger.info(
                        "New key cycle will start from the beginning of the new API key list (no specific start key determined or needed)."
                    )
                else:
                    logger.info(
                        "New key cycle not applicable as the new API key list is empty."
                    )

            # 清理所有保存的状态
            _preserved_old_api_keys_for_reset = None
            _preserved_next_key_in_cycle = None

            # 3. 调整 vertex_key_cycle 的起始点
            start_key_for_new_vertex_cycle = None
            if (
                _preserved_vertex_old_api_keys_for_reset
                and _preserved_vertex_next_key_in_cycle
                and _singleton_instance.vertex_api_keys
            ):
                try:
                    start_idx_in_old = _preserved_vertex_old_api_keys_for_reset.index(
                        _preserved_vertex_next_key_in_cycle
                    )

                    for i in range(len(_preserved_vertex_old_api_keys_for_reset)):
                        current_old_key_idx = (start_idx_in_old + i) % len(
                            _preserved_vertex_old_api_keys_for_reset
                        )
                        key_candidate = _preserved_vertex_old_api_keys_for_reset[
                            current_old_key_idx
                        ]
                        if key_candidate in _singleton_instance.vertex_api_keys:
                            start_key_for_new_vertex_cycle = key_candidate
                            break
                except ValueError:
                    logger.warning(
                        f"Preserved next key '{_preserved_vertex_next_key_in_cycle}' not found in preserved old Vertex Express API keys. "
                        "New cycle will start from the beginning of the new list."
                    )
                except Exception as e:
                    logger.error(
                        f"Error determining start key for new Vertex key cycle from preserved state: {e}. "
                        "New cycle will start from the beginning."
                    )

            if start_key_for_new_vertex_cycle and _singleton_instance.vertex_api_keys:
                try:
                    target_idx = _singleton_instance.vertex_api_keys.index(
                        start_key_for_new_vertex_cycle
                    )
                    for _ in range(target_idx):
                        next(_singleton_instance.vertex_key_cycle)
                    logger.info(
                        f"Vertex key cycle in new instance advanced. Next call to get_next_vertex_key() will yield: {start_key_for_new_vertex_cycle}"
                    )
                except ValueError:
                    logger.warning(
                        f"Determined start key '{start_key_for_new_vertex_cycle}' not found in new Vertex Express API keys during cycle advancement. "
                        "New cycle will start from the beginning."
                    )
                except StopIteration:
                    logger.error(
                        "StopIteration while advancing Vertex key cycle, implies empty new Vertex Express API key list previously missed."
                    )
                except Exception as e:
                    logger.error(
                        f"Error advancing new Vertex key cycle: {e}. Cycle will start from beginning."
                    )
            else:
                if _singleton_instance.vertex_api_keys:
                    logger.info(
                        "New Vertex key cycle will start from the beginning of the new Vertex Express API key list (no specific start key determined or needed)."
                    )
                else:
                    logger.info(
                        "New Vertex key cycle not applicable as the new Vertex Express API key list is empty."
                    )

            # 清理所有保存的状态
            _preserved_vertex_old_api_keys_for_reset = None
            _preserved_vertex_next_key_in_cycle = None

        return _singleton_instance


async def reset_key_manager_instance():
    """
    重置 KeyManager 单例实例。
    将保存当前实例的状态（失败计数、旧 API keys、下一个 key 提示）
    以供下一次 get_key_manager_instance 调用时恢复。
    """
    global _singleton_instance, _preserved_failure_counts, _preserved_vertex_failure_counts, _preserved_old_api_keys_for_reset, _preserved_vertex_old_api_keys_for_reset, _preserved_next_key_in_cycle, _preserved_vertex_next_key_in_cycle, _preserved_usage_counts, _preserved_vertex_usage_counts, _preserved_fixed_key_index, _preserved_vertex_fixed_key_index
    async with _singleton_lock:
        if _singleton_instance:
            # 1. 保存失败计数
            _preserved_failure_counts = _singleton_instance.key_failure_counts.copy()
            _preserved_vertex_failure_counts = (
                _singleton_instance.vertex_key_failure_counts.copy()
            )

            # 1.5. 保存使用计数
            _preserved_usage_counts = _singleton_instance.key_usage_counts.copy()
            _preserved_vertex_usage_counts = _singleton_instance.vertex_key_usage_counts.copy()

            # 1.6. 保存固定key索引
            _preserved_fixed_key_index = _singleton_instance.current_fixed_key_index
            _preserved_vertex_fixed_key_index = _singleton_instance.current_vertex_fixed_key_index

            # 2. 保存旧的 API keys 列表
            _preserved_old_api_keys_for_reset = _singleton_instance.api_keys.copy()
            _preserved_vertex_old_api_keys_for_reset = (
                _singleton_instance.vertex_api_keys.copy()
            )

            # 3. 保存 key_cycle 的下一个 key 提示
            try:
                if _singleton_instance.api_keys:
                    _preserved_next_key_in_cycle = (
                        await _singleton_instance.get_next_key()
                    )
                else:
                    _preserved_next_key_in_cycle = None
            except StopIteration:
                logger.warning(
                    "Could not preserve next key hint: key cycle was empty or exhausted in old instance."
                )
                _preserved_next_key_in_cycle = None
            except Exception as e:
                logger.error(f"Error preserving next key hint during reset: {e}")
                _preserved_next_key_in_cycle = None

            # 4. 保存 vertex_key_cycle 的下一个 key 提示
            try:
                if _singleton_instance.vertex_api_keys:
                    _preserved_vertex_next_key_in_cycle = (
                        await _singleton_instance.get_next_vertex_key()
                    )
                else:
                    _preserved_vertex_next_key_in_cycle = None
            except StopIteration:
                logger.warning(
                    "Could not preserve next key hint: Vertex key cycle was empty or exhausted in old instance."
                )
                _preserved_vertex_next_key_in_cycle = None
            except Exception as e:
                logger.error(f"Error preserving next key hint during reset: {e}")
                _preserved_vertex_next_key_in_cycle = None

            _singleton_instance = None
            logger.info(
                "KeyManager instance has been reset. State (failure counts, old keys, next key hint) preserved for next instantiation."
            )
        else:
            logger.info(
                "KeyManager instance was not set (or already reset), no reset action performed."
            )
