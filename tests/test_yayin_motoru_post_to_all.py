"""Tests for yayin-motoru.post_to_all feed+story behaviour.

NO REAL SENDS: every platform helper (publish_*_post / publish_*_story) is mocked
with unittest.mock, so no Meta/LinkedIn API is called, no .env is needed, and
paylasilan.json is never written (post_to_all does not touch it).

Runs under pytest OR standalone:
    python tests/test_yayin_motoru_post_to_all.py
"""
import importlib.util
import inspect
import sys
from pathlib import Path
from unittest import mock

MOD_PATH = Path(__file__).resolve().parent.parent / "scripts" / "yayin-motoru.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("yayin_motoru_under_test", MOD_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


ym = _load_module()

CAPTIONS = {"fb": "FB copy", "ig": "IG copy", "linkedin": "LI copy"}


def _ok(platform, pid):
    return {"success": True, "platform": platform, "post_id": pid}


def _fail(platform, err):
    return {"success": False, "platform": platform, "error": err}


def _feed(fb=None, ig=None, li=None):
    """Patch the three feed helpers; defaults to all-success."""
    return (
        mock.patch.object(ym, "publish_facebook_post", return_value=fb or _ok("facebook", "FB1")),
        mock.patch.object(ym, "publish_instagram_post", return_value=ig or _ok("instagram", "IG1")),
        mock.patch.object(ym, "publish_linkedin_post", return_value=li or _ok("linkedin", "LI1")),
    )


def test_feed_only_calls_three_helpers_and_returns_feed_keys():
    fb, ig, li = _feed()
    with fb as mfb, ig as mig, li as mli, \
         mock.patch.object(ym, "publish_facebook_story") as mfbs, \
         mock.patch.object(ym, "publish_instagram_story") as migs:
        out = ym.post_to_all(CAPTIONS, "/tmp/post.jpg")

    mfb.assert_called_once()
    mig.assert_called_once()
    mli.assert_called_once()
    # the right caption is routed to the right platform
    assert mfb.call_args.args[1] == "FB copy"
    assert mig.call_args.args[1] == "IG copy"
    assert mli.call_args.args[1] == "LI copy"
    # existing expected return keys preserved
    assert out["fb_post_id"] == "FB1"
    assert out["ig_post_id"] == "IG1"
    assert out["linkedin_post_urn"] == "LI1"
    # backward compatible: no story attempted/returned
    assert "stories" not in out
    mfbs.assert_not_called()
    migs.assert_not_called()


def test_story_publishes_feed_plus_fb_and_ig_stories():
    fb, ig, li = _feed()
    with fb, ig, li, \
         mock.patch.object(ym, "publish_facebook_story", return_value=_ok("facebook_story", "FBS1")) as mfbs, \
         mock.patch.object(ym, "publish_instagram_story", return_value=_ok("instagram_story", "IGS1")) as migs:
        out = ym.post_to_all(CAPTIONS, "/tmp/post.jpg", story_image_path="/tmp/story.jpg")

    mfbs.assert_called_once()
    migs.assert_called_once()
    # story helpers got the STORY image, not the feed image
    assert str(mfbs.call_args.args[0]).endswith("story.jpg")
    assert str(migs.call_args.args[0]).endswith("story.jpg")
    # feed result preserved alongside the nested story result
    assert out["fb_post_id"] == "FB1"
    assert out["stories"]["facebook_story_post_id"] == "FBS1"
    assert out["stories"]["instagram_story_post_id"] == "IGS1"


def test_no_story_key_when_story_image_absent():
    fb, ig, li = _feed()
    with fb, ig, li:
        out = ym.post_to_all(CAPTIONS, "/tmp/post.jpg")
    assert "stories" not in out


def test_story_failure_preserves_feed_success_and_reports():
    fb, ig, li = _feed()
    with fb, ig, li, \
         mock.patch.object(ym, "publish_facebook_story", return_value=_fail("facebook_story", "token expired")), \
         mock.patch.object(ym, "publish_instagram_story", return_value=_fail("instagram_story", "container error")):
        out = ym.post_to_all(CAPTIONS, "/tmp/post.jpg", story_image_path="/tmp/story.jpg")

    # feed success is NOT erased by the story failure
    assert out["fb_post_id"] == "FB1"
    assert out["ig_post_id"] == "IG1"
    assert out["linkedin_post_urn"] == "LI1"
    # story not faked: ids None + structured failure info
    assert out["stories"]["facebook_story_post_id"] is None
    assert out["stories"]["instagram_story_post_id"] is None
    assert out["stories"]["errors"]["facebook_story"] == "token expired"
    assert out["stories"]["errors"]["instagram_story"] == "container error"


def test_feed_failure_is_not_marked_success():
    fb, ig, li = _feed(fb=_fail("facebook", "no token"))
    with fb, ig, li:
        out = ym.post_to_all(CAPTIONS, "/tmp/post.jpg")
    # failed platform → None (never a fake id) + structured error; others unaffected
    assert out["fb_post_id"] is None
    assert out["errors"]["facebook"] == "no token"
    assert out["ig_post_id"] == "IG1"
    assert out["linkedin_post_urn"] == "LI1"


def test_linkedin_story_is_never_attempted():
    fb, ig, li = _feed()
    with fb, ig, li as mli, \
         mock.patch.object(ym, "publish_facebook_story", return_value=_ok("facebook_story", "FBS1")), \
         mock.patch.object(ym, "publish_instagram_story", return_value=_ok("instagram_story", "IGS1")):
        out = ym.post_to_all(CAPTIONS, "/tmp/post.jpg", story_image_path="/tmp/story.jpg")

    # LinkedIn is called once for the FEED only
    mli.assert_called_once()
    # no LinkedIn story anywhere in the result, and none in the story registry
    assert "linkedin" not in out["stories"]
    assert "linkedin_story" not in out["stories"]
    assert "linkedin" not in ym.STORY_PUBLISHERS


def test_raised_exception_in_story_is_caught_and_feed_preserved():
    # A helper that RAISES (network/timeout) must not unwind post_to_all and lose
    # the already-collected feed success — it is captured as a structured error.
    fb, ig, li = _feed()
    with fb, ig, li, \
         mock.patch.object(ym, "publish_facebook_story", side_effect=RuntimeError("network down")), \
         mock.patch.object(ym, "publish_instagram_story", return_value=_ok("instagram_story", "IGS1")):
        out = ym.post_to_all(CAPTIONS, "/tmp/post.jpg", story_image_path="/tmp/story.jpg")

    # feed intact despite the story exception
    assert out["fb_post_id"] == "FB1"
    assert out["ig_post_id"] == "IG1"
    assert out["linkedin_post_urn"] == "LI1"
    # raised exception captured (not fatal, not faked); the other story still recorded
    assert out["stories"]["facebook_story_post_id"] is None
    assert "network down" in out["stories"]["errors"]["facebook_story"]
    assert out["stories"]["instagram_story_post_id"] == "IGS1"


def test_signature_contains_story_image_path():
    params = inspect.signature(ym.post_to_all).parameters
    assert "story_image_path" in params
    assert params["story_image_path"].default is None


if __name__ == "__main__":
    import traceback

    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    passed = failed = 0
    for t in tests:
        try:
            t()
            print(f"PASS {t.__name__}")
            passed += 1
        except Exception:
            print(f"FAIL {t.__name__}")
            traceback.print_exc()
            failed += 1
    print(f"\n{passed} passed, {failed} failed")
    sys.exit(1 if failed else 0)
