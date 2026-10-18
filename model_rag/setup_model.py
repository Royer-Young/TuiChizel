from pathlib import Path

from modelscope import snapshot_download

print("正在检查本地模型...")
# 默认下载到项目根目录的 models 文件夹下（不依赖从哪个目录运行）
model_dir = Path(__file__).resolve().parents[1] / "models"
model_dir.mkdir(parents=True, exist_ok=True)

try:
    print("正在下载/校验 bge-small-zh-v1.5 模型（首次运行需等待）...")
    # 使用国内魔搭社区下载
    downloaded_path = snapshot_download(
        "AI-ModelScope/bge-small-zh-v1.5", cache_dir=str(model_dir)
    )
    print(f"\n✅ 模型下载成功！真实路径为：\n{downloaded_path}")
    print(
        "\n后端会自动在 models/ 下查找 bge 模型，通常不需要手动配置。"
        "\n如果路径不同，把上面这行写进 .env 的 BGE_MODEL_PATH=... 即可。"
    )
except Exception as e:
    print(f"\n❌ 下载失败: {e}")