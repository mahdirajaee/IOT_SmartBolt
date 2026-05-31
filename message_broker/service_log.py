def print_banner(title: str, lines=None, kind: str = 'info') -> None:
    header = f"*** {title.upper()} ***"
    print(f"\n{header}", flush=True)
    for ln in lines or []:
        print(f"  {ln}", flush=True)
