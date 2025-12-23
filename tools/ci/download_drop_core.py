"""
下载 drop_core 模块

从私有仓库的 release 下载对应平台的 drop_core 模块
"""

import os
import sys
import platform
import urllib.request
import zipfile
import shutil

# 私有仓库信息
PRIVATE_REPO = "MAA1999/drop-upload-sign"  # 修改为你的私有仓库
RELEASE_TAG = "v1.2.0"  # 修改为要下载的版本

# 目标目录
DEST_DIR = os.path.join("agent", "libs")


def get_platform_info():
    """获取当前平台信息"""
    os_type = platform.system().lower()
    os_arch = platform.machine().lower()

    # 标准化架构名称
    arch_mapping = {
        "amd64": "x64",
        "x86_64": "x64",
        "arm64": "arm64",
        "aarch64": "arm64",
    }

    # Windows ARM64 检测
    if os_type == "windows":
        processor_id = os.environ.get("PROCESSOR_IDENTIFIER", "")
        if "ARM" in processor_id.upper():
            os_arch = "arm64"

    arch = arch_mapping.get(os_arch, os_arch)

    # 平台标签
    if os_type == "windows":
        platform_tag = f"win-{arch}"
    elif os_type == "darwin":
        platform_tag = f"macos-{'x86_64' if arch == 'x64' else 'aarch64'}"
    elif os_type == "linux":
        platform_tag = f"linux-{arch}"
    else:
        platform_tag = f"{os_type}-{arch}"

    return os_type, arch, platform_tag


def get_python_version():
    """获取 Python 版本"""
    return f"{sys.version_info.major}.{sys.version_info.minor}"


def download_file(url, dest_path, token=None):
    """下载文件"""
    print(f"下载: {url}")
    print(f"到: {dest_path}")

    os.makedirs(os.path.dirname(dest_path), exist_ok=True)

    request = urllib.request.Request(url)
    if token:
        request.add_header("Authorization", f"token {token}")
    request.add_header("Accept", "application/octet-stream")

    try:
        with urllib.request.urlopen(request) as response:
            with open(dest_path, "wb") as f:
                shutil.copyfileobj(response, f)
        print("下载完成")
        return True
    except urllib.error.HTTPError as e:
        print(f"HTTP 错误 {e.code}: {e.reason}")
        return False
    except Exception as e:
        print(f"下载失败: {e}")
        return False


def main():
    # 获取 token（从环境变量）
    token = os.environ.get("PRIVATE_REPO_TOKEN")
    if not token:
        print("警告: PRIVATE_REPO_TOKEN 未设置，可能无法访问私有仓库")

    # 获取平台信息
    os_type, arch, platform_tag = get_platform_info()
    py_version = get_python_version()

    print(f"平台: {os_type}, 架构: {arch}, Python: {py_version}")

    # 构造下载列表
    # macOS 不带 Python 版本
    # Linux 需要下载所有 Python 版本（用户可能用不同版本）
    # Windows 只下载当前版本
    if os_type == "darwin":
        artifacts = [f"drop_core-{platform_tag}-{RELEASE_TAG}"]
    elif os_type == "linux":
        # Linux 下载所有支持的 Python 版本
        linux_py_versions = ["3.11", "3.12", "3.13"]
        artifacts = [
            f"drop_core-{platform_tag}-py{v}-{RELEASE_TAG}" for v in linux_py_versions
        ]
    else:
        artifacts = [f"drop_core-{platform_tag}-py{py_version}-{RELEASE_TAG}"]

    # 下载所有需要的文件
    success_count = 0
    for artifact_name in artifacts:
        download_url = f"https://github.com/{PRIVATE_REPO}/releases/download/{RELEASE_TAG}/{artifact_name}.zip"
        zip_path = os.path.join(DEST_DIR, f"{artifact_name}.zip")

        if download_file(download_url, zip_path, token):
            # 解压
            print(f"解压: {artifact_name}")
            try:
                with zipfile.ZipFile(zip_path, "r") as zf:
                    zf.extractall(DEST_DIR)
                os.remove(zip_path)
                success_count += 1
            except Exception as e:
                print(f"解压失败: {e}")
        else:
            print(f"下载失败: {artifact_name}")

    if success_count == 0:
        print("没有成功下载任何文件，跳过 drop_core 模块")
        return False

    # 列出文件
    print("已安装的文件:")
    for f in os.listdir(DEST_DIR):
        if f.endswith((".pyd", ".so")):
            print(f"  {f}")

    return True


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
