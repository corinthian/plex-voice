"""
Intent mapping examples for plexctl voice interface.

These tests document expected voice -> argv mappings for a future intent parser.
They do not test plexctl itself — they validate that each example has a well-formed
argv where argv[0] == "plexctl".
"""

import pytest

INTENT_EXAMPLES = [
    # Transport
    ("pause the Apple TV", ["plexctl", "pause"]),
    ("resume", ["plexctl", "play"]),
    ("unpause", ["plexctl", "play"]),
    ("stop playback", ["plexctl", "stop"]),
    ("skip forward", ["plexctl", "next"]),
    ("go back", ["plexctl", "prev"]),
    ("previous episode", ["plexctl", "prev"]),
    # Seek — absolute
    ("seek to 2:15", ["plexctl", "seek", "2:15"]),
    ("go to one minute thirty", ["plexctl", "seek", "1:30"]),
    # Seek — relative
    ("skip ahead 30 seconds", ["plexctl", "seek", "+30s"]),
    ("go back 10 seconds", ["plexctl", "seek", "-10s"]),
    # Volume
    ("set volume to 40", ["plexctl", "volume", "40"]),
    ("volume 75", ["plexctl", "volume", "75"]),
    # Search
    ("search for Dune", ["plexctl", "search", "Dune"]),
    ("find The Bear", ["plexctl", "search", "The Bear"]),
    # play-latest — default client
    ("play Strange New Worlds", ["plexctl", "play-latest", "Strange New Worlds"]),
    ("play the latest The Bear", ["plexctl", "play-latest", "The Bear"]),
    # play-latest — with --unwatched
    (
        "play next episode of Strange New Worlds",
        ["plexctl", "play-latest", "Strange New Worlds", "--unwatched"],
    ),
    (
        "play the next unwatched episode of The Bear",
        ["plexctl", "play-latest", "The Bear", "--unwatched"],
    ),
    # play-latest — explicit client
    (
        "play the latest Strange New Worlds on the TV",
        ["plexctl", "play-latest", "Strange New Worlds", "--client", "Apple TV"],
    ),
    # play-media
    ("play media 12345", ["plexctl", "play-media", "12345"]),
    (
        "play media 12345 on the bedroom TV",
        ["plexctl", "play-media", "12345", "--client", "Bedroom TV"],
    ),
    # Clients / status
    ("what's playing", ["plexctl", "now-playing"]),
    ("what's on", ["plexctl", "now-playing"]),
    ("list available clients", ["plexctl", "clients"]),
    # Now-playing / status
    ("mark this watched", ["plexctl", "watched"]),
    ("mark as unwatched", ["plexctl", "unwatched"]),
    ("rate this 8", ["plexctl", "rate", "8"]),
    ("continue watching", ["plexctl", "continue-watching"]),
    ("what did I watch", ["plexctl", "history"]),
    # pause with explicit client
    ("pause on the bedroom TV", ["plexctl", "pause", "--client", "Bedroom TV"]),
    # Queue management
    ("show the queue", ["plexctl", "queue-show"]),
    ("what's in the queue", ["plexctl", "queue-show"]),
    ("shuffle the queue", ["plexctl", "queue-shuffle"]),
    ("stop shuffling", ["plexctl", "queue-unshuffle"]),
    ("clear the queue", ["plexctl", "queue-clear"]),
]


@pytest.mark.parametrize("phrase,argv", INTENT_EXAMPLES)
def test_intent_has_argv(phrase, argv):
    assert len(argv) >= 1, f"argv empty for phrase: {phrase!r}"
    assert argv[0] == "plexctl", f"argv[0] != 'plexctl' for phrase: {phrase!r}"


@pytest.mark.parametrize("phrase,argv", INTENT_EXAMPLES)
def test_intent_subcommand_present(phrase, argv):
    """Every mapping must specify a subcommand."""
    assert len(argv) >= 2, f"No subcommand for phrase: {phrase!r}"


@pytest.mark.parametrize("phrase,argv", INTENT_EXAMPLES)
def test_intent_subcommand_valid(phrase, argv):
    valid = {
        "auth", "clients", "play", "pause", "stop", "seek",
        "next", "prev", "volume", "search", "play-latest", "play-media",
        "queue-show", "queue-shuffle", "queue-unshuffle", "queue-clear", "queue-remove",
        "now-playing", "watched", "unwatched", "rate", "continue-watching", "history",
    }
    assert argv[1] in valid, f"Unknown subcommand {argv[1]!r} for phrase: {phrase!r}"
