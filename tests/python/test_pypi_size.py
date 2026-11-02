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
    for index in range(count):
        (directory/f'dancerudiments-{version}-cp{index}-none-test.whl').write_bytes(b'w'*100)
    (directory/f'dancerudiments-{version}.tar.gz').write_bytes(b's'*200)


def test_reviewed_budget_and_complete_release(tmp_path):
    budget = size.load_budget()
    assert budget['release_wheel_count'] == 18
    release(tmp_path)
    assert size.inspect(tmp_path, 1, 1, 1, expected_wheels=18, expected_version='0.4.8') == 0


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
