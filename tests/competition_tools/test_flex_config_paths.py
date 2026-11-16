"""Private Flex configuration must tolerate an empty non-repository marker."""

import json
import os

import pytest

from competition_tools.competition_review.flex_client import FlexError, load_config


def config_file(tmp_path):
    owner = tmp_path / "private-owner"
    owner.mkdir()
    path = owner / "config" / "flex.json"
    path.parent.mkdir()
    path.write_text(
        json.dumps(
            {
                "token": "123456789012345678",
                "query_id": "12345",
                "expected_account": "SIMULATED",
                "account_ref": "synthetic-paper",
                "base_currency": "SGD",
            }
        )
    )
    path.chmod(0o600)
    return owner, path


def test_empty_ancestor_marker_is_not_a_source_repository(tmp_path):
    owner, path = config_file(tmp_path)
    (owner / ".git").mkdir()
    result = load_config(path)
    assert result.account_ref == "synthetic-paper"
    assert result.base_currency == "SGD"
    assert "123456789012345678" not in repr(result)


def test_collection_accepts_validated_private_config_beneath_empty_marker(tmp_path):
    from competition_tools.competition_review.flex_cli import collect
    from competition_tools.competition_review.flex_client import FlexError
    from competition_tools.crypto_evidence import verify_seal

    owner, path = config_file(tmp_path)
    (owner / ".git").mkdir()

    def stop(*args, **kwargs):
        raise FlexError("FLEX_TRANSPORT_UNAVAILABLE")

    out = tmp_path / "outside-private-config"
    result = collect(path, out, transport=stop)
    assert result["status"] == "blocked"
    assert result["issue_code"] == "FLEX_TRANSPORT_UNAVAILABLE"
    verify_seal(out)


def test_output_cannot_overlap_private_config(tmp_path):
    from competition_tools.competition_review.flex_cli import collect

    owner, path = config_file(tmp_path)
    with pytest.raises(ValueError):
        collect(path, owner)


@pytest.mark.parametrize("marker", ["directory", "file", "symlink"])
def test_actual_repository_markers_and_symlinks_still_block_credentials(
    tmp_path, marker
):
    owner, path = config_file(tmp_path)
    git = owner / ".git"
    if marker == "directory":
        git.mkdir()
        (git / "HEAD").write_text("ref: refs/heads/main\n")
    elif marker == "file":
        git.write_text("gitdir: /not-used\n")
    else:
        if os.name == "nt":
            pytest.skip("Symbolic links require elevated Windows privileges")
        target = tmp_path / "empty"
        target.mkdir()
        git.symlink_to(target, target_is_directory=True)
    with pytest.raises(FlexError):
        load_config(path)
