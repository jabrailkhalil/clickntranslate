"""Relabel existing settings controls without recreating pages or signals."""

# Explicit catalog bindings, matching the initial settings form.
BINDINGS = (
    ('autostart_checkbox', 'setText', 'settings_text', 'autostart'),
    ('start_minimized_checkbox', 'setText', 'settings_text', 'start_minimized'),
    ('translator_engine_label', 'setText', 'settings_text', 'translator_label'),
    ('copy_translated_checkbox', 'setText', 'settings_text', 'copy_translated_text'),
    ('result_window_label', 'setText', 'settings_text', 'result_window_label'),
    ('copy_history_checkbox', 'setText', 'settings_text', 'copy_history'),
    ('history_checkbox', 'setText', 'settings_text', 'history'),
    ('button_tooltips_checkbox', 'setText', 'settings_text', 'button_hover_tips'),
    ('replace_select_all_checkbox', 'setText', 'settings_text', 'replace_select_all'),
    ('ui_scale_label', 'setText', 'settings_text', 'ui_scale_caption'),
    ('translation_font_label', 'setText', 'settings_text', 'translation_result_font_label'),
    ('translation_font_preview', 'setText', 'settings_text', 'translation_result_font_sample'),
    ('keep_visible_checkbox', 'setText', 'settings_text', 'keep_visible_on_ocr'),
    ('freeze_screen_checkbox', 'setText', 'settings_text', 'freeze_screen_on_ocr'),
    ('clear_cache_btn', 'setText', 'settings_text', 'clear_cache'),
    ('reset_btn', 'setText', 'settings_text', 'reset'),
    ('update_btn', 'setText', 'settings_text', 'update'),
    ('ocr_languages_btn', 'setText', 'settings_text', 'ocr_language_packs'),
    ('hotkeys_button', 'setText', 'settings_text', 'hotkeys'),
    ('translation_history_btn', 'setText', 'settings_text', 'translation_history_button'),
    ('copy_history_btn', 'setText', 'settings_text', 'copy_history_button'),
    ('dim_screen_during_ocr_checkbox', 'setText', 'settings_text', 'dim_screen_during_ocr'),
    ('restore_clipboard_checkbox', 'setText', 'settings_text', 'restore_clipboard_after_selection'),
    ('copy_notification_checkbox', 'setText', 'settings_text', 'copy_notification'),
    ('update_check_on_launch_checkbox', 'setText', 'settings_text', 'update_check_on_launch'),
    ('export_settings_btn', 'setText', 'settings_text', 'export_settings'),
    ('import_settings_btn', 'setText', 'settings_text', 'import_settings'),
    ('create_bug_report_btn', 'setText', 'settings_text', 'create_bug_report'),
    ('game_settings_heading', 'setText', 'settings_text', 'game_settings_heading'),
    ('game_pause_inactive_checkbox', 'setText', 'settings_text', 'game_pause_inactive'),
    ('game_show_original_checkbox', 'setText', 'settings_text', 'game_show_original'),
    ('game_manual_output_checkbox', 'setText', 'dynamic_text', 'manual_output'),
    ('game_toolbar_checkbox', 'setText', 'dynamic_text', 'show_toolbar'),
    ('game_remember_template_checkbox', 'setText', 'region_text', 'dynamic_remember'),
    ('game_template_label', 'setText', 'region_text', 'template_label'),
    ('game_workflow_note', 'setText', 'settings_text', 'game_intro'),
    ('game_launch_button', 'setText', 'settings_text', 'game_launch'),
    ('game_help_button', 'setText', 'dynamic_text', 'help'),
    ('result_window_control', 'setAccessibleName', 'settings_text', 'result_window_label'),
    ('result_window_label', 'setToolTip', 'settings_text', 'result_window_tooltip'),
    ('replace_select_all_checkbox', 'setToolTip', 'settings_text', 'replace_select_all_hint'),
    ('replace_select_all_checkbox', 'setAccessibleDescription', 'settings_text', 'replace_select_all_hint'),
    ('ui_scale_value', 'setAccessibleName', 'settings_text', 'ui_scale'),
    ('ui_scale_value', 'setToolTip', 'settings_text', 'ui_scale_edit_hint'),
    ('translation_font_control', 'setAccessibleName', 'settings_text', 'translation_result_font_label'),
    ('translation_font_control', 'setAccessibleDescription', 'settings_text', 'translation_result_font_tooltip'),
    ('ocr_languages_btn', 'setToolTip', 'settings_text', 'manage_ocr_languages'),
    ('ocr_dim_strength_control', 'setAccessibleName', 'settings_text', 'dim_screen_during_ocr'),
    ('restore_clipboard_checkbox', 'setToolTip', 'settings_text', 'restore_clipboard_tooltip'),
    ('copy_notification_checkbox', 'setToolTip', 'settings_text', 'copy_notification_tooltip'),
    ('export_settings_btn', 'setToolTip', 'settings_text', 'export_settings_tooltip'),
    ('import_settings_btn', 'setToolTip', 'settings_text', 'import_settings_tooltip'),
    ('create_bug_report_btn', 'setToolTip', 'settings_text', 'bug_report_tooltip'),
    ('game_swap_button', 'setToolTip', 'settings_text', 'game_swap_languages'),
    ('game_swap_button', 'setAccessibleName', 'settings_text', 'game_swap_languages'),
    ('game_interval_controls', 'setAccessibleName', 'settings_text', 'game_scan_interval'),
    ('game_opacity_controls', 'setAccessibleName', 'settings_text', 'game_overlay_opacity'),
    ('game_pause_inactive_checkbox', 'setToolTip', 'settings_text', 'game_pause_inactive_tooltip'),
    ('game_remember_template_checkbox', 'setToolTip', 'region_text', 'dynamic_hint'),
    ('game_template_combo', 'setToolTip', 'region_text', 'dynamic_hint'),
    ('game_template_combo', 'setAccessibleName', 'region_text', 'template_label'),
    ('game_delete_template_button', 'setToolTip', 'dynamic_text', 'delete_selected_template'),
    ('game_delete_template_button', 'setAccessibleName', 'dynamic_text', 'delete_selected_template'),
    ('game_workflow_note', 'setToolTip', 'settings_text', 'game_workflow_note'),
    ('game_launch_button', 'setToolTip', 'settings_text', 'game_workflow_note'),
)


