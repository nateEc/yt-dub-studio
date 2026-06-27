def iter_progress(progress, iterable, desc=None):
    tqdm_fn = getattr(progress, "tqdm", None)
    if not tqdm_fn:
        return iterable

    try:
        wrapped = tqdm_fn(iterable, desc=desc)
    except Exception:
        return iterable

    if wrapped is progress:
        return iterable
    return wrapped
