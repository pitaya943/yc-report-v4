"""The storage contract: the same tests run against both real backends."""
import pytest

from spike.storage import (FileNotStored, StorageUnavailable,
                           storage_from_config)


def test_a_stored_file_reads_back_byte_for_byte(backend):
    storage = storage_from_config(backend.config)
    data = bytes(range(256)) * 1000  # larger than one chunk
    storage.put("a/b/one", data)
    assert b"".join(storage.open("a/b/one")) == data
    assert backend.stored_keys() == ["a/b/one"]


def test_opening_a_key_that_was_never_stored_says_so(backend):
    storage = storage_from_config(backend.config)
    with pytest.raises(FileNotStored):
        storage.open("nothing/here")


def test_delete_removes_the_file_from_the_backend(backend):
    storage = storage_from_config(backend.config)
    storage.put("a/one", b"1")
    storage.put("a/two", b"2")
    storage.delete("a/one")
    assert backend.stored_keys() == ["a/two"]
    with pytest.raises(FileNotStored):
        storage.open("a/one")


def test_deleting_a_missing_key_is_not_an_error(backend):
    storage_from_config(backend.config).delete("never/stored")


def test_no_storage_settings_means_not_configured_rather_than_a_crash():
    storage = storage_from_config({})
    assert storage.configured is False
    with pytest.raises(StorageUnavailable):
        storage.put("k", b"x")
    with pytest.raises(StorageUnavailable):
        storage.open("k")


def test_local_storage_refuses_a_key_that_points_outside_its_directory(tmp_path):
    root = tmp_path / "files"
    storage = storage_from_config(
        {"STORAGE_BACKEND": "local", "STORAGE_LOCAL_DIR": str(root)})
    with pytest.raises(ValueError):
        storage.put("../outside", b"x")
    assert not (tmp_path / "outside").exists()
