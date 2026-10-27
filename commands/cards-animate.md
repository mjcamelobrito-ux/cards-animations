---
description: Render any card animation by name (lists them when no name is given)
argument-hint: <animation|all> [photos] [--label "text"] [--bg #hex] [--mov]
---

Arguments: $ARGUMENTS

Load the `cards-animations` skill. The first argument is the animation name (or `all`); match close names ("bloom", "tunnel"). With no name, run `python3 ${CLAUDE_PLUGIN_ROOT}/cardfx.py list`, show the list and ask which one. Then follow the skill.
