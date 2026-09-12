import json
import os
import subprocess
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value), encoding="utf-8")


def prepare_release_project(
    root: Path,
    imports: list[str] | None = None,
    languages: dict[str, str] | None = None,
    mxu: bool = False,
) -> None:
    root.mkdir(exist_ok=True)
    write_json(root / "maa-project.lock.json", {"pending": []})
    write_json(
        root / "maa-project.json",
        {"runtime": {"mfa": {"enabled": not mxu}, "mxu": {"enabled": mxu}}},
    )
    interface: dict[str, object] = {
        "name": "m9a",
        "version": "v0.1.0",
        "resource": [],
        "import": imports or [],
        "agent": [{}],
    }
    if languages is not None:
        interface["languages"] = languages
    write_json(root / "interface.json", interface)

    for relative_path in (
        "tasks",
        "resource",
        "runtimes/win-x64/native",
        "libs/MaaAgentBinary",
        "plugins",
        "agent/__pycache__",
        ".create-maa-project/runtime/mfaa/win-x64",
        ".create-maa-project/runtime/mxu/win-x64",
        ".create-maa-project/runtime/python/win-x64",
    ):
        (root / relative_path).mkdir(parents=True)

    (root / "runtimes/win-x64/native/MaaPiCli.exe").write_bytes(b"cli")
    (root / "runtimes/win-x64/native/MaaFramework.dll").write_bytes(b"maafw")
    (root / ".create-maa-project/runtime/mfaa/win-x64/MFAAvalonia.exe").write_bytes(b"gui")
    (root / ".create-maa-project/runtime/mxu/win-x64/mxu.exe").write_bytes(b"gui")
    (root / ".create-maa-project/runtime/python/win-x64/python.exe").write_bytes(b"python")
    (root / "agent/bootstrap.py").write_text("# bootstrap\n", encoding="utf-8")
    (root / "agent/main.py").write_text("# main\n", encoding="utf-8")
    (root / "agent/__pycache__/main.cpython-313.pyc").write_bytes(b"cache")
    (root / "agent/main.pyo").write_bytes(b"cache")
    (root / "requirements.txt").write_text("maafw\n", encoding="utf-8")


def run_release_builder(root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            "node",
            str(PROJECT_ROOT / "tools" / "build-release.mjs"),
            "--release-tag",
            "v0.0.0-test",
        ],
        cwd=root,
        env={**os.environ, "CREATE_MAA_PROJECT_RUNTIME_PLATFORM": "win-x64"},
        capture_output=True,
        text=True,
        check=False,
    )


