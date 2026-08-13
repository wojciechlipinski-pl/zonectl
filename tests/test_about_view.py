from zonectl.ui.about_view import AboutView


def test_about_view_preserves_project_authorship_and_history() -> None:
    view = AboutView.build("4.8.0")
    text = "\n".join(view.lines)
    assert "Wojciech Lipiński" in text
    assert "OpenAI ChatGPT" in text
    assert "prostego skryptu Python" in text
    assert "github.com/wojciechlipinski-pl/zonectl" in text
