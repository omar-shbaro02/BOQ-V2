"""Read current task-only progress sheets and previously downloaded workbooks."""

from app.services.ms_project_export import PROGRESS_HEADERS

TASK_PROGRESS_HEADERS = PROGRESS_HEADERS[1:]


def progress_input_rows(sheet):
    headers = tuple(cell.value for cell in sheet[4])
    if headers[:12] == PROGRESS_HEADERS:
        yield from sheet.iter_rows(min_row=5, values_only=True)
    elif headers[:11] == TASK_PROGRESS_HEADERS:
        for row in sheet.iter_rows(min_row=5, values_only=True):
            # Normalize old positional consumers without adding a visible column.
            yield (None, *row[:11])
    else:
        raise ValueError("Progress Report headers have changed; download a fresh template")