def retranslate(settings):
    from PyQt5 import QtCore, QtWidgets
    from settings_window import settings_text, _populate_grouped_ocr_combo, _populate_grouped_translator_combo
    from dynamic_templates import text as dynamic_text
    from capture_regions import text as region_text
    from capture_memory_settings import text as memory_text
    from settings_categories import COMPACT, DYNAMIC_COMPACT, PARAGRAPH_TEXT, fit_dynamic_flags
    from settings_sections import page_caption, section_text
    from engine_center import text as center_text
    from styled_dialogs import tooltip_text
    from provider_settings import refresh_provider_routing
    from provider_catalog import provider_id
    lang = settings.parent.current_interface_language
    old_lang = settings._ui_language
    automatic = [control for control in settings.findChildren(QtWidgets.QWidget)
                 if control.property('automaticHoverHint')
                 and control.toolTip() == control.property('automaticHoverHint')]
    from guide_setup import GUIDE_SETTING_STEPS, setting_body
    for action, (attribute, _page, _default) in GUIDE_SETTING_STEPS.items():
        control = getattr(settings, attribute, None)
        if control is not None and control.toolTip() == tooltip_text(setting_body(old_lang, action)):
            control.setToolTip(tooltip_text(setting_body(lang, action)))
    catalogs = dict(settings_text=settings_text, dynamic_text=dynamic_text, region_text=region_text)
    for attribute, setter, catalog, key in BINDINGS:
        control = getattr(settings, attribute, None)
        if control is not None:
            value = catalogs[catalog](lang, key)
            getattr(control, setter)(tooltip_text(value) if setter == 'setToolTip' else value)
    compact = COMPACT[lang]
    settings.restore_clipboard_checkbox.setText(compact[0])
    settings.close_result_on_outside_click_checkbox.setText(compact[1])
    settings.close_result_on_outside_click_checkbox.setToolTip(tooltip_text(settings_text(lang, 'close_result_window_on_outside_click_tooltip')))
    settings.ocr_engine_label.setText('OCR:')
    settings.ocr_engine_label.setToolTip(section_text(lang, 'recognition').rstrip(':： '))
    settings.capture_memory_label.setText(memory_text(lang, 'label'))
    settings.capture_memory_label.setToolTip(tooltip_text(memory_text(lang, 'hint')))
    caption, hint = PARAGRAPH_TEXT[lang]
    settings.ocr_join_paragraphs_checkbox.setText(caption)
    settings.ocr_join_paragraphs_checkbox.setToolTip(tooltip_text(hint))
    settings.ocr_join_paragraphs_checkbox.setAccessibleDescription(hint)
    settings.ocr_dim_strength_label.setText(section_text(lang, 'dim_strength'))
    margin = settings.ocr_dimming_options.layout()
    rtl = settings.layoutDirection() == QtCore.Qt.RightToLeft
    margin.setContentsMargins(0 if rtl else 30, 0, 30 if rtl else 0, 0)
    from text_direction import ui_directional_text
    dynamic = [ui_directional_text(value, lang) for value in DYNAMIC_COMPACT[lang]]
    for control, value in zip((settings.game_scan_interval_label, settings.game_overlay_opacity_label,
                              settings.game_pause_inactive_checkbox, settings.game_toolbar_checkbox), dynamic):
        control.setText(value)
    settings.game_languages_label.setText(settings_text(lang, 'game_languages'))
    settings.engines_button.setText(center_text(lang, 'title'))
    settings.engines_button.setAccessibleName(center_text(lang, 'title'))
    settings.engines_button.setToolTip(tooltip_text(center_text(lang, 'intro')))
    settings.engines_button.setAccessibleDescription(center_text(lang, 'intro'))
    for control in (settings.ui_scale_label, settings.ui_scale_control):
        control.setToolTip(tooltip_text(settings_text(lang, 'ui_scale_hint')))
    for button, key in ((settings.ui_scale_decrease,'ui_scale_decrease'), (settings.ui_scale_increase,'ui_scale_increase')):
        label = settings_text(lang, key)
        button.setAccessibleName(label)
        button.setToolTip(tooltip_text(label+' (1%)'))
    for control in (settings.translation_font_label, settings.translation_font_preview):
        control.setToolTip(tooltip_text(settings_text(lang, 'translation_result_font_tooltip')))
    for control in (settings.ocr_dim_strength_label, settings.ocr_dim_strength_control,
                    settings.dim_screen_during_ocr_checkbox):
        control.setToolTip(tooltip_text(settings_text(lang, 'ocr_dim_strength_tooltip')))
    for control in (settings.game_pause_inactive_checkbox, settings.game_manual_output_checkbox,
                    settings.game_toolbar_checkbox, settings.game_remember_template_checkbox):
        control.setAccessibleName(control.text())
        # Later theme changes rewrap this full label, not the displayed lines.
        control.setProperty('dynamicFlagLabel', control.text())
    fit_dynamic_flags(settings)
    settings.game_toolbar_checkbox.setToolTip(tooltip_text(dynamic_text(lang, 'toolbar_hint').format(
        hotkey=settings.parent.config.get('game_translate_hotkey', 'Ctrl+Alt+G'))))
    for index, button in enumerate(settings.settings_page_tabs):
        caption = page_caption(lang, index)
        button.setText(caption)
        button.setAccessibleName(caption)
        button.setToolTip(tooltip_text(caption))
    local, translators = settings._ready_engine_inventory()
    color = '#f4f6fb' if settings.parent.current_theme != 'Светлая' else '#202124'
    with QtCore.QSignalBlocker(settings.ocr_engine_combo), QtCore.QSignalBlocker(settings.translator_combo):
        _populate_grouped_ocr_combo(settings.ocr_engine_combo, lang, color, local, ready_only=True)
        settings._translator_engines = _populate_grouped_translator_combo(
            settings.translator_combo, lang, color, translators, ready_only=True)
        settings.ocr_engine_combo.setCurrentIndex(settings.ocr_engine_combo.findData(settings.parent.config.get('ocr_engine')))
        settings.translator_combo.setCurrentIndex(settings.translator_combo.findData(provider_id(settings.parent.config.get('translator_engine'))))
        for combo in (settings.ocr_engine_combo, settings.translator_combo):
            combo.setPlaceholderText(center_text(lang, 'select'))
            combo.setToolTip(tooltip_text(center_text(lang, 'ready_help')))
    settings.translator_engine_label.setToolTip(settings.translator_combo.toolTip())
    result = settings.result_window_control
    result.set_labels({mode: settings_text(lang, 'result_window_row_'+mode) for mode in result._modes},
        {key: settings_text(lang, 'result_window_summary_'+key) for key in ('all','none','count','on','off')},
        {mode: settings_text(lang, 'result_window_mode_'+mode) for mode in result._modes},
        header=settings_text(lang, 'result_window_header'), footer=settings_text(lang, 'result_window_footer'))
    for mode in result._modes:
        result._item(mode).setToolTip(settings_text(lang, 'result_window_mode_'+mode+'_tooltip'))
    result.set_help_text(settings_text(lang, 'result_window_tooltip'))
    memory = settings.capture_memory_modes
    memory.set_labels({mode: memory_text(lang, mode) for mode in memory._modes},
        {key: memory_text(lang, key) for key in ('all','none','count','on','off')},
        {mode: memory_text(lang, 'short_'+mode) for mode in memory._modes})
    memory.set_help_text(memory_text(lang, 'hint'))
    memory.setAccessibleName(memory_text(lang, 'label'))
    for mode in memory._modes:
        memory._item(mode).setToolTip(memory_text(lang, 'hint'))
    control = settings.translation_font_control
    control.set_labels({key: settings_text(lang, 'translation_result_font_'+key) for key, _label in control._choices})
    settings._refresh_translation_font_preview()
    # Relabel existing rows without rescanning installed models. Initial,
    # untouched translation pairs can follow the UI language; reconcile that
    # intentional config change without changing a customized pair.
    configured_pair = (settings.parent.config.get('game_translate_source_language'),
                       settings.parent.config.get('game_translate_target_language'))
    visible_pair = (settings.game_source_combo.currentData(), settings.game_target_combo.currentData())
    if configured_pair != visible_pair and all(configured_pair):
        settings._refresh_game_language_controls()
    from languages import language_display_name
    for combo in (settings.game_source_combo, settings.game_target_combo):
        with QtCore.QSignalBlocker(combo):
            for row in range(combo.count()):
                code = combo.itemData(row)
                if isinstance(code, str):
                    label = language_display_name(code, lang)
                    combo.setItemText(row, label)
                    combo.setItemData(row, tooltip_text(label), QtCore.Qt.ToolTipRole)
    settings._refresh_game_templates()
    for control in (settings.game_remember_template_checkbox, settings.game_template_label):
        control.setToolTip(tooltip_text(region_text(lang, 'dynamic_hint')))
    for control in automatic:
        caption = getattr(control, 'text', lambda: '')()
        if caption:
            hint = tooltip_text(caption)
            control.setToolTip(hint)
            control.setProperty('automaticHoverHint', hint)
    settings._set_control_hints()
    _retranslate_companion(settings.settings_assistant_page, lang)
    refresh_provider_routing(settings)
    settings._fit_copy_translated_checkbox()
    settings._position_settings_updates_page()
    settings._ui_language = lang
    settings._relanguage_language_manager()


