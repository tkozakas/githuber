from githuber.prs import Snapshot


def make_snapshot(**overrides):
    fields = {
        "repo": "org/repo",
        "number": 7,
        "title": "Title",
        "url": "https://x/7",
        "sha": "abc",
        "ci": "green",
        "conflicts": False,
        "reviews": (),
    }
    fields.update(overrides)
    return Snapshot(**fields)
