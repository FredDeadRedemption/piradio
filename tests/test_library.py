import pytest

from api import library


def test_accepts_every_supported_extension():
    for name in ("track.mp3", "track.FLAC", "track.opus", "track.wav"):
        assert library.safe_filename(name)


def test_rejects_anything_that_is_not_audio():
    with pytest.raises(library.LibraryError):
        library.safe_filename("payload.txt")


def test_strips_directories_from_an_uploaded_name():
    assert library.safe_filename("../../etc/passwd.mp3") == "passwd.mp3"
    assert library.safe_filename("/tmp/a b.mp3") == "a b.mp3"


def test_replaces_shell_and_path_characters():
    assert library.safe_filename("a;rm -rf$.mp3") == "a_rm -rf_.mp3"


def test_unique_path_never_overwrites(tmp_path):
    (tmp_path / "song.mp3").touch()
    assert library.unique_path(tmp_path, "song.mp3").name == "song-1.mp3"
    (tmp_path / "song-1.mp3").touch()
    assert library.unique_path(tmp_path, "song.mp3").name == "song-2.mp3"


@pytest.mark.parametrize("name", ["with/slash", "", "-leading", "x" * 49, "d\u00e9j\u00e0 vu"])
def test_rejects_bad_channel_names(name):
    with pytest.raises(library.LibraryError):
        library.create_channel(name)


def test_creates_and_lists_channels():
    library.create_channel("  Late Night  ")
    library.create_channel("jazz_hour")
    assert library.channels() == ["jazz_hour", "late night"]


def test_resolve_track_refuses_to_leave_its_pool():
    library.create_channel("jazz")
    (library.pool_dir("channel", "jazz") / "a.mp3").touch()
    assert library.resolve_track("channel", "a.mp3", "jazz").name == "a.mp3"
    with pytest.raises(library.LibraryError):
        library.resolve_track("channel", "../../../etc/passwd", "jazz")


def test_tracks_ignores_files_that_are_not_audio():
    directory = library.pool_dir("random")
    (directory / "b.mp3").touch()
    (directory / "notes.txt").touch()
    assert [t["name"] for t in library.tracks("random")] == ["b.mp3"]
