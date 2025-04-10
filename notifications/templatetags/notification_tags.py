# notifications/templatetags/notification_tags.py
from django import template
from django.utils.html import format_html, escape

register = template.Library()

@register.simple_tag
def status_badge(status):
    """
    Generates a Bootstrap 5 badge span with an icon based on the status string.
    Provides better color contrast and cleaner look.
    """
    status_lower = status.lower() if status else ''
    badge_class = 'bg-secondary' # Default background
    text_class = ''              # Default text color (inherits)
    icon_class = 'bi-question-circle-fill' # Default icon

    # Define status mappings for clarity and maintainability
    status_map = {
        'pending':     {'badge': 'bg-warning', 'text': 'text-dark', 'icon': 'bi-hourglass-split'},
        'in progress': {'badge': 'bg-info',    'text': 'text-dark', 'icon': 'bi-person-workspace'},
        'resolved':    {'badge': 'bg-success', 'text': '',          'icon': 'bi-check-circle-fill'},
        'rejected':    {'badge': 'bg-danger',  'text': '',          'icon': 'bi-x-octagon-fill'},
        'duplicate':   {'badge': 'bg-light',   'text': 'text-dark border', 'icon': 'bi-subtract'}
        # Add other statuses like 'assigned', 'information requested' etc. as needed
    }

    if status_lower in status_map:
        config = status_map[status_lower]
        badge_class = config['badge']
        text_class = config['text']
        icon_class = config['icon']

    # Escape the status text for security and handle None/empty
    status_display = escape(status or "N/A")

    # Construct the HTML using format_html for safety
    # Using d-inline-flex and align-items-center for better icon+text alignment
    html_output = format_html(
        '<span class="badge {} {} py-1 px-2 small d-inline-flex align-items-center">'
        '<i class="bi {} me-1 small"></i>{}'
        '</span>',
        badge_class,
        text_class,
        icon_class,
        status_display
    )
    return html_output


@register.simple_tag
def get_pagination_range(page_obj, pages_around=2, pages_edge=1):
    """
    Generates a list of page numbers for pagination controls,
    including ellipses for skipped pages. Robust version.

    Example: [1, '...', 5, 6, 7, 8, 9, '...', 20]
    """
    current_page = page_obj.number
    total_pages = page_obj.paginator.num_pages
    page_numbers = []

    # Handle simple case: fewer pages than the display window
    if total_pages <= (pages_around * 2) + (pages_edge * 2) + 1:
        return list(range(1, total_pages + 1))

    # Leading edge pages
    leading_edge = list(range(1, pages_edge + 1))
    page_numbers.extend(leading_edge)

    # Ellipsis after leading edge?
    # Needed if the first page 'around' current is greater than the last leading edge page + 1
    if (current_page - pages_around) > (pages_edge + 1):
        page_numbers.append('...')

    # Pages around current page
    start_range = max(pages_edge + 1, current_page - pages_around)
    end_range = min(total_pages - pages_edge, current_page + pages_around)
    pages_in_range = list(range(start_range, end_range + 1))

    # Add pages from the 'around' range, avoiding duplicates from leading edge
    for p in pages_in_range:
        if p not in page_numbers:
            page_numbers.append(p)

    # Ellipsis before trailing edge?
    # Needed if the last page 'around' current is less than the first trailing edge page - 1
    if (current_page + pages_around) < (total_pages - pages_edge):
        # Avoid double ellipsis if already added one just before
        if page_numbers[-1] != '...':
            page_numbers.append('...')

    # Trailing edge pages
    trailing_edge = list(range(total_pages - pages_edge + 1, total_pages + 1))
     # Add pages from the trailing edge, avoiding duplicates from the middle range or ellipses
    for p in trailing_edge:
        if p not in page_numbers and page_numbers[-1] != p:
             page_numbers.append(p)

    # Final check for duplicate '...' just in case logic above missed an edge case
    final_pages = []
    last_item = None
    for item in page_numbers:
        if item == '...' and last_item == '...':
            continue
        final_pages.append(item)
        last_item = item

    return final_pages