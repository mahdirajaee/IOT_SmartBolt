_DASHES = '-' * 11


def print_banner(title: str, lines=None, kind: str = 'info') -> None:
    print(f"\n{_DASHES} {title.lower()}", flush=True)
    for ln in lines or []:
        print(f"  {ln}", flush=True)