def _retranslate_companion(page, lang):
    from PyQt5 import QtCore, QtWidgets
    from assistant_text import assistant_text
    from control_hints import control_hint
    tr = lambda key: assistant_text(lang, key)
    page.language = lang
    for control, key in ((page.main_visible, 'main_visible_short'), (page.toggle, 'enabled'),
                         (page.topmost, 'topmost'), (page.reactions, 'reactions'),
                         (page.menu_buttons, 'menu_buttons'), (page.replace_image, 'change_image')):
        control.setText(tr(key))
        control.setAccessibleName(tr('main_visible') if control is page.main_visible else tr(key))
    for control, key in ((page.main_visible, 'desktop_main'), (page.toggle, 'desktop_enabled'),
                         (page.topmost, 'desktop_topmost')):
        control.setToolTip(control_hint(lang, key))
    page.reactions.setToolTip(tr('reactions_hint'))
    page.menu_buttons.setToolTip(tr('menu_buttons_hint'))
    page.menu_buttons.setAccessibleDescription(tr('menu_buttons_hint'))
    page.menu_buttons.setFixedWidth(max(230, page.menu_buttons.fontMetrics().horizontalAdvance(page.menu_buttons.text())+32))
    page.replace_image.setToolTip(tr('choose_image'))
    custom = page.findChild(QtWidgets.QToolButton, 'assistantAppearance')
    custom.setText(tr('custom'))
    custom.setToolTip(tr('choose_image'))
    custom.setAccessibleName(tr('choose_image'))
    with QtCore.QSignalBlocker(page.mode_combo):
        for index, key in enumerate(('mode_animated', 'mode_static', 'custom')):
            page.mode_combo.setItemText(index, tr(key))
    page.mode_combo.setToolTip(tr('display_mode_hint'))
    for name, label in page.field_labels.items():
        label.setText(tr(name))
        field = page.mode_combo if name == 'display_mode' else page.values[name]
        field.setAccessibleName(tr(name))
        if name != 'display_mode':
            field.setToolTip(f'{tr(name)}: {field.minimum()}–{field.maximum()}%')
            for button, direction in ((field.decrease,'decrease'), (field.increase,'increase')):
                button.setToolTip(tr(name+'_'+direction))
                button.setAccessibleName(tr(name+'_'+direction))
        label.setToolTip(field.toolTip())
    page.refresh()
