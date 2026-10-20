"""Command-line tool smoke test (simulator)."""


def test_cli_roles_scan_get(tmp_path, capsys):
    from vescentcomb.cli import main
    s = str(tmp_path / "s.json")
    assert main(["--sim", "--settings", s, "scan", "--save"]) == 0
    assert main(["--sim", "--settings", s, "roles"]) == 0
    assert "ffc" in capsys.readouterr().out
    assert main(["--sim", "--settings", s, "--json", "info", "ffc"]) == 0
    assert '"identity"' in capsys.readouterr().out