def test_release_agent_child_args_per_platform() -> None:
    script_url = (PROJECT_ROOT / "tools" / "build-release.mjs").as_uri()
    code = (
        "import {releaseAgentChildArgs} from " + json.dumps(script_url) + ";"
        "console.log(JSON.stringify(["
        "releaseAgentChildArgs('win-x64'),"
        "releaseAgentChildArgs('osx-arm64'),"
        "releaseAgentChildArgs('linux-x64')"
        "]));"
    )
    result = subprocess.run(
        ["node", "--input-type=module", "-e", code],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert json.loads(result.stdout.strip().splitlines()[-1]) == [
        ["-u", "agent/main.py"],
        ["-u", "agent/main.py"],
        ["-u", "agent/bootstrap.py"],
    ]


def test_release_gui_agent_config_matches_platform() -> None:
    script_url = (PROJECT_ROOT / "tools" / "build-release.mjs").as_uri()
    code = (
        "import {releaseGuiInterface} from " + json.dumps(script_url) + ";"
        "const base = {name: 'm9a', agent: [{child_exec: 'uv', child_args: ['run', 'python', 'agent/main.py']}]};"
        "const configs = {};"
        "for (const gui of ['mfaa', 'mxu']) {"
        "for (const platform of ['win-x64', 'osx-arm64', 'linux-x64']) {"
        "configs[gui + ':' + platform] = releaseGuiInterface(gui, base, 'v0.0.0-test', platform).agent[0];"
        "}"
        "}"
        "console.log(JSON.stringify(configs));"
    )
    result = subprocess.run(
        ["node", "--input-type=module", "-e", code],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert json.loads(result.stdout.strip().splitlines()[-1]) == {
        "mfaa:win-x64": {"child_exec": "python/python.exe", "child_args": ["-u", "agent/main.py"]},
        "mfaa:osx-arm64": {"child_exec": "python/bin/python3", "child_args": ["-u", "agent/main.py"]},
        "mfaa:linux-x64": {"child_exec": "python3", "child_args": ["-u", "agent/bootstrap.py"]},
        "mxu:win-x64": {"child_exec": "python/python.exe", "child_args": ["-u", "agent/main.py"]},
        "mxu:osx-arm64": {"child_exec": "python/bin/python3", "child_args": ["-u", "agent/main.py"]},
        "mxu:linux-x64": {"child_exec": "python3", "child_args": ["-u", "agent/bootstrap.py"]},
    }


def test_release_wheelhouse_path_maps_to_deps_directory() -> None:
    script_url = (PROJECT_ROOT / "tools" / "build-release.mjs").as_uri()
    code = (
        "import {linuxPythonDepsPath, releasePackagePath} from " + json.dumps(script_url) + ";"
        "const platforms = ['linux-x64', 'linux-arm64'];"
        "const backslash = String.fromCharCode(92);"
        "console.log(JSON.stringify({"
        "source: platforms.map((p) => linuxPythonDepsPath(p)),"
        "mapped: platforms.map((p) => releasePackagePath(linuxPythonDepsPath(p))),"
        "hostStyle: releasePackagePath(['.create-maa-project', 'runtime', 'python-deps', 'linux-x64'].join(backslash)),"
        "passthrough: ['agent', 'requirements.txt'].map((p) => releasePackagePath(p))"
        "}));"
    )
    result = subprocess.run(
        ["node", "--input-type=module", "-e", code],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    packages = json.loads(result.stdout.strip().splitlines()[-1])
    # A Linux package can be cross-built on Windows, where join() would produce backslashes
    # and the wheelhouse would land in the package as .create-maa-project/... instead of deps/.
    assert packages["source"] == [
        ".create-maa-project/runtime/python-deps/linux-x64",
        ".create-maa-project/runtime/python-deps/linux-arm64",
    ]
    assert packages["mapped"] == ["deps", "deps"]
    assert packages["hostStyle"] == "deps"
    assert packages["passthrough"] == ["agent", "requirements.txt"]


def test_release_package_excludes_python_cache_files(tmp_path: Path) -> None:
    prepare_release_project(tmp_path)
    result = run_release_builder(tmp_path)

    assert result.returncode == 0, result.stdout + result.stderr
    package_root = tmp_path / "dist/package-mfaa"
    package_agent = package_root / "agent"
    assert (package_agent / "bootstrap.py").is_file()
    assert (package_agent / "main.py").is_file()
    assert not (package_agent / "__pycache__").exists()
    assert not (package_agent / "main.pyo").exists()
    packaged_interface = json.loads((package_root / "interface.json").read_text(encoding="utf-8"))
    assert packaged_interface["agent"][0]["child_args"] == ["-u", "agent/main.py"]
    # win/mac runtimes ship with preinstalled dependencies: no wheelhouse inputs
    assert not (package_root / "requirements.txt").exists()
    assert not (package_root / "python/.create-maa-project-requirements.sha256").exists()


def test_release_mxu_package_keeps_agent_command(tmp_path: Path) -> None:
    prepare_release_project(tmp_path, mxu=True)

    result = run_release_builder(tmp_path)

    assert result.returncode == 0, result.stdout + result.stderr
    assert not (tmp_path / "dist/package-mfaa").exists()
    package_root = tmp_path / "dist/package-mxu"
    assert (package_root / "m9a.exe").is_file()
    packaged_interface = json.loads((package_root / "interface.json").read_text(encoding="utf-8"))
    assert packaged_interface["mirrorchyan_rid"] == "M9A-MXU"
    assert packaged_interface["agent"][0]["child_exec"] == "python/python.exe"
    # The MXU package must not re-declare the Agent command: on Linux it has to go through
    # agent/bootstrap.py, otherwise the .venv is never built and dependencies are never installed.
    assert packaged_interface["agent"][0]["child_args"] == ["-u", "agent/main.py"]
    # MXU packages use the maafw layout instead of top-level runtimes/libs/plugins
    for relative_path in ("runtimes", "libs", "plugins"):
        assert not (package_root / relative_path).exists()
    assert (package_root / "maafw/MaaFramework.dll").is_file()
    assert not (package_root / "maafw/MaaPiCli.exe").exists()
    assert (package_root / "maafw/MaaAgentBinary").is_dir()
    assert (package_root / "python/python.exe").is_file()


def test_release_package_includes_translation_files(tmp_path: Path) -> None:
    languages = {"zh_cn": "i18n/zh_cn.json", "en_us": "i18n/en_us.json"}
    prepare_release_project(tmp_path, languages=languages)
    (tmp_path / "i18n").mkdir()
    for relative_path in languages.values():
        write_json(tmp_path / relative_path, {"Task.Demo": "demo"})

    result = run_release_builder(tmp_path)

    assert result.returncode == 0, result.stdout + result.stderr
    package_root = tmp_path / "dist/package-mfaa"
    for relative_path in languages.values():
        assert (package_root / relative_path).is_file(), f"{relative_path} is missing from the package"
    packaged_interface = json.loads((package_root / "interface.json").read_text(encoding="utf-8"))
    assert packaged_interface["languages"] == languages


def test_release_package_omits_i18n_when_no_languages_declared(tmp_path: Path) -> None:
    prepare_release_project(tmp_path)

    result = run_release_builder(tmp_path)

    assert result.returncode == 0, result.stdout + result.stderr
    assert not (tmp_path / "dist/package-mfaa/i18n").exists()


def test_release_builder_rejects_unsafe_language_paths(tmp_path: Path) -> None:
    outside_path = tmp_path / "outside.json"
    outside_path.write_text("{}\n", encoding="utf-8")

    for index, unsafe_path in enumerate(("../outside.json", outside_path.resolve().as_posix())):
        project_root = tmp_path / f"language-project-{index}"
        prepare_release_project(project_root, languages={"zh_cn": unsafe_path})

        result = run_release_builder(project_root)

        assert result.returncode != 0
        assert "release paths must stay within the project root" in result.stdout + result.stderr


def test_release_builder_rejects_paths_outside_project_root(tmp_path: Path) -> None:
    outside_path = tmp_path / "outside.json"
    outside_path.write_text("{}\n", encoding="utf-8")

    for index, unsafe_path in enumerate(("", ".", "../outside.json", outside_path.resolve().as_posix())):
        project_root = tmp_path / f"project-{index}"
        prepare_release_project(project_root, [unsafe_path])

        result = run_release_builder(project_root)

        assert result.returncode != 0
        assert "release paths must stay within the project root" in result.stdout + result.stderr
