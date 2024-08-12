from kaniko_deploy.main import main
import subprocess

cases = ["python ..\kaniko_deploy\main.py deploy --context_dir=git://github.com//Imoustak/kaniko-build-demo.git --docker_filepath=dockerfile --docker_username=pratikuk --docker_email=pratikuk26@gmail.com --docker_repo=testing-first-time"]

def test_main(monkeypatch):
    monkeypatch = monkeypatch.setattr(
        "builtins.input", lambda _: "dckr_pat_dRtU1Ah3w90Ad9uCBiJUWYPA29s"
    )
    # main(
    #     cmd="deploy",
    #     context_dir="git://github.com//Imoustak/kaniko-build-demo.git",
    #     docker_filepath="dockerfile",
    #     no_push=False,
    #     docker_username="pratikuk",
    #     docker_repo="testing-first-time",
    #     docker_email="pratikuk26@gmail.com",
    # )

    result = subprocess.run(
        cases[0],
        capture_output=True, text=True
    )
    print(result)
    # assert result.returncode != 0
    # assert "error" in result.stderr.lower()
