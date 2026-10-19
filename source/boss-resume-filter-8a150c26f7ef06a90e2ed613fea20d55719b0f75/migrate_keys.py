"""
API Key 迁移工具 - 清理冗余的 keyring 条目

将旧版按模型存储的 API Key 迁移到按服务商 + Base URL 组合存储。
"""
import json
import sys
from pathlib import Path

# Windows PowerShell 编码兼容
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

from security import save_api_key, get_api_key, delete_api_key

BASE_DIR = Path(__file__).parent
API_CONFIG_PATH = BASE_DIR / "api_config.json"


def migrate():
    if not API_CONFIG_PATH.exists():
        print("配置文件不存在")
        return

    with open(API_CONFIG_PATH, 'r', encoding='utf-8') as f:
        config = json.load(f)

    saved_models = config.get("saved_models", [])
    if not saved_models:
        print("没有已保存的模型")
        return

    print(f"发现 {len(saved_models)} 个已保存的模型")
    print()

    # 按 provider + base_url 分组
    provider_urls = {}
    for model_config in saved_models:
        provider = model_config.get("api_provider", "unknown")
        base_url = model_config.get("base_url", "")
        key = (provider, base_url)
        if key not in provider_urls:
            provider_urls[key] = []
        provider_urls[key].append(model_config)

    # 检查每个 provider + base_url 组合的 API Key
    for (provider, base_url), models in provider_urls.items():
        print(f"检查服务商：{provider}（Base URL: {base_url}）")

        # 先检查是否已有按 provider + base_url 存储的 Key
        existing_key = get_api_key(provider, base_url)

        if existing_key:
            print(f"  ✓ {provider} 的 API Key 已按 provider+base_url 存储")
            continue

        # 回退检查旧的仅 provider 格式
        old_key_only = get_api_key(provider)
        if old_key_only:
            print(f"  迁移：从旧格式（仅 provider）读取 Key → 存储到 {provider}+{base_url}")
            save_api_key(provider, old_key_only, base_url)
            continue

        # 尝试从旧格式迁移
        migrated = False
        for model_config in models:
            # 旧版本的 api_key_ref 字段
            if model_config.get("api_key_ref"):
                # 尝试从 keyring 读取旧 Key
                old_key = None
                try:
                    from security import get_api_key as get_old_api_key
                    old_key = get_old_api_key(model_config["api_key_ref"])
                except Exception:
                    pass

                if old_key:
                    print(f"  迁移：从模型 '{model_config['model']}' 读取旧 Key → 存储到 {provider}+{base_url}")
                    save_api_key(provider, old_key, base_url)
                    migrated = True
                    break

        if not migrated:
            # 尝试从 api_key 明文读取（如果有）
            if config.get("api_key") and provider == config.get("api_provider") and base_url == config.get("base_url", ""):
                old_key = config.get("api_key")
                if old_key:
                    print(f"  迁移：从配置文件读取 {provider} 的 Key")
                    save_api_key(provider, old_key, base_url)
                    migrated = True

        if not migrated:
            print(f"  ⚠ {provider}+{base_url} 的 API Key 未找到，需要重新配置")

    # 清理 api_config.json 中的冗余字段
    for model_config in saved_models:
        model_config.pop("api_key_ref", None)
        model_config.pop("api_key", None)

    # 移除顶层 api_key
    config.pop("api_key", None)

    # 保存清理后的配置
    with open(API_CONFIG_PATH, 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=4)

    print()
    print("迁移完成！")
    print("- API Key 现在按 provider + base_url 组合存储（同一服务商不同接入方式独立管理）")
    print("- 配置文件中已移除冗余的 api_key_ref 字段")


def cleanup_old_keys():
    """清理 keyring 中旧的按模型存储的 API Key"""
    print("\n清理 keyring 中的冗余条目...")
    # 由于无法枚举 keyring 中的所有 key，这里只提示用户
    print("提示：keyring 中可能残留旧的 API Key 条目，不影响使用，可忽略")


if __name__ == "__main__":
    migrate()
    cleanup_old_keys()
