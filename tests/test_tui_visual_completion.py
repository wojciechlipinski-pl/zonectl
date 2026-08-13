import inspect

from zonectl.ui.curses_app import CursesApp
from zonectl.ui.records.editor import RecordEditor


def test_shared_message_renderer_uses_48_layout() -> None:
    view = inspect.getsource(CursesApp._message_view)
    renderer = inspect.getsource(CursesApp._draw_message_view_48)
    assert "width >= 100 and height >= 20" in view
    assert "_draw_message_view_48" in view
    assert "SZCZEGÓŁY" in renderer
    assert "STAN OPERACYJNY" in renderer
    assert "curses.ACS_VLINE" in renderer


def test_all_custom_collection_views_use_context_panels() -> None:
    methods = (
        CursesApp._onboarding_candidates_view,
        CursesApp._pending_changes_view,
        CursesApp._diff_view,
        CursesApp._bulk_preview_view,
        CursesApp._multi_zone_view,
        CursesApp._zone_secondary_view,
        CursesApp._bind_access_view,
        CursesApp._acl_entry_editor,
        CursesApp._secondary_address_editor,
        CursesApp._zone_migration_view,
    )
    for method in methods:
        assert "_draw_context_panel_48" in inspect.getsource(method)


def test_record_form_has_responsive_preview_panel() -> None:
    source = inspect.getsource(RecordEditor.edit_record_dialog)
    assert "width >= 100 and height >= 20" in source
    assert "PODGLĄD REKORDU" in source
    assert "curses.ACS_VLINE" in source
    assert "BŁĄD" in source
