"""Release-budget, complete-matrix and exact-version regression checks."""
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('pypi_size', ROOT/'tools/check_pypi_size.py')
size = importlib.util.module_from_spec(spec)
spec.loader.exec_module(size)


def release(directory, count=18, version='0.4.8'):
    matrix = [(python, platform) for python in ('cp39', 'cp310', 'cp311', 'cp312', 'cp313', 'cp314')
              for platform in ('manylinux_2_28_x86_64', 'win_amd64', 'macosx_11_0_arm64')]
    for python, platform in matrix[:count]:
        (directory/f'dancerudiments-{version}-{python}-{python}-{platform}.whl').write_bytes(b'w'*100)
    (directory/f'dancerudiments-{version}.tar.gz').write_bytes(b's'*200)


def test_reviewed_budget_and_complete_release(tmp_path):
    budget = size.load_budget()
    assert budget['release_wheel_count'] == 18
    release(tmp_path)
    matrix = {(python, platform) for python in budget['python_tags'] for platform in budget['platform_families']}
    assert size.inspect(tmp_path, 1, 1, 1, expected_wheels=18, expected_version='0.4.8', expected_matrix=matrix) == 0


def test_same_file_count_cannot_hide_a_missing_abi_or_architecture(tmp_path):
    release(tmp_path)
    matrix = {(python, platform) for python in size.load_budget()['python_tags']
              for platform in size.load_budget()['platform_families']}
    original = tmp_path/'dancerudiments-0.4.8-cp310-cp310-win_amd64.whl'
    duplicate = tmp_path/'dancerudiments-0.4.8-1-cp39-cp39-win_amd64.whl'
    original.rename(duplicate)
    assert size.inspect(tmp_path, 1, 1, 1, expected_wheels=18, expected_matrix=matrix) == 1
    duplicate.rename(tmp_path/'dancerudiments-0.4.8-cp310-cp310-macosx_11_0_x86_64.whl')
    assert size.inspect(tmp_path, 1, 1, 1, expected_wheels=18, expected_matrix=matrix) == 1


def test_compound_linux_tags_are_one_identity_and_abi_mismatch_is_rejected():
    assert size.wheel_identity('dancerudiments-0.4.8-cp313-cp313-manylinux_2_27_x86_64.manylinux_2_28_x86_64.whl') == ('cp313', 'linux_x86_64')
    assert size.wheel_identity('dancerudiments-0.4.8-cp314-cp313-win_amd64.whl') is None


def test_missing_or_extra_wheel_does_not_pass_aggregate_budget(tmp_path):
    release(tmp_path, count=17)
    assert size.inspect(tmp_path, 1, 1, 1, expected_wheels=18) == 1
    (tmp_path/'dancerudiments-0.4.8-extra1-none-test.whl').write_bytes(b'w')
    (tmp_path/'dancerudiments-0.4.8-extra2-none-test.whl').write_bytes(b'w')
    assert size.inspect(tmp_path, 1, 1, 1, expected_wheels=18) == 1


def test_wrong_version_cannot_be_combined_with_current_release(tmp_path):
    release(tmp_path)
    current = next(tmp_path.glob('*.whl'))
    current.rename(current.with_name(current.name.replace('0.4.8', '0.4.7')))
    assert size.inspect(tmp_path, 1, 1, 1, expected_wheels=18, expected_version='0.4.8') == 1


def test_individual_and_aggregate_limits_remain_independent(tmp_path):
    release(tmp_path)
    assert size.inspect(tmp_path, 0.00001, 1, 1) == 1
    assert size.inspect(tmp_path, 1, 0.00001, 1) == 1
    assert size.inspect(tmp_path, 1, 1, 0.0001) == 1


@pytest.mark.parametrize('bad', [0, -1, float('inf'), float('nan'), True])
def test_invalid_policy_or_cli_limit_is_rejected(tmp_path, bad):
    budget = size.load_budget()
    budget['max_wheel_mib'] = bad
    path = tmp_path/'budget.json'
    path.write_text(json.dumps(budget), encoding='utf-8')
    with pytest.raises(ValueError):
        size.load_budget(path)
    with pytest.raises(ValueError):
        size.inspect(tmp_path, bad, 1, 1)
