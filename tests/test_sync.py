from playlistgit.models import PlaylistSnapshot, Service, Track
from playlistgit.sync import diff_snapshots


def test_diff_snapshots_reports_additive_differences() -> None:
    spotify = PlaylistSnapshot(
        playlist_name="Main",
        service=Service.SPOTIFY,
        service_playlist_id="sp",
        tracks=[
            Track(title="Shared", artists=["A"], isrc="1"),
            Track(title="Spotify Only", artists=["B"], isrc="2"),
        ],
    )
    ytmusic = PlaylistSnapshot(
        playlist_name="Main",
        service=Service.YOUTUBE_MUSIC,
        service_playlist_id="yt",
        tracks=[
            Track(title="Shared", artists=["A"], isrc="1"),
            Track(title="YT Only", artists=["C"], youtube_music_id="abc"),
        ],
    )

    diff = diff_snapshots(spotify, ytmusic, threshold=88)

    assert [match.source.title for match in diff.spotify_only] == ["Spotify Only"]
    assert [match.source.title for match in diff.youtube_music_only] == ["YT Only"]

