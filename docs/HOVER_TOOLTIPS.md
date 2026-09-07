# Shared hover tooltips for Windows and Linux

Branch: `codex/shared-hover-tooltips`, based on `main` at `091099a`.
This ports the hover tooltip appearance from the native Mac work to the
Windows/Linux source tree. It contains only the tooltip changes in
`styled_dialogs.py` and the main window's theme notification in `main.py`.

The dark surface is `#211d28`, with light text and a purple border. The light
surface is `#faf7fc`, with dark text and a muted purple border. Both use the
same 8 px corner radius and 7×11 px padding. The existing rich-text wrapping
keeps long hints readable while short labels stay compact. Windows/Linux keep
their existing rounded window mask so transparent corners remain cut out.

The shared `QTipLabel` refreshes its theme when shown, reused by another control,
or repolished by Qt. A control's older stylesheet cannot leave a dark tooltip
in the light theme. Queued appearance updates tolerate a tooltip being deleted
before they execute. The application stylesheet remains stable across theme
changes; the tooltip palette changes without repolishing the whole interface.

The existing `TOOLTIP_QSS` and `install_tooltip_style(app)` APIs remain available.
The main window publishes `ui_theme` on the QApplication and calls
`install_tooltip_style(app, dark)` whenever its theme is applied. The shared
filter handles other controls, settings and document-window hints too.

The Mac branch already contains this appearance. To incorporate the isolated
Windows/Linux change, merge this branch or cherry-pick its commit onto a branch
based on the current `main`. Do not replace `styled_dialogs.py` wholesale in the
newer Mac branch: it has additional native integration there.

Validation on 2026-09-07: Python syntax and patch whitespace checked. Runtime
tests and native Windows/Linux visual acceptance are deferred at the user's
request. No Windows/Linux binary or release was built or published. When testing
resumes, check short/long hints, both themes, moving between controls with their
own stylesheets, switching theme while a hint is visible, and display scaling.
