"""Abre a janela e os diálogos com dados simulados (sem rede)."""
from PySide6.QtCore import Qt

from getscope.core import formats
from getscope.core.settings import Settings

INFO = {
    "title": "Vídeo de teste", "uploader": "Canal", "duration": 754, "extractor_key": "Youtube",
    "view_count": 12345, "upload_date": "20261101", "webpage_url": "https://www.youtube.com/watch?v=x",
    "formats": [{"vcodec": "none", "acodec": "opus", "filesize": 3_000_000},
                {"height": 2160, "vcodec": "vp9", "acodec": "none", "filesize": 400_000_000},
                {"height": 1080, "vcodec": "avc1", "acodec": "none", "filesize": 90_000_000},
                {"height": 720, "vcodec": "avc1", "acodec": "none", "filesize": 40_000_000}],
}
PLAYLIST = {"_type": "playlist", "title": "Minha playlist", "uploader": "Canal", "extractor_key": "YoutubeTab",
            "entries": [{"url": f"https://www.youtube.com/watch?v=id{i}", "title": f"Item {i}", "duration": 60 * i,
                         "ie_key": "Youtube"} for i in range(1, 6)]}


def test_window_pages(home_env, qapp):
    from getscope.ui.window import MainWindow
    w = MainWindow(startup_checks=False)
    for k in ("downloads", "history", "diag", "settings"):
        w.go(k)
        assert w.stack.currentWidget() is w.pages[k]
    w.m.add("https://example.com/a", formats.choice_from_settings(w.settings), "A", start=False)
    assert w.p_down.tree.topLevelItemCount() == 1
    w.p_down.tree.setCurrentItem(w.p_down.tree.topLevelItem(0))
    assert w.p_down.s_main.text().endswith("RETOMAR")
    w.m.remove(w.m.jobs[0].id)
    assert w.p_down.tree.topLevelItemCount() == 0
    w.m.save_queue()
    w.close()


def test_video_dialog(home_env, qapp):
    from getscope.core.jobs import Env
    from getscope.ui.dialogs import VideoDialog
    s = Settings()
    s.update({"quality": 1080})
    d = VideoDialog(None, INFO, s, Env())
    labels = [d.opts.cb_quality.itemText(i) for i in range(d.opts.cb_quality.count())]
    assert labels[0].startswith("Melhor disponível (2160p 4K)")
    assert any(x.startswith("1080p") for x in labels)
    c, folder = d.result_data()
    assert c["quality"] == 1080 and folder == s["download_dir"]
    d.opts.rb_audio.setChecked(True)
    assert d.result_data()[0]["mode"] == "audio"


def test_playlist_dialog(home_env, qapp):
    from getscope.core.jobs import Env
    from getscope.ui.dialogs import PlaylistDialog
    d = PlaylistDialog(None, PLAYLIST, Settings(), Env())
    assert len(d.entries) == 5 and "5 ITENS" in d.ok.text()
    d.tree.topLevelItem(0).setCheckState(0, Qt.Unchecked)
    assert len(d.selected()) == 4 and "4 ITENS" in d.ok.text()
    d._mark(False)
    assert not d.ok.isEnabled()


def test_about(home_env, qapp):
    from getscope.core.jobs import Env
    from getscope.ui.dialogs import AboutDialog
    d = AboutDialog(None, Env())
    from PySide6.QtWidgets import QLabel
    texts = " ".join(lb.text() for lb in d.findChildren(QLabel))
    assert "Samuel Gomes" in texts and "steam" not in texts.lower()
