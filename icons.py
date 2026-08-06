"""Inline SVG assets for the site.

All artwork here is original. We deliberately do NOT use CDC, FDA or any
company's logo: this site publishes its own risk estimates, and an agency mark
beside them would imply an endorsement that does not exist and that the
site's own disclaimers explicitly deny.

Icons are geometric, single-stroke, and inherit currentColor so they work in
both themes without a second copy.
"""

# Sprite symbols. Rendered once per page inside a hidden <svg>, referenced by
# <use href="#i-name">. 24x24 viewBox, 1.7 stroke, round caps.
SPRITE_SYMBOLS = {
    "leaf": '<path d="M20 4C10 4 4 9 4 16c0 2 .6 3.3 1.4 4.2C7 18 10 15.4 14 14c-3 2-5.6 4.6-7 8 1 .6 2.3 1 3.6 1C18 23 21 15 20 4Z"/>',
    "herb": '<path d="M12 21V9"/><path d="M12 13c0-3-2.2-5.5-5-6 0 3 2 5.6 5 6Z"/><path d="M12 13c0-3 2.2-5.5 5-6 0 3-2 5.6-5 6Z"/><path d="M12 8c0-2.5 1.5-4.5 3-5 0 2.5-1.2 4.4-3 5Z"/>',
    "bag": '<path d="M5 8h14l-1.2 12.2a1 1 0 0 1-1 .8H7.2a1 1 0 0 1-1-.8Z"/><path d="M8.5 8V6a3.5 3.5 0 0 1 7 0v2"/>',
    "cucumber": '<rect x="3.2" y="9" width="17.6" height="6" rx="3"/><path d="M8 11.2v1.6M12 11v2M16 11.2v1.6"/>',
    "onion": '<path d="M12 21c-4 0-6.5-2.4-6.5-5.6C5.5 11.5 9 8 12 4c3 4 6.5 7.5 6.5 11.4C18.5 18.6 16 21 12 21Z"/><path d="M12 21V9"/>',
    "berry": '<circle cx="9" cy="14.5" r="3.2"/><circle cx="15" cy="14.5" r="3.2"/><circle cx="12" cy="9.5" r="3.2"/>',
    "pod": '<path d="M4 15c2-7 8-11 16-11 0 8-5 15-12 15-2.6 0-4.4-1.6-4-4Z"/><circle cx="10" cy="12" r="1.1"/><circle cx="14" cy="9.5" r="1.1"/>',
    "tomato": '<circle cx="12" cy="14" r="7"/><path d="M12 7V4"/><path d="M9 5.5 12 7l3-1.5"/>',
    "fruit": '<path d="M12 7c-4 0-7 3-7 7s3 7 7 7 7-3 7-7-3-7-7-7Z"/><path d="M12 7V3.5"/><path d="M12 4.5c1.6-1.4 3.4-1.6 4.5-1-.2 1.6-1.6 3-4.5 3"/>',
    "cooked": '<path d="M4 11h16v4a5 5 0 0 1-5 5H9a5 5 0 0 1-5-5Z"/><path d="M20 12.5h1.5a1.5 1.5 0 0 1 0 3H20"/><path d="M9 7.5c0-1 1-1.5 1-2.5M12 7.5c0-1 1-1.5 1-2.5M15 7.5c0-1 1-1.5 1-2.5"/>',
    # UI icons
    "search": '<circle cx="11" cy="11" r="6.5"/><path d="m20 20-4.4-4.4"/>',
    "flame": '<path d="M12 21c3.9 0 6.5-2.4 6.5-6 0-4.5-4.5-6.5-4-11-3 1.5-5 4.5-5 7.5 0 1-.7 1.5-1.3 1-.7-.6-.9-1.6-.9-2.5-1.3 1.5-2.3 3.4-2.3 5.5 0 3.3 2.6 5.5 7 5.5Z"/>',
    "peel": '<path d="M5 19c6-1 11-6 12-13"/><path d="M17 6c-6 0-10 4-11 10 4-1 7-3 8-6"/>',
    "ban": '<circle cx="12" cy="12" r="8.2"/><path d="m6.2 6.2 11.6 11.6"/>',
    "droplet": '<path d="M12 3.5c3.5 4.2 5.5 7 5.5 9.7A5.5 5.5 0 0 1 6.5 13.2C6.5 10.5 8.5 7.7 12 3.5Z"/>',
    "alert": '<path d="M12 4.5 21 20H3Z"/><path d="M12 10.5v4"/><path d="M12 17.2v.1"/>',
    "info": '<circle cx="12" cy="12" r="8.2"/><path d="M12 11v5.5"/><path d="M12 7.8v.1"/>',
    "check": '<path d="m5 12.5 4.6 4.5L19 7.5"/>',
    "cross": '<path d="M6 6l12 12M18 6 6 18"/>',
    "stethoscope": '<path d="M6 3v5a4 4 0 0 0 8 0V3"/><path d="M6 3H4.5M14 3h1.5"/><path d="M10 12v2.5a5 5 0 0 0 5 5 4 4 0 0 0 4-4V14"/><circle cx="19" cy="12.2" r="2"/>',
}


def sprite():
    syms = "".join(
        f'<symbol id="i-{name}" viewBox="0 0 24 24" fill="none" '
        f'stroke="currentColor" stroke-width="1.7" stroke-linecap="round" '
        f'stroke-linejoin="round">{body}</symbol>'
        for name, body in SPRITE_SYMBOLS.items()
    )
    return f'<svg class="sprite" aria-hidden="true" focusable="false">{syms}</svg>'


def icon(name, cls="icon"):
    return (f'<svg class="{cls}" aria-hidden="true" focusable="false">'
            f'<use href="#i-{name}"></use></svg>')


def logo():
    """Original wordmark: a leaf under a magnifier - 'looking closely at produce'.

    Not derived from any agency or company mark.
    """
    return (
        '<svg class="logo-mark" viewBox="0 0 32 32" aria-hidden="true" focusable="false">'
        '<circle cx="14" cy="14" r="9.5" fill="none" stroke="currentColor" stroke-width="2"/>'
        '<path d="m21.2 21.2 6 6" fill="none" stroke="currentColor" stroke-width="2.6" '
        'stroke-linecap="round"/>'
        '<path d="M18.5 9.2c-6 0-9.6 3-9.6 7.2 0 1.2.4 2 .9 2.5 1-1.3 2.8-2.9 5.2-3.7'
        '-1.8 1.2-3.4 2.7-4.2 4.8.6.3 1.4.6 2.2.6 4.4 0 6.2-4.8 5.5-11.4Z" '
        'fill="currentColor"/>'
        '</svg>'
    )
